"""Cross-host runtime discovery regression tests."""

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SKILL_MD = ROOT / "SKILL.md"
WRAPPER = ROOT / "bin" / "ripper-collector-exec"


def test_skill_md_has_one_cross_host_discovery_loop():
    text = SKILL_MD.read_text(encoding="utf-8")
    assert text.count("for candidate in \\") == 1
    for host in (".claude", ".codex", ".gemini", ".opencode"):
        assert f'"$HOME/{host}/skills/ripper-collector"' in text


def test_skill_uses_new_wrapper_and_installer_message():
    text = SKILL_MD.read_text(encoding="utf-8")
    assert 'RS="$SKILL_ROOT/bin/ripper-collector-exec"' in text
    assert "bash $SKILL_ROOT/install.sh" in text


def test_wrapper_checks_posix_and_windows_venv_layouts():
    text = WRAPPER.read_text(encoding="utf-8")
    assert ".venv/bin/python" in text
    assert ".venv/Scripts/python.exe" in text


def test_wrapper_supports_explicit_runtime_override():
    text = WRAPPER.read_text(encoding="utf-8")
    assert "RIPPER_COLLECTOR_PYTHON" in text
    assert "RIPPER_COLLECTOR_VENV" in text
