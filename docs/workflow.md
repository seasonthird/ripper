# Lifecycle workflow

All commands below run from the complete repository root with Python 3.10+.
In an installed runtime, `ripper-collector/bin/ripper-collector-exec ripper`
can replace `python3 ripper/scripts/ripper.py`.

## Inspect and deposit

Ask the agent to follow [the unified Skill](../ripper/SKILL.md). The Collector
inspects submitted Markdown/PDF documents and selected source; the Evidence
Modeler produces [canonical analysis](../ripper-evidence-modeler/references/asset_analysis_contract.md).
The CLI stores an existing analysis; it does not automatically run the model.

```bash
python3 ripper/scripts/ripper.py deposit "Project Name" \
  --analysis /absolute/project-analysis.json \
  --source /absolute/design.md --core /absolute/src
```

Exit `2` and `confirmation_required` mean a likely duplicate was found. Resolve
which project is being updated, then use the user's existing authorization or
obtain that decision before retrying:

```bash
python3 ripper/scripts/ripper.py deposit "Project Name" \
  --analysis /absolute/updated-analysis.json --source /absolute/design.md \
  --update --update-project-name "Existing Project Name"
```

Keep the same claim ID or `identity_key` for the same result. Updates replace
the current analysis while preserving history. Re-submitted source paths replace
their active copies; unchanged sources are retained. Do not use this operation
as an implicit deletion command for sources omitted from the new invocation.

## Browse and confirm

```bash
python3 ripper/scripts/ripper.py list
python3 ripper/scripts/ripper.py browse --capability reliability
python3 ripper/scripts/ripper.py confirm PROJECT_ID CLAIM_ID \
  --question "Exact question from browse" --answer "User-provided answer" \
  --revision 1 --status confirmed
```

Use the actual revision from `browse`. A stale revision fails without applying
the answer. Statuses are `open`, `confirmed` and `rejected`. Answers persist in
the archive and survive index deletion. Confirming a question does not
implicitly change implementation/production/impact fields; update the analysis
with the corresponding evidence when those facts change.

## Export and verify

```bash
python3 ripper/scripts/ripper.py export star "Backend Engineer"
python3 ripper/scripts/ripper.py export resume "Backend Engineer" --perspective team
python3 ripper/scripts/ripper.py verify-export /absolute/output.manifest.json
```

Export types: `star`, `resume`, `promotion`, `yearly-review`, `handover`, `blog`.
Outputs are Markdown drafts, with a local audit manifest. Optional LaTeX/PDF
rendering belongs to [ripper-cv](../ripper-cv/skills/ripper-cv/SKILL.md).

The manifest snapshots selected claims, evidence and confirmations, and hashes
the rendered text. Verification establishes file integrity; it does not prove
that the underlying engineering claim is true. The manifest can contain private
paths/answers and should not accompany an externally shared draft without review.

## Diagnose and recover

```bash
python3 ripper/scripts/ripper.py doctor
python3 ripper/scripts/ripper.py recover
python3 ripper/scripts/ripper.py rebuild
```

- `doctor` validates archives using a disposable index and reports the live cache
  status, stale evidence and foreign-key violations. It can restore a pending
  journal before inspection; it is not a completely read-only command.
- `recover` restores an interrupted operation and rebuilds the index when recovery
  occurred. It does not repair arbitrary missing archive files.
- `rebuild` validates the archive first and replaces the cache after success. A
  damaged database is preserved in a diagnostic copy.

A missing analysis/source/knowledge file stops processing. Restore it from backup
and retry; do not silently reinterpret the project as empty. Busy-lock errors
mean another operation is active. Wait and retry without deleting the lock file.

Archive journals cover process interruption. Back up the archive directory to
protect against machine power loss, filesystem corruption and disk failure.
