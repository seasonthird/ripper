from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "ripper_domain_enrichment_test",
    ROOT / "ripper-core" / "domain_enrichment.py",
)
assert SPEC and SPEC.loader
DOMAIN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DOMAIN)


def valid_bundle(profile: dict, *, published_at: str = "2026-09-17") -> dict:
    sources = [
        {
            "id": "src_large",
            "title": "大型互联网公司调度实践",
            "url": "https://example.com/large",
            "published_at": published_at,
            "geography": "CN",
            "organization_size": "large",
        },
        {
            "id": "src_medium",
            "title": "中型互联网公司调度实践",
            "url": "https://example.com/medium",
            "published_at": published_at,
            "geography": "CN",
            "organization_size": "medium",
        },
        {
            "id": "src_small",
            "title": "创业公司调度实践",
            "url": "https://example.com/small",
            "published_at": published_at,
            "geography": "CN",
            "organization_size": "small",
        },
    ]
    cards = [
        {
            "id": "lease_recovery",
            "name": "租约与失联恢复",
            "basis_source_ids": ["src_large", "src_medium"],
            "historical_fact": False,
            "project_fit": "延伸现有心跳和重试机制",
            "compatibility_requirements": ["任务状态持久化"],
            "conflicts_with": [],
        },
        {
            "id": "adaptive_retry",
            "name": "自适应重试",
            "basis_source_ids": ["src_small"],
            "historical_fact": False,
            "project_fit": "在原有重试上补充分类退避",
            "compatibility_requirements": ["错误分类"],
            "conflicts_with": [],
        },
    ]
    preserved = profile.get("locked_terms", [])[:3]
    return {
        "profile_id": profile["profile_id"],
        "project_direction_candidates": [{
            "name": "任务调度与工作流编排",
            "confidence": "high",
            "project_source_refs": [profile["source_inventory"][0]["path"]],
            "rationale": "项目材料直接出现 DAG、心跳、租约和重试机制。",
            "search_keywords": ["任务调度", "DAG", "心跳租约"],
        }],
        "sources": sources,
        "module_cards": cards,
        "architecture_candidates": [
            {
                "variant": "conservative",
                "module_card_ids": ["lease_recovery"],
                "preserved_terms": preserved,
                "historical_fact": False,
                "coherence_rationale": "仅沿现有任务状态和心跳路径增强失联恢复。",
            },
            {
                "variant": "enhanced",
                "module_card_ids": ["lease_recovery", "adaptive_retry"],
                "preserved_terms": preserved,
                "historical_fact": False,
                "coherence_rationale": "租约恢复与错误分类共用既有调度状态，不引入第二套控制面。",
            },
        ],
    }


