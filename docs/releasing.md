# Preparing a source release

The working folder can contain private runtime state. A source release contains
code, Skill instructions, documentation, licenses, tests and synthetic examples.

The current bundle version is **0.1.0**, recorded in the root `VERSION` file.
Before preparing a new version, update `VERSION`, both README version labels and
`CHANGELOG.md` together. Bundle versions are independent of claim revisions and
storage schema versions. Keep all root, component and font license texts.

```bash
python3 tools/package_source.py
```

The builder uses an explicit root allowlist, omits environments/caches/private
output and upstream administration folders, rejects symbolic links and scans
text for common credential/internal-path patterns. It creates:

```text
dist/ripper-source.tar.gz
dist/ripper-source-manifest.json
```

The manifest records the bundle version, included paths and SHA-256 hashes.
The archive contains `VERSION` and `CHANGELOG.md`. The archive is for source
publication, not a backup of `~/Ripper/archives/`. A passing scan is a useful
check, not a proof that arbitrary text contains no confidential information.

Before publishing:

1. Inspect the included-path manifest and the README installation instructions.
2. Run the demo and deterministic tests from the extracted source package.
3. Retain root/component/font licenses and third-party notices.
4. Check any additional examples or screenshots for private content.

For the first GitHub release, tag the verified release commit `v0.1.0` and
create a corresponding GitHub Release with the changelog summary and known
limitations. Attach the source package and its manifest. Version preparation
does not itself create a Git tag or publish a Release.

When creating a repository from a personal workspace, start from the extracted
clean source package. Do not run a blanket `git add .`
on a personal workspace without inspecting the staged paths. An ignore rule
cannot remove data that was already committed. Publishing to GitHub remains a
separate action.

Local exclusions include `ripper-output/`, `zip_backup/`, `.myflicker/`,
`.codeflicker/`, `.venv/`, caches and nested upstream `.github/` administration.
They are retained locally; the Ripper root `.github/` defines the new project CI.
