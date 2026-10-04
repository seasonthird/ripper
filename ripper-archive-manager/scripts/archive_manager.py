"""Filesystem-first project archive manager for Ripper."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path


# Cross-host, user-visible data location. Keep archives outside the Skill
# installation so upgrading/removing a Skill cannot remove user data.
ARCHIVE_HOME = Path.home() / "Ripper"


def archive_root() -> Path:
    # Stable user-level location, independent of the current project or Skill
    # installation directory.
    path = ARCHIVE_HOME / "archives"
    path.mkdir(parents=True, exist_ok=True)
    return path


def slug(value: str) -> str:
    """Return a readable, filesystem-safe and collision-resistant slug.

    Keep Unicode letters/numbers (so Chinese project names remain legible),
    while replacing punctuation/whitespace.  A short digest is appended for
    names that would otherwise collapse to the same slug (for example names
    made only of punctuation).
    """
    value = str(value).strip()
    normalized = re.sub(r"[^\w\-]+", "-", value.casefold(), flags=re.UNICODE)
    normalized = re.sub(r"-+", "-", normalized).strip("-_ ")
    if not normalized:
        normalized = "project"
    # Avoid path names becoming unreasonably long while preserving identity.
    max_length = 80
    if len(normalized) > max_length:
        normalized = normalized[:max_length].rstrip("-")
    return normalized


def project_id(project_name: str) -> str:
    canonical = re.sub(r"\s+", " ", str(project_name).strip().casefold())
    return "project_" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def atomic_write_json(path: Path, payload: dict) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


CORE_EXCLUDED_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "vendor", ".venv", "venv",
    "dist", "build", "target", ".cache", "__pycache__",
}
CORE_EXCLUDED_SUFFIXES = {
    ".pyc", ".pyo", ".class", ".o", ".so", ".dylib", ".dll", ".bin",
    ".zip", ".tar", ".gz", ".db", ".sqlite",
}
CORE_SENSITIVE_DIRS = {".aws", ".ssh", ".gnupg", "credentials", "secrets", "private-keys"}
CORE_SENSITIVE_NAMES = {
    ".npmrc", ".pypirc", "credentials.json", "service-account.json",
    "secrets.yaml", "secrets.yml", "secret.yaml", "secret.yml",
    "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519",
}
CORE_SENSITIVE_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".jks", ".keystore"}
CORE_MAX_FILE_BYTES = 2 * 1024 * 1024


def is_sensitive_core_file(path: Path, root: Path) -> bool:
    try:
        parts = {part.casefold() for part in path.relative_to(root).parts[:-1]} if root.is_dir() else set()
    except ValueError:
        return True
    name = path.name.casefold()
    return (
        bool(parts & CORE_SENSITIVE_DIRS)
        or name == ".env"
        or name.startswith(".env.")
        or name in CORE_SENSITIVE_NAMES
        or path.suffix.casefold() in CORE_SENSITIVE_SUFFIXES
    )


def files_under(path: Path, *, core: bool = False) -> list[Path]:
    """Expand a source path, applying the same bounded-core policy everywhere."""
    candidates = [path] if path.is_file() else sorted(item for item in path.rglob("*") if item.is_file())
    if not core:
        return candidates
    result: list[Path] = []
    for item in candidates:
        relative_parts = set(item.relative_to(path).parts) if path.is_dir() else set()
        if (
            item.is_symlink()
            or relative_parts & CORE_EXCLUDED_DIRS
            or item.suffix.lower() in CORE_EXCLUDED_SUFFIXES
            or is_sensitive_core_file(item, path)
        ):
            continue
        try:
            if item.stat().st_size > CORE_MAX_FILE_BYTES:
                continue
        except OSError:
            continue
        result.append(item)
    return result


def validate_document(path: Path) -> None:
    if not path.is_file() or path.suffix.lower() not in {".md", ".pdf"}:
        raise ValueError(f"document source must be an existing .md or .pdf file: {path}")


def manifest_path(folder: Path) -> Path:
    return folder / "archive-manifest.json"


def archive_folder_for(project_name: str, *, allow_existing: bool = False, requested_project_id: str | None = None) -> Path:
    """Resolve a stable archive folder without collapsing distinct names."""
    root = archive_root()
    requested_project_id = requested_project_id or project_id(project_name)
    base = root / slug(project_name)
    if not base.exists():
        return base
    if manifest_path(base).exists():
        try:
            existing = read_manifest(base)
            if existing.get("project_id") == requested_project_id:
                return base
        except (OSError, json.JSONDecodeError):
            pass
    candidate = root / f"{slug(project_name)}-{requested_project_id.removeprefix('project_')[:10]}"
    if allow_existing and manifest_path(candidate).exists():
        try:
            if read_manifest(candidate).get("project_id") == requested_project_id:
                return candidate
        except (OSError, json.JSONDecodeError):
            pass
    return candidate


def read_manifest(folder: Path) -> dict:
    return json.loads(manifest_path(folder).read_text(encoding="utf-8"))


def analysis_summary(manifest: dict) -> dict:
    analysis = Path(manifest.get("analysis_path", ""))
    if not analysis.is_absolute() and manifest.get("archive_path"):
        analysis = Path(manifest["archive_path"]) / analysis
    if not analysis.is_file():
        return {"analysis_available": False, "themes": []}
    try:
        raw_text = analysis.read_text(encoding="utf-8")
        if analysis.suffix.lower() == ".json":
            try:
                payload = json.loads(raw_text)
            except json.JSONDecodeError:
                payload = None
            claims = payload.get("claims", []) if isinstance(payload, dict) else payload if isinstance(payload, list) else []
            if payload is not None:
                return {
                    "analysis_available": True,
                    "themes": [str(item.get("title") or item.get("name")) for item in claims if isinstance(item, dict)][:8],
                    "highlights": [str(item.get("statement") or item.get("description")) for item in claims if isinstance(item, dict)][:5],
                    "summary": str(claims[0].get("statement", ""))[:240] if claims and isinstance(claims[0], dict) else "",
                    "source_types": sorted({item.get("source_type") for item in manifest.get("sources", []) if item.get("source_type")}),
                    "has_documents": bool(manifest.get("document_count")),
                    "has_core_source": bool(manifest.get("core_source_count")),
                }
        lines = raw_text.splitlines()
    except OSError:
        return {"analysis_available": False, "themes": []}
    headings = [line.lstrip("# ").strip() for line in lines if line.startswith("##") and line.lstrip("# ").strip()]
    highlights = [line.lstrip("- *").strip() for line in lines if line.startswith(("- ", "* ")) and line[2:].strip()]
    intro = next((line.strip() for line in lines if line.strip() and not line.startswith("#") and not line.startswith(("- ", "* "))), "")
    source_types = sorted({item.get("source_type") for item in manifest.get("sources", []) if item.get("source_type")})
    return {
        "analysis_available": True,
        "themes": headings[:8],
        "highlights": highlights[:5],
        "summary": intro[:240],
        "source_types": source_types,
        "has_documents": bool(manifest.get("document_count")),
        "has_core_source": bool(manifest.get("core_source_count")),
    }


def source_records(paths: list[Path], source_type: str) -> list[dict]:
    records = []
    for source in paths:
        if not source.exists():
            raise ValueError(f"source does not exist: {source}")
        for item in files_under(source, core=source_type == "core-source"):
            records.append({"path": str(item), "name": item.name, "source_type": source_type, "sha256": sha256(item), "size_bytes": item.stat().st_size})
    return records


def list_archives() -> list[dict]:
    result = []
    for folder in sorted(archive_root().iterdir()):
        if folder.is_dir() and manifest_path(folder).exists():
            try:
                manifest = read_manifest(folder)
            except (OSError, json.JSONDecodeError):
                # One damaged archive must not make the archive browser unusable.
                continue
            manifest["archive_path"] = str(folder)
            manifest.update(analysis_summary(manifest))
            manifest.update(knowledge_summary(manifest))
            result.append(manifest)
    return result


def knowledge_summary(manifest: dict) -> dict:
    """Read compact direction/candidate metadata without rescanning sources."""
    folder = Path(manifest.get("archive_path", ""))
    result = {
        "has_domain_profile": False,
        "has_market_practices": False,
        "project_directions": [],
        "architecture_candidates": [],
    }
    for key, flag in (("domain_profile_path", "has_domain_profile"), ("market_practices_path", "has_market_practices")):
        relative = manifest.get(key)
        if not relative:
            continue
        path = Path(relative)
        if not path.is_absolute():
            path = folder / path
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        result[flag] = True
        if key == "market_practices_path":
            result["project_directions"] = [
                item.get("name") for item in payload.get("project_direction_candidates", [])
                if isinstance(item, dict) and item.get("name")
            ]
            result["architecture_candidates"] = [
                item.get("variant") for item in payload.get("architecture_candidates", [])
                if isinstance(item, dict) and item.get("variant")
            ]
        elif not result["project_directions"]:
            result["project_directions"] = [
                item.get("name") for item in payload.get("direction_candidates", [])
                if isinstance(item, dict) and item.get("name")
            ]
    return result


def archive_overview(manifest: dict) -> dict:
    """Small user-facing listing record; source details stay in the manifest."""
    return {
        "project_id": manifest.get("project_id"),
        "project_name": manifest.get("project_name"),
        "slug": manifest.get("slug"),
        "archive_path": manifest.get("archive_path"),
        "created_at": manifest.get("created_at"),
        "updated_at": manifest.get("updated_at"),
        "document_count": manifest.get("document_count", 0),
        "core_source_count": manifest.get("core_source_count", 0),
        "source_types": manifest.get("source_types", []),
        "themes": manifest.get("themes", []),
        "highlights": manifest.get("highlights", []),
        "summary": manifest.get("summary", ""),
        "omitted_core_source_count": len(manifest.get("omitted_core_source", [])),
        "has_domain_profile": manifest.get("has_domain_profile", False),
        "has_market_practices": manifest.get("has_market_practices", False),
        "project_directions": manifest.get("project_directions", []),
        "architecture_candidates": manifest.get("architecture_candidates", []),
    }


def find_duplicates(paths: list[Path], project_name: str | None = None, core_paths: list[Path] | None = None) -> list[dict]:
    if core_paths is None:
        # The standalone diagnostic has no explicit role flags. Treat only
        # submitted Markdown/PDF files as documents; folders and all other
        # files use the bounded core-source policy so secrets and symlinks are
        # never read merely to compute duplicate hashes.
        documents = [path for path in paths if path.is_file() and path.suffix.lower() in {".md", ".pdf"}]
        core = [path for path in paths if path not in documents]
    else:
        documents = paths
        core = core_paths
    incoming = source_records(documents, "document") + source_records(core, "core-source")
    incoming_hashes = {item["sha256"] for item in incoming}
    incoming_names = {item["name"].lower() for item in incoming}
    incoming_paths = {str(Path(item["path"])).lower() for item in incoming}
    matches = []
    for manifest in list_archives():
        existing = manifest.get("sources", [])
        overlap_hashes = sorted(incoming_hashes & {item.get("sha256") for item in existing})
        overlap_names = sorted(incoming_names & {item.get("name", "").lower() for item in existing})
        existing_paths = {str(Path(item.get("original_path", item.get("path", "")))).lower() for item in existing}
        overlap_paths = sorted(incoming_paths & existing_paths)
        name_match = bool(project_name and slug(project_name) == manifest.get("slug"))
        generic_names = {"readme.md", "readme.markdown", "index.md"}
        meaningful_name_overlap = bool(set(overlap_names) - generic_names)
        if overlap_hashes or meaningful_name_overlap or overlap_paths or name_match:
            if overlap_hashes:
                match_type, confidence = "hash", "high"
            elif overlap_paths:
                match_type, confidence = "path", "high"
            elif name_match:
                match_type, confidence = "project-name", "medium"
            else:
                # Basename overlap is only a candidate; generic names such as
                # README.md are deliberately low confidence.
                confidence = "medium"
                match_type = "name"
            matches.append({
                "project_name": manifest.get("project_name"),
                "archive_path": manifest.get("archive_path"),
                "project_id": manifest.get("project_id"),
                "match_type": match_type,
                "confidence": confidence,
                "matching_hashes": overlap_hashes,
                "matching_names": overlap_names,
                "matching_paths": overlap_paths,
            })
    return matches


def prepare_input(project_name: str, documents: list[Path], core: list[Path]) -> dict:
    for document in documents:
        validate_document(document)
    for source in core:
        if not source.exists():
            raise ValueError(f"source does not exist: {source}")
    document_records = source_records(documents, "document")
    core_records = source_records(core, "core-source")
    all_sources = document_records + core_records
    return {
        "project_id": project_id(project_name),
        "project_name": project_name,
        "slug": slug(project_name),
        "sources": all_sources,
        "document_count": len(document_records),
        "core_source_count": len(core_records),
        "duplicate_matches": find_duplicates(documents, project_name, core),
    }


def copy_sources(sources: list[Path], destination: Path, source_type: str, omitted: list[str] | None = None) -> list[dict]:
    destination.mkdir(parents=True, exist_ok=True)
    records = []
    for source in sources:
        if not source.exists():
            raise ValueError(f"source does not exist: {source}")
        all_items = files_under(source)
        selected_items = files_under(source, core=source_type == "core-source")
        if source_type == "core-source" and omitted is not None:
            omitted.extend(str(item) for item in all_items if item not in set(selected_items))
        for item in selected_items:
            relative = Path(item.name) if source.is_file() else item.relative_to(source)
            target = destination / relative
            if target.exists():
                # Preserve the first source's convenient path, but make every
                # subsequent same-named source collision-safe and auditable.
                prefix = re.sub(r"[^\w\-]+", "-", source.parent.name.casefold(), flags=re.UNICODE).strip("-") or "source"
                target = destination / prefix / relative.name
                if target.exists():
                    target = target.with_name(f"{target.stem}-{sha256(item)[:10]}{target.suffix}")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)
            records.append({"path": str(target.relative_to(destination)), "original_path": str(item), "name": item.name, "source_type": source_type, "sha256": sha256(target), "size_bytes": target.stat().st_size})
    return records


def archived_source_path(folder: Path, record: dict) -> Path:
    """Resolve one manifest source record to its active archived file."""
    bucket = "documents" if record.get("source_type") == "document" else "core-source"
    source = folder / "sources" / bucket / str(record.get("path", ""))
    if not source.resolve().is_relative_to(folder.resolve()):
        raise ValueError("source path escapes project archive")
    return source


def create_archive(project_name: str, analysis: Path, documents: list[Path], core: list[Path], omitted_core_source: list[str] | None = None) -> Path:
    for document in documents:
        validate_document(document)
    if not analysis.is_file():
        raise ValueError(f"analysis file does not exist: {analysis}")
    folder = archive_folder_for(project_name)
    if folder.exists():
        raise ValueError(f"archive already exists; confirm update explicitly: {folder}")
    folder.mkdir(parents=True)
    try:
        omitted = list(omitted_core_source or [])
        document_records = copy_sources(documents, folder / "sources" / "documents", "document")
        core_records = copy_sources(core, folder / "sources" / "core-source", "core-source", omitted)
        analysis_suffix = ".json" if analysis.suffix.lower() == ".json" else ".md"
        analysis_target = folder / "analysis" / f"project-analysis{analysis_suffix}"
        analysis_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(analysis, analysis_target)
        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        manifest = {
            "project_id": project_id(project_name),
            "project_name": project_name,
            "slug": folder.name,
            "archive_path": str(folder),
            "created_at": now,
            "updated_at": now,
            # Keep manifest portable when the fixed archive folder is backed
            # up or moved to another host; paths inside the archive are
            # relative, while source records retain their original paths for
            # duplicate diagnostics.
            "analysis_path": str(analysis_target.relative_to(folder)),
            "sources": document_records + core_records,
            "document_count": len(document_records),
            "core_source_count": len(core_records),
            "omitted_core_source": omitted,
        }
        atomic_write_json(manifest_path(folder), manifest)
        return folder
    except Exception:
        # A failed first deposit must not leave a directory that blocks a
        # retry or looks like a valid project to the browser.
        shutil.rmtree(folder, ignore_errors=True)
        raise


def _update_archive_impl(project_name: str, analysis: Path, documents: list[Path], core: list[Path], omitted_core_source: list[str] | None = None) -> Path:
    for document in documents:
        validate_document(document)
    if not analysis.is_file():
        raise ValueError(f"analysis file does not exist: {analysis}")
    folder = archive_folder_for(project_name, allow_existing=True)
    if not folder.is_dir() or not manifest_path(folder).exists():
        raise ValueError(f"archive does not exist; create it first: {folder}")
    manifest = read_manifest(folder)
    manifest_analysis = Path(manifest.get("analysis_path", ""))
    if manifest_analysis.is_absolute():
        current = manifest_analysis
    elif manifest_analysis.parts:
        current = folder / manifest_analysis
    else:
        current = folder / "analysis" / "project-analysis.md"
    if not current.resolve().is_relative_to(folder.resolve()):
        raise ValueError("analysis path escapes project archive")
    # Validate all source paths before copying or unlinking any active files.
    for record in manifest.get("sources", []):
        archived_source_path(folder, record)
    history = folder / "analysis" / "history"
    history.mkdir(parents=True, exist_ok=True)
    if current.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        shutil.copy2(current, history / f"project-analysis-{stamp}{current.suffix or '.md'}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    old_sources = manifest.get("sources", [])
    if old_sources:
        snapshot = history / f"sources-{stamp}"
        snapshot.mkdir(parents=True, exist_ok=True)
        for item in old_sources:
            old_path = archived_source_path(folder, item)
            if old_path.is_file():
                bucket = "documents" if item.get("source_type") == "document" else "core-source"
                target = snapshot / bucket / item.get("path", old_path.name)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(old_path, target)
    # Domain profiles and researched practices belong to the analyzed input
    # version. Preserve them before the collector writes the refreshed pair.
    knowledge = folder / "knowledge"
    if knowledge.is_dir() and any(item.is_file() for item in knowledge.rglob("*")):
        shutil.copytree(knowledge, history / f"knowledge-{stamp}")
    # Remove active records/files for explicitly re-submitted source paths so
    # the new version replaces them instead of being treated as a collision.
    incoming_paths = {str(item.resolve()) for source in [*documents, *core] for item in files_under(source)}
    retained_sources = []
    for item in old_sources:
        original = item.get("original_path", "")
        try:
            original = str(Path(original).expanduser().resolve())
        except (OSError, RuntimeError):
            original = str(original)
        if original in incoming_paths:
            old_path = archived_source_path(folder, item)
            if old_path.is_file():
                old_path.unlink()
            continue
        retained_sources.append(item)
    omitted = list(omitted_core_source or [])
    document_records = copy_sources(documents, folder / "sources" / "documents", "document")
    core_records = copy_sources(core, folder / "sources" / "core-source", "core-source", omitted)
    analysis_suffix = ".json" if analysis.suffix.lower() == ".json" else ".md"
    next_current = folder / "analysis" / f"project-analysis{analysis_suffix}"
    next_current.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(analysis, next_current)
    if current != next_current and current.is_file():
        current.unlink()
    manifest["analysis_path"] = str(next_current.relative_to(folder))
    # The manifest's sources are the active set. Existing sources are retained
    # when an update supplies no replacement; replaced files are represented by
    # the history snapshot above rather than silently mixed into the active set.
    existing_by_path = {(item.get("source_type"), item.get("path")): item for item in retained_sources}
    for item in document_records + core_records:
        existing_by_path[(item.get("source_type"), item["path"])] = item
    manifest["updated_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    manifest["sources"] = list(existing_by_path.values())
    manifest["document_count"] = sum(1 for item in (folder / "sources" / "documents").glob("**/*") if item.is_file())
    manifest["core_source_count"] = sum(1 for item in (folder / "sources" / "core-source").glob("**/*") if item.is_file())
    if omitted_core_source is not None:
        manifest["omitted_core_source"] = omitted
    atomic_write_json(manifest_path(folder), manifest)
    return folder


def update_archive(project_name: str, analysis: Path, documents: list[Path], core: list[Path], omitted_core_source: list[str] | None = None) -> Path:
    """Update an archive with rollback protection for partial filesystem failures."""
    folder = archive_folder_for(project_name, allow_existing=True)
    if not folder.is_dir() or not manifest_path(folder).exists():
        raise ValueError(f"archive does not exist; create it first: {folder}")
    backup_root = Path(tempfile.mkdtemp(prefix="ripper-update-", dir=str(folder.parent)))
    backup = backup_root / "archive"
    shutil.copytree(folder, backup)
    try:
        return _update_archive_impl(project_name, analysis, documents, core, omitted_core_source)
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        shutil.copytree(backup, folder)
        raise
    finally:
        shutil.rmtree(backup_root, ignore_errors=True)


def deposit(project_name: str, analysis: Path, documents: list[Path], core: list[Path], update: bool = False, omitted_core_source: list[str] | None = None) -> tuple[int, dict]:
    """Complete one create/update deposit transaction.

    Returns ``(0, result)`` on success and ``(2, result)`` when duplicate
    candidates require explicit user confirmation. No archive is changed in
    the latter case.
    """
    if not documents:
        raise ValueError("at least one .md or .pdf document is required")
    for document in documents:
        validate_document(document)
    for source in core:
        if not source.exists():
            raise ValueError(f"source does not exist: {source}")
    matches = find_duplicates(documents, project_name, core)
    if matches and not update:
        return 2, {
            "status": "confirmation_required",
            "project_name": project_name,
            "project_id": project_id(project_name),
            "matches": matches,
            "message": "duplicate project candidates found; rerun with --update after confirming the target project",
        }
    if update:
        folder = update_archive(project_name, analysis, documents, core, omitted_core_source)
        action = "updated"
    else:
        folder = create_archive(project_name, analysis, documents, core, omitted_core_source)
        action = "created"
    actual_manifest = read_manifest(folder)
    return 0, {
        "status": action,
        "project_name": actual_manifest.get("project_name", project_name),
        "project_id": actual_manifest.get("project_id", project_id(project_name)),
        "archive_path": str(folder),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Ripper project archive manager")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    duplicate = sub.add_parser("find-duplicates")
    duplicate.add_argument("sources", nargs="+")
    duplicate.add_argument("--project-name", default=None)
    prepare = sub.add_parser("prepare-input")
    prepare.add_argument("project_name")
    prepare.add_argument("--source", action="append", default=[])
    prepare.add_argument("--core", action="append", default=[])
    create = sub.add_parser("create")
    create.add_argument("project_name")
    create.add_argument("--analysis", required=True)
    create.add_argument("--source", action="append", default=[])
    create.add_argument("--core", action="append", default=[])
    update = sub.add_parser("update")
    update.add_argument("project_name")
    update.add_argument("--analysis", required=True)
    update.add_argument("--source", action="append", default=[])
    update.add_argument("--core", action="append", default=[])
    deposit_parser = sub.add_parser("deposit", help="Validate, deduplicate, and create/update one project archive")
    deposit_parser.add_argument("project_name")
    deposit_parser.add_argument("--analysis", required=True)
    deposit_parser.add_argument("--source", action="append", default=[])
    deposit_parser.add_argument("--core", action="append", default=[])
    deposit_parser.add_argument("--update", action="store_true")
    args = parser.parse_args()

    if args.command == "list":
        print(json.dumps([archive_overview(item) for item in list_archives()], ensure_ascii=False, indent=2))
        return 0
    if args.command == "find-duplicates":
        print(json.dumps(find_duplicates([Path(item).expanduser().resolve() for item in args.sources], args.project_name), ensure_ascii=False, indent=2))
        return 0
    if args.command == "prepare-input":
        print(json.dumps(prepare_input(
            args.project_name,
            [Path(item).expanduser().resolve() for item in args.source],
            [Path(item).expanduser().resolve() for item in args.core],
        ), ensure_ascii=False, indent=2))
        return 0
    if args.command == "deposit":
        code, result = deposit(
            args.project_name,
            Path(args.analysis).expanduser().resolve(),
            [Path(item).expanduser().resolve() for item in args.source],
            [Path(item).expanduser().resolve() for item in args.core],
            args.update,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return code
    if args.command == "update":
        folder = update_archive(
            args.project_name,
            Path(args.analysis).expanduser().resolve(),
            [Path(item).expanduser().resolve() for item in args.source],
            [Path(item).expanduser().resolve() for item in args.core],
        )
    else:
        folder = create_archive(
            args.project_name,
            Path(args.analysis).expanduser().resolve(),
            [Path(item).expanduser().resolve() for item in args.source],
            [Path(item).expanduser().resolve() for item in args.core],
        )
    print(folder)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
