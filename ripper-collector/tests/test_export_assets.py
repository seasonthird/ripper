"""Tests for auditable Ripper asset exports."""

from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STORE_SPEC = importlib.util.spec_from_file_location("asset_store_for_export", ROOT / "ripper-core" / "asset_store.py")
assert STORE_SPEC and STORE_SPEC.loader
STORE_MODULE = importlib.util.module_from_spec(STORE_SPEC)
STORE_SPEC.loader.exec_module(STORE_MODULE)
AssetStore = STORE_MODULE.AssetStore
ARCHIVE_SPEC = importlib.util.spec_from_file_location("archive_manager_for_export", ROOT / "ripper-archive-manager" / "scripts" / "archive_manager.py")
assert ARCHIVE_SPEC and ARCHIVE_SPEC.loader
ARCHIVE_MODULE = importlib.util.module_from_spec(ARCHIVE_SPEC)
ARCHIVE_SPEC.loader.exec_module(ARCHIVE_MODULE)
EXPORT_SPEC = importlib.util.spec_from_file_location("ripper_exporter", ROOT / "ripper-exporter" / "export_assets.py")
assert EXPORT_SPEC and EXPORT_SPEC.loader
EXPORT_MODULE = importlib.util.module_from_spec(EXPORT_SPEC)
EXPORT_SPEC.loader.exec_module(EXPORT_MODULE)


class ExportAssetsTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.TemporaryDirectory()
        old_home = os.environ.get("HOME")
        old_archive_home = ARCHIVE_MODULE.ARCHIVE_HOME
        os.environ["HOME"] = self.home.name
        ARCHIVE_MODULE.ARCHIVE_HOME = Path(self.home.name) / "Ripper"
        def restore():
            if old_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = old_home
            ARCHIVE_MODULE.ARCHIVE_HOME = old_archive_home
            self.home.cleanup()
        self.addCleanup(restore)

    def test_export_rebuilds_empty_host_index_from_fixed_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            previous_home, previous_output = os.environ.get("HOME"), os.environ.get("RIPPER_OUTPUT_DIR")
            os.environ["HOME"] = str(root / "home")
            ARCHIVE_MODULE.ARCHIVE_HOME = Path(os.environ["HOME"]) / "Ripper"
            try:
                document = root / "project.md"; document.write_text("# Project", encoding="utf-8")
                analysis = root / "analysis.json"
                analysis.write_text('{"claims":[{"title":"跨宿主成果","statement":"建立任务恢复机制","realization_status":"implemented"}]}', encoding="utf-8")
                ARCHIVE_MODULE.create_archive("跨宿主工程", analysis, [document], [])
                os.environ["RIPPER_OUTPUT_DIR"] = str(root / "fresh-host-output")
                output, _, manifest = EXPORT_MODULE.render("resume", "Backend Engineer")
                self.assertIn("任务恢复机制", output.read_text(encoding="utf-8"))
                self.assertTrue(manifest["claim_ids"])
            finally:
                if previous_home is None: os.environ.pop("HOME", None)
                else: os.environ["HOME"] = previous_home
                if previous_output is None: os.environ.pop("RIPPER_OUTPUT_DIR", None)
                else: os.environ["RIPPER_OUTPUT_DIR"] = previous_output

    def test_export_refreshes_changed_archive_and_removes_old_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            previous_home, previous_output = os.environ.get("HOME"), os.environ.get("RIPPER_OUTPUT_DIR")
            os.environ["HOME"] = str(root / "home")
            os.environ["RIPPER_OUTPUT_DIR"] = str(root / "host-output")
            ARCHIVE_MODULE.ARCHIVE_HOME = Path(os.environ["HOME"]) / "Ripper"
            try:
                document = root / "project.md"; document.write_text("# Project", encoding="utf-8")
                analysis = root / "analysis.json"
                analysis.write_text('{"claims":[{"title":"旧成果","statement":"旧恢复链路","realization_status":"implemented"}]}', encoding="utf-8")
                ARCHIVE_MODULE.create_archive("持续更新工程", analysis, [document], [])
                first, _, _ = EXPORT_MODULE.render("resume", "Backend Engineer")
                self.assertIn("旧恢复链路", first.read_text(encoding="utf-8"))

                analysis.write_text('{"claims":[{"title":"新成果","statement":"新一致性链路","realization_status":"implemented"}]}', encoding="utf-8")
                ARCHIVE_MODULE.update_archive("持续更新工程", analysis, [], [])
                second, _, _ = EXPORT_MODULE.render("resume", "Backend Engineer")
                rendered = second.read_text(encoding="utf-8")
                self.assertIn("新一致性链路", rendered)
                self.assertNotIn("旧恢复链路", rendered)
            finally:
                if previous_home is None: os.environ.pop("HOME", None)
                else: os.environ["HOME"] = previous_home
                if previous_output is None: os.environ.pop("RIPPER_OUTPUT_DIR", None)
                else: os.environ["RIPPER_OUTPUT_DIR"] = previous_output

    def test_export_drops_claims_when_authoritative_archive_is_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            previous_home, previous_output = os.environ.get("HOME"), os.environ.get("RIPPER_OUTPUT_DIR")
            os.environ["HOME"] = str(root / "home")
            os.environ["RIPPER_OUTPUT_DIR"] = str(root / "host-output")
            ARCHIVE_MODULE.ARCHIVE_HOME = Path(os.environ["HOME"]) / "Ripper"
            try:
                document = root / "project.md"; document.write_text("# Project", encoding="utf-8")
                analysis = root / "analysis.json"
                analysis.write_text('{"claims":[{"title":"将被移除","statement":"不应成为孤儿成果"}]}', encoding="utf-8")
                folder = ARCHIVE_MODULE.create_archive("移除工程", analysis, [document], [])
                EXPORT_MODULE.render("resume", "Backend Engineer")
                import shutil
                shutil.rmtree(folder)
                with self.assertRaisesRegex(ValueError, "没有可用资产"):
                    EXPORT_MODULE.render("resume", "Backend Engineer")
                self.assertEqual(AssetStore().query_claims([], include_unconfirmed=True), [])
            finally:
                if previous_home is None: os.environ.pop("HOME", None)
                else: os.environ["HOME"] = previous_home
                if previous_output is None: os.environ.pop("RIPPER_OUTPUT_DIR", None)
                else: os.environ["RIPPER_OUTPUT_DIR"] = previous_output

    def test_export_refreshes_when_active_archived_source_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            previous_home, previous_output = os.environ.get("HOME"), os.environ.get("RIPPER_OUTPUT_DIR")
            os.environ["HOME"] = str(root / "home")
            os.environ["RIPPER_OUTPUT_DIR"] = str(root / "output")
            ARCHIVE_MODULE.ARCHIVE_HOME = Path(os.environ["HOME"]) / "Ripper"
            try:
                document = root / "project.md"; document.write_text("# Project", encoding="utf-8")
                analysis = root / "analysis.json"
                analysis.write_text('{"claims":[{"title":"源码事实","statement":"旧源码路径"}]}', encoding="utf-8")
                folder = ARCHIVE_MODULE.create_archive("档案源码指纹工程", analysis, [document], [])
                EXPORT_MODULE.render("resume", "Backend Engineer")
                active = folder / "sources" / "documents" / "project.md"
                active.write_text("# Project changed", encoding="utf-8")
                # The manifest is intentionally untouched: source bytes alone
                # are part of the filesystem fact source and must invalidate
                # the host-local index.
                with EXPORT_MODULE.AssetStore().connect() as conn:
                    conn.execute("UPDATE claims SET statement='旧源码路径' WHERE title='源码事实'")
                self.assertFalse(EXPORT_MODULE.AssetStore().archive_index_is_current(Path(os.environ["HOME"]) / "Ripper" / "archives"))
            finally:
                if previous_home is None: os.environ.pop("HOME", None)
                else: os.environ["HOME"] = previous_home
                if previous_output is None: os.environ.pop("RIPPER_OUTPUT_DIR", None)
                else: os.environ["RIPPER_OUTPUT_DIR"] = previous_output

    def test_star_export_keeps_all_submitted_claims_and_reports_redaction(self):
        with tempfile.TemporaryDirectory() as directory:
            previous = os.environ.get("RIPPER_OUTPUT_DIR")
            os.environ["RIPPER_OUTPUT_DIR"] = directory
            try:
                store = AssetStore()
                repository = store.register_repository(str(Path(directory) / "demo"))
                confirmed_id = store.record_candidate(
                    repository["id"],
                    {
                        "title": "可恢复编排",
                        "statement": "持久化阶段状态并隔离运行产物",
                        "path": "scripts/orchestration.py",
                        "claim_text": "读取统一状态目录中的阶段产物",
                        "capabilities": ["reliability"],
                    },
                )
                with store.connect() as conn:
                    conn.execute("UPDATE claims SET ownership_status='confirmed' WHERE id=?", (confirmed_id,))
                unconfirmed_id = store.record_claim(repository["id"], {"title": "待确认实现", "capabilities": ["reliability"]})
                restricted_id = store.record_claim(
                    repository["id"],
                    {
                        "title": "受限内部成果",
                        "capabilities": ["reliability"],
                        "disclosure_level": "restricted",
                    },
                )
                output, manifest_path, manifest = EXPORT_MODULE.render("star", "Backend Engineer", ["reliability"])
                self.assertTrue(output.exists())
                self.assertTrue(manifest_path.exists())
                self.assertIn(confirmed_id, manifest["claim_ids"])
                self.assertIn(unconfirmed_id, manifest["claim_ids"])
                self.assertFalse(any(item["claim_id"] == unconfirmed_id for item in manifest["excluded"]))
                self.assertIn(restricted_id, manifest["claim_ids"])
                self.assertEqual(manifest["excluded"], [])
                self.assertTrue(any(item["id"] == restricted_id for item in manifest["redaction_notes"]))
                rendered = output.read_text(encoding="utf-8")
                self.assertIn("Evidence", rendered)
                self.assertIn("围绕该成果承担并完成相关工作", rendered)

                team_output, _, _ = EXPORT_MODULE.render("resume", "Platform Team", ["reliability"], "team")
                self.assertIn("当前叙述视角为‘团队’", team_output.read_text(encoding="utf-8"))
            finally:
                if previous is None:
                    os.environ.pop("RIPPER_OUTPUT_DIR", None)
                else:
                    os.environ["RIPPER_OUTPUT_DIR"] = previous

    def test_export_maximizes_partial_and_designed_results_without_calling_them_implemented(self):
        with tempfile.TemporaryDirectory() as directory:
            previous = os.environ.get("RIPPER_OUTPUT_DIR")
            os.environ["RIPPER_OUTPUT_DIR"] = directory
            try:
                store = AssetStore()
                repository = store.register_repository(str(Path(directory) / "demo"))
                store.record_claim(repository["id"], {
                    "title": "核心链路",
                    "statement": "完成约七成核心流程",
                    "realization_status": "partial",
                    "capabilities": ["reliability"],
                })
                store.record_claim(repository["id"], {
                    "title": "完整优化方案",
                    "statement": "从现有实现推导完整扩展路径",
                    "realization_status": "derived",
                    "capabilities": ["reliability"],
                })
                output, _, _ = EXPORT_MODULE.render("resume", "Reliability Engineer", ["reliability"])
                rendered = output.read_text(encoding="utf-8")
                self.assertIn("部分实现", rendered)
                self.assertIn("由现有成果推导的优化方案", rendered)
                self.assertNotIn("完整实现并落地完整优化方案", rendered)
            finally:
                if previous is None:
                    os.environ.pop("RIPPER_OUTPUT_DIR", None)
                else:
                    os.environ["RIPPER_OUTPUT_DIR"] = previous
