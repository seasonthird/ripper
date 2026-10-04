"""Behavioral coverage for the public Skill lifecycle and corruption cases."""

import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("unified_ripper_tests", ROOT / "ripper/scripts/ripper.py")
CLI = importlib.util.module_from_spec(spec)
spec.loader.exec_module(CLI)


@pytest.fixture
def environment(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setattr(CLI.PIPELINE.ARCHIVE, "ARCHIVE_HOME", tmp_path / "home" / "Ripper")
    doc = tmp_path / "design.md"
    doc.write_text("task retry design")
    analysis = tmp_path / "analysis.json"
    analysis.write_text(json.dumps({"claims": [{"id": "retry", "title": "retry", "statement": "persistent retry", "realization_status": "implemented", "source_refs": [{"path": str(doc)}], "confirmations": [{"question": "Production?", "status": "open"}]}]}))
    result = CLI.PIPELINE.deposit_project("Unified", analysis, [doc])
    return tmp_path, doc, analysis, result


def test_public_cli_deposit_confirm_rebuild_export(environment):
    _, _, _, result = environment
    runner = ROOT / "ripper/scripts/ripper.py"
    def run(*args, code=0):
        response = subprocess.run([sys.executable, str(runner), *args], capture_output=True, text=True)
        assert response.returncode == code, response.stderr
        return json.loads(response.stdout if code in {0, 2} else response.stderr)
    run("doctor")
    confirmed = run("confirm", result["project_id"], "retry", "--question", "Production?", "--answer", "Yes, verified", "--revision", "1")
    assert confirmed["revision"] == 2
    run("confirm", result["project_id"], "retry", "--question", "Production?", "--answer", "old version", "--revision", "1", code=1)
    CLI.PIPELINE.ASSET.AssetStore().db_path.unlink()
    run("rebuild")
    claim = run("browse")["usable_claims"][0]
    assert claim["confirmations"][0]["answer"] == "Yes, verified"
    assert claim["confirmations"][0]["status"] == "confirmed"
    exported = run("export", "star", "Backend Engineer")
    manifest = json.loads(Path(exported["manifest_path"]).read_text())
    assert manifest["claim_revisions"] == {"retry": 2}
    assert manifest["claim_snapshot"][0]["confirmations"][0]["answer"] == "Yes, verified"
    assert manifest["claim_snapshot"][0]["evidence"]
    run("verify-export", exported["manifest_path"])
    Path(exported["output_path"]).write_text("changed")
    assert "mismatch" in run("verify-export", exported["manifest_path"], code=1)["error"]


def test_confirmed_answer_survives_analysis_refresh(environment):
    _, doc, analysis, result = environment
    CLI.PIPELINE.confirm_claim(result["project_id"], "retry", "Production?", "Verified", "confirmed", 1)
    payload = json.loads(analysis.read_text())
    payload["claims"][0]["statement"] = "updated wording"
    payload["claims"][0]["confirmations"] = ["Production?"]
    analysis.write_text(json.dumps(payload))
    CLI.PIPELINE.deposit_project("Unified", analysis, [doc], update=True)
    claim = CLI.EXPORTER.browse()["usable_claims"][0]
    assert claim["revision"] == 3
    assert claim["confirmations"][0]["status"] == "confirmed"
    assert claim["confirmations"][0]["answer"] == "Verified"


@pytest.mark.parametrize("missing", ["analysis/project-analysis.json", "sources/documents/design.md", "knowledge/domain-profile.json"])
def test_incomplete_archive_preserves_previous_index(environment, missing):
    _, _, _, result = environment
    store = CLI.PIPELINE.ASSET.AssetStore()
    archive = Path(result["archive_path"])
    store.rebuild_from_archives(archive.parent)
    (archive / missing).unlink()
    with pytest.raises(ValueError, match="missing"):
        store.rebuild_from_archives(archive.parent)
    assert store.query_claims()[0]["id"] == "retry"
    assert not store.archive_index_is_current(archive.parent)


def test_update_rejects_manifest_source_traversal_before_unlink(environment):
    root, doc, analysis, result = environment
    outside = root / "outside.md"
    outside.write_text("must survive")
    archive = Path(result["archive_path"])
    manifest_path = archive / "archive-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["sources"][0]["path"] = str(outside)
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="escapes"):
        CLI.PIPELINE.deposit_project("Unified", analysis, [doc], update=True)
    assert outside.read_text() == "must survive"


def test_foreign_keys_enabled_on_every_connection(environment):
    store = CLI.PIPELINE.ASSET.AssetStore()
    with store.connect() as conn:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO claim_evidence VALUES ('missing', 'missing')")


def test_damaged_cache_can_be_rebuilt_from_validated_archive(environment):
    store = CLI.PIPELINE.ASSET.AssetStore()
    store.db_path.write_bytes(b"not a database")
    with pytest.raises(ValueError, match="damaged"):
        CLI.maintain()
    result = CLI.maintain(rebuild=True)
    assert Path(result["damaged_cache_backup"]).read_bytes() == b"not a database"
    assert CLI.PIPELINE.ASSET.AssetStore().query_claims()[0]["id"] == "retry"


def test_real_process_interruption_recovers_old_archive(environment):
    _, _, _, result = environment
    archive = Path(result["archive_path"])
    before = (archive / "analysis/project-analysis.json").read_bytes()
    # Abrupt termination bypasses both exception handlers and context cleanup.
    code = """
import importlib.util, os, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location('transaction', sys.argv[1])
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
target = Path(sys.argv[2])
with m.archive_lock(target.parent):
    with m.deposit_transaction(target.parent, target):
        (target / 'analysis/project-analysis.json').write_text('partial')
        os._exit(17)
"""
    child = subprocess.run([sys.executable, "-c", code, str(ROOT / "ripper-core/archive_transaction.py"), str(archive)])
    assert child.returncode == 17
    recovery = CLI.maintain()
    assert recovery["recovered"]
    assert (archive / "analysis/project-analysis.json").read_bytes() == before
    assert not (archive.parent / ".ripper-transaction").exists()


def test_export_serializes_concurrent_deposit(environment, monkeypatch):
    _, doc, analysis, result = environment
    original = CLI.EXPORTER._evidence_ids
    attempted = []
    def competing_deposit(store, claim_id):
        # A second process tries the production deposit path while export is
        # between selecting claims and reading their evidence.
        process = subprocess.run([sys.executable, str(ROOT / "ripper/scripts/ripper.py"), "deposit", "Unified", "--analysis", str(analysis), "--source", str(doc), "--update"], capture_output=True, text=True)
        assert process.returncode == 1
        attempted.append(process.returncode)
        return original(store, claim_id)
    monkeypatch.setattr(CLI.EXPORTER, "_evidence_ids", competing_deposit)
    _, _, manifest = CLI.EXPORTER.render("resume", "Engineer")
    assert attempted and manifest["claim_ids"] == ["retry"]
    assert manifest["evidence_ids"]
    with CLI.PIPELINE.ASSET.AssetStore().connect() as conn:
        assert not list(conn.execute("PRAGMA foreign_key_check"))
