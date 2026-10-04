from __future__ import annotations

import importlib.util
import json
import os
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PIPELINE = load("ripper_pipeline_closed_loop", ROOT / "ripper-collector" / "scripts" / "project_pipeline.py")
EXPORT = load("ripper_export_closed_loop", ROOT / "ripper-exporter" / "export_assets.py")


def knowledge_bundle(profile: dict) -> dict:
    published_at = profile["retrieval_request"]["published_to"]
    project_ref = profile["source_inventory"][0]["path"]
    direction = profile["direction_candidates"][0]["name"]
    sources = [
        {"id": "large", "title": "大型互联网调度实践", "url": "https://example.com/large", "published_at": published_at, "geography": "CN", "organization_size": "large"},
        {"id": "medium", "title": "中型互联网调度实践", "url": "https://example.com/medium", "published_at": published_at, "geography": "CN", "organization_size": "medium"},
        {"id": "small", "title": "小型互联网调度实践", "url": "https://example.com/small", "published_at": published_at, "geography": "CN", "organization_size": "small"},
    ]
    cards = [
        {
            "id": "lease_recovery",
            "name": "租约失联恢复",
            "basis_source_ids": ["large", "medium"],
            "historical_fact": False,
            "project_fit": "沿用已有心跳状态",
            "compatibility_requirements": ["任务状态持久化"],
            "conflicts_with": [],
        },
        {
            "id": "adaptive_retry",
            "name": "自适应分类重试",
            "basis_source_ids": ["small"],
            "historical_fact": False,
            "project_fit": "扩展已有重试路径",
            "compatibility_requirements": ["错误分类"],
            "conflicts_with": [],
        },
    ]
    preserved = profile.get("locked_terms", [])[:3]
    return {
        "profile_id": profile["profile_id"],
        "project_direction_candidates": [{
            "name": direction,
            "confidence": "high",
            "project_source_refs": [project_ref],
            "rationale": "项目材料包含 DAG、心跳、租约和重试。",
            "search_keywords": ["任务调度", "DAG", "租约恢复"],
        }],
        "sources": sources,
        "module_cards": cards,
        "architecture_candidates": [
            {
                "variant": "conservative",
                "module_card_ids": ["lease_recovery"],
                "preserved_terms": preserved,
                "historical_fact": False,
                "coherence_rationale": "仅增强现有心跳和任务状态路径。",
            },
            {
                "variant": "enhanced",
                "module_card_ids": ["lease_recovery", "adaptive_retry"],
                "preserved_terms": preserved,
                "historical_fact": False,
                "coherence_rationale": "在同一调度状态中组合恢复与分类重试。",
            },
        ],
    }


def test_markdown_deposit_is_queryable_and_exportable():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        old_home, old_output = os.environ.get("HOME"), os.environ.get("RIPPER_OUTPUT_DIR")
        os.environ["HOME"] = str(root / "home")
        os.environ["RIPPER_OUTPUT_DIR"] = str(root / "output")
        PIPELINE.ARCHIVE.ARCHIVE_HOME = Path(os.environ["HOME"]) / "Ripper"
        try:
            document = root / "project.md"
            document.write_text("# 工程\n", encoding="utf-8")
            analysis = root / "analysis.md"
            analysis.write_text("# 稳定性\n\n实现持久化运行状态。\n", encoding="utf-8")
            result = PIPELINE.deposit_project("闭环工程", analysis, [document])
            assert result["indexed_claims"] == 1
            output, manifest, _ = EXPORT.render("resume", "后端工程师", ["稳定性"])
            assert output.is_file() and manifest.is_file()
            assert "持久化运行状态" in output.read_text(encoding="utf-8")
        finally:
            if old_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = old_home
            if old_output is None:
                os.environ.pop("RIPPER_OUTPUT_DIR", None)
            else:
                os.environ["RIPPER_OUTPUT_DIR"] = old_output


