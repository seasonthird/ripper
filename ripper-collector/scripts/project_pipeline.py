"""End-to-end project deposit orchestration.

This is intentionally small and stdlib-only: analysis is produced by the
evidence modeler/agent, while this module owns deterministic input
normalization, duplicate gating, archival and index synchronization.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ARCHIVE = _load("ripper_archive_manager", ROOT / "ripper-archive-manager" / "scripts" / "archive_manager.py")
ASSET = _load("ripper_asset_store", ROOT / "ripper-core" / "asset_store.py")
PROJECT = _load("ripper_project_input", ROOT / "ripper-core" / "project_input.py")
DOMAIN = _load("ripper_domain_enrichment", ROOT / "ripper-core" / "domain_enrichment.py")
LIFECYCLE = _load("ripper_lifecycle", ROOT / "ripper-core" / "lifecycle.py")
TRANSACTION = _load("ripper_archive_transaction", ROOT / "ripper-core" / "archive_transaction.py")


def list_project_archives() -> list[dict]:
    """Return compact, human-readable records from the fixed archive store."""
    root = ARCHIVE.archive_root()
    with TRANSACTION.archive_lock(root):
        if TRANSACTION.recover(root):
            ASSET.AssetStore().rebuild_from_archives(root)
        return [ARCHIVE.archive_overview(item) for item in ARCHIVE.list_archives()]


def build_input(project_name: str, documents: Iterable[str | Path], core_source: Iterable[str | Path] = ()) -> dict:
    item = PROJECT.build_project_input(project_name, [Path(p) for p in documents], [Path(p) for p in core_source])
    item.project_id = ARCHIVE.project_id(item.project_name)
    payload = item.to_dict()
    payload["domain_profile"] = DOMAIN.infer_domain_profile(
        item.project_name,
        [entry.path for entry in item.sources],
    )
    return payload


def validate_domain_knowledge(profile: str | Path, knowledge: str | Path) -> dict:
    """Validate a researched knowledge bundle against its archived profile."""
    profile_payload = json.loads(Path(profile).expanduser().resolve().read_text(encoding="utf-8"))
    knowledge_payload = json.loads(Path(knowledge).expanduser().resolve().read_text(encoding="utf-8"))
    return DOMAIN.validate_knowledge_bundle(knowledge_payload, profile_payload)


def _deposit_project(
    project_name: str,
    analysis: str | Path,
    documents: Iterable[str | Path],
    core_source: Iterable[str | Path] = (),
    *,
    update: bool = False,
    update_project_name: str | None = None,
    knowledge: str | Path | None = None,
) -> dict:
    """Run the complete deterministic deposit transaction.

    A duplicate result is returned unchanged with ``status=confirmation_required``;
    no archive or index mutation occurs until the caller retries with
    ``update=True`` (and, when needed, the confirmed existing project name).
    """
    normalized = build_input(project_name, documents, core_source)
    knowledge_payload = None
    knowledge_validation = None
    if knowledge is not None:
        knowledge_path = Path(knowledge).expanduser().resolve()
        knowledge_payload = json.loads(knowledge_path.read_text(encoding="utf-8"))
        knowledge_validation = DOMAIN.validate_knowledge_bundle(knowledge_payload, normalized["domain_profile"])
        if not knowledge_validation["valid"]:
            raise ValueError("invalid domain knowledge bundle: " + "; ".join(knowledge_validation["errors"]))
    target_name = update_project_name or project_name
    existing_folder = ARCHIVE.archive_folder_for(target_name, allow_existing=True)
    previous_analysis = {}
    if update and existing_folder.is_dir():
        previous_manifest = json.loads((existing_folder / "archive-manifest.json").read_text(encoding="utf-8"))
        for key in ("domain_profile_path", "market_practices_path"):
            if previous_manifest.get(key) and not (existing_folder / previous_manifest[key]).resolve().is_relative_to(existing_folder.resolve()):
                raise ValueError(f"previous {key} escapes project archive")
        previous_path = Path(previous_manifest["analysis_path"])
        if not previous_path.is_absolute():
            previous_path = existing_folder / previous_path
        if not previous_path.resolve().is_relative_to(existing_folder.resolve()):
            raise ValueError("previous analysis path escapes project archive")
        previous_analysis = ASSET.parse_analysis(previous_path, target_name)
    backup_root: Path | None = None
    backup_archive: Path | None = None
    if update and existing_folder.is_dir():
        backup_root = Path(tempfile.mkdtemp(prefix="ripper-pipeline-update-", dir=str(existing_folder.parent)))
        backup_archive = backup_root / "archive"
        shutil.copytree(existing_folder, backup_archive)
    mutated_archive: Path | None = None
    try:
        code, result = ARCHIVE.deposit(
            target_name,
            Path(analysis).expanduser().resolve(),
            [Path(item["path"]) for item in normalized["documents"]],
            [Path(item["path"]) for item in normalized["core_source"]],
            update=update,
            omitted_core_source=normalized.get("omitted_core_source", []),
        )
        result["project_input"] = normalized
        if code != 0:
            return result
        mutated_archive = Path(result["archive_path"])
        manifest_path = mutated_archive / "archive-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        # Persist identities/versions in the authoritative archive. A cache
        # rebuild must never manufacture a new revision or lose an old ID.
        active_analysis = mutated_archive / manifest["analysis_path"]
        payload = ASSET.parse_analysis(active_analysis, target_name)
        for claim in payload.get("claims", []):
            for ref in claim.get("source_refs", []) or []:
                if not isinstance(ref, dict):
                    continue
                ref_path = str(ref.get("path", ""))
                matches = [s for s in manifest.get("sources", [])
                           if ref_path and ((Path(ref_path).is_absolute() and Path(s.get("original_path", "")).resolve() == Path(ref_path).resolve())
                           or str(s.get("original_path", "")).endswith("/" + ref_path))]
                if len(matches) == 1:
                    source = matches[0]
                    bucket = "documents" if source["source_type"] == "document" else "core-source"
                    ref["archive_source_path"] = "sources/" + bucket + "/" + source["path"]
                    ref.setdefault("content_hash", source["sha256"])
        payload = LIFECYCLE.prepare_analysis(payload, previous_analysis, manifest["project_id"], ASSET.now())
        canonical_analysis = mutated_archive / "analysis" / "project-analysis.json"
        ARCHIVE.atomic_write_json(canonical_analysis, payload)
        manifest["analysis_path"] = str(canonical_analysis.relative_to(mutated_archive))
        knowledge_dir = mutated_archive / "knowledge"
        knowledge_dir.mkdir(parents=True, exist_ok=True)
        domain_profile_path = knowledge_dir / "domain-profile.json"
        ARCHIVE.atomic_write_json(domain_profile_path, normalized["domain_profile"])
        manifest["domain_profile_path"] = str(domain_profile_path.relative_to(mutated_archive))
        if knowledge_payload is not None:
            market_path = knowledge_dir / "market-practices.json"
            ARCHIVE.atomic_write_json(market_path, knowledge_payload)
            manifest["market_practices_path"] = str(market_path.relative_to(mutated_archive))
            result["knowledge_validation"] = knowledge_validation
        elif manifest.get("market_practices_path"):
            # A refreshed project profile invalidates prior external research
            # unless a new validated bundle is submitted in this transaction.
            # update_archive has already snapshotted the old knowledge tree.
            stale_market = Path(manifest["market_practices_path"])
            if not stale_market.is_absolute():
                stale_market = mutated_archive / stale_market
            if stale_market.is_file():
                stale_market.unlink()
            manifest.pop("market_practices_path", None)
        ARCHIVE.atomic_write_json(manifest_path, manifest)
        store = ASSET.AssetStore()
        result["indexed_repositories"] = store.sync_archive_manifest(manifest)
        # Expose the actual archive identity (especially important when a renamed
        # project is explicitly confirmed as an update to an older archive).
        result["project_id"] = manifest.get("project_id", result.get("project_id"))
        result["project_name"] = manifest.get("project_name", result.get("project_name"))
        result["project_input"]["project_id"] = result["project_id"]
        with store.connect() as conn:
            result["indexed_claims"] = conn.execute(
                "SELECT COUNT(*) FROM claims c JOIN repositories r ON r.id=c.repository_id WHERE r.project_id=?",
                (result["project_id"],),
            ).fetchone()[0]
        result["index_database"] = str(store.db_path)
        return result
    except Exception:
        if mutated_archive is not None:
            if backup_archive is not None and backup_archive.is_dir():
                shutil.rmtree(mutated_archive, ignore_errors=True)
                shutil.copytree(backup_archive, mutated_archive)
            elif not update:
                shutil.rmtree(mutated_archive, ignore_errors=True)
        # Restore the derived index from the authoritative post-rollback tree.
        try:
            ASSET.AssetStore().rebuild_from_archives(ARCHIVE.archive_root())
        except Exception:
            pass
        raise
    finally:
        if backup_root is not None:
            shutil.rmtree(backup_root, ignore_errors=True)


def deposit_project(project_name, analysis, documents, core_source=(), *,
                    update=False, update_project_name=None, knowledge=None):
    """Serialize archive mutations and journal a rollback copy before writes."""
    root = ARCHIVE.archive_root()
    with TRANSACTION.archive_lock(root):
        recovered = TRANSACTION.recover(root)
        if recovered:
            ASSET.AssetStore().rebuild_from_archives(root)
        target = ARCHIVE.archive_folder_for(update_project_name or project_name, allow_existing=True)
        with TRANSACTION.deposit_transaction(root, target):
            result = _deposit_project(project_name, analysis, documents, core_source,
                                      update=update, update_project_name=update_project_name,
                                      knowledge=knowledge)
        result["recovered_interrupted_deposit"] = recovered
        return result


def confirm_claim(project_id: str, claim_id: str, question: str, answer: str,
                  status: str, expected_revision: int) -> dict:
    """Update an existing confirmation in the archive, with optimistic locking."""
    if status not in {"confirmed", "rejected", "open"} or not answer.strip():
        raise ValueError("confirmation requires an answer and a valid status")
    root = ARCHIVE.archive_root()
    with TRANSACTION.archive_lock(root):
        if TRANSACTION.recover(root):
            ASSET.AssetStore().rebuild_from_archives(root)
        manifests = [m for m in ARCHIVE.list_archives() if m.get("project_id") == project_id]
        if len(manifests) != 1:
            raise ValueError("project_id must resolve to exactly one archive")
        manifest = manifests[0]
        folder = Path(manifest["archive_path"])
        analysis_path = (folder / manifest["analysis_path"]).resolve()
        if not analysis_path.is_relative_to(folder.resolve()):
            raise ValueError("analysis path escapes project archive")
        previous = ASSET.parse_analysis(analysis_path)
        payload = json.loads(json.dumps(previous))
        matches = [c for c in payload.get("claims", []) if c.get("id") == claim_id]
        if len(matches) != 1:
            raise ValueError("claim_id must resolve to exactly one claim")
        claim = matches[0]
        if int(claim.get("revision", 1)) != expected_revision:
            raise ValueError("claim revision changed; browse again before confirming")
        entries = claim.get("confirmation_questions", claim.get("confirmations", [])) or []
        entries = [dict(e) if isinstance(e, dict) else {"question": str(e)} for e in entries]
        matches = [e for e in entries if (e.get("question") or e.get("text")) == question]
        if len(matches) != 1:
            raise ValueError("question must match exactly one existing confirmation")
        matches[0].update(question=question, answer=answer, status=status)
        claim.pop("confirmation_questions", None)
        claim["confirmations"] = entries
        payload = LIFECYCLE.prepare_analysis(payload, previous, project_id, ASSET.now())
        with TRANSACTION.deposit_transaction(root, folder):
            history = folder / "analysis" / "history"
            history.mkdir(parents=True, exist_ok=True)
            from datetime import datetime, timezone
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
            shutil.copy2(analysis_path, history / f"project-analysis-confirmation-{stamp}{analysis_path.suffix}")
            canonical = folder / "analysis" / "project-analysis.json"
            ARCHIVE.atomic_write_json(canonical, payload)
            manifest["analysis_path"] = str(canonical.relative_to(folder))
            manifest["updated_at"] = ASSET.now()
            ARCHIVE.atomic_write_json(folder / "archive-manifest.json", manifest)
            ASSET.AssetStore().sync_archive_manifest(manifest)
        return {"status": "updated", "project_id": project_id, "claim_id": claim_id,
                "revision": next(c["revision"] for c in payload["claims"] if c["id"] == claim_id)}
