from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("project_pipeline", ROOT / "ripper-collector" / "scripts" / "project_pipeline.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ProjectPipelineTests(unittest.TestCase):
    def test_interrupted_deposit_is_recovered_before_next_write(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.dict(os.environ, {"HOME": str(root / "home"), "RIPPER_OUTPUT_DIR": str(root / "output")}), patch.object(MODULE.ARCHIVE, "ARCHIVE_HOME", root / "home" / "Ripper"):
                doc = root / "project.md"
                doc.write_text("task retry", encoding="utf-8")
                analysis = root / "analysis.json"
                analysis.write_text('{"claims":[{"title":"retry","statement":"original"}]}')
                result = MODULE.deposit_project("Recovery", analysis, [doc])
                target = Path(result["archive_path"])
                # Simulate process death after backup/journal and partial writes.
                import shutil
                transaction = target.parent / ".ripper-transaction"
                transaction.mkdir()
                shutil.copytree(target, transaction / "backup")
                MODULE.TRANSACTION.write_journal(transaction / "journal.json", {"target": target.name, "existed": True, "status": "pending"})
                (target / "archive-manifest.json").write_text("partial")
                result = MODULE.deposit_project("Recovery", analysis, [doc])
                self.assertEqual(result["status"], "confirmation_required")
                self.assertTrue(result["recovered_interrupted_deposit"])
                self.assertFalse(transaction.exists())
                self.assertEqual(json.loads((target / "archive-manifest.json").read_text())["project_name"], "Recovery")

    def test_claim_lifecycle_survives_update_rebuild_and_source_changes(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.dict(os.environ, {"HOME": str(root / "home"), "RIPPER_OUTPUT_DIR": str(root / "output")}), patch.object(MODULE.ARCHIVE, "ARCHIVE_HOME", root / "home" / "Ripper"):
                doc = root / "design.md"
                doc.write_text("task retry design", encoding="utf-8")
                analysis = root / "analysis.json"
                def write(statement):
                    analysis.write_text(json.dumps({"claims": [{"title": "retry", "identity_key": "retry", "statement": statement, "source_refs": [{"path": str(doc)}]}]}), encoding="utf-8")
                write("v1")
                first = MODULE.deposit_project("Lifecycle", analysis, [doc])
                archive = Path(first["archive_path"])
                initial = json.loads((archive / "analysis/project-analysis.json").read_text())["claims"][0]
                write("v2")
                MODULE.deposit_project("Lifecycle", analysis, [doc], update=True)
                revised = json.loads((archive / "analysis/project-analysis.json").read_text())["claims"][0]
                self.assertEqual(initial["id"], revised["id"])
                self.assertEqual(revised["revision"], 2)
                MODULE.deposit_project("Lifecycle", analysis, [doc], update=True)
                unchanged = json.loads((archive / "analysis/project-analysis.json").read_text())["claims"][0]
                self.assertEqual(unchanged["revision"], 2)
                store = MODULE.ASSET.AssetStore()
                store.rebuild_from_archives(archive.parent)
                rebuilt = store.query_claims()[0]
                self.assertEqual((rebuilt["id"], rebuilt["revision"]), (initial["id"], 2))
                self.assertEqual(rebuilt["evidence_freshness"], "current")
                (archive / revised["source_refs"][0]["archive_source_path"]).write_text("modified", encoding="utf-8")
                store.rebuild_from_archives(archive.parent)
                self.assertEqual(store.query_claims()[0]["evidence_freshness"], "stale")
                # An invalid archive cannot erase the last usable index.
                (archive / "archive-manifest.json").write_text("invalid", encoding="utf-8")
                with self.assertRaises(ValueError):
                    store.rebuild_from_archives(archive.parent)
                self.assertEqual(store.query_claims()[0]["id"], initial["id"])

    def test_document_only_deposit_has_one_project_id_and_index(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old_home, old_output = os.environ.get("HOME"), os.environ.get("RIPPER_OUTPUT_DIR")
            os.environ["HOME"] = str(root / "home")
            os.environ["RIPPER_OUTPUT_DIR"] = str(root / "output")
            MODULE.ARCHIVE.ARCHIVE_HOME = Path(os.environ["HOME"]) / "Ripper"
            try:
                doc = root / "材料.md"; doc.write_text("# 成果\n", encoding="utf-8")
                analysis = root / "analysis.md"; analysis.write_text("# 分析\n## 稳定性\n", encoding="utf-8")
                result = MODULE.deposit_project("支付工程", analysis, [doc])
                self.assertEqual(result["status"], "created")
                manifest = json.loads((Path(result["archive_path"]) / "archive-manifest.json").read_text(encoding="utf-8"))
                self.assertEqual(manifest["project_id"], result["project_input"]["project_id"])
                self.assertIn("domain_profile", result["project_input"])
                self.assertEqual(manifest["domain_profile_path"], "knowledge/domain-profile.json")
                self.assertTrue((Path(result["archive_path"]) / manifest["domain_profile_path"]).is_file())
                self.assertTrue(result["indexed_repositories"])
                with MODULE.ASSET.AssetStore(Path(os.environ["RIPPER_OUTPUT_DIR"]) / "assets").connect() as conn:
                    self.assertEqual(conn.execute("SELECT COUNT(*) FROM repositories WHERE project_id=?", (manifest["project_id"],)).fetchone()[0], 1)
            finally:
                if old_home is None: os.environ.pop("HOME", None)
                else: os.environ["HOME"] = old_home
                if old_output is None: os.environ.pop("RIPPER_OUTPUT_DIR", None)
                else: os.environ["RIPPER_OUTPUT_DIR"] = old_output

    def test_valid_knowledge_bundle_is_archived_and_index_remains_rebuildable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old_home, old_output = os.environ.get("HOME"), os.environ.get("RIPPER_OUTPUT_DIR")
            os.environ["HOME"] = str(root / "home")
            os.environ["RIPPER_OUTPUT_DIR"] = str(root / "output")
            MODULE.ARCHIVE.ARCHIVE_HOME = Path(os.environ["HOME"]) / "Ripper"
            try:
                doc = root / "design.md"
                doc.write_text("任务调度 DAG 支持重试和心跳。", encoding="utf-8")
                analysis = root / "analysis.json"
                analysis.write_text(json.dumps({"claims": [{"title": "调度", "statement": "建立 DAG 调度机制"}]}, ensure_ascii=False), encoding="utf-8")
                profile = MODULE.build_input("ORK", [doc])["domain_profile"]
                today = datetime.now(timezone.utc).date().isoformat()
                knowledge_payload = {
                    "profile_id": profile["profile_id"],
                    "project_direction_candidates": [{
                        "name": "任务调度与工作流编排", "confidence": "high",
                        "project_source_refs": [profile["source_inventory"][0]["path"]],
                        "rationale": "文档包含 DAG、心跳与重试机制。", "search_keywords": ["任务调度", "DAG"],
                    }],
                    "sources": [{
                        "id": f"s_{size}", "title": f"{size} practice", "url": f"https://example.com/{size}",
                        "published_at": today, "geography": "CN", "organization_size": size,
                    } for size in ("large", "medium", "small")],
                    "module_cards": [{
                        "id": "m1", "basis_source_ids": ["s_large"], "historical_fact": False,
                        "project_fit": "延伸心跳机制", "compatibility_requirements": ["状态持久化"], "conflicts_with": [],
                    }],
                    "architecture_candidates": [
                        {"variant": "conservative", "module_card_ids": ["m1"], "preserved_terms": profile["locked_terms"][:1], "historical_fact": False, "coherence_rationale": "沿用现有状态机。"},
                        {"variant": "enhanced", "module_card_ids": ["m1"], "preserved_terms": profile["locked_terms"][:1], "historical_fact": False, "coherence_rationale": "增强心跳恢复且不增加控制面。"},
                    ],
                }
                knowledge = root / "market-practices.json"
                knowledge.write_text(json.dumps(knowledge_payload, ensure_ascii=False), encoding="utf-8")

                result = MODULE.deposit_project("ORK", analysis, [doc], knowledge=knowledge)
                archive = Path(result["archive_path"])
                manifest = json.loads((archive / "archive-manifest.json").read_text(encoding="utf-8"))
                self.assertEqual(manifest["market_practices_path"], "knowledge/market-practices.json")
                self.assertTrue((archive / manifest["market_practices_path"]).is_file())
                self.assertTrue(result["knowledge_validation"]["valid"])
                overview = MODULE.list_project_archives()[0]
                self.assertTrue(overview["has_domain_profile"])
                self.assertTrue(overview["has_market_practices"])
                self.assertEqual(overview["project_directions"], ["任务调度与工作流编排"])
                self.assertEqual(overview["architecture_candidates"], ["conservative", "enhanced"])
                claims = [
                    item for item in MODULE.ASSET.AssetStore().query_claims([])
                    if item["project_id"] == result["project_id"]
                ]
                self.assertEqual(len(claims), 3)
                derived = [item for item in claims if item["realization_status"] == "derived"]
                self.assertEqual({item["reconstruction"]["variant"] for item in derived}, {"conservative", "enhanced"})
                self.assertTrue(all(item["derived_optimizations"][0]["historical_fact"] is False for item in derived))
                rebuilt = MODULE.ASSET.AssetStore(Path(os.environ["RIPPER_OUTPUT_DIR"]) / "rebuilt")
                self.assertTrue(rebuilt.rebuild_from_archives(MODULE.ARCHIVE.archive_root()))
                rebuilt_claims = [item for item in rebuilt.query_claims([]) if item["project_id"] == result["project_id"]]
                self.assertEqual(len(rebuilt_claims), 3)
            finally:
                if old_home is None: os.environ.pop("HOME", None)
                else: os.environ["HOME"] = old_home
                if old_output is None: os.environ.pop("RIPPER_OUTPUT_DIR", None)
                else: os.environ["RIPPER_OUTPUT_DIR"] = old_output

    def test_invalid_knowledge_is_rejected_before_archive_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old_home = os.environ.get("HOME")
            os.environ["HOME"] = str(root / "home")
            MODULE.ARCHIVE.ARCHIVE_HOME = Path(os.environ["HOME"]) / "Ripper"
            try:
                doc = root / "design.md"; doc.write_text("任务调度", encoding="utf-8")
                analysis = root / "analysis.md"; analysis.write_text("# 分析", encoding="utf-8")
                profile = MODULE.build_input("ORK", [doc])["domain_profile"]
                knowledge = root / "bad.json"
                knowledge.write_text(json.dumps({"profile_id": profile["profile_id"], "sources": [], "module_cards": [], "architecture_candidates": []}), encoding="utf-8")
                with self.assertRaises(ValueError):
                    MODULE.deposit_project("ORK", analysis, [doc], knowledge=knowledge)
                self.assertFalse(list((MODULE.ARCHIVE.ARCHIVE_HOME / "archives").glob("*/archive-manifest.json")))
            finally:
                if old_home is None: os.environ.pop("HOME", None)
                else: os.environ["HOME"] = old_home

    def test_post_archive_failure_rolls_back_new_deposit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old_home, old_output = os.environ.get("HOME"), os.environ.get("RIPPER_OUTPUT_DIR")
            os.environ["HOME"] = str(root / "home")
            os.environ["RIPPER_OUTPUT_DIR"] = str(root / "output")
            MODULE.ARCHIVE.ARCHIVE_HOME = Path(os.environ["HOME"]) / "Ripper"
            doc = root / "design.md"; doc.write_text("任务调度", encoding="utf-8")
            analysis = root / "analysis.json"; analysis.write_text('{"claims":[]}', encoding="utf-8")
            original = MODULE.ASSET.AssetStore.sync_archive_manifest
            MODULE.ASSET.AssetStore.sync_archive_manifest = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("index failure"))
            try:
                with self.assertRaisesRegex(RuntimeError, "index failure"):
                    MODULE.deposit_project("事务工程", analysis, [doc])
                archives = MODULE.ARCHIVE.ARCHIVE_HOME / "archives"
                self.assertFalse(list(archives.glob("*/archive-manifest.json")))
                self.assertFalse((archives / ".ripper-transaction").exists())
            finally:
                MODULE.ASSET.AssetStore.sync_archive_manifest = original
                if old_home is None: os.environ.pop("HOME", None)
                else: os.environ["HOME"] = old_home
                if old_output is None: os.environ.pop("RIPPER_OUTPUT_DIR", None)
                else: os.environ["RIPPER_OUTPUT_DIR"] = old_output

    def test_update_without_new_knowledge_removes_stale_market_practices(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old_home, old_output = os.environ.get("HOME"), os.environ.get("RIPPER_OUTPUT_DIR")
            os.environ["HOME"] = str(root / "home")
            os.environ["RIPPER_OUTPUT_DIR"] = str(root / "output")
            MODULE.ARCHIVE.ARCHIVE_HOME = Path(os.environ["HOME"]) / "Ripper"
            try:
                doc = root / "design.md"; doc.write_text("任务调度 DAG 心跳 租约 重试", encoding="utf-8")
                analysis = root / "analysis.json"; analysis.write_text('{"claims":[{"title":"旧成果","statement":"旧实现"}]}', encoding="utf-8")
                profile = MODULE.build_input("知识失效工程", [doc])["domain_profile"]
                knowledge = root / "knowledge.json"
                payload = {
                    "profile_id": profile["profile_id"],
                    "project_direction_candidates": [{"name": "任务调度与工作流编排", "confidence": "high", "project_source_refs": [str(doc.resolve())], "rationale": "材料含调度机制", "search_keywords": ["任务调度"]}],
                    "sources": [{"id": f"s_{size}", "title": f"{size}实践", "url": f"https://example.com/{size}", "published_at": "2026-09-17", "geography": "CN", "organization_size": size} for size in ("large", "medium", "small")],
                    "module_cards": [{"id": "m1", "name": "租约恢复", "basis_source_ids": ["s_large"], "historical_fact": False, "project_fit": "延伸租约", "compatibility_requirements": ["状态持久化"], "conflicts_with": []}],
                    "architecture_candidates": [{"variant": "conservative", "module_card_ids": ["m1"], "preserved_terms": profile["locked_terms"][:1], "historical_fact": False, "coherence_rationale": "沿用状态"}, {"variant": "enhanced", "module_card_ids": ["m1"], "preserved_terms": profile["locked_terms"][:1], "historical_fact": False, "coherence_rationale": "增强状态"}],
                }
                knowledge.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
                first = MODULE.deposit_project("知识失效工程", analysis, [doc], knowledge=knowledge)
                archive = Path(first["archive_path"])
                analysis.write_text('{"claims":[{"title":"新成果","statement":"新实现"}]}', encoding="utf-8")
                updated = MODULE.deposit_project("知识失效工程", analysis, [doc], update=True)
                manifest = json.loads((archive / "archive-manifest.json").read_text(encoding="utf-8"))
                self.assertNotIn("market_practices_path", manifest)
                self.assertFalse((archive / "knowledge" / "market-practices.json").exists())
                self.assertTrue(list((archive / "analysis" / "history").glob("knowledge-*/market-practices.json")))
                claims = [item for item in MODULE.ASSET.AssetStore().query_claims([]) if item["project_id"] == updated["project_id"]]
                self.assertEqual([item["title"] for item in claims], ["新成果"])
            finally:
                if old_home is None: os.environ.pop("HOME", None)
                else: os.environ["HOME"] = old_home
                if old_output is None: os.environ.pop("RIPPER_OUTPUT_DIR", None)
                else: os.environ["RIPPER_OUTPUT_DIR"] = old_output


if __name__ == "__main__":
    unittest.main()
