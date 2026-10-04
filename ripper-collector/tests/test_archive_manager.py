"""Tests for the filesystem-first project archive manager."""

from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("archive_manager", ROOT / "ripper-archive-manager" / "scripts" / "archive_manager.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ArchiveManagerTests(unittest.TestCase):
    def test_create_list_duplicate_and_update_preserves_history(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home"
            previous_home = os.environ.get("HOME")
            os.environ["HOME"] = str(home)
            try:
                # ARCHIVE_HOME is intentionally resolved at import time in
                # production. Rebind it here to isolate the test filesystem.
                MODULE.ARCHIVE_HOME = home / "Ripper"
                incoming = Path(directory) / "project.md"
                incoming.write_text("# Project\n", encoding="utf-8")
                analysis = Path(directory) / "analysis.md"
                analysis.write_text("# Analysis\n## Reliability\n", encoding="utf-8")
                folder = MODULE.create_archive("Project Alpha", analysis, [incoming], [])
                self.assertTrue((folder / "sources" / "documents" / incoming.name).exists())
                listed = MODULE.list_archives()
                self.assertEqual(listed[0]["project_id"], MODULE.project_id("Project Alpha"))
                self.assertIn("Reliability", listed[0]["themes"])
                matches = MODULE.find_duplicates([incoming], "Project Alpha")
                self.assertEqual(matches[0]["project_name"], "Project Alpha")
                prepared = MODULE.prepare_input("Project Alpha", [incoming], [])
                self.assertEqual(prepared["project_id"], MODULE.project_id("Project Alpha"))
                self.assertEqual(prepared["document_count"], 1)
                code, result = MODULE.deposit("Project Alpha", analysis, [incoming], [], update=False)
                self.assertEqual(code, 2)
                self.assertEqual(result["status"], "confirmation_required")
                knowledge = folder / "knowledge"
                knowledge.mkdir()
                (knowledge / "domain-profile.json").write_text('{"profile_id":"old"}', encoding="utf-8")
                analysis.write_text("# Analysis v2\n## Recovery\n", encoding="utf-8")
                MODULE.update_archive("Project Alpha", analysis, [], [])
                self.assertTrue(list((folder / "analysis" / "history").glob("project-analysis-*.md")))
                snapshots = list((folder / "analysis" / "history").glob("knowledge-*/domain-profile.json"))
                self.assertEqual(len(snapshots), 1)
                self.assertIn('"old"', snapshots[0].read_text(encoding="utf-8"))
            finally:
                if previous_home is None:
                    os.environ.pop("HOME", None)
                else:
                    os.environ["HOME"] = previous_home

    def test_unicode_project_names_and_same_named_sources_are_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home"
            previous_home = os.environ.get("HOME")
            os.environ["HOME"] = str(home)
            MODULE.ARCHIVE_HOME = home / "Ripper"
            try:
                first = Path(directory) / "a" / "README.md"
                second = Path(directory) / "b" / "README.md"
                first.parent.mkdir(); second.parent.mkdir()
                first.write_text("one", encoding="utf-8")
                second.write_text("two", encoding="utf-8")
                analysis = Path(directory) / "analysis.md"
                analysis.write_text("# 分析\n## 亮点\n", encoding="utf-8")
                folder = MODULE.create_archive("支付风控工程", analysis, [first, second], [])
                files = list((folder / "sources" / "documents").rglob("README.md"))
                self.assertEqual(len(files), 2)
                self.assertEqual(len({p.relative_to(folder).as_posix() for p in files}), 2)
                self.assertIn("支付风控工程", folder.name)
                self.assertTrue(MODULE.project_id("支付风控工程").startswith("project_"))
            finally:
                if previous_home is None:
                    os.environ.pop("HOME", None)
                else:
                    os.environ["HOME"] = previous_home

    def test_update_replaces_active_source_and_snapshots_previous_version(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            previous_home = os.environ.get("HOME")
            os.environ["HOME"] = str(home)
            MODULE.ARCHIVE_HOME = home / "Ripper"
            try:
                document = root / "project.md"; document.write_text("v1", encoding="utf-8")
                analysis = root / "analysis.md"; analysis.write_text("# v1", encoding="utf-8")
                folder = MODULE.create_archive("更新工程", analysis, [document], [])
                document.write_text("v2", encoding="utf-8")
                analysis.write_text("# v2", encoding="utf-8")
                MODULE.update_archive("更新工程", analysis, [document], [])
                active = [item for item in (folder / "sources" / "documents").rglob("*") if item.is_file()]
                snapshots = list((folder / "analysis" / "history").glob("sources-*/documents/project.md"))
                manifest = MODULE.read_manifest(folder)
                self.assertEqual(len(active), 1)
                self.assertEqual(active[0].read_text(encoding="utf-8"), "v2")
                self.assertEqual(len(snapshots), 1)
                self.assertEqual(snapshots[0].read_text(encoding="utf-8"), "v1")
                self.assertEqual(manifest["document_count"], 1)
                self.assertEqual(len(manifest["sources"]), 1)
            finally:
                if previous_home is None: os.environ.pop("HOME", None)
                else: os.environ["HOME"] = previous_home

    def test_update_uses_manifest_path_for_json_analysis(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            previous_home = os.environ.get("HOME")
            os.environ["HOME"] = str(home)
            MODULE.ARCHIVE_HOME = home / "Ripper"
            try:
                document = root / "project.md"; document.write_text("project", encoding="utf-8")
                analysis = root / "analysis.json"; analysis.write_text('{"claims":[{"title":"v1"}]}', encoding="utf-8")
                folder = MODULE.create_archive("JSON 更新工程", analysis, [document], [])
                analysis.write_text('{"claims":[{"title":"v2"}]}', encoding="utf-8")
                MODULE.update_archive("JSON 更新工程", analysis, [], [])
                manifest = MODULE.read_manifest(folder)
                active = folder / manifest["analysis_path"]
                history = list((folder / "analysis" / "history").glob("project-analysis-*.json"))
                self.assertIn('"v2"', active.read_text(encoding="utf-8"))
                self.assertEqual(len(history), 1)
                self.assertIn('"v1"', history[0].read_text(encoding="utf-8"))
                self.assertFalse((folder / "analysis" / "project-analysis.md").exists())
            finally:
                if previous_home is None: os.environ.pop("HOME", None)
                else: os.environ["HOME"] = previous_home

    def test_update_migrates_markdown_analysis_to_canonical_json(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            previous_home = os.environ.get("HOME")
            os.environ["HOME"] = str(home)
            MODULE.ARCHIVE_HOME = home / "Ripper"
            try:
                document = root / "project.md"; document.write_text("project", encoding="utf-8")
                markdown = root / "analysis.md"; markdown.write_text("# 旧分析\n- 旧成果", encoding="utf-8")
                folder = MODULE.create_archive("分析迁移工程", markdown, [document], [])
                structured = root / "analysis.json"
                structured.write_text('{"claims":[{"title":"结构化成果"}]}', encoding="utf-8")
                MODULE.update_archive("分析迁移工程", structured, [], [])
                manifest = MODULE.read_manifest(folder)
                self.assertEqual(manifest["analysis_path"], "analysis/project-analysis.json")
                self.assertTrue((folder / "analysis" / "project-analysis.json").is_file())
                self.assertFalse((folder / "analysis" / "project-analysis.md").exists())
                self.assertTrue(list((folder / "analysis" / "history").glob("project-analysis-*.md")))
            finally:
                if previous_home is None: os.environ.pop("HOME", None)
                else: os.environ["HOME"] = previous_home

    def test_update_preserves_same_relative_path_across_document_and_core_buckets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            previous_home = os.environ.get("HOME")
            os.environ["HOME"] = str(home)
            MODULE.ARCHIVE_HOME = home / "Ripper"
            try:
                document = root / "docs" / "README.md"
                core = root / "core"
                document.parent.mkdir(); core.mkdir()
                document.write_text("document", encoding="utf-8")
                (core / "README.md").write_text("core", encoding="utf-8")
                analysis = root / "analysis.json"; analysis.write_text('{"claims":[{"title":"成果"}]}', encoding="utf-8")
                folder = MODULE.create_archive("同名路径工程", analysis, [document], [core])
                MODULE.update_archive("同名路径工程", analysis, [], [])
                manifest = MODULE.read_manifest(folder)
                keys = {(item["source_type"], item["path"]) for item in manifest["sources"]}
                self.assertEqual(keys, {("document", "README.md"), ("core-source", "README.md")})
                self.assertTrue((folder / "sources" / "documents" / "README.md").is_file())
                self.assertTrue((folder / "sources" / "core-source" / "README.md").is_file())
            finally:
                if previous_home is None: os.environ.pop("HOME", None)
                else: os.environ["HOME"] = previous_home

    def test_core_archive_omits_credentials_and_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            previous_home = os.environ.get("HOME")
            os.environ["HOME"] = str(home)
            MODULE.ARCHIVE_HOME = home / "Ripper"
            try:
                document = root / "project.md"; document.write_text("# Project", encoding="utf-8")
                analysis = root / "analysis.md"; analysis.write_text("# Analysis", encoding="utf-8")
                core = root / "core"; core.mkdir()
                (core / "app.py").write_text("print('ok')", encoding="utf-8")
                (core / ".env").write_text("TOKEN=secret", encoding="utf-8")
                (core / "private.pem").write_text("secret", encoding="utf-8")
                secrets = core / "secrets"; secrets.mkdir()
                (secrets / "config.yaml").write_text("password: secret", encoding="utf-8")
                outside = root / "outside.key"; outside.write_text("secret", encoding="utf-8")
                (core / "linked.key").symlink_to(outside)
                folder = MODULE.create_archive("安全工程", analysis, [document], [core])
                archived = [item.relative_to(folder / "sources" / "core-source").as_posix() for item in (folder / "sources" / "core-source").rglob("*") if item.is_file()]
                manifest = MODULE.read_manifest(folder)
                self.assertEqual(archived, ["app.py"])
                self.assertTrue(any(path.endswith(".env") for path in manifest["omitted_core_source"]))
                self.assertTrue(any(path.endswith("linked.key") for path in manifest["omitted_core_source"]))
                prepared = MODULE.prepare_input("安全工程预检", [document], [core])
                self.assertEqual(prepared["core_source_count"], 1)
                self.assertEqual([item["name"] for item in prepared["sources"] if item["source_type"] == "core-source"], ["app.py"])
            finally:
                if previous_home is None: os.environ.pop("HOME", None)
                else: os.environ["HOME"] = previous_home


if __name__ == "__main__":
    unittest.main()
