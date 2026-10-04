"""Public source inventory must exclude private state and machine artifacts."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("source_release_tests", ROOT / "tools/package_source.py")
PACKAGE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(PACKAGE)


def test_public_inventory_excludes_runtime_and_upstream_administration(tmp_path, monkeypatch):
    monkeypatch.setattr(PACKAGE, "ROOT", tmp_path)
    allowed = ["README.md", "VERSION", "CHANGELOG.md", ".gitignore", "ripper/SKILL.md", "ripper-core/asset_store.py", ".github/workflows/ci.yml", "examples/task-recovery/project.md"]
    excluded = ["ripper-output/private.json", "zip_backup/history.zip", ".myflicker/local.json", "ripper-core/__pycache__/asset.pyc", "ripper-collector/.venv/lib/package.py", "ripper-cv/.github/FUNDING.yml", "ripper-collector/.env", "ripper-cv/demo-output.png"]
    for name in allowed + excluded:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture")
    assert {p.relative_to(tmp_path).as_posix() for p in PACKAGE.collect()} == set(allowed)


def test_public_inventory_rejects_external_directory_symlinks(tmp_path, monkeypatch):
    monkeypatch.setattr(PACKAGE, "ROOT", tmp_path)
    source = tmp_path / "ripper"
    source.mkdir()
    outside = tmp_path / "private"
    outside.mkdir()
    try:
        (source / "linked").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks unavailable")
    with pytest.raises(ValueError, match="symbolic"):
        PACKAGE.collect()
