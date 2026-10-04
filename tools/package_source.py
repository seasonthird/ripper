"""Build a clean source release without touching personal runtime files."""
from pathlib import Path
import hashlib
import json
import re
import tarfile

ROOT = Path(__file__).resolve().parents[1]
DIRECTORIES = {"ripper", "ripper-core", "ripper-collector", "ripper-archive-manager",
               "ripper-evidence-modeler", "ripper-exporter", "ripper-cv", "docs", "examples", "tools", ".github"}
FILES = {"README.md", "README.zh-CN.md", "VERSION", "CHANGELOG.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "CONTRIBUTING.md", ".gitignore"}
EXCLUDED_PREFIXES = ("ripper-cv/demo-output.png", "ripper-collector/assets/img/", "ripper-evidence-modeler/assets/readme/")
EXCLUDED = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "internal_notes",
            ".gstack", ".context", "trace_comparison", "samples-issue42", "node_modules", "venv"}
SECRET = re.compile(r"(?:ghp_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9]{32,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|docs\.corp\.|corp\.kuaishou|/Users/linfg)")


def eligible(path):
    if any(path.as_posix().startswith(prefix) for prefix in EXCLUDED_PREFIXES):
        return False
    parts = path.parts
    if len(parts) == 1:
        return path.name in FILES
    if parts[0] not in DIRECTORIES:
        return False
    if any(p in EXCLUDED or p.startswith('.venv') or p.endswith('.egg-info') for p in parts):
        return False
    if any(p.startswith('.') and p != '.gitignore' for p in parts[1:]):
        return False
    if path.suffix.lower() in {'.pyc', '.pyo', '.sqlite', '.db', '.pem', '.key', '.p12', '.pfx'}:
        return False
    if path.name in {'.DS_Store', 'Thumbs.db'}:
        return False
    return True


def collect():
    result = []
    # Walk only allowed roots, pruning environments before traversal.
    import os
    for name in sorted(FILES):
        path = ROOT / name
        if path.is_file():
            result.append(path)
    for name in sorted(DIRECTORIES):
        base = ROOT / name
        if base.is_symlink():
            raise ValueError('source root must not be a symbolic link: ' + name)
        if not base.is_dir():
            continue
        for current, dirs, files in os.walk(base, followlinks=False):
            if any((Path(current) / d).is_symlink() for d in dirs):
                raise ValueError('symbolic-link directory found under source root: ' + str(Path(current).relative_to(ROOT)))
            dirs[:] = sorted(d for d in dirs if eligible((Path(current) / d / '_').relative_to(ROOT)))
            for filename in sorted(files):
                path = Path(current) / filename
                if eligible(path.relative_to(ROOT)):
                    result.append(path)
    return sorted(result)


def build():
    version = (ROOT / 'VERSION').read_text().strip()
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('VERSION must contain a release version such as 0.1.0')
    paths = collect()
    records, violations = [], []
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        if path.is_symlink():
            raise ValueError('symbolic links are not allowed in a source release: ' + relative)
        data = path.read_bytes()
        # Scanner rules themselves contain literals; exclude only this tool's
        # own source from content scanning, not from release inclusion.
        if relative != 'tools/package_source.py':
            try:
                if SECRET.search(data.decode('utf-8')):
                    violations.append(relative)
            except UnicodeDecodeError:
                pass
        records.append({'path': relative, 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)})
    if violations:
        raise ValueError('review sensitive-looking content before packaging: ' + ', '.join(violations))
    if not (ROOT / 'ripper-collector/assets/DejaVu-LICENSE.txt').is_file():
        raise ValueError('bundled font license is missing')
    output = ROOT / 'dist'
    output.mkdir(exist_ok=True)
    archive = output / 'ripper-source.tar.gz'
    temporary = archive.with_suffix('.tmp')
    try:
        with tarfile.open(temporary, 'w:gz') as handle:
            for path in paths:
                info = handle.gettarinfo(str(path), arcname='ripper/' + path.relative_to(ROOT).as_posix())
                info.uid = info.gid = 0
                info.uname = info.gname = ''
                with path.open('rb') as source:
                    handle.addfile(info, source)
        temporary.replace(archive)
    finally:
        temporary.unlink(missing_ok=True)
    manifest = output / 'ripper-source-manifest.json'
    manifest.write_text(json.dumps({'version': version, 'archive': archive.name, 'file_count': len(records), 'files': records}, indent=2) + '\n')
    print(json.dumps({'version': version, 'archive': str(archive), 'manifest': str(manifest), 'file_count': len(records)}, indent=2))


if __name__ == '__main__':
    build()
