"""Project-material-only domain inference and enrichment validation for Ripper.

This module deliberately has no network or model dependency. It creates an
auditable retrieval request from submitted project files; an agent may then
perform web research and return a knowledge bundle that is validated here.
Job descriptions, resumes and target roles are outside this stage. PDF text
extraction uses pdfminer.six when the collector environment provides it and
degrades to filename-only evidence when it is unavailable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


MAX_FILE_CHARS = 24_000
MAX_TOTAL_CHARS = 240_000
TEXT_SUFFIXES = {
    ".md", ".markdown", ".txt", ".rst", ".py", ".js", ".jsx", ".ts", ".tsx",
    ".java", ".kt", ".go", ".rs", ".c", ".cc", ".cpp", ".h", ".hpp", ".cs",
    ".rb", ".php", ".scala", ".sql", ".graphql", ".proto", ".json", ".yaml",
    ".yml", ".toml", ".ini", ".conf", ".properties", ".xml", ".gradle", ".sh",
    ".pdf",
}
IGNORED_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "vendor", ".venv", "venv", "dist",
    "build", "target", ".cache", "__pycache__", "ripper-output",
}
GENERIC_TERMS = {
    "class", "public", "private", "return", "import", "from", "const", "function",
    "string", "object", "config", "main", "index", "utils", "common", "service",
    "test", "tests", "readme", "项目", "系统", "功能", "实现", "模块", "相关", "支持",
}

# Signals are intentionally broad candidates. The agent refines them from the
# cited project excerpts instead of treating this dictionary as ground truth.
DIRECTION_SIGNALS: dict[str, dict[str, Any]] = {
    "任务调度与工作流编排": {
        "terms": {"scheduler", "scheduling", "workflow", "orchestrator", "orchestration", "dag", "cron", "executor", "worker", "job", "task", "retry", "compensation", "heartbeat", "调度", "编排", "任务实例", "补偿", "重试", "执行器", "工作流"},
        "queries": ["任务调度 平台实践", "工作流编排 架构落地", "DAG 调度 失败恢复"],
    },
    "数据平台与批处理": {
        "terms": {"pipeline", "etl", "batch", "stream", "warehouse", "lakehouse", "spark", "flink", "airflow", "kafka", "数据平台", "数据管道", "批处理", "流处理", "数仓", "湖仓"},
        "queries": ["数据平台 架构实践", "批流一体 工程落地", "数据管道 稳定性治理"],
    },
    "稳定性与可观测性平台": {
        "terms": {"observability", "tracing", "metrics", "alert", "incident", "slo", "sla", "prometheus", "opentelemetry", "recovery", "failover", "可观测性", "稳定性", "告警", "链路追踪", "容灾", "故障恢复"},
        "queries": ["稳定性平台 技术实践", "可观测性 平台落地", "故障恢复 架构实践"],
    },
    "风控与规则决策": {
        "terms": {"risk", "fraud", "rule", "decision", "feature", "strategy", "风控", "反欺诈", "规则引擎", "决策引擎", "策略平台", "风险"},
        "queries": ["风控平台 架构实践", "规则决策引擎 技术落地", "策略平台 实时决策"],
    },
    "推荐与搜索": {
        "terms": {"recommend", "ranking", "recall", "retrieval", "search", "embedding", "indexer", "推荐", "召回", "排序", "检索", "搜索引擎", "向量索引"},
        "queries": ["推荐系统 工程实践", "搜索平台 架构落地", "召回排序 平台化"],
    },
    "AI Agent 与模型应用": {
        "terms": {"agent", "llm", "prompt", "rag", "embedding", "toolcall", "tool_call", "model", "智能体", "大模型", "检索增强", "提示词", "模型服务"},
        "queries": ["AI Agent 平台 工程实践", "RAG 系统 架构落地", "大模型应用 稳定性治理"],
    },
    "支付与账务": {
        "terms": {"payment", "ledger", "settlement", "transaction", "refund", "accounting", "支付", "账务", "清结算", "退款", "对账", "交易"},
        "queries": ["支付平台 架构实践", "账务系统 一致性", "清结算 平台落地"],
    },
    "研发效能与交付平台": {
        "terms": {"cicd", "ci/cd", "pipeline", "deployment", "release", "build", "devops", "研发效能", "发布平台", "构建平台", "持续交付", "流水线"},
        "queries": ["研发效能平台 技术实践", "发布平台 架构落地", "持续交付 平台治理"],
    },
}

MECHANISM_SIGNALS = {
    "状态机": {"state_machine", "statemachine", "transition", "状态机", "状态流转"},
    "幂等控制": {"idempotent", "idempotency", "deduplicate", "幂等", "去重"},
    "失败重试": {"retry", "backoff", "重试", "退避"},
    "补偿机制": {"compensation", "saga", "rollback", "补偿", "回滚"},
    "节点心跳与租约": {"heartbeat", "lease", "心跳", "租约"},
    "分布式锁与并发控制": {"distributed_lock", "mutex", "cas", "compareandswap", "分布式锁", "并发控制"},
    "事件驱动": {"event", "eventbus", "message", "queue", "事件驱动", "消息队列"},
    "缓存": {"cache", "redis", "缓存"},
    "多租户隔离": {"tenant", "namespace", "quota", "多租户", "配额", "资源隔离"},
    "灰度与版本隔离": {"version", "canary", "gray", "版本隔离", "灰度"},
}

QUALITY_SIGNALS = {
    "可靠性": {"retry", "recovery", "failover", "compensation", "可靠性", "恢复", "容灾"},
    "可扩展性": {"shard", "partition", "scale", "cluster", "扩展性", "分片", "集群"},
    "一致性": {"transaction", "consistency", "lock", "version", "一致性", "事务", "锁"},
    "可观测性": {"metrics", "trace", "log", "alert", "监控", "链路", "告警", "可观测"},
    "安全与审计": {"auth", "permission", "audit", "security", "鉴权", "权限", "审计", "安全"},
}


def _files(paths: Iterable[str | Path]) -> list[Path]:
    result: list[Path] = []
    for raw in paths:
        path = Path(raw).expanduser().resolve()
        if not path.exists():
            continue
        candidates = [path] if path.is_file() else sorted(item for item in path.rglob("*") if item.is_file())
        for item in candidates:
            if any(part in IGNORED_DIRS for part in item.parts):
                continue
            if item.suffix.lower() in TEXT_SUFFIXES or item.name.lower() in {"dockerfile", "makefile"}:
                result.append(item)
    return sorted(set(result))


def _read(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        try:
            from pdfminer.high_level import extract_text
        except ImportError:
            return ""
        try:
            return (extract_text(str(path)) or "")[:MAX_FILE_CHARS]
        except Exception:
            return ""
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:MAX_FILE_CHARS]
    except OSError:
        return ""


def _tokens(text: str) -> list[str]:
    result = re.findall(r"[A-Za-z][A-Za-z0-9_.\-/]{2,}|[\u4e00-\u9fff]{2,12}", text.casefold())
    return [item.strip("._-/") for item in result if item.strip("._-/") not in GENERIC_TERMS]


def _fingerprint(files: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in files:
        digest.update(str(path).encode("utf-8"))
        try:
            digest.update(str(path.stat().st_size).encode("ascii"))
            with path.open("rb") as handle:
                digest.update(handle.read(4096))
        except OSError:
            continue
    return digest.hexdigest()


def infer_domain_profile(project_name: str, paths: Iterable[str | Path], *, today: date | None = None) -> dict[str, Any]:
    """Infer a retrieval-ready project profile using project materials only."""
    files = _files(paths)
    remaining = MAX_TOTAL_CHARS
    corpus_parts: list[str] = [project_name]
    token_sources: dict[str, set[str]] = {}
    source_texts: dict[str, str] = {}
    source_inventory: list[dict[str, Any]] = []
    for path in files:
        if remaining <= 0:
            break
        content = _read(path)[:remaining]
        remaining -= len(content)
        sample = f"{path.as_posix()}\n{content}"
        corpus_parts.append(sample)
        source_texts[str(path)] = sample.casefold()
        source_inventory.append({
            "path": str(path),
            "format": path.suffix.lower().lstrip(".") or path.name.lower(),
            "extracted_chars": len(content),
            "text_extracted": bool(content.strip()),
        })
        for token in set(_tokens(sample)):
            token_sources.setdefault(token, set()).add(str(path))
    corpus = "\n".join(corpus_parts).casefold()
    corpus_tokens = Counter(_tokens(corpus))

    def term_count(term: str) -> int:
        normalized = term.casefold()
        # Chinese prose is commonly written without whitespace, so token
        # equality alone misses phrases such as `任务调度问题`.
        if re.search(r"[\u4e00-\u9fff]", normalized):
            return corpus.count(normalized)
        return corpus_tokens[normalized]

    def term_refs(term: str) -> set[str]:
        normalized = term.casefold()
        if re.search(r"[\u4e00-\u9fff]", normalized):
            return {path for path, text in source_texts.items() if normalized in text}
        return token_sources.get(normalized, set())

    directions: list[dict[str, Any]] = []
    for name, definition in DIRECTION_SIGNALS.items():
        hits = [(term, term_count(term)) for term in definition["terms"] if term_count(term)]
        score = sum(min(count, 5) for _, count in hits)
        if score:
            refs = sorted({ref for term, _ in hits for ref in term_refs(term)})[:12]
            directions.append({"name": name, "score": score, "matched_terms": sorted(term for term, _ in hits), "source_refs": refs})
    directions.sort(key=lambda item: (-item["score"], item["name"]))

    def matched_groups(groups: dict[str, set[str]]) -> list[dict[str, Any]]:
        found = []
        for name, terms in groups.items():
            hits = sorted(term for term in terms if term_count(term))
            if hits:
                refs = sorted({ref for term in hits for ref in term_refs(term)})[:8]
                found.append({"name": name, "matched_terms": hits, "source_refs": refs})
        return found

    mechanisms = matched_groups(MECHANISM_SIGNALS)
    qualities = matched_groups(QUALITY_SIGNALS)
    locked_terms = [
        term for term, count in corpus_tokens.most_common(80)
        if count >= 2 and (term in token_sources) and term not in GENERIC_TERMS
    ][:30]

    current = today or datetime.now(timezone.utc).date()
    start = current - timedelta(days=365)
    direction_names = [item["name"] for item in directions[:3]] or ["待语义分析的工程系统"]
    mechanism_names = [item["name"] for item in mechanisms[:5]]
    queries: list[str] = []
    for direction in direction_names:
        queries.extend([
            f"{current.year} 国内互联网 {direction} 技术实践",
            f"{start.year}..{current.year} {direction} 架构 落地 复盘",
            f"{direction} 国内 大厂 中型公司 创业公司 工程实践",
        ])
    for mechanism in mechanism_names[:4]:
        queries.append(f"{current.year} 国内互联网 {direction_names[0]} {mechanism} 实践")
    for direction in directions[:2]:
        for fragment in DIRECTION_SIGNALS[direction["name"]]["queries"]:
            queries.append(f"{current.year} 国内互联网 {fragment}")

    profile = {
        "schema_version": 1,
        "basis": "project-material-only",
        "project_name": project_name,
        "project_fingerprint": _fingerprint(files),
        "analyzed_file_count": len(files),
        "analysis_truncated": remaining <= 0,
        "source_inventory": source_inventory,
        "direction_candidates": directions[:5],
        "mechanisms": mechanisms,
        "quality_attributes": qualities,
        "locked_terms": locked_terms,
        "retrieval_request": {
            "purpose": "project-domain-enrichment",
            "forbidden_context": ["resume", "job-description", "target-role", "career-direction"],
            "geography": "CN",
            "organization_sizes": ["large", "medium", "small"],
            "published_from": start.isoformat(),
            "published_to": current.isoformat(),
            "preferred_sources": ["company-official", "official-conference", "official-open-source", "paper", "attributed-technical-media"],
            "queries": list(dict.fromkeys(queries)),
        },
    }
    # Bind researched knowledge to the project material and inferred structure,
    # not to the wall-clock retrieval window. A bundle generated near midnight
    # must remain depositable the next day when the submitted files are unchanged.
    stable_identity = {key: value for key, value in profile.items() if key != "retrieval_request"}
    profile["profile_id"] = "domain_" + hashlib.sha256(
        json.dumps(stable_identity, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    return profile


def validate_knowledge_bundle(bundle: dict[str, Any], profile: dict[str, Any], *, today: date | None = None) -> dict[str, Any]:
    """Validate researched module cards and multi-candidate architectures."""
    errors: list[str] = []
    warnings: list[str] = []
    current = today or datetime.now(timezone.utc).date()
    earliest = current - timedelta(days=365)
    if profile.get("basis") != "project-material-only":
        errors.append("domain profile must use basis=project-material-only")
    if not isinstance(bundle, dict):
        return {"valid": False, "errors": ["knowledge bundle must be a JSON object"], "warnings": [], "stats": {}}
    if bundle.get("profile_id") != profile.get("profile_id"):
        errors.append("knowledge bundle profile_id does not match the project domain profile")
    forbidden = {"resume", "job_description", "job-description", "target_role", "target-role", "jd", "career_direction"}

    def nested_keys(value: Any) -> set[str]:
        if isinstance(value, dict):
            return {str(key).casefold() for key in value} | {item for child in value.values() for item in nested_keys(child)}
        if isinstance(value, list):
            return {item for child in value for item in nested_keys(child)}
        return set()

    if forbidden & nested_keys(bundle):
        errors.append("knowledge enrichment must not contain resume, JD, target-role or career-direction inputs")

    project_directions = bundle.get("project_direction_candidates", [])
    if not isinstance(project_directions, list) or not project_directions:
        errors.append("knowledge bundle requires project_direction_candidates inferred from project materials")
        project_directions = []
    known_project_sources = {str(item.get("path")) for item in profile.get("source_inventory", []) if isinstance(item, dict)}
    for index, direction in enumerate(project_directions):
        if not isinstance(direction, dict):
            errors.append(f"project_direction_candidate[{index}] must be an object")
            continue
        name = str(direction.get("name") or "")
        if not name or direction.get("confidence") not in {"low", "medium", "high"}:
            errors.append(f"project_direction_candidate[{index}] requires name and confidence=low|medium|high")
        refs = set(direction.get("project_source_refs", []))
        if not refs or not refs <= known_project_sources:
            errors.append(f"project direction {name or index} must cite known project source paths")
        if not direction.get("rationale") or not direction.get("search_keywords"):
            errors.append(f"project direction {name or index} requires rationale and search_keywords")

    sources = bundle.get("sources", [])
    if not isinstance(sources, list) or not sources:
        errors.append("knowledge bundle requires at least one recent external source")
        sources = []
    source_ids: set[str] = set()
    for index, source in enumerate(sources):
        sid = str(source.get("id") or "") if isinstance(source, dict) else ""
        if not sid or sid in source_ids:
            errors.append(f"source[{index}] requires a unique id")
            continue
        source_ids.add(sid)
        published = source.get("published_at")
        try:
            published_date = date.fromisoformat(str(published)[:10])
            if published_date < earliest or published_date > current:
                errors.append(f"source {sid} is outside the required one-year window")
        except (TypeError, ValueError):
            errors.append(f"source {sid} requires a verifiable published_at date")
        if source.get("geography") != "CN":
            warnings.append(f"source {sid} is not marked as a domestic CN practice")
        if not source.get("url") or not source.get("title"):
            errors.append(f"source {sid} requires title and URL")
        if source.get("organization_size") not in {"large", "medium", "small"}:
            errors.append(f"source {sid} requires organization_size=large|medium|small")

    cards = bundle.get("module_cards", [])
    if not isinstance(cards, list) or not cards:
        errors.append("knowledge bundle requires at least one compatible module card")
        cards = []
    card_ids: set[str] = set()
    conflicts: dict[str, set[str]] = {}
    for index, card in enumerate(cards):
        cid = str(card.get("id") or "") if isinstance(card, dict) else ""
        if not cid or cid in card_ids:
            errors.append(f"module_card[{index}] requires a unique id")
            continue
        card_ids.add(cid)
        basis = set(card.get("basis_source_ids", []))
        if not basis or not basis <= source_ids:
            errors.append(f"module card {cid} must cite known external sources")
        if card.get("historical_fact") is not False:
            errors.append(f"module card {cid} must set historical_fact=false")
        if not card.get("project_fit") or not card.get("compatibility_requirements"):
            errors.append(f"module card {cid} requires project_fit and compatibility_requirements")
        conflicts[cid] = set(card.get("conflicts_with", []))

    candidates = bundle.get("architecture_candidates", [])
    if not isinstance(candidates, list):
        errors.append("architecture_candidates must be a list")
        candidates = []
    if len(candidates) < 2:
        errors.append("at least two architecture candidates are required; do not collapse to one guess")
    variants: set[str] = set()
    locked_terms = set(profile.get("locked_terms", []))
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            errors.append(f"architecture_candidate[{index}] must be an object")
            continue
        variant = str(candidate.get("variant") or "")
        if not variant or variant in variants:
            errors.append(f"architecture_candidate[{index}] requires a unique variant")
        variants.add(variant)
        selected = set(candidate.get("module_card_ids", []))
        if not selected:
            errors.append(f"candidate {variant or index} must select at least one module card")
        if not selected <= card_ids:
            errors.append(f"candidate {variant or index} references unknown module cards")
        for cid in selected:
            if conflicts.get(cid, set()) & selected:
                errors.append(f"candidate {variant or index} selects conflicting module cards")
        preserved = set(candidate.get("preserved_terms", []))
        if locked_terms and not (preserved & locked_terms):
            warnings.append(f"candidate {variant or index} preserves none of the project locked terms")
        if candidate.get("historical_fact") is not False:
            errors.append(f"candidate {variant or index} must set historical_fact=false")
        if not candidate.get("coherence_rationale"):
            errors.append(f"candidate {variant or index} requires a coherence_rationale")

    sizes = {str(source.get("organization_size")) for source in sources if isinstance(source, dict)}
    missing_sizes = {"large", "medium", "small"} - sizes
    if missing_sizes:
        warnings.append("source coverage misses organization sizes: " + ", ".join(sorted(missing_sizes)))
    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "stats": {
            "project_direction_candidates": len(project_directions),
            "sources": len(sources),
            "module_cards": len(cards),
            "architecture_candidates": len(candidates),
        },
    }


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Ripper project-material domain enrichment helper")
    sub = parser.add_subparsers(dest="command", required=True)
    profile = sub.add_parser("profile")
    profile.add_argument("project_name")
    profile.add_argument("paths", nargs="+")
    validate = sub.add_parser("validate")
    validate.add_argument("profile")
    validate.add_argument("bundle")
    args = parser.parse_args()
    if args.command == "profile":
        print(json.dumps(infer_domain_profile(args.project_name, args.paths), ensure_ascii=False, indent=2))
        return 0
    profile_payload = json.loads(Path(args.profile).read_text(encoding="utf-8"))
    bundle_payload = json.loads(Path(args.bundle).read_text(encoding="utf-8"))
    result = validate_knowledge_bundle(bundle_payload, profile_payload)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 2


if __name__ == "__main__":
    raise SystemExit(_cli())
