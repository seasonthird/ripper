"""Canonical project input model shared by collector, archive and indexer."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable


DOCUMENT_EXTENSIONS = {".md", ".pdf"}
EXCLUDED_CORE_DIRS = {".git", ".hg", ".svn", "node_modules", "vendor", ".venv", "venv", "dist", "build", "target", ".cache", "__pycache__"}
EXCLUDED_CORE_SUFFIXES = {".pyc", ".pyo", ".class", ".o", ".so", ".dylib", ".dll", ".bin", ".zip", ".tar", ".gz", ".db", ".sqlite"}
SENSITIVE_CORE_DIRS = {".aws", ".ssh", ".gnupg", "credentials", "secrets", "private-keys"}
SENSITIVE_CORE_NAMES = {
    ".npmrc", ".pypirc", "credentials.json", "service-account.json",
    "secrets.yaml", "secrets.yml", "secret.yaml", "secret.yml",
    "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519",
}
SENSITIVE_CORE_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".jks", ".keystore"}
MAX_CORE_FILE_BYTES = 2 * 1024 * 1024


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_sensitive_core_file(path: Path, root: Path) -> bool:
    try:
        parts = {part.casefold() for part in path.relative_to(root).parts[:-1]} if root.is_dir() else set()
    except ValueError:
        return True
    name = path.name.casefold()
    return (
        bool(parts & SENSITIVE_CORE_DIRS)
        or name == ".env"
        or name.startswith(".env.")
        or name in SENSITIVE_CORE_NAMES
        or path.suffix.casefold() in SENSITIVE_CORE_SUFFIXES
    )


@dataclass(frozen=True)
class ProjectSource:
    path: str
    source_role: str  # document | core-source
    sha256: str
    size_bytes: int


@dataclass
class ProjectInput:
    project_name: str
    documents: list[ProjectSource] = field(default_factory=list)
    core_source: list[ProjectSource] = field(default_factory=list)
    project_id: str | None = None
    omitted_core_source: list[str] = field(default_factory=list)

    @property
    def sources(self) -> list[ProjectSource]:
        return self.documents + self.core_source

    def to_dict(self) -> dict:
        return {
            "project_name": self.project_name,
            "project_id": self.project_id,
            "documents": [asdict(item) for item in self.documents],
            "core_source": [asdict(item) for item in self.core_source],
            "sources": [asdict(item) for item in self.sources],
            "document_count": len(self.documents),
            "core_source_count": len(self.core_source),
            "hashes": [item.sha256 for item in self.sources],
            "omitted_core_source": self.omitted_core_source,
        }


def _expand(items: Iterable[Path], role: str) -> tuple[list[ProjectSource], list[str]]:
    result: list[ProjectSource] = []
    omitted: list[str] = []
    for raw in items:
        submitted = Path(raw).expanduser()
        if role == "core-source" and submitted.is_symlink():
            omitted.append(str(submitted.absolute()))
            continue
        path = submitted.resolve()
        if not path.exists():
            raise ValueError(f"source does not exist: {path}")
        candidates = [path] if path.is_file() else sorted(item for item in path.rglob("*") if item.is_file())
        for item in candidates:
            if role == "document" and item.suffix.lower() not in DOCUMENT_EXTENSIONS:
                raise ValueError(f"document source must be .md or .pdf: {item}")
            if role == "core-source":
                relative_parts = set(item.relative_to(path).parts) if path.is_dir() else set()
                if (
                    item.is_symlink()
                    or relative_parts & EXCLUDED_CORE_DIRS
                    or item.suffix.lower() in EXCLUDED_CORE_SUFFIXES
                    or is_sensitive_core_file(item, path)
                    or item.stat().st_size > MAX_CORE_FILE_BYTES
                ):
                    omitted.append(str(item))
                    continue
            result.append(ProjectSource(str(item), role, file_hash(item), item.stat().st_size))
    return result, omitted


def build_project_input(project_name: str, documents: Iterable[Path], core_source: Iterable[Path] = ()) -> ProjectInput:
    if not str(project_name).strip():
        raise ValueError("project_name is required")
    docs, omitted_docs = _expand(documents, "document")
    if not docs:
        raise ValueError("at least one .md or .pdf document is required")
    core, omitted_core = _expand(core_source, "core-source")
    return ProjectInput(project_name=str(project_name).strip(), documents=docs, core_source=core, omitted_core_source=omitted_docs + omitted_core)