class DomainProfileTests(unittest.TestCase):
    def test_profile_is_derived_from_project_materials_only(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "design.md"
            source.write_text("任务调度系统通过 DAG 编排任务，支持心跳、租约、重试和补偿。", encoding="utf-8")
            profile = DOMAIN.infer_domain_profile("ORK", [source], today=date(2026, 9, 17))

        self.assertEqual(profile["basis"], "project-material-only")
        self.assertEqual(profile["direction_candidates"][0]["name"], "任务调度与工作流编排")
        self.assertEqual(profile["retrieval_request"]["published_from"], "2025-09-17")
        self.assertEqual(profile["retrieval_request"]["published_to"], "2026-09-17")
        self.assertEqual(profile["retrieval_request"]["organization_sizes"], ["large", "medium", "small"])
        serialized = json.dumps(profile, ensure_ascii=False).casefold()
        self.assertNotIn("target_role", serialized)
        self.assertNotIn("job_description", serialized)

    def test_low_signal_profile_keeps_semantic_analysis_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "notes.md"
            source.write_text("这是一个待分析的内部专项。", encoding="utf-8")
            profile = DOMAIN.infer_domain_profile("ORK", [source], today=date(2026, 9, 17))

        self.assertEqual(profile["direction_candidates"], [])
        self.assertTrue(any("待语义分析" in query for query in profile["retrieval_request"]["queries"]))

    def test_profile_identity_is_stable_when_only_retrieval_day_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "design.md"
            source.write_text("任务调度 DAG 心跳重试", encoding="utf-8")
            first = DOMAIN.infer_domain_profile("ORK", [source], today=date(2026, 9, 17))
            second = DOMAIN.infer_domain_profile("ORK", [source], today=date(2026, 9, 18))

        self.assertEqual(first["profile_id"], second["profile_id"])
        self.assertNotEqual(first["retrieval_request"]["published_to"], second["retrieval_request"]["published_to"])

    def test_pdf_text_participates_when_pdfminer_is_available(self):
        try:
            from reportlab.pdfgen import canvas
        except ImportError:
            self.skipTest("reportlab is not installed")
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "design.pdf"
            pdf = canvas.Canvas(str(source))
            pdf.drawString(72, 720, "workflow scheduler DAG heartbeat retry compensation")
            pdf.save()
            profile = DOMAIN.infer_domain_profile("ORK", [source], today=date(2026, 9, 17))

        self.assertEqual(profile["analyzed_file_count"], 1)
        self.assertTrue(profile["source_inventory"][0]["text_extracted"])
        self.assertEqual(profile["direction_candidates"][0]["name"], "任务调度与工作流编排")

    def test_project_domain_profile_cli_writes_standalone_json(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "design.md"
            output = root / "nested" / "domain-profile.json"
            source.write_text("任务调度系统通过 DAG、心跳和租约恢复任务。", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "ripper-collector" / "scripts" / "orchestration.py"),
                    "project-domain-profile",
                    "ORK",
                    "--source",
                    str(source),
                    "--output",
                    str(output),
                ],
                cwd=ROOT / "ripper-collector",
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            written = json.loads(output.read_text(encoding="utf-8"))
            emitted = json.loads(result.stdout)
            self.assertEqual(written, emitted)
            self.assertEqual(written["basis"], "project-material-only")
            self.assertNotIn("target_role", json.dumps(written, ensure_ascii=False).casefold())


class DomainKnowledgeValidationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        source = Path(self.directory.name) / "design.md"
        source.write_text("任务调度 DAG 心跳 租约 重试", encoding="utf-8")
        self.profile = DOMAIN.infer_domain_profile("ORK", [source], today=date(2026, 9, 17))

    def tearDown(self):
        self.directory.cleanup()

    def test_valid_bundle_preserves_multiple_candidates(self):
        result = DOMAIN.validate_knowledge_bundle(valid_bundle(self.profile), self.profile, today=date(2026, 9, 17))
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["stats"]["architecture_candidates"], 2)

    def test_rejects_single_candidate(self):
        bundle = valid_bundle(self.profile)
        bundle["architecture_candidates"] = bundle["architecture_candidates"][:1]
        result = DOMAIN.validate_knowledge_bundle(bundle, self.profile, today=date(2026, 9, 17))
        self.assertFalse(result["valid"])
        self.assertTrue(any("at least two" in error for error in result["errors"]))

    def test_rejects_stale_source_and_nested_job_context(self):
        bundle = valid_bundle(self.profile, published_at="2025-09-16")
        bundle["research_context"] = {"target_role": "backend"}
        result = DOMAIN.validate_knowledge_bundle(bundle, self.profile, today=date(2026, 9, 17))
        self.assertFalse(result["valid"])
        self.assertTrue(any("one-year" in error for error in result["errors"]))
        self.assertTrue(any("target-role" in error for error in result["errors"]))

    def test_rejects_conflicting_modules_in_one_candidate(self):
        bundle = valid_bundle(self.profile)
        bundle["module_cards"][0]["conflicts_with"] = ["adaptive_retry"]
        result = DOMAIN.validate_knowledge_bundle(bundle, self.profile, today=date(2026, 9, 17))
        self.assertFalse(result["valid"])
        self.assertTrue(any("conflicting module" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
