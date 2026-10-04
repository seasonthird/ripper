"""Generate auditable material views from Ripper's deposited assets."""

from __future__ import annotations

import argparse
import importlib.util
import json
import hashlib
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STORE_SPEC = importlib.util.spec_from_file_location("ripper_asset_store", ROOT / "ripper-core" / "asset_store.py")
assert STORE_SPEC and STORE_SPEC.loader
STORE_MODULE = importlib.util.module_from_spec(STORE_SPEC)
STORE_SPEC.loader.exec_module(STORE_MODULE)
AssetStore = STORE_MODULE.AssetStore
TRANSACTION_SPEC = importlib.util.spec_from_file_location("ripper_archive_transaction", ROOT / "ripper-core" / "archive_transaction.py")
assert TRANSACTION_SPEC and TRANSACTION_SPEC.loader
TRANSACTION = importlib.util.module_from_spec(TRANSACTION_SPEC)
TRANSACTION_SPEC.loader.exec_module(TRANSACTION)


EXPORT_DIRECTORIES = {
    "star": "interview-stars",
    "resume": "resumes",
    "promotion": "promotions",
    "yearly-review": "yearly-reviews",
    "handover": "handovers",
    "blog": "blogs",
}

REALIZATION_LABELS = {
    "implemented": "已实现",
    "partial": "部分实现",
    "designed": "已完成方案设计",
    "derived": "由现有成果推导的优化方案",
    "hypothetical": "理论可行、待验证",
    "unknown": "状态待补充",
}

REALIZATION_VERBS = {
    "implemented": "实现并落地",
    "partial": "完成核心部分，并推进了",
    "designed": "设计并形成了",
    "derived": "基于现有成果推导并形成了",
    "hypothetical": "提出了理论上可行的",
    "unknown": "围绕该成果形成了",
}


def output_root() -> Path:
    configured = os.environ.get("RIPPER_OUTPUT_DIR")
    return Path(configured).expanduser().resolve() if configured else ROOT / "ripper-output"


def slug(value: str) -> str:
    result = re.sub(r"[^\w\-]+", "-", str(value).casefold(), flags=re.UNICODE).strip("-_ ")
    return result or "export"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def atomic_text(path: Path, text: str) -> None:
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _redact_text(value: str) -> str:
    """Remove common credential/PII shapes before material leaves the index."""
    text = str(value)
    text = re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", "[已脱敏邮箱]", text)
    text = re.sub(r"\b(?:Bearer\s+)?(?:sk|ghp|xoxb|xoxp)-[A-Za-z0-9_-]{8,}\b", "[已脱敏令牌]", text, flags=re.IGNORECASE)
    text = re.sub(r"(?i)(password|passwd|secret|token)\s*[:=]\s*\S+", r"\1=[已脱敏]", text)
    return text


def _evidence_ids(store: Any, claim_id: str) -> list[str]:
    with store.connect() as conn:
        return [row[0] for row in conn.execute("SELECT evidence_id FROM claim_evidence WHERE claim_id=?", (claim_id,))]


def _open_questions(store: Any, claim_id: str) -> list[str]:
    with store.connect() as conn:
        return [row[0] for row in conn.execute("SELECT question FROM confirmations WHERE claim_id=? AND status='open'", (claim_id,))]


