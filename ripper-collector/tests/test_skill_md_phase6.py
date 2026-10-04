"""Active Collector deposit-stage contract assertions."""

from pathlib import Path


SKILL_MD = Path(__file__).resolve().parent.parent / "SKILL.md"


def _text() -> str:
    return SKILL_MD.read_text(encoding="utf-8")


def test_every_document_is_mapped_and_read():
    text = _text()
    assert "document-map" in text
    assert "document-context" in text
    assert "PDF 必须审阅提取出的正文" in text


def test_source_is_bounded_before_analysis():
    text = _text()
    assert "repository-map" in text
    assert "不整库拼进一个提示" in text
    assert "只把高信号核心文件作为 `--core` 输入" in text


def test_domain_enrichment_keeps_multiple_candidates():
    text = _text()
    assert "365 天" in text
    assert "conservative" in text and "enhanced" in text
    assert "不要把冲突模块拼成一个“猜测版本”" in text


def test_analysis_keeps_realization_boundaries():
    text = _text()
    assert "project-analysis.json" in text
    assert "realization_status" in text
    assert "historical_fact: false" in text
    assert "不要因为成果来自团队而省略" in text


def test_duplicate_gate_precedes_archive_mutation():
    text = _text()
    assert "confirmation_required" in text
    assert "尚未修改任何档案" in text
    assert "--update-project-name" in text
