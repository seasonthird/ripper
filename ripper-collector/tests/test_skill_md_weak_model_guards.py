"""Prescriptions that prevent weak orchestrators from bypassing deposit safety."""

from pathlib import Path


SKILL_MD = Path(__file__).resolve().parent.parent / "SKILL.md"


def test_skill_requires_wrapper_for_deterministic_operations():
    text = SKILL_MD.read_text(encoding="utf-8")
    assert '"$RS" orchestration <subcommand> [arguments]' in text
    assert "不得直接调用系统 Python" in text


def test_skill_never_requires_user_sqlite_configuration():
    text = SKILL_MD.read_text(encoding="utf-8")
    assert "不得要求用户配置 SQLite" in text
    assert "可以重建的查询索引" in text


def test_update_requires_explicit_confirmation_and_full_transaction():
    text = SKILL_MD.read_text(encoding="utf-8")
    assert "只有得到明确确认后才能重试" in text
    assert "--update --update-project-name" in text
    assert "不得手工复制到档案目录、静默覆盖或跳过重复门禁" in text


def test_failed_knowledge_validation_cannot_be_deposited():
    text = SKILL_MD.read_text(encoding="utf-8")
    assert "validate-domain-knowledge" in text
    assert "验证返回非零时修正知识包" in text
    assert "省略 `--knowledge`" in text