def test_structured_analysis_survives_index_rebuild():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        old_home, old_output = os.environ.get("HOME"), os.environ.get("RIPPER_OUTPUT_DIR")
        os.environ["HOME"] = str(root / "home")
        os.environ["RIPPER_OUTPUT_DIR"] = str(root / "output")
        PIPELINE.ARCHIVE.ARCHIVE_HOME = Path(os.environ["HOME"]) / "Ripper"
        try:
            document = root / "project.pdf"
            document.write_bytes(b"%PDF-1.4 placeholder")
            analysis = root / "analysis.json"
            analysis.write_text(json.dumps({"claims": [{
                "title": "故障恢复", "statement": "恢复失败任务", "status": "confirmed",
                "capabilities": ["reliability"], "metrics": [{"name": "恢复率", "value": "99%"}],
                "evidence": [{"claim_text": "state store", "kind": "code"}],
            }]}, ensure_ascii=False), encoding="utf-8")
            result = PIPELINE.deposit_project("恢复工程", analysis, [document])
            store = PIPELINE.ASSET.AssetStore()
            store.clear_index()
            assert store.rebuild_from_archives() == 1
            claims = store.query_claims(["reliability"])
            assert len(claims) == 1 and claims[0]["title"] == "故障恢复"
            with store.connect() as conn:
                assert conn.execute("SELECT COUNT(*) FROM metrics").fetchone()[0] == 1
                assert conn.execute("SELECT COUNT(*) FROM evidence").fetchone()[0] == 1
        finally:
            if old_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = old_home
            if old_output is None:
                os.environ.pop("RIPPER_OUTPUT_DIR", None)
            else:
                os.environ["RIPPER_OUTPUT_DIR"] = old_output


def test_enriched_project_update_survives_cross_host_rebuild_end_to_end():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        old_home, old_output = os.environ.get("HOME"), os.environ.get("RIPPER_OUTPUT_DIR")
        os.environ["HOME"] = str(root / "home")
        os.environ["RIPPER_OUTPUT_DIR"] = str(root / "host-one")
        PIPELINE.ARCHIVE.ARCHIVE_HOME = Path(os.environ["HOME"]) / "Ripper"
        try:
            document = root / "design.md"
            document.write_text("任务调度 DAG 心跳 租约 重试 补偿", encoding="utf-8")
            core = root / "core"
            core.mkdir()
            (core / "scheduler.py").write_text("def retry_task(): return 'v1'", encoding="utf-8")
            analysis = root / "project-analysis.json"
            analysis.write_text(json.dumps({"claims": [{
                "title": "旧版恢复链路",
                "statement": "通过固定重试恢复失败任务",
                "realization_status": "implemented",
                "capabilities": ["可靠性"],
            }]}, ensure_ascii=False), encoding="utf-8")
            profile = PIPELINE.build_input("调度闭环工程", [document], [core])["domain_profile"]
            knowledge = root / "market-practices.json"
            knowledge.write_text(json.dumps(knowledge_bundle(profile), ensure_ascii=False), encoding="utf-8")

            deposited = PIPELINE.deposit_project("调度闭环工程", analysis, [document], [core], knowledge=knowledge)
            assert deposited["indexed_claims"] == 3
            archive = Path(deposited["archive_path"])

            os.environ["RIPPER_OUTPUT_DIR"] = str(root / "host-two")
            first_export, _, first_manifest = EXPORT.render("resume", "调度平台后端工程师")
            first_text = first_export.read_text(encoding="utf-8")
            assert "固定重试恢复失败任务" in first_text
            assert "增强候选（conservative）" in first_text
            assert "增强候选（enhanced）" in first_text
            assert len(first_manifest["claim_ids"]) == 3

            document.write_text("任务调度 DAG 心跳 租约 分类重试 补偿 一致性", encoding="utf-8")
            (core / "scheduler.py").write_text("def retry_task(kind): return kind", encoding="utf-8")
            analysis.write_text(json.dumps({"claims": [{
                "title": "新版恢复链路",
                "statement": "通过错误分类和一致性状态恢复失败任务",
                "realization_status": "implemented",
                "capabilities": ["可靠性", "一致性"],
            }]}, ensure_ascii=False), encoding="utf-8")
            updated_profile = PIPELINE.build_input("调度闭环工程", [document], [core])["domain_profile"]
            knowledge.write_text(json.dumps(knowledge_bundle(updated_profile), ensure_ascii=False), encoding="utf-8")
            updated = PIPELINE.deposit_project(
                "调度闭环工程",
                analysis,
                [document],
                [core],
                update=True,
                knowledge=knowledge,
            )
            assert updated["indexed_claims"] == 3
            assert list((archive / "analysis" / "history").glob("sources-*/documents/design.md"))
            assert list((archive / "analysis" / "history").glob("sources-*/core-source/scheduler.py"))

            os.environ["RIPPER_OUTPUT_DIR"] = str(root / "host-three")
            second_export, _, second_manifest = EXPORT.render("resume", "调度平台后端工程师")
            second_text = second_export.read_text(encoding="utf-8")
            assert "错误分类和一致性状态恢复失败任务" in second_text
            assert "固定重试恢复失败任务" not in second_text
            assert "增强候选（conservative）" in second_text
            assert "增强候选（enhanced）" in second_text
            assert len(second_manifest["claim_ids"]) == 3
        finally:
            if old_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = old_home
            if old_output is None:
                os.environ.pop("RIPPER_OUTPUT_DIR", None)
            else:
                os.environ["RIPPER_OUTPUT_DIR"] = old_output