def _archive_refs(claims: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Resolve selected repository slugs to the fixed user archive."""
    root = Path.home() / "Ripper" / "archives"
    refs: dict[str, dict[str, Any]] = {}
    if not root.is_dir():
        return refs
    manifests = []
    for path in root.glob("*/archive-manifest.json"):
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
            item["archive_path"] = str(path.parent)
            manifests.append(item)
        except (OSError, json.JSONDecodeError):
            continue
    for claim in claims:
        claim_slug = claim.get("repository_slug")
        claim_project_id = claim.get("project_id")
        match = next((item for item in manifests if claim_project_id and item.get("project_id") == claim_project_id), None)
        if match is None:
            match = next((item for item in manifests if claim_slug and item.get("slug") == claim_slug), None)
        if match is not None:
            refs[str(claim.get("project_id") or claim_slug)] = {
                "project_id": match.get("project_id"),
                "project_name": match.get("project_name"),
                "archive_path": match.get("archive_path"),
            }
    return refs


def asset_store_with_archive_recovery() -> Any:
    """Open the local index and sync it from the fixed cross-host archive."""
    with TRANSACTION.archive_lock(Path.home() / "Ripper" / "archives"):
        recovered = TRANSACTION.recover(Path.home() / "Ripper" / "archives")
        store = _asset_store_with_archive_recovery()
        if recovered:
            store.rebuild_from_archives(Path.home() / "Ripper" / "archives")
            store.recovery_status = "recovered"
        return store


def _asset_store_with_archive_recovery() -> Any:
    store = AssetStore()
    store.recovery_status = "current"
    archive_root = Path.home() / "Ripper" / "archives"
    has_manifests = archive_root.is_dir() and any(archive_root.glob("*/archive-manifest.json"))
    managed_by_archives = has_manifests or store.has_archive_index_state()
    if managed_by_archives and not store.archive_index_is_current(archive_root):
        # The archive tree is authoritative. Rebuild instead of incrementally
        # syncing so a removed project, source or claim cannot survive as an
        # orphan in a host-local SQLite index.
        store.rebuild_from_archives(archive_root)
        store.recovery_status = "rebuilt"
    return store


def browse(capabilities: list[str] | None = None) -> dict[str, Any]:
    with TRANSACTION.archive_lock(Path.home() / "Ripper" / "archives"):
        TRANSACTION.recover(Path.home() / "Ripper" / "archives")
        return _browse(capabilities)


def _browse(capabilities: list[str] | None = None) -> dict[str, Any]:
    store = _asset_store_with_archive_recovery()
    # Every claim from a user-submitted source is selectable.
    # The product treats submitted material as the user's career source; only
    # evidence, implementation state, production state, and disclosure remain
    # relevant boundaries.
    claims = store.query_claims(capabilities or [], include_unconfirmed=True)
    with store.connect() as conn:
        redaction = [dict(row) for row in conn.execute(
            "SELECT id, title, disclosure_level FROM claims WHERE disclosure_level IN ('restricted', 'internal-safe-after-redaction')"
        )]
    return {"usable_claims": claims, "excluded_claims": [], "redaction_notes": redaction,
            "index_status": store.recovery_status}


def _select_claims(claims: list[dict[str, Any]], target: str, capabilities: list[str], per_project: int = 5) -> list[dict[str, Any]]:
    """Rank claims for a role/scenario while keeping project coverage bounded."""
    wanted = set(re.findall(r"[\w\u4e00-\u9fff]+", (target or "").casefold()))
    cap_wanted = {str(item).casefold() for item in capabilities}
    scored: list[tuple[float, dict[str, Any]]] = []
    seen_statements: set[str] = set()
    for claim in claims:
        statement_key = re.sub(r"\s+", " ", claim.get("statement", "").casefold()).strip()
        if statement_key in seen_statements:
            continue
        seen_statements.add(statement_key)
        text = " ".join(str(claim.get(key, "")) for key in ("title", "statement", "repository_slug")).casefold()
        overlap = len(wanted & set(re.findall(r"[\w\u4e00-\u9fff]+", text)))
        score = overlap * 4.0
        if claim.get("status") in {"confirmed", "code-verifiable"}:
            score += 2
        if claim.get("production_status") == "confirmed":
            score += 1.5
        score += {"implemented": 2.0, "partial": 1.5, "designed": 1.0, "derived": 0.8, "hypothetical": 0.5}.get(claim.get("realization_status"), 0)
        # Evidence coverage is a ranking signal, never an eligibility gate.
        score += min(len(claim.get("source_refs", [])), 3) * 0.6
        score += min(len(claim.get("related_tests", [])), 2) * 0.8
        score += min(len(claim.get("related_config", [])), 2) * 0.4
        score += min(len(claim.get("derived_optimizations", [])), 2) * 0.3
        if cap_wanted:
            score += 1 if any(cap in text for cap in cap_wanted) else 0
        scored.append((score, claim))
    scored.sort(key=lambda pair: (-pair[0], pair[1].get("title", "")))
    counts: dict[str, int] = {}
    selected: list[dict[str, Any]] = []
    for score, claim in scored:
        project = str(claim.get("project_id") or claim.get("repository_slug") or "unassigned")
        if counts.get(project, 0) >= per_project:
            continue
        selected.append({**claim, "selection_score": round(score, 2), "selection_reason": "岗位/场景关键词、证据状态、实现状态与生产状态综合排序"})
        counts[project] = counts.get(project, 0) + 1
    return selected


def render(export_type: str, target: str, capabilities: list[str] | None = None, perspective: str = "individual") -> tuple[Path, Path, dict[str, Any]]:
    # Keep claims, evidence, archive references and export links in one
    # serialized snapshot. Helpers below must not reacquire this lock.
    with TRANSACTION.archive_lock(Path.home() / "Ripper" / "archives"):
        TRANSACTION.recover(Path.home() / "Ripper" / "archives")
        return _render(export_type, target, capabilities, perspective)


def _render(export_type: str, target: str, capabilities: list[str] | None = None, perspective: str = "individual") -> tuple[Path, Path, dict[str, Any]]:
    if export_type not in EXPORT_DIRECTORIES:
        raise ValueError(f"unsupported export type: {export_type}")
    if perspective not in {"individual", "team"}:
        raise ValueError(f"unsupported perspective: {perspective}")
    store = _asset_store_with_archive_recovery()
    all_claims = store.query_claims(capabilities or [], include_unconfirmed=True)
    # A capability hint is a ranking/filter preference, not a hard gate that
    # can make a freshly deposited project impossible to export. If no exact
    # capability exists, fall back to the complete submitted asset inventory.
    if not all_claims and capabilities:
        all_claims = store.query_claims([], include_unconfirmed=True)
    claims = _select_claims(all_claims, target, capabilities or [])
    if not claims:
        raise ValueError("没有可用资产；请先完成资产沉淀。")

    export_root = output_root() / "exports" / EXPORT_DIRECTORIES[export_type]
    export_root.mkdir(parents=True, exist_ok=True)
    # Include microseconds so two exports in the same second are independent
    # and their audit manifests cannot overwrite each other.
    base = f"{slug(target)}-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    output_path = export_root / f"{base}.md"
    manifest_path = export_root / f"{base}.manifest.json"
    evidence_ids: list[str] = []
    subject = "团队" if perspective == "team" else "我"
    lines = [f"# {target} — {export_type}", "", f"本材料选择与目标相关的用户提交成果；当前叙述视角为‘{subject}’，具体事实边界以证据、实现状态、生产状态和脱敏要求为准。", ""]
    for claim in claims:
        claim_id = claim["id"]
        statement = _redact_text(claim.get("statement", ""))
        evidence = _evidence_ids(store, claim_id)
        evidence_ids.extend(evidence)
        questions = _open_questions(store, claim_id)
        if claim.get("evidence_freshness") == "stale":
            questions.append("来源内容已改变或缺失，证据须重新核验。")
        realization = claim.get("realization_status", "unknown")
        realization_label = REALIZATION_LABELS.get(realization, REALIZATION_LABELS["unknown"])
        realization_verb = REALIZATION_VERBS.get(realization, REALIZATION_VERBS["unknown"])
        derived = claim.get("derived_optimizations", []) or []
        reconstruction = claim.get("reconstruction", {}) or {}
        if export_type == "star":
            lines.extend([
                f"## {claim['title']}",
                f"- Situation：{statement}",
                f"- Task：{subject}围绕该成果承担并完成相关工作（{realization_verb}）；具体边界以证据和实现状态为准。",
                "- Action：根据关联证据展开具体机制、权衡和实现路径。",
                f"- Result：{realization_label}；工程事实状态为 `{claim['status']}`，生产状态为 `{claim['production_status']}`。",
                f"- Evidence：`{claim_id}`；{', '.join(f'`{item}`' for item in evidence) or '需补充来源'}",
            ])
        elif export_type == "resume":
            lines.append(f"- {subject}{realization_verb}{claim['title']}：{statement}（状态：{realization_label}；证据：`{claim_id}`）。")
        else:
            lines.extend([
                f"## {claim['title']}",
                f"**实现状态：{realization_label}**\n\n{statement}",
                f"- 资产：`{claim_id}`",
                f"- 证据：{', '.join(evidence) or '需补充'}",
            ])
        if derived:
            lines.append("- 可扩展/优化方向：" + "；".join(_redact_text(str(item)) for item in derived))
        if reconstruction:
            note = reconstruction.get("note") or reconstruction.get("summary") or reconstruction.get("basis")
            if note:
                lines.append(f"- 重建/推演提示：{_redact_text(str(note))}")
        if questions:
            lines.append("- 待确认：" + "；".join(questions))
        lines.append("")
    selected_ids = {claim["id"] for claim in claims}
    excluded = [
        {"claim_id": claim["id"], "reason": "本次岗位/场景排序未选入，仍保留在资产库"}
        for claim in all_claims
        if claim["id"] not in selected_ids
    ]
    manifest = {
        "export_type": export_type,
        "target": target,
        "created_at": utc_now(),
        "claim_ids": [claim["id"] for claim in claims],
        "claim_revisions": {claim["id"]: claim["revision"] for claim in claims},
        "evidence_freshness": {claim["id"]: claim.get("evidence_freshness", "unknown") for claim in claims},
        "index_status": store.recovery_status,
        "selection": [{"claim_id": claim["id"], "score": claim.get("selection_score"), "reason": claim.get("selection_reason")} for claim in claims],
        "evidence_ids": sorted(set(evidence_ids)),
        "excluded": excluded,
        "redaction_notes": [{"id": c["id"], "title": c["title"], "disclosure_level": c["disclosure_level"]} for c in all_claims if c["disclosure_level"] in {"restricted", "internal-safe-after-redaction"}],
        "archive_fingerprint": STORE_MODULE.archive_fingerprint(Path.home() / "Ripper" / "archives"),
        "claim_snapshot": claims,
        "project_archives": _archive_refs(claims),
        "asset_database": str(store.db_path),
    }
    rendered_text = "\n".join(lines).rstrip() + "\n"
    manifest["output_sha256"] = hashlib.sha256(rendered_text.encode("utf-8")).hexdigest()
    manifest["output_file"] = output_path.name
    export_id = STORE_MODULE.stable_id("export", export_type, target, str(output_path))
    with store.connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO exports(id, export_type, target, output_path, manifest_path, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (export_id, export_type, target, str(output_path), str(manifest_path), manifest["created_at"]),
        )
        conn.execute("DELETE FROM export_claims WHERE export_id=?", (export_id,))
        for claim in claims:
            conn.execute(
                "INSERT OR REPLACE INTO export_claims(export_id, claim_id, inclusion_reason) VALUES (?, ?, ?)",
                (export_id, claim["id"], claim.get("selection_reason")),
            )
    manifest["export_id"] = export_id
    atomic_text(output_path, rendered_text)
    # Publish the complete manifest last. Its hash detects a partial or
    # subsequently modified material without requiring the mutable index.
    atomic_text(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return output_path, manifest_path, manifest


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Export Ripper asset views")
    parser.add_argument("command", choices=("browse", *EXPORT_DIRECTORIES))
    parser.add_argument("target", nargs="?", default="Ripper asset view")
    parser.add_argument("--capability", action="append", default=[])
    parser.add_argument("--perspective", choices=("individual", "team"), default="individual")
    args = parser.parse_args()
    if args.command == "browse":
        print(json.dumps(browse(args.capability), ensure_ascii=False, indent=2))
        return 0
    output_path, manifest_path, _ = render(args.command, args.target, args.capability, args.perspective)
    print(json.dumps({"output": str(output_path), "manifest": str(manifest_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
