"""Regression tests for the local Ripper asset store."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "ripper-core" / "asset_store.py"
SPEC = importlib.util.spec_from_file_location("ripper_asset_store", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
AssetStore = MODULE.AssetStore


class AssetStoreTests(unittest.TestCase):
    def test_empty_archive_index_is_current_after_rebuild(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = AssetStore(root / "assets")
            store.rebuild_from_archives(root / "archives")
            self.assertTrue(store.archive_index_is_current(root / "archives"))

    def test_markdown_fallback_preserves_every_distinct_bullet(self):
        with tempfile.TemporaryDirectory() as directory:
            analysis = Path(directory) / "analysis.md"
            analysis.write_text("# ORK\n\n- 成果一\n- 成果二\n- 成果三\n", encoding="utf-8")
            payload = MODULE.parse_analysis(analysis, "ORK")
            self.assertEqual([item["statement"] for item in payload["claims"]], ["成果一", "成果二", "成果三"])
            self.assertTrue(all(item["realization_status"] == "designed" for item in payload["claims"]))

    def test_store_records_evidence_backed_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = AssetStore(root / "assets")
            repository = store.register_repository(str(root / "demo"))
            claim_id = store.record_candidate(
                repository["id"],
                {
                    "title": "可恢复任务编排",
                    "statement": "存在持久化运行状态与失败恢复机制",
                    "path": "scripts/orchestration.py",
                    "symbol": "build_prompt",
                    "line_start": 100,
                    "line_end": 140,
                    "claim_text": "从持久化状态目录读取阶段产物并构造后续输入",
                    "capabilities": ["workflow-orchestration", "reliability"],
                    "confirmation_questions": ["你在该机制中承担什么职责？"],
                },
            )
            self.assertTrue(claim_id.startswith("claim_"))
            with store.connect() as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM evidence").fetchone()[0], 1)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM confirmations WHERE status='open'").fetchone()[0], 1)
            claims = store.query_claims(["reliability"])
            self.assertEqual(len(claims), 1)
            self.assertNotIn("ownership_status", claims[0])

    def test_confirmed_claim_is_queryable_and_snapshot_is_readable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = AssetStore(root / "assets")
            repository = store.register_repository(str(root / "demo"))
            claim_id = store.record_claim(
                repository["id"],
                {
                    "title": "提示词输入隔离",
                    "statement": "将不可信工程文本与控制提示分隔",
                    "ownership_status": "confirmed",
                    "capabilities": ["prompt-safety"],
                },
            )
            snapshot = store.write_repository_snapshot(
                repository,
                {"source_path": str(root / "demo"), "modules": [{"path": "scripts", "role": "orchestration"}]},
            )
            claims = store.query_claims(["prompt-safety"])
            self.assertEqual(claims[0]["id"], claim_id)
            self.assertIn("modules:", snapshot.read_text(encoding="utf-8"))
            self.assertTrue(store.db_path.exists())

    def test_refresh_preserves_lifecycle_metadata_when_payload_omits_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = AssetStore(root / "assets")
            repository = store.register_repository(str(root / "demo"))
            payload = {
                "title": "可观测任务执行",
                "statement": "记录任务阶段和失败原因",
                "production_status": "confirmed",
                "disclosure_level": "public",
                "capabilities": ["observability"],
            }
            claim_id = store.record_claim(repository["id"], payload)
            store.record_claim(repository["id"], {"id": claim_id, "title": payload["title"], "statement": "刷新后的事实描述"})
            with store.connect() as conn:
                row = conn.execute(
                    "SELECT production_status, disclosure_level FROM claims WHERE id=?", (claim_id,)
                ).fetchone()
            self.assertEqual(tuple(row), ("confirmed", "public"))

    def test_claim_revision_and_identity_key_survive_wording_refresh(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = AssetStore(root / "assets")
            repository = store.register_repository(str(root / "demo"))
            claim_id = store.record_claim(repository["id"], {
                "identity_key": "async-retry",
                "title": "异步任务恢复",
                "statement": "初始描述",
            })
            same_id = store.record_claim(repository["id"], {
                "identity_key": "async-retry",
                "title": "异步任务恢复",
                "statement": "修订后的描述",
            })
            self.assertEqual(claim_id, same_id)
            with store.connect() as conn:
                row = conn.execute("SELECT identity_key, revision FROM claims WHERE id=?", (claim_id,)).fetchone()
            self.assertEqual((row[0], row[1]), ("async-retry", 2))

    def test_evidence_can_be_marked_stale_after_source_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = AssetStore(root / "assets")
            repository = store.register_repository(str(root / "demo"))
            store.record_candidate(repository["id"], {
                "title": "可验证机制",
                "statement": "来源可追踪",
                "path": "src/worker.py",
                "claim_text": "重试逻辑位于 worker",
                "content_hash": "old-hash",
            })
            with store.connect() as conn:
                artifact_id = conn.execute("SELECT id FROM artifacts LIMIT 1").fetchone()[0]
            self.assertEqual(store.mark_stale_evidence(artifact_id, "new-hash"), 1)
            with store.connect() as conn:
                status = conn.execute("SELECT freshness_status FROM evidence LIMIT 1").fetchone()[0]
            self.assertEqual(status, "stale")

    def test_register_document_accepts_markdown_and_pdf_extensions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = root / "project.md"
            document.write_text("# Project\n", encoding="utf-8")
            store = AssetStore(root / "assets")
            registered = store.register_document(str(document))
            with store.connect() as conn:
                row = conn.execute(
                    "SELECT source_kind, source_path FROM repositories WHERE id=?", (registered["id"],)
                ).fetchone()
            self.assertEqual(row[0], "document")
            self.assertEqual(row[1], str(document.resolve()))

            invalid = root / "project.txt"
            invalid.write_text("unsupported", encoding="utf-8")
            with self.assertRaises(ValueError):
                store.register_document(str(invalid))

    def test_realization_status_is_retained_and_normalized(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = AssetStore(root / "assets")
            repository = store.register_repository(str(root / "demo"))
            claim_id = store.record_claim(repository["id"], {
                "title": "可扩展方案",
                "statement": "在部分实现基础上形成完整优化设计",
                "realization_status": "design",
            })
            claim = store.query_claims()[0]
            self.assertEqual(claim["id"], claim_id)
            self.assertEqual(claim["realization_status"], "designed")

    def test_structured_p0_code_protocol_persists_refs_tests_and_reconstruction(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = AssetStore(root / "assets")
            repository = store.register_repository(str(root / "demo"))
            store.record_analysis(repository["id"], {"claims": [{
                "title": "高层项目架构",
                "statement": "基于方案和 PRD 形成可扩展的任务链路",
                "status": "inferred",
                "realization_status": "derived",
                "source_refs": [{"path": "docs/plan.md", "symbol": "TaskFlow", "line_start": 12, "line_end": 30}],
                "related_tests": ["tests/test_recovery.py"],
                "related_config": ["deploy/workflow.yaml"],
                "derived_optimizations": ["增加幂等重试和跨节点恢复"],
                "reconstruction": {"mode": "material-grounded-reconstruction", "note": "源码缺失时用于面试准备的合理复原"},
            }]})
            claim = store.query_claims()[0]
            self.assertEqual(claim["source_refs"][0]["path"], "docs/plan.md")
            self.assertEqual(claim["related_tests"], ["tests/test_recovery.py"])
            self.assertEqual(claim["related_config"], ["deploy/workflow.yaml"])
            self.assertIn("幂等重试", claim["derived_optimizations"][0])
            self.assertEqual(claim["reconstruction"]["mode"], "material-grounded-reconstruction")
            with store.connect() as conn:
                self.assertGreaterEqual(conn.execute("SELECT COUNT(*) FROM evidence WHERE kind='doc'").fetchone()[0], 1)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM artifacts WHERE path='docs/plan.md'").fetchone()[0], 1)

    def test_sync_replaces_removed_claims_for_same_project(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "project.md"
            source.write_text("# Project", encoding="utf-8")
            store = AssetStore(root / "assets")
            repository = store.register_repository(str(source), source_kind="document", project_id="project_demo")
            manifest = {"project_id": "project_demo", "archive_path": str(root), "sources": []}
            store.record_analysis(repository["id"], {"claims": [
                {"id": "keep", "title": "保留", "statement": "v1"},
                {"id": "remove", "title": "删除", "statement": "old"},
            ]}, manifest)
            # Exercise the exact-replacement primitive used by archive sync.
            store._clear_repository_derived(repository["id"])
            store.record_analysis(repository["id"], {"claims": [{"id": "keep", "title": "保留", "statement": "v2"}]}, manifest)
            claims = store.query_claims()
            self.assertEqual([(item["id"], item["statement"]) for item in claims], [("keep", "v2")])
