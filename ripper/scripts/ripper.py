"""Unified local Ripper CLI. No background services or external writes."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys
import sqlite3
import hashlib


ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    if not spec or not spec.loader:
        raise RuntimeError(f"missing Ripper bundle component: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


PIPELINE = load("ripper_pipeline_cli", ROOT / "ripper-collector/scripts/project_pipeline.py")
EXPORTER = load("ripper_exporter_cli", ROOT / "ripper-exporter/export_assets.py")


def maintain(rebuild=False):
    root = PIPELINE.ARCHIVE.archive_root()
    with PIPELINE.TRANSACTION.archive_lock(root):
        recovered = PIPELINE.TRANSACTION.recover(root)
        # Validate all archives in a disposable index even when the live cache
        # reports current. Never replace the cache with an incomplete archive.
        import tempfile
        with tempfile.TemporaryDirectory(prefix="ripper-doctor-") as directory:
            probe = PIPELINE.ASSET.AssetStore(Path(directory))
            probe.sync_from_archives(root)
            claims = probe.query_claims()
            with probe.connect() as conn:
                violations = [list(r) for r in conn.execute("PRAGMA foreign_key_check")]
            cache_backup = None
            try:
                store = PIPELINE.ASSET.AssetStore()
            except sqlite3.DatabaseError as exc:
                if not rebuild:
                    raise ValueError("local index is damaged; run rebuild to preserve it and restore from validated archives") from exc
                # Archive validation completed before touching the damaged
                # cache. Preserve its bytes for diagnostics; publish the probe.
                import shutil
                import uuid
                assets = PIPELINE.ASSET.assets_root()
                legacy = assets / "ripper-assets.sqlite"
                db_path = legacy if legacy.exists() else assets / ".cache" / "ripper-assets.sqlite"
                cache_backup = str(db_path.with_name(db_path.name + ".corrupt-" + uuid.uuid4().hex))
                shutil.copy2(db_path, cache_backup)
                db_path.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(prefix="ripper-repair-", dir=db_path.parent, delete=False) as staged_file:
                    staged_path = Path(staged_file.name)
                try:
                    shutil.copy2(probe.db_path, staged_path)
                    staged_path.replace(db_path)
                finally:
                    staged_path.unlink(missing_ok=True)
                store = PIPELINE.ASSET.AssetStore()
        if recovered or rebuild:
            store.rebuild_from_archives(root)
        with store.connect() as conn:
            live_violations = [list(r) for r in conn.execute("PRAGMA foreign_key_check")]
        return {**store.index_status(root), "recovered": recovered,
                "rebuilt": recovered or rebuild, "claim_count": len(claims),
                "stale_claim_ids": [c["id"] for c in claims if c["evidence_freshness"] == "stale"],
                "foreign_key_violations": live_violations,
                "archive_projection_violations": violations,
                "damaged_cache_backup": cache_backup}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Ripper asset lifecycle")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("doctor", "recover", "rebuild", "list"):
        sub.add_parser(command)
    browse = sub.add_parser("browse")
    browse.add_argument("--capability", action="append", default=[])
    export = sub.add_parser("export")
    export.add_argument("type", choices=EXPORTER.EXPORT_DIRECTORIES)
    export.add_argument("target")
    export.add_argument("--capability", action="append", default=[])
    export.add_argument("--perspective", choices=("individual", "team"), default="individual")
    deposit = sub.add_parser("deposit")
    deposit.add_argument("name")
    deposit.add_argument("--analysis", required=True)
    deposit.add_argument("--source", action="append", required=True)
    deposit.add_argument("--core", action="append", default=[])
    deposit.add_argument("--knowledge")
    deposit.add_argument("--update", action="store_true")
    deposit.add_argument("--update-project-name")
    confirm = sub.add_parser("confirm")
    confirm.add_argument("project_id")
    confirm.add_argument("claim_id")
    confirm.add_argument("--question", required=True)
    confirm.add_argument("--answer", required=True)
    confirm.add_argument("--status", choices=("confirmed", "rejected", "open"), default="confirmed")
    confirm.add_argument("--revision", type=int, required=True)
    verify = sub.add_parser("verify-export")
    verify.add_argument("manifest")
    args = parser.parse_args(argv)
    try:
        if args.command in {"doctor", "recover", "rebuild"}:
            result = maintain(args.command == "rebuild")
        elif args.command == "list":
            result = PIPELINE.list_project_archives()
        elif args.command == "browse":
            result = EXPORTER.browse(args.capability)
        elif args.command == "deposit":
            result = PIPELINE.deposit_project(args.name, args.analysis, args.source, args.core,
                                             update=args.update, update_project_name=args.update_project_name,
                                             knowledge=args.knowledge)
        elif args.command == "confirm":
            result = PIPELINE.confirm_claim(args.project_id, args.claim_id, args.question,
                                           args.answer, args.status, args.revision)
        elif args.command == "verify-export":
            manifest_path = Path(args.manifest).expanduser().resolve()
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            name = manifest.get("output_file", "")
            if not name or Path(name).name != name:
                raise ValueError("invalid export output_file")
            output = manifest_path.parent / name
            if hashlib.sha256(output.read_bytes()).hexdigest() != manifest.get("output_sha256"):
                raise ValueError("export material hash mismatch")
            result = {"status": "verified", "manifest_path": str(manifest_path), "output_path": str(output)}
        else:
            output, manifest, _ = EXPORTER.render(args.type, args.target, args.capability, args.perspective)
            result = {"status": "exported", "output_path": str(output), "manifest_path": str(manifest)}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if isinstance(result, dict) and result.get("status") == "confirmation_required" else 0
    except (ValueError, OSError, RuntimeError, sqlite3.DatabaseError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
