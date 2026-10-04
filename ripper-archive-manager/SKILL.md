---
name: ripper-archive-manager
description: Manage Ripper project archives, including source snapshots, analysis, project-only domain profiles, and researched enhancement candidates. Use when depositing one or more .md/.pdf documents, documents plus source code, checking whether a deposit duplicates an existing project, confirming an update to an existing archive, or listing what the user has already deposited.
---

# Ripper Archive Manager

For the full lifecycle, use `../ripper/SKILL.md` and its unified CLI. Normal
writes go through unified `deposit`/`confirm`, and browsing through `list`/`browse`.
These entries coordinate the lock, interruption recovery, archive and index.
The helper examples below are compatibility diagnostics, not alternatives for
normal deposit or update operations.

Keep one human-readable archive folder for every analyzed project. Each archive contains the analysis result, original submitted documents, and a bounded copy of core source files. It is the durable handoff between deposit, later updates, browsing, and export.

## Archive Layout

Use the fixed, user-visible, cross-host location `~/Ripper/archives/`. Do not derive the archive path from the current project directory, current working directory, host product, or Skill installation directory:

```text
~/Ripper/archives/<project-slug>/
├── archive-manifest.json
├── analysis/
│   ├── project-analysis.md
│   └── history/
├── knowledge/
│   ├── domain-profile.json
│   └── market-practices.json
└── sources/
    ├── documents/
    └── core-source/
```

The manifest records project name, timestamps, source hashes, archived paths, the analysis path, and knowledge paths. `domain-profile.json` is a project-material-only direction profile. `market-practices.json` is attributable external reference material with multiple compatible candidates; it is not proof that the historical project implemented those modules. Never store credentials or raw secrets in the manifest.

## Deposit Workflow

1. Normalize the input into one project package: one or more `.md`/`.pdf` documents, optionally plus a source folder or selected source files.
2. Run duplicate detection against existing manifests and source hashes before creating anything.
3. If a likely match exists, show the existing project name and matching sources. Ask whether this is an update to that project. Never silently merge or overwrite an archive.
4. If new, choose a stable project name/slug and create one archive folder.
5. Copy original documents unchanged into `sources/documents/`. For a source folder, automatically omit dependency/build/cache/binary/private-data areas and copy bounded core files into `sources/core-source/`; record every omitted path in `archive-manifest.json` and the analysis.
6. Save the complete structured result to `analysis/project-analysis.json`, including every extracted achievement, evidence reference, implementation state, metric, redaction note and open gap. Treat Markdown only as an optional human review or compatibility input.
7. Always save the generated project-only profile to `knowledge/domain-profile.json`. When enrichment research was performed, validate and save `knowledge/market-practices.json`; reject it before archive mutation if it contains job-search context, stale/unattributed sources, conflicting modules, or fewer than two architecture candidates.
8. Update the manifest atomically and report the archive path and `project_id`.

Structured JSON (`{"claims": [...]}`) is the canonical analysis input. The
collector indexes its claims and evidence/metrics/narratives after the archive
is written. A plain Markdown compatibility input retains every distinct bullet
as a conservative claim, but cannot represent the complete asset contract.

Submitted team results are not filtered by personal ownership. Claims may be
marked `implemented`, `partial`, `designed`, `derived`, `hypothetical`, or
`unknown`; this affects later wording only, so incomplete or theoretical ideas
remain available for maximum extraction and scenario-specific export.

Pass the same `project_id` to every document and repository registration in the query index so all evidence resolves to one project archive.

For an update, preserve the previous analysis, active source snapshot, and knowledge snapshot under `analysis/history/` before replacing the current result. The current manifest contains only active sources and current knowledge paths; a re-submitted path replaces its active copy, while unchanged sources are retained.

## Duplicate Detection

Use exact SHA-256 matches first, then normalized filename/path overlap and project-name similarity. A match is a prompt for confirmation, not proof that the project is identical. When the user confirms “更新工程 X”, update that archive; otherwise create a new archive.

## Listing Existing Deposits

When the user asks what has been deposited, inspect only manifests, analysis summaries, and compact knowledge JSON under `~/Ripper/archives/`. Return project name, last update, source types, document count, core-source count, key themes, inferred project directions, and available architecture-candidate variants. Do not re-scan all source files.

## Helper

Use `ripper-collector`'s `orchestration deposit-project` as the only complete public deposit entry. Use `scripts/archive_manager.py` only for low-level archive inspection, duplicate diagnostics, or a transaction already coordinated by the Collector:

```bash
python3 scripts/archive_manager.py deposit "Project Name" --analysis project-analysis.md --source overview.md --source test-report.pdf --core src/main.py
python3 scripts/archive_manager.py list
python3 scripts/archive_manager.py find-duplicates /path/to/doc.md /path/to/source
python3 scripts/archive_manager.py prepare-input "Project Name" --source /path/to/doc.md --source /path/to/report.pdf --core /path/to/core.py
python3 scripts/archive_manager.py create "Project Name" --analysis analysis.md --source /path/to/doc.md --core /path/to/core.py
```

The low-level `deposit` command validates archive inputs and performs duplicate gating, but it does not generate domain profiles or coordinate the complete asset-index transaction. If it exits with code `2`, inspect the returned matches and ask the user whether to update the named project; the Collector must rerun its complete command with `--update` only after confirmation:

```bash
python3 scripts/archive_manager.py deposit "Project Name" --analysis project-analysis-v2.md --source new-report.pdf --update
```

The helper never deletes archives and never decides an update automatically.
