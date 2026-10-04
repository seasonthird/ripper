"""Local, auditable asset storage for Ripper.

The filesystem archive is authoritative. SQLite is an automatically-created,
rebuildable query index; JSON and Markdown snapshots remain readable without a
database client.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
import re
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS repositories (
  id TEXT PRIMARY KEY,
  project_id TEXT,
  slug TEXT NOT NULL UNIQUE,
  source_path TEXT NOT NULL,
  source_kind TEXT NOT NULL CHECK(source_kind IN ('folder', 'git', 'document')),
  revision TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS scan_runs (
  id TEXT PRIMARY KEY,
  repository_id TEXT NOT NULL REFERENCES repositories(id),
  scope_path TEXT,
  source_hash TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('started', 'completed', 'failed')),
  scanned_at TEXT NOT NULL,
  report_path TEXT
);
CREATE TABLE IF NOT EXISTS modules (
  id TEXT PRIMARY KEY,
  repository_id TEXT NOT NULL REFERENCES repositories(id),
  path TEXT NOT NULL,
  title TEXT NOT NULL,
  role TEXT,
  UNIQUE(repository_id, path)
);
CREATE TABLE IF NOT EXISTS artifacts (
  id TEXT PRIMARY KEY,
  repository_id TEXT NOT NULL REFERENCES repositories(id),
  module_id TEXT REFERENCES modules(id),
  path TEXT NOT NULL,
  artifact_kind TEXT NOT NULL,
  content_hash TEXT,
  UNIQUE(repository_id, path)
);
CREATE TABLE IF NOT EXISTS evidence (
  id TEXT PRIMARY KEY,
  artifact_id TEXT NOT NULL REFERENCES artifacts(id),
  kind TEXT NOT NULL CHECK(kind IN ('code', 'doc', 'config', 'test', 'user', 'inferred')),
  symbol TEXT,
  line_start INTEGER,
  line_end INTEGER,
  claim_text TEXT NOT NULL,
  confidence TEXT NOT NULL CHECK(confidence IN ('confirmed', 'code-verifiable', 'inferred', 'planned', 'blocked', 'unknown')),
  source_content_hash TEXT,
  observed_at TEXT,
  freshness_status TEXT NOT NULL DEFAULT 'unknown'
);
CREATE TABLE IF NOT EXISTS claims (
  id TEXT PRIMARY KEY,
  repository_id TEXT NOT NULL REFERENCES repositories(id),
  title TEXT NOT NULL,
  statement TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('confirmed', 'code-verifiable', 'inferred', 'planned', 'blocked', 'unknown')),
  realization_status TEXT NOT NULL DEFAULT 'unknown',
  source_refs_json TEXT NOT NULL DEFAULT '[]',
  related_tests_json TEXT NOT NULL DEFAULT '[]',
  related_config_json TEXT NOT NULL DEFAULT '[]',
  derived_optimizations_json TEXT NOT NULL DEFAULT '[]',
  reconstruction_json TEXT NOT NULL DEFAULT '{}',
  analysis_coverage_json TEXT NOT NULL DEFAULT '{}',
  ownership_status TEXT NOT NULL DEFAULT 'confirmed',
  production_status TEXT NOT NULL DEFAULT 'unknown',
  disclosure_level TEXT NOT NULL DEFAULT 'internal-safe-after-redaction',
  identity_key TEXT,
  revision INTEGER NOT NULL DEFAULT 1,
  created_at TEXT,
  updated_at TEXT
);
CREATE TABLE IF NOT EXISTS claim_evidence (
  claim_id TEXT NOT NULL REFERENCES claims(id),
  evidence_id TEXT NOT NULL REFERENCES evidence(id),
  PRIMARY KEY (claim_id, evidence_id)
);
CREATE TABLE IF NOT EXISTS capabilities (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  description TEXT
);
CREATE TABLE IF NOT EXISTS claim_capabilities (
  claim_id TEXT NOT NULL REFERENCES claims(id),
  capability_id TEXT NOT NULL REFERENCES capabilities(id),
  PRIMARY KEY (claim_id, capability_id)
);
CREATE TABLE IF NOT EXISTS contributions (
  id TEXT PRIMARY KEY,
  claim_id TEXT NOT NULL REFERENCES claims(id),
  role TEXT,
  ownership TEXT NOT NULL DEFAULT 'confirmed',
  confirmation_note TEXT
);
CREATE TABLE IF NOT EXISTS metrics (
  id TEXT PRIMARY KEY,
  claim_id TEXT NOT NULL REFERENCES claims(id),
  name TEXT NOT NULL,
  value TEXT,
  time_range TEXT,
  source TEXT,
  disclosure_level TEXT NOT NULL DEFAULT 'unknown'
);
CREATE TABLE IF NOT EXISTS confirmations (
  id TEXT PRIMARY KEY,
  claim_id TEXT NOT NULL REFERENCES claims(id),
  question TEXT NOT NULL,
  answer TEXT,
  status TEXT NOT NULL CHECK(status IN ('open', 'confirmed', 'rejected'))
);
CREATE TABLE IF NOT EXISTS narrative_units (
  id TEXT PRIMARY KEY,
  claim_id TEXT NOT NULL REFERENCES claims(id),
  situation TEXT,
  task TEXT,
  actions TEXT,
  verified_results TEXT,
  status TEXT NOT NULL DEFAULT 'draft'
);
CREATE TABLE IF NOT EXISTS exports (
  id TEXT PRIMARY KEY,
  export_type TEXT NOT NULL,
  target TEXT,
  output_path TEXT NOT NULL,
  manifest_path TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS export_claims (
  export_id TEXT NOT NULL REFERENCES exports(id),
  claim_id TEXT NOT NULL REFERENCES claims(id),
  inclusion_reason TEXT,
  PRIMARY KEY (export_id, claim_id)
);
CREATE TABLE IF NOT EXISTS index_state (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""

REALIZATION_STATUSES = frozenset({
    "implemented",  # 已实现/已落地
    "partial",      # 部分实现
    "designed",     # 已设计但未完整落地
    "derived",      # 从现有成果推导出的优化方案
    "hypothetical", # 理论可行、尚未验证
    "unknown",
})


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^\w\-]+", "-", str(value).casefold(), flags=re.UNICODE).strip("-_ ")
    return slug or "untitled"


def normalize_realization_status(value: Any) -> str:
    status = str(value or "unknown").strip().casefold()
    aliases = {
        "implemented": "implemented", "complete": "implemented", "completed": "implemented",
        "partial": "partial", "partially-implemented": "partial",
        "designed": "designed", "design": "designed", "planned": "designed",
        "derived": "derived", "optimized": "derived",
        "hypothetical": "hypothetical", "theoretical": "hypothetical",
    }
    return aliases.get(status, "unknown")


def json_field(value: Any, default: Any) -> str:
    """Serialize optional structured analysis fields deterministically."""
    if value is None:
        value = default
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def parse_json_field(value: Any, default: Any) -> Any:
    try:
        parsed = json.loads(value) if value else default
        return parsed if parsed is not None else default
    except (TypeError, json.JSONDecodeError):
        return default


def stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def output_root() -> Path:
    configured = os.environ.get("RIPPER_OUTPUT_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[1] / "ripper-output"


def assets_root() -> Path:
    return output_root() / "assets"


def archive_fingerprint(root: Path) -> str:
    """Hash manifests and their active analysis/knowledge files."""
    digest = hashlib.sha256()
    if not root.is_dir():
        return digest.hexdigest()
    for manifest_path in sorted(root.glob("*/archive-manifest.json")):
        try:
            raw = manifest_path.read_bytes()
            payload = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        digest.update(manifest_path.name.encode("utf-8"))
        digest.update(raw)
        for key in ("analysis_path", "domain_profile_path", "market_practices_path"):
            relative = payload.get(key)
            if not relative:
                continue
            path = Path(relative)
            if not path.is_absolute():
                path = manifest_path.parent / path
            try:
                digest.update(key.encode("utf-8"))
                digest.update(path.read_bytes())
            except OSError:
                continue
        for source in payload.get("sources", []) or []:
            if not isinstance(source, dict):
                continue
            relative = source.get("path") or source.get("archived_path")
            if not relative:
                continue
            bucket = "documents" if source.get("source_type") == "document" else "core-source"
            source_path = Path(relative)
            if not source_path.is_absolute():
                source_path = manifest_path.parent / "sources" / bucket / source_path
            try:
                digest.update(bucket.encode("utf-8"))
                digest.update(str(relative).encode("utf-8"))
                digest.update(source_path.read_bytes())
            except OSError:
                continue
    return digest.hexdigest()


def parse_analysis(path: Path, project_name: str = "项目分析") -> dict[str, Any]:
    """Load the optional structured analysis sidecar, with Markdown fallback.

    Agents may emit ``project-analysis.json`` next to the Markdown report. A
    plain Markdown report is still a valid input and becomes one auditable
    summary claim, so every successful deposit is queryable/exportable.
    """
    if path.suffix.lower() == ".json":
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                return {"claims": payload}
            if isinstance(payload, dict):
                return payload
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid analysis JSON: {path}") from exc
        raise ValueError(f"analysis JSON must be an object or list: {path}")
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
    heading = next((line.lstrip("# ").strip() for line in lines if line.startswith("#") and line.lstrip("# ").strip()), project_name)
    body = next((line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")), "")
    bullets = [line.lstrip("-* ").strip() for line in lines if line.lstrip().startswith(("-", "*")) and line.lstrip("-* ").strip()]
    # Markdown is a compatibility input, not a reason to collapse every
    # recorded result into the first bullet. Preserve each distinct bullet as
    # a conservative claim; structured JSON remains the canonical format for
    # precise lifecycle, metric and narrative fields.
    statements = list(dict.fromkeys(bullets)) or [body or f"已完成{project_name}的工程分析并形成可复用资产。"]
    claims = []
    for index, statement in enumerate(statements, 1):
        short = re.split(r"[：:]", statement, maxsplit=1)[0].strip() or f"成果 {index}"
        title = heading if len(statements) == 1 else f"{heading}：{short[:80]}"
        claims.append({
            "title": title or project_name,
            "statement": statement,
            "status": "inferred",
            "realization_status": "designed",
            "evidence": [{"claim_text": statement, "kind": "doc", "confidence": "inferred"}],
        })
    return {"claims": claims}


def materialize_knowledge_claims(bundle: dict[str, Any], manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert validated market-practice candidates into exportable claims.

    These claims remain explicitly derived. They never assert that the
    historical project implemented an external module.
    """
    if not isinstance(bundle, dict):
        return []
    profile_id = str(bundle.get("profile_id") or "")
    cards = {
        str(item.get("id")): item
        for item in bundle.get("module_cards", [])
        if isinstance(item, dict) and item.get("id")
    }
    sources = {
        str(item.get("id")): item
        for item in bundle.get("sources", [])
        if isinstance(item, dict) and item.get("id")
    }
    directions = [
        str(item.get("name")) for item in bundle.get("project_direction_candidates", [])
        if isinstance(item, dict) and item.get("name")
    ]
    claims: list[dict[str, Any]] = []
    for candidate in bundle.get("architecture_candidates", []):
        if not isinstance(candidate, dict):
            continue
        variant = str(candidate.get("variant") or "").strip()
        selected = [cards[cid] for cid in candidate.get("module_card_ids", []) if cid in cards]
        if not variant or not selected:
            continue
        module_names = [str(card.get("name") or card.get("id")) for card in selected]
        basis_ids = list(dict.fromkeys(
            str(source_id)
            for card in selected
            for source_id in card.get("basis_source_ids", [])
            if str(source_id) in sources
        ))
        coherence = str(candidate.get("coherence_rationale") or "").strip()
        direction = " / ".join(directions) or str(manifest.get("project_name") or "项目")
        statement = f"基于{direction}的工程材料与近期同方向实践，形成 {variant} 增强候选：{'、'.join(module_names)}。"
        if coherence:
            statement += coherence
        derived = [{
            "module_card_id": str(card.get("id")),
            "name": str(card.get("name") or card.get("id")),
            "project_fit": card.get("project_fit"),
            "compatibility_requirements": card.get("compatibility_requirements", []),
            "historical_fact": False,
            "realization_status": "derived",
            "source_ids": [str(item) for item in card.get("basis_source_ids", [])],
        } for card in selected]
        evidences = [{
            "claim_text": f"{source.get('title')}（{source.get('published_at')}） {source.get('url')}",
            "kind": "doc",
            "confidence": "inferred",
        } for source_id in basis_ids for source in [sources[source_id]]]
        claims.append({
            "id": stable_id("claim", str(manifest.get("project_id") or ""), profile_id, variant),
            "title": f"{direction}增强候选（{variant}）",
            "statement": statement,
            "status": "inferred",
            "realization_status": "derived",
            "production_status": "not-verified",
            "disclosure_level": "public",
            "capabilities": list(dict.fromkeys([*directions, *module_names])),
            "source_refs": [{
                "path": "knowledge/market-practices.json",
                "kind": "doc",
                "claim": f"外部实践支撑 {variant} 候选，不代表历史项目已实现。",
                "confidence": "inferred",
            }],
            "evidence": evidences,
            "derived_optimizations": derived,
            "reconstruction": {
                "mode": "market-informed-reconstruction",
                "profile_id": profile_id,
                "variant": variant,
                "historical_fact": False,
                "preserved_terms": candidate.get("preserved_terms", []),
                "coherence_rationale": coherence,
                "source_ids": basis_ids,
                "note": "该候选由项目材料和外部实践推导，用于方案表达，不作为历史落地事实。",
            },
            "confirmation_questions": [f"是否将 {variant} 候选用于本次对外材料？"],
        })
    return claims


class AssetStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or assets_root()).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        cache_dir = self.root / ".cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        legacy_db = self.root / "ripper-assets.sqlite"
        self.db_path = legacy_db if legacy_db.exists() else cache_dir / "ripper-assets.sqlite"
        # Plug-and-play contract: callers never need a separate database
        # setup step. SQLite is an internal local index, not user config.
        self.initialize()

    @contextmanager
    def connect(self) -> Iterable[sqlite3.Connection]:
        """Yield a transaction connection and always close it.

        sqlite3.Connection's context manager commits/rolls back but does not
        close the connection. Ripper opens short-lived connections throughout
        its CLI workflows, so explicit closing prevents descriptor leaks.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> Path:
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            columns = {row[1] for row in conn.execute("PRAGMA table_info(repositories)")}
            if "project_id" not in columns:
                conn.execute("ALTER TABLE repositories ADD COLUMN project_id TEXT")
            claim_columns = {row[1] for row in conn.execute("PRAGMA table_info(claims)")}
            if "realization_status" not in claim_columns:
                conn.execute("ALTER TABLE claims ADD COLUMN realization_status TEXT NOT NULL DEFAULT 'unknown'")
            for column, definition in {
                "source_refs_json": "TEXT NOT NULL DEFAULT '[]'",
                "related_tests_json": "TEXT NOT NULL DEFAULT '[]'",
                "related_config_json": "TEXT NOT NULL DEFAULT '[]'",
                "derived_optimizations_json": "TEXT NOT NULL DEFAULT '[]'",
                "reconstruction_json": "TEXT NOT NULL DEFAULT '{}'",
                "analysis_coverage_json": "TEXT NOT NULL DEFAULT '{}'",
            }.items():
                if column not in claim_columns:
                    conn.execute(f"ALTER TABLE claims ADD COLUMN {column} {definition}")
            for column, definition in {
                "identity_key": "TEXT",
                "revision": "INTEGER NOT NULL DEFAULT 1",
                "created_at": "TEXT",
                "updated_at": "TEXT",
            }.items():
                if column not in claim_columns:
                    conn.execute(f"ALTER TABLE claims ADD COLUMN {column} {definition}")
            evidence_columns = {row[1] for row in conn.execute("PRAGMA table_info(evidence)")}
            for column, definition in {
                "source_content_hash": "TEXT",
                "observed_at": "TEXT",
                "freshness_status": "TEXT NOT NULL DEFAULT 'unknown'",
            }.items():
                if column not in evidence_columns:
                    conn.execute(f"ALTER TABLE evidence ADD COLUMN {column} {definition}")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_claims_identity_key ON claims(identity_key)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_evidence_freshness ON evidence(freshness_status)")
        for name in ("repositories", "capability-map", "confirmations", "snapshots"):
            (self.root / name).mkdir(parents=True, exist_ok=True)
        return self.db_path

    def register_repository(self, source_path: str, source_kind: str = "folder", revision: str | None = None, project_id: str | None = None) -> dict[str, str]:
        self.initialize()
        source = str(Path(source_path).expanduser().resolve()) if source_kind == "folder" else source_path
        repository_id = stable_id("repo", source)
        slug = safe_slug(Path(source.rstrip("/")).name or source)
        # The schema keeps slugs unique for human-readable folders. Two
        # unrelated submitted files often share a basename (README.md), so
        # suffix only the colliding slug with a stable source digest.
        with self.connect() as conn:
            collision = conn.execute("SELECT id FROM repositories WHERE slug=? AND id<>?", (slug, repository_id)).fetchone()
        if collision:
            slug = f"{slug}-{hashlib.sha256(source.encode('utf-8')).hexdigest()[:10]}"
        timestamp = now()
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO repositories(id, project_id, slug, source_path, source_kind, revision, created_at, updated_at)
                   VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET project_id=COALESCE(excluded.project_id, repositories.project_id), revision=excluded.revision, updated_at=excluded.updated_at""",
                (repository_id, project_id, slug, source, source_kind, revision, timestamp, timestamp),
            )
        repo_dir = self.root / "repositories" / slug
        for name in ("modules", "evidence"):
            (repo_dir / name).mkdir(parents=True, exist_ok=True)
        return {"id": repository_id, "slug": slug, "path": str(repo_dir)}

    def record_analysis(self, repository_id: str, analysis: dict[str, Any], manifest: dict[str, Any] | None = None) -> list[str]:
        """Persist claims, evidence, metrics and narrative units from analysis."""
        self.initialize()
        claims = analysis.get("claims", []) if isinstance(analysis, dict) else []
        if not claims:
            return []
        claim_ids: list[str] = []
        with self.connect() as conn:
            module_id = stable_id("module", repository_id, "analysis")
            artifact_id = stable_id("artifact", repository_id, "analysis/project-analysis")
            conn.execute("INSERT OR IGNORE INTO modules(id, repository_id, path, title, role) VALUES (?, ?, ?, ?, ?)", (module_id, repository_id, "analysis", "项目分析", "analysis"))
            conn.execute("INSERT OR IGNORE INTO artifacts(id, repository_id, module_id, path, artifact_kind, content_hash) VALUES (?, ?, ?, ?, ?, ?)", (artifact_id, repository_id, module_id, "analysis/project-analysis", "document", None))
        for raw in claims:
            if not isinstance(raw, dict):
                raw = {"title": str(raw), "statement": str(raw)}
            title = str(raw.get("title") or raw.get("name") or "未命名成果")
            statement = str(raw.get("statement") or raw.get("description") or title)
            realization = normalize_realization_status(raw.get("realization_status"))
            source_refs = raw.get("source_refs", raw.get("sources", [])) or []
            if isinstance(source_refs, (str, Path)):
                source_refs = [{"path": str(source_refs)}]
            reconstruction = raw.get("reconstruction", raw.get("reconstruction_notes", {})) or {}
            if not reconstruction and realization in {"partial", "designed", "derived", "hypothetical", "unknown"}:
                reconstruction = {
                    "mode": "material-grounded-reconstruction",
                    "basis": "基于用户提交的文档、方案、PRD或现有模块进行合理补全",
                    "note": "该补充用于面试准备和方案表达，具体历史落地范围需结合用户记忆确认。",
                }
            confirmations = raw.get("confirmation_questions", raw.get("confirmations", [])) or []
            confirmations = [item for item in confirmations if item]
            raw = {
                **raw,
                "source_refs": source_refs,
                "reconstruction": reconstruction,
                "confirmation_questions": confirmations,
            }
            payload = {**raw, "title": title, "statement": statement}
            claim_id = self.record_claim(repository_id, payload)
            claim_ids.append(claim_id)
            evidences = raw.get("evidence", []) or []
            if isinstance(evidences, str):
                evidences = [{"claim_text": evidences}]
            if not evidences:
                evidences = [{"claim_text": statement, "kind": "doc", "confidence": raw.get("status", "inferred")}]
            with self.connect() as conn:
                # Preserve precise source locations as first-class artifacts;
                # the analysis report remains a fallback artifact, not the
                # only provenance for every claim.
                for ref in source_refs:
                    if isinstance(ref, str):
                        ref = {"path": ref}
                    ref = dict(ref)
                    freshness = "unknown"
                    archived = ref.get("archive_source_path")
                    if archived and manifest and manifest.get("archive_path"):
                        archive_root = Path(manifest["archive_path"]).resolve()
                        source = (archive_root / archived).resolve()
                        if not source.is_relative_to(archive_root):
                            raise ValueError("evidence path escapes project archive")
                        if source.is_file() and ref.get("content_hash"):
                            digest = hashlib.sha256(source.read_bytes()).hexdigest()
                            freshness = "current" if digest == ref["content_hash"] else "stale"
                        elif not source.is_file():
                            freshness = "missing"
                    ref["freshness_status"] = freshness
                    ref_path = str(ref.get("path") or ref.get("source") or "analysis/project-analysis")
                    ref_module = str(Path(ref_path).parent)
                    ref_module_id = stable_id("module", repository_id, ref_module)
                    ref_artifact_id = stable_id("artifact", repository_id, ref_path)
                    conn.execute("INSERT OR IGNORE INTO modules(id, repository_id, path, title, role) VALUES (?, ?, ?, ?, ?)", (ref_module_id, repository_id, ref_module, Path(ref_module).name or "repository-root", ref.get("role", "source")))
                    conn.execute("INSERT OR IGNORE INTO artifacts(id, repository_id, module_id, path, artifact_kind, content_hash) VALUES (?, ?, ?, ?, ?, ?)", (ref_artifact_id, repository_id, ref_module_id, ref_path, ref.get("kind", "file"), ref.get("content_hash")))
                    ref_text = str(ref.get("claim") or ref.get("claim_text") or statement)
                    ref_kind = ref.get("evidence_kind") or ("test" if "test" in ref_path.lower() else "config" if any(part in ref_path.lower() for part in ("config", "yaml", "yml", "toml", "docker")) else "code" if Path(ref_path).suffix.lower() in {".py", ".js", ".ts", ".java", ".go", ".rs", ".cpp", ".h"} else "doc")
                    ref_confidence = ref.get("confidence", raw.get("status", "inferred"))
                    if ref_confidence not in {"confirmed", "code-verifiable", "inferred", "planned", "blocked", "unknown"}:
                        ref_confidence = "inferred"
                    ref_evidence_id = stable_id("evidence", ref_artifact_id, claim_id, ref_text)
                    conn.execute("INSERT OR IGNORE INTO evidence(id, artifact_id, kind, symbol, line_start, line_end, claim_text, confidence, source_content_hash, observed_at, freshness_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (ref_evidence_id, ref_artifact_id, ref_kind, ref.get("symbol"), ref.get("line_start"), ref.get("line_end"), ref_text, ref_confidence, ref.get("content_hash"), now(), ref.get("freshness_status", "current")))
                    conn.execute("INSERT OR IGNORE INTO claim_evidence(claim_id, evidence_id) VALUES (?, ?)", (claim_id, ref_evidence_id))
                for evidence in evidences:
                    if isinstance(evidence, str):
                        evidence = {"claim_text": evidence}
                    claim_text = str(evidence.get("claim_text") or evidence.get("text") or statement)
                    kind = evidence.get("kind", "doc")
                    if kind not in {"code", "doc", "config", "test", "user", "inferred"}:
                        kind = "doc"
                    confidence = evidence.get("confidence", raw.get("status", "inferred"))
                    if confidence not in {"confirmed", "code-verifiable", "inferred", "planned", "blocked", "unknown"}:
                        confidence = "inferred"
                    evidence_id = stable_id("evidence", artifact_id, claim_id, claim_text)
                    conn.execute("INSERT OR IGNORE INTO evidence(id, artifact_id, kind, symbol, line_start, line_end, claim_text, confidence, source_content_hash, observed_at, freshness_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (evidence_id, artifact_id, kind, evidence.get("symbol"), evidence.get("line_start"), evidence.get("line_end"), claim_text, confidence, evidence.get("content_hash"), evidence.get("observed_at") or raw.get("updated_at"), evidence.get("freshness_status", "unknown")))
                    conn.execute("INSERT OR IGNORE INTO claim_evidence(claim_id, evidence_id) VALUES (?, ?)", (claim_id, evidence_id))
                for metric in raw.get("metrics", []) or []:
                    if isinstance(metric, str):
                        metric = {"name": metric}
                    metric_name = str(metric.get("name") or "未命名指标")
                    metric_id = stable_id("metric", claim_id, metric_name, str(metric.get("value", "")))
                    conn.execute("INSERT OR REPLACE INTO metrics(id, claim_id, name, value, time_range, source, disclosure_level) VALUES (?, ?, ?, ?, ?, ?, ?)", (metric_id, claim_id, metric_name, str(metric.get("value", "")), metric.get("time_range"), metric.get("source"), metric.get("disclosure_level", "unknown")))
                narrative = raw.get("narrative") or raw.get("narrative_unit")
                if isinstance(narrative, dict):
                    narrative_id = stable_id("narrative", claim_id)
                    conn.execute("INSERT OR REPLACE INTO narrative_units(id, claim_id, situation, task, actions, verified_results, status) VALUES (?, ?, ?, ?, ?, ?, ?)", (narrative_id, claim_id, narrative.get("situation"), narrative.get("task"), narrative.get("actions"), narrative.get("verified_results") or narrative.get("result"), narrative.get("status", "draft")))
        return claim_ids

    def _clear_repository_derived(self, repository_id: str, *, remove_repository: bool = False) -> None:
        """Remove rebuildable rows for one repository in foreign-key order."""
        with self.connect() as conn:
            claim_ids = [row[0] for row in conn.execute("SELECT id FROM claims WHERE repository_id=?", (repository_id,))]
            for claim_id in claim_ids:
                conn.execute("DELETE FROM export_claims WHERE claim_id=?", (claim_id,))
                conn.execute("DELETE FROM claim_evidence WHERE claim_id=?", (claim_id,))
                for table in ("confirmations", "claim_capabilities", "metrics", "narrative_units", "contributions"):
                    conn.execute(f"DELETE FROM {table} WHERE claim_id=?", (claim_id,))
            conn.execute("DELETE FROM claims WHERE repository_id=?", (repository_id,))
            conn.execute("DELETE FROM evidence WHERE artifact_id IN (SELECT id FROM artifacts WHERE repository_id=?)", (repository_id,))
            conn.execute("DELETE FROM artifacts WHERE repository_id=?", (repository_id,))
            conn.execute("DELETE FROM modules WHERE repository_id=?", (repository_id,))
            conn.execute("DELETE FROM scan_runs WHERE repository_id=?", (repository_id,))
            if remove_repository:
                conn.execute("DELETE FROM repositories WHERE id=?", (repository_id,))

    def sync_archive_manifest(self, manifest: dict[str, Any], analysis: dict[str, Any] | None = None) -> list[dict[str, str]]:
        """Index the active sources of one archive using its project_id.

        The filesystem archive remains authoritative. This operation is
        idempotent and may be rerun after deleting/recreating the SQLite cache.
        """
        # An interrupted per-project sync must not retain a fingerprint that
        # falsely claims the partially modified index is current.
        with self.connect() as conn:
            conn.execute("DELETE FROM index_state WHERE key='archive_fingerprint'")
            conn.execute("INSERT OR REPLACE INTO index_state(key, value) VALUES ('archive_managed', '1')")
        project_id = manifest.get("project_id")
        records: list[dict[str, str]] = []
        expected_paths: set[str] = set()
        archive_path = manifest.get("archive_path")
        if archive_path:
            archive_directory = Path(archive_path).resolve()
            for key in ("analysis_path", "domain_profile_path", "market_practices_path"):
                if manifest.get(key):
                    candidate = (archive_directory / manifest[key]).resolve()
                    if not candidate.is_relative_to(archive_directory):
                        raise ValueError(f"{key} escapes project archive")
                    if not candidate.is_file():
                        raise ValueError(f"archive {key} is missing: {candidate}")
                    if candidate.suffix.lower() == ".json":
                        try:
                            json.loads(candidate.read_text(encoding="utf-8"))
                        except (OSError, json.JSONDecodeError) as exc:
                            raise ValueError(f"archive {key} is invalid: {candidate}") from exc
            if not manifest.get("analysis_path"):
                raise ValueError("archive analysis_path is required")
            if not manifest.get("sources"):
                raise ValueError("archive sources are required")
        if archive_path:
            for source in manifest.get("sources", []):
                relative = source.get("archived_path") or source.get("path")
                if not relative:
                    continue
                bucket = "documents" if source.get("source_type") == "document" else "core-source"
                candidate = Path(relative)
                if not candidate.is_absolute():
                    candidate = Path(archive_path) / "sources" / bucket / relative
                if not candidate.resolve().is_relative_to(Path(archive_path).resolve()):
                    raise ValueError("source path escapes project archive")
                expected_paths.add(str(candidate.expanduser().resolve()))
        # Updates can remove/rename active sources. Prune only stale derived
        # repositories belonging to this project; the archive remains intact.
        if project_id:
            with self.connect() as conn:
                stale = [row[0] for row in conn.execute("SELECT id FROM repositories WHERE project_id=? AND source_path NOT IN ({})".format(",".join("?" for _ in expected_paths) or "''"), (project_id, *expected_paths)).fetchall()]
            for repository_id in stale:
                self._clear_repository_derived(repository_id, remove_repository=True)
        for source in manifest.get("sources", []):
            path = source.get("archived_path") or source.get("path")
            if not path:
                continue
            source_path = Path(path)
            if not source_path.is_absolute() and manifest.get("archive_path"):
                bucket = "documents" if source.get("source_type") == "document" else "core-source"
                source_path = Path(manifest["archive_path"]) / "sources" / bucket / path
            if not source_path.exists():
                raise ValueError(f"archive source is missing: {source_path}")
            kind = "document" if source.get("source_type") == "document" else "folder"
            records.append(self.register_repository(str(source_path), source_kind=kind, project_id=project_id))
        if records:
            analysis_payload = analysis
            if analysis_payload is None:
                analysis_path = Path(manifest.get("analysis_path", ""))
                if not analysis_path.is_absolute() and manifest.get("archive_path"):
                    analysis_path = Path(manifest["archive_path"]) / analysis_path
                if analysis_path.is_file():
                    analysis_payload = parse_analysis(analysis_path, str(manifest.get("project_name") or "项目分析"))
                else:
                    raise ValueError(f"archive analysis is missing: {analysis_path}")
            analysis_payload = analysis_payload if isinstance(analysis_payload, dict) else {}
            knowledge_claims: list[dict[str, Any]] = []
            knowledge_path = manifest.get("market_practices_path")
            if knowledge_path:
                knowledge_file = Path(knowledge_path)
                if not knowledge_file.is_absolute() and manifest.get("archive_path"):
                    knowledge_file = Path(manifest["archive_path"]) / knowledge_file
                try:
                    knowledge_bundle = json.loads(knowledge_file.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    raise ValueError(f"archive knowledge is missing or invalid: {knowledge_file}")
                knowledge_claims = materialize_knowledge_claims(knowledge_bundle, manifest)

            combined: list[dict[str, Any]] = []
            positions: dict[str, int] = {}
            for raw in [*(analysis_payload.get("claims", []) or []), *knowledge_claims]:
                if not isinstance(raw, dict):
                    raw = {"title": str(raw), "statement": str(raw)}
                claim_id = str(raw.get("id") or "")
                if claim_id and claim_id in positions:
                    combined[positions[claim_id]] = raw
                else:
                    if claim_id:
                        positions[claim_id] = len(combined)
                    combined.append(raw)

            # The archive is authoritative: replace the project's derived
            # index rows so removed/renamed claims cannot survive an update.
            if project_id:
                with self.connect() as conn:
                    project_repositories = [row[0] for row in conn.execute("SELECT id FROM repositories WHERE project_id=?", (project_id,))]
                for repository_id in project_repositories:
                    self._clear_repository_derived(repository_id)
            if combined:
                self.record_analysis(records[0]["id"], {**analysis_payload, "claims": combined}, manifest)
        return records

    def sync_from_archives(self, archive_root: Path | None = None) -> int:
        """Synchronize every readable archive into the current local index."""
        root = (archive_root or (Path.home() / "Ripper" / "archives")).expanduser()
        count = 0
        for manifest_path in sorted(root.glob("*/archive-manifest.json")):
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ValueError(f"cannot rebuild from invalid manifest: {manifest_path}") from exc
            # Resolve archive-relative paths from the manifest's actual
            # location, allowing a copied ~/Ripper/archives tree to rebuild
            # on another host even if the old absolute path is stale.
            manifest["archive_path"] = str(manifest_path.parent)
            analysis_path = manifest.get("analysis_path")
            if analysis_path and not Path(analysis_path).is_absolute():
                manifest["analysis_path"] = str(manifest_path.parent / analysis_path)
            count += len(self.sync_archive_manifest(manifest))
        with self.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO index_state(key, value) VALUES ('archive_fingerprint', ?)",
                (archive_fingerprint(root),),
            )
        return count

    def archive_index_is_current(self, archive_root: Path | None = None) -> bool:
        root = (archive_root or (Path.home() / "Ripper" / "archives")).expanduser()
        with self.connect() as conn:
            row = conn.execute("SELECT value FROM index_state WHERE key='archive_fingerprint'").fetchone()
        return bool(row and row[0] == archive_fingerprint(root))

    def has_archive_index_state(self) -> bool:
        """Return whether this host-local index has ever mirrored archives."""
        with self.connect() as conn:
            row = conn.execute("SELECT 1 FROM index_state WHERE key IN ('archive_fingerprint', 'archive_managed')").fetchone()
        return row is not None

    def index_status(self, archive_root: Path | None = None) -> dict[str, Any]:
        root = archive_root or (Path.home() / "Ripper" / "archives")
        return {"status": "current" if self.archive_index_is_current(root) else "stale",
                "archive_root": str(root), "index_database": str(self.db_path)}

    def rebuild_from_archives(self, archive_root: Path | None = None) -> int:
        """Rebuild the complete query index from human-readable archives.

        Because the database is derived state, stale rows are removed first;
        manifests then repopulate repositories, claims, evidence, metrics and
        narrative links in one deterministic pass.
        """
        # Build separately: a failed rebuild must not destroy the last usable
        # index. All connections are closed before the atomic replacement.
        with tempfile.TemporaryDirectory(prefix="ripper-index-", dir=self.db_path.parent) as directory:
            staged = AssetStore(Path(directory))
            count = staged.sync_from_archives(archive_root)
            os.replace(staged.db_path, self.db_path)
        return count

    def clear_index(self) -> None:
        """Clear derived SQLite rows while leaving the filesystem archive intact."""
        self.initialize()
        tables = ("export_claims", "exports", "claim_evidence", "evidence", "metrics", "narrative_units", "confirmations", "contributions", "claim_capabilities", "capabilities", "claims", "artifacts", "modules", "scan_runs", "repositories")
        with self.connect() as conn:
            for table in tables:
                conn.execute(f"DELETE FROM {table}")

    def register_document(self, source_path: str, project_id: str | None = None) -> dict[str, str]:
        """Register a submitted Markdown or PDF as a first-class source."""
        source = Path(source_path).expanduser().resolve()
        if not source.is_file():
            raise ValueError(f"document does not exist or is not a file: {source}")
        if source.suffix.lower() not in {".md", ".pdf"}:
            raise ValueError("document input must be .md or .pdf")
        return self.register_repository(str(source), source_kind="document", project_id=project_id)

    def record_claim(self, repository_id: str, payload: dict[str, Any]) -> str:
        self.initialize()
        title = str(payload["title"])
        statement = str(payload.get("statement", title))
        identity_key = str(payload.get("identity_key") or "").strip() or None
        claim_id = str(payload.get("id") or (stable_id("claim", repository_id, identity_key) if identity_key else ""))
        status = payload.get("status", "code-verifiable")
        timestamp = now()
        with self.connect() as conn:
            owner = conn.execute("SELECT repository_id FROM claims WHERE id=?", (claim_id,)).fetchone() if claim_id else None
            if owner and owner[0] != repository_id:
                raise ValueError("claim ID already belongs to another repository: " + claim_id)
            if not claim_id and identity_key:
                prior = conn.execute(
                    "SELECT id FROM claims WHERE repository_id=? AND identity_key=? ORDER BY revision DESC LIMIT 1",
                    (repository_id, identity_key),
                ).fetchone()
                claim_id = str(prior[0]) if prior else ""
            claim_id = claim_id or stable_id("claim", repository_id, identity_key or title, statement)
            # A submitted source is, by product policy, a user-owned career
            # source. Preserve any explicitly recorded lifecycle metadata when
            # a later scan refreshes the same claim instead of resetting it to
            # defaults. The legacy ownership column remains only for schema
            # compatibility and is no longer an eligibility gate.
            existing = conn.execute(
                "SELECT ownership_status, production_status, disclosure_level, realization_status, revision, created_at FROM claims WHERE id=?",
                (claim_id,),
            ).fetchone()
            ownership = payload.get("ownership_status", existing[0] if existing else "confirmed")
            production = payload.get("production_status", existing[1] if existing else "unknown")
            disclosure = payload.get("disclosure_level", existing[2] if existing else "internal-safe-after-redaction")
            realization = normalize_realization_status(payload.get("realization_status", existing[3] if existing else "unknown"))
            revision = int(payload.get("revision") or (int(existing[4] or 1) + 1 if existing else 1))
            created_at = payload.get("created_at") or (existing[5] or timestamp if existing else timestamp)
            timestamp = payload.get("updated_at") or timestamp
            source_refs = json_field(payload.get("source_refs", payload.get("sources", [])), [])
            related_tests = json_field(payload.get("related_tests", []), [])
            related_config = json_field(payload.get("related_config", []), [])
            derived_optimizations = json_field(payload.get("derived_optimizations", []), [])
            reconstruction = json_field(payload.get("reconstruction", payload.get("reconstruction_notes", {})), {})
            analysis_coverage = json_field(payload.get("analysis_coverage", {}), {})
            conn.execute(
                """INSERT INTO claims(id, repository_id, title, statement, status, realization_status,
                   source_refs_json, related_tests_json, related_config_json, derived_optimizations_json,
                   reconstruction_json, analysis_coverage_json, ownership_status, production_status, disclosure_level,
                   identity_key, revision, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET title=excluded.title, statement=excluded.statement, status=excluded.status,
                   realization_status=excluded.realization_status, ownership_status=excluded.ownership_status,
                   source_refs_json=excluded.source_refs_json, related_tests_json=excluded.related_tests_json,
                   related_config_json=excluded.related_config_json, derived_optimizations_json=excluded.derived_optimizations_json,
                   reconstruction_json=excluded.reconstruction_json, analysis_coverage_json=excluded.analysis_coverage_json,
                   production_status=excluded.production_status, disclosure_level=excluded.disclosure_level,
                   identity_key=COALESCE(excluded.identity_key, claims.identity_key), revision=excluded.revision,
                   updated_at=excluded.updated_at""",
                (claim_id, repository_id, title, statement, status, realization, source_refs, related_tests,
                 related_config, derived_optimizations, reconstruction, analysis_coverage, ownership, production, disclosure,
                 identity_key, revision, created_at, timestamp),
            )
            for capability in payload.get("capabilities", []):
                capability_id = stable_id("cap", capability)
                conn.execute("INSERT OR IGNORE INTO capabilities(id, name) VALUES (?, ?)", (capability_id, capability))
                conn.execute("INSERT OR IGNORE INTO claim_capabilities(claim_id, capability_id) VALUES (?, ?)", (claim_id, capability_id))
            for entry in payload.get("confirmation_questions", []):
                entry = entry if isinstance(entry, dict) else {"question": str(entry)}
                question = str(entry.get("question") or entry.get("text") or "").strip()
                if not question:
                    raise ValueError("confirmation question is required")
                confirmation_status = entry.get("status", "open")
                if confirmation_status not in {"open", "confirmed", "rejected"}:
                    raise ValueError("invalid confirmation status")
                confirmation_id = stable_id("confirm", claim_id, question)
                conn.execute("INSERT INTO confirmations(id, claim_id, question, answer, status) VALUES (?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET answer=excluded.answer, status=excluded.status", (confirmation_id, claim_id, question, entry.get("answer"), confirmation_status))
        return claim_id

    def record_scan(self, repository_id: str, source_hash: str, scope_path: str | None = None, status: str = "completed", report_path: str | None = None) -> str:
        self.initialize()
        scan_id = stable_id("scan", repository_id, source_hash, scope_path or "")
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO scan_runs(id, repository_id, scope_path, source_hash, status, scanned_at, report_path)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET status=excluded.status, scanned_at=excluded.scanned_at, report_path=excluded.report_path""",
                (scan_id, repository_id, scope_path, source_hash, status, now(), report_path),
            )
        return scan_id

    def scan_is_current(self, repository_id: str, source_hash: str, scope_path: str | None = None) -> bool:
        self.initialize()
        with self.connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM scan_runs WHERE repository_id=? AND source_hash=? AND scope_path IS ? AND status='completed'",
                (repository_id, source_hash, scope_path),
            ).fetchone()
        return row is not None

    def record_candidate(self, repository_id: str, candidate: dict[str, Any]) -> str:
        """Persist one code/document-backed candidate claim and its source evidence."""
        self.initialize()
        path = str(candidate["path"])
        module_path = str(candidate.get("module_path") or Path(path).parent)
        module_id = stable_id("module", repository_id, module_path)
        artifact_id = stable_id("artifact", repository_id, path)
        claim_payload = {
            "id": candidate.get("id"),
            "identity_key": candidate.get("identity_key"),
            "title": candidate["title"],
            "statement": candidate.get("statement", candidate["title"]),
            "status": candidate.get("status", "code-verifiable"),
            "realization_status": candidate.get("realization_status", "implemented"),
            "source_refs": candidate.get("source_refs", [{"path": path, "symbol": candidate.get("symbol"), "line_start": candidate.get("line_start"), "line_end": candidate.get("line_end")}]),
            "related_tests": candidate.get("related_tests", []),
            "related_config": candidate.get("related_config", []),
            "derived_optimizations": candidate.get("derived_optimizations", []),
            "reconstruction": candidate.get("reconstruction", {}),
            "analysis_coverage": candidate.get("analysis_coverage", {}),
            "capabilities": candidate.get("capabilities", []),
            "confirmation_questions": candidate.get("confirmation_questions", []),
        }
        claim_id = self.record_claim(repository_id, claim_payload)
        with self.connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO modules(id, repository_id, path, title, role) VALUES (?, ?, ?, ?, ?)",
                (module_id, repository_id, module_path, Path(module_path).name or "repository-root", candidate.get("module_role")),
            )
            conn.execute(
                "INSERT OR IGNORE INTO artifacts(id, repository_id, module_id, path, artifact_kind, content_hash) VALUES (?, ?, ?, ?, ?, ?)",
                (artifact_id, repository_id, module_id, path, candidate.get("artifact_kind", "file"), candidate.get("content_hash")),
            )
            evidence_id = stable_id("evidence", artifact_id, candidate["claim_text"])
            conn.execute(
                """INSERT OR IGNORE INTO evidence(id, artifact_id, kind, symbol, line_start, line_end, claim_text, confidence,
                   source_content_hash, observed_at, freshness_status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (evidence_id, artifact_id, candidate.get("evidence_kind", "code"), candidate.get("symbol"), candidate.get("line_start"), candidate.get("line_end"), candidate["claim_text"], candidate.get("status", "code-verifiable"), candidate.get("content_hash"), now(), "unknown"),
            )
            conn.execute("INSERT OR IGNORE INTO claim_evidence(claim_id, evidence_id) VALUES (?, ?)", (claim_id, evidence_id))
        return claim_id

    def query_claims(self, capabilities: Iterable[str] = (), include_unconfirmed: bool = True) -> list[dict[str, Any]]:
        """Query non-restricted claims.

        ``include_unconfirmed`` is retained as a compatibility argument for
        older callers. User-submitted sources are eligible by policy, so
        personal-attribution state is never used as a filter.
        """
        self.initialize()
        # Submitted sources are eligible by policy. Disclosure metadata is
        # retained for redaction guidance, but never suppresses a result from
        # the user's internal asset inventory or role-focused selection.
        clauses = ["1=1"]
        params: list[Any] = []
        capability_list = list(capabilities)
        if capability_list:
            placeholders = ",".join("?" for _ in capability_list)
            clauses.append(f"c.id IN (SELECT cc.claim_id FROM claim_capabilities cc JOIN capabilities cap ON cap.id=cc.capability_id WHERE cap.name IN ({placeholders}))")
            params.extend(capability_list)
        sql = f"""SELECT c.id, c.repository_id, r.project_id, c.title, c.statement, c.status,
                         c.realization_status, c.source_refs_json, c.related_tests_json,
                         c.related_config_json, c.derived_optimizations_json, c.reconstruction_json,
                         c.analysis_coverage_json, c.production_status, c.disclosure_level,
                         c.identity_key, c.revision, c.created_at, c.updated_at,
                         r.slug AS repository_slug
                  FROM claims c JOIN repositories r ON r.id=c.repository_id
                  WHERE {' AND '.join(clauses)} ORDER BY c.title"""
        with self.connect() as conn:
            rows = []
            for row in conn.execute(sql, params):
                item = dict(row)
                item["confirmations"] = [dict(r) for r in conn.execute("SELECT id, question, answer, status FROM confirmations WHERE claim_id=? ORDER BY id", (item["id"],))]
                item["evidence"] = [dict(r) for r in conn.execute("SELECT e.*, a.path FROM evidence e JOIN artifacts a ON a.id=e.artifact_id JOIN claim_evidence ce ON ce.evidence_id=e.id WHERE ce.claim_id=? ORDER BY e.id", (item["id"],))]
                states = [r[0] for r in conn.execute("SELECT e.freshness_status FROM evidence e JOIN claim_evidence ce ON ce.evidence_id=e.id WHERE ce.claim_id=?", (item["id"],))]
                item["evidence_freshness"] = "stale" if any(s in {"stale", "missing"} for s in states) else "current" if "current" in states else "unknown"
                for field, default in (("source_refs_json", []), ("related_tests_json", []), ("related_config_json", []), ("derived_optimizations_json", []), ("reconstruction_json", {}), ("analysis_coverage_json", {})):
                    item[field.removesuffix("_json")] = parse_json_field(item.pop(field), default)
                rows.append(item)
            return rows

    def mark_stale_evidence(self, artifact_id: str, current_hash: str | None) -> int:
        """Mark evidence stale when its source artifact changed since observation."""
        self.initialize()
        with self.connect() as conn:
            if not current_hash:
                result = conn.execute(
                    "UPDATE evidence SET freshness_status='unknown' WHERE artifact_id=? AND freshness_status='current'",
                    (artifact_id,),
                )
            else:
                result = conn.execute(
                    "UPDATE evidence SET freshness_status='stale' WHERE artifact_id=? AND source_content_hash IS NOT NULL AND source_content_hash<>?",
                    (artifact_id, current_hash),
                )
            return result.rowcount

    def write_repository_snapshot(self, repository: dict[str, str], scan: dict[str, Any]) -> Path:
        path = Path(repository["path"]) / "repository-map.yaml"
        lines = [
            f"repository_id: {repository['id']}",
            f"slug: {repository['slug']}",
            f"source_path: {scan['source_path']}",
            f"scanned_at: {now()}",
            "modules:",
        ]
        for module in scan.get("modules", []):
            lines.extend([f"  - path: {module['path']}", f"    role: {module.get('role', 'unknown')}"])
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        report = path.parent / "scan-report.md"
        report.write_text(
            f"# 扫描报告：{repository['slug']}\n\n"
            f"- 来源：`{scan['source_path']}`\n"
            f"- 扫描时间：{now()}\n"
            f"- 已发现模块：{len(scan.get('modules', []))}\n\n"
            "本报告记录用户提交来源中的工程结构和候选成果；生产状态、指标和披露边界需按证据分别确认。\n",
            encoding="utf-8",
        )
        return path


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Ripper local asset store")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init")
    repo_parser = subparsers.add_parser("register-repository")
    repo_parser.add_argument("source")
    repo_parser.add_argument("--kind", choices=("folder", "git", "document"), default="folder")
    repo_parser.add_argument("--project-id", default=None)
    document_parser = subparsers.add_parser("register-document")
    document_parser.add_argument("source")
    document_parser.add_argument("--project-id", default=None)
    claim_parser = subparsers.add_parser("record-claim")
    claim_parser.add_argument("repository_id")
    claim_parser.add_argument("payload", help="Path to a JSON claim payload")
    candidate_parser = subparsers.add_parser("record-candidate")
    candidate_parser.add_argument("repository_id")
    candidate_parser.add_argument("payload", help="Path to a JSON candidate payload")
    query_parser = subparsers.add_parser("query-claims")
    query_parser.add_argument("--capability", action="append", default=[])
    query_parser.add_argument("--include-unconfirmed", action="store_true")
    rebuild_parser = subparsers.add_parser("rebuild-from-archives")
    rebuild_parser.add_argument("--archive-root", default=None)
    status_parser = subparsers.add_parser("index-status")
    status_parser.add_argument("--archive-root", default=None)
    args = parser.parse_args()
    store = AssetStore()
    if args.command == "init":
        print(store.initialize())
    elif args.command == "index-status":
        print(json.dumps(store.index_status(Path(args.archive_root).expanduser() if args.archive_root else None), ensure_ascii=False, indent=2))
    elif args.command == "rebuild-from-archives":
        print(store.rebuild_from_archives(Path(args.archive_root).expanduser() if args.archive_root else None))
    elif args.command == "register-document":
        print(json.dumps(store.register_document(args.source, args.project_id), ensure_ascii=False))
    elif args.command == "register-repository":
        print(json.dumps(store.register_repository(args.source, args.kind, project_id=args.project_id), ensure_ascii=False))
    elif args.command == "record-claim":
        payload = json.loads(Path(args.payload).read_text(encoding="utf-8"))
        print(store.record_claim(args.repository_id, payload))
    elif args.command == "record-candidate":
        payload = json.loads(Path(args.payload).read_text(encoding="utf-8"))
        print(store.record_candidate(args.repository_id, payload))
    else:
        print(json.dumps(store.query_claims(args.capability, args.include_unconfirmed), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
