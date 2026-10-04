"""Product identity and active-entrypoint regression tests."""

from __future__ import annotations

import re
from pathlib import Path


COLLECTOR_ROOT = Path(__file__).resolve().parent.parent
BUNDLE_ROOT = COLLECTOR_ROOT.parent

SKILLS = {
    BUNDLE_ROOT / "ripper-collector": "ripper-collector",
    BUNDLE_ROOT / "ripper-archive-manager": "ripper-archive-manager",
    BUNDLE_ROOT / "ripper-evidence-modeler": "ripper-evidence-modeler",
    BUNDLE_ROOT / "ripper-exporter": "ripper-exporter",
    BUNDLE_ROOT / "ripper-cv" / "skills" / "ripper-cv": "ripper-cv",
}

FORBIDDEN_IDENTITY = (
    "resume" + "asher",
    "project-resume-" + "writer-main",
    "project " + "resume " + "writer",
    "clau" + "de-" + "res" + "ume-" + "main",
    "github.com/" + "ear" + "ino",
    "github.com/" + "ear" + "ino/ripper-collector",
    "ear" + "ino.github.io/" + "ripper-collector",
)


def _text_files():
    ignored = {".venv", ".pytest_cache", "__pycache__", ".git"}
    for path in BUNDLE_ROOT.rglob("*"):
        if not path.is_file() or any(part in ignored for part in path.parts):
            continue
        if path.suffix.lower() in {".zip", ".pdf", ".png", ".jpg", ".jpeg", ".ttf"}:
            continue
        try:
            yield path, path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue


def test_skill_directory_and_frontmatter_names_are_consistent():
    for folder, expected in SKILLS.items():
        skill = folder / "SKILL.md"
        assert skill.is_file(), f"missing {skill}"
        match = re.search(r"(?m)^name:\s*([^\n]+)$", skill.read_text(encoding="utf-8"))
        assert match and match.group(1).strip() == expected
        assert folder.name == expected


def test_retired_names_and_fabricated_upstream_urls_are_absent():
    hits = []
    for path, text in _text_files():
        # Genuine upstream links belong in the attribution document. They
        # must remain absent from active product identities and endpoints.
        if path == BUNDLE_ROOT / "THIRD_PARTY_NOTICES.md":
            continue
        lowered = text.lower()
        for forbidden in FORBIDDEN_IDENTITY:
            if forbidden in lowered:
                hits.append(f"{path.relative_to(BUNDLE_ROOT)}: {forbidden}")
    assert not hits, "\n".join(hits)


def test_active_collector_entrypoints_use_new_name():
    assert (COLLECTOR_ROOT / "bin" / "ripper-collector-exec").is_file()
    assert (COLLECTOR_ROOT / "commands" / "ripper-collector.md").is_file()
    retired = "resume" + "asher"
    assert not any((COLLECTOR_ROOT / "bin").glob(f"*{retired}*"))
    assert not any((COLLECTOR_ROOT / "commands").glob(f"*{retired}*"))


def test_collector_command_cannot_route_to_legacy_job_pipeline():
    command = (COLLECTOR_ROOT / "commands" / "ripper-collector.md").read_text(encoding="utf-8").lower()
    for forbidden in ("job source", "resume.md", "nine-phase"):
        assert forbidden not in command
    for required in ("project-analysis.json", "deposit-project", ".md`/`.pdf", "optional source"):
        assert required in command


def test_no_bundled_supabase_endpoint_or_key():
    relevant = [
        COLLECTOR_ROOT / "supabase" / "config.sh",
        COLLECTOR_ROOT / "stats.md",
    ]
    for path in relevant:
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"https://[a-z0-9-]+\.supabase\.co", text)
        assert not re.search(r"\beyJ[a-zA-Z0-9_-]{20,}\.", text)


def test_openai_metadata_exists_for_collector_and_cv():
    assert (COLLECTOR_ROOT / "agents" / "openai.yaml").is_file()
    assert (BUNDLE_ROOT / "ripper-cv" / "skills" / "ripper-cv" / "agents" / "openai.yaml").is_file()


def test_documented_storage_contract_has_one_durable_fact_source():
    readmes = "\n".join(
        (BUNDLE_ROOT / name).read_text(encoding="utf-8")
        for name in ("README.md", "README.zh-CN.md")
    )
    assert "~/Ripper/archives/" in readmes
    assert "assets/.cache/ripper-assets.sqlite" in readmes
    assert "repositories/<repo-slug>" not in readmes


def test_evidence_modeler_does_not_require_resume_rules_for_deposit():
    text = (BUNDLE_ROOT / "ripper-evidence-modeler" / "SKILL.md").read_text(encoding="utf-8")
    required_block = text.split("**每次沉淀必读：**", 1)[1].split("**分析代码时读取：**", 1)[0]
    assert "asset_analysis_contract.md" in required_block
    assert "resume_" not in required_block
    assert "岗位、简历和导出表达规则不属于沉淀阶段" in text


def test_cv_reads_the_canonical_rebuildable_index_path():
    text = (BUNDLE_ROOT / "ripper-cv" / "skills" / "ripper-cv" / "SKILL.md").read_text(encoding="utf-8")
    assert "$RIPPER_OUTPUT_DIR/assets/.cache/ripper-assets.sqlite" in text
    assert "$RIPPER_OUTPUT_DIR/assets/ripper-assets.sqlite" not in text
    assert "不按 `ownership_status` 过滤" in text


def test_legacy_helpers_are_explicitly_separated_from_active_cli_contract():
    source = (COLLECTOR_ROOT / "scripts" / "orchestration.py").read_text(encoding="utf-8")
    assert "Legacy job-application compatibility commands" in source
    assert 'help="[legacy] Locate a resume input"' in source
    skill = (COLLECTOR_ROOT / "SKILL.md").read_text(encoding="utf-8").lower()
    assert "parse-job-mode" not in skill
    assert "discover-resume" not in skill
