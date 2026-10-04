# Structured Asset Analysis Contract

Read this contract for every deposit. Write `project-analysis.json` as the canonical machine-readable analysis; optionally write a Markdown review beside it for humans.

## Required Shape

```json
{
  "schema_version": 1,
  "project_id": "project_...",
  "project_name": "Project Name",
  "claims": [
    {
      "id": "claim_stable-id",
      "title": "Independent engineering result",
      "statement": "What the submitted material supports",
      "status": "confirmed|code-verifiable|inferred|planned|blocked|unknown",
      "realization_status": "implemented|partial|designed|derived|hypothetical|unknown",
      "production_status": "confirmed|unknown|not-verified",
      "disclosure_level": "public|internal-safe-after-redaction|restricted",
      "capabilities": ["reliability"],
      "source_refs": [
        {
          "path": "relative/source/path",
          "symbol": "optional symbol",
          "line_start": 1,
          "line_end": 20,
          "claim": "What this source proves"
        }
      ],
      "evidence": [
        {
          "kind": "code|doc|config|test|user|inferred",
          "claim_text": "Evidence statement",
          "confidence": "confirmed|code-verifiable|inferred|planned|blocked|unknown"
        }
      ],
      "related_tests": [],
      "related_config": [],
      "metrics": [],
      "derived_optimizations": [],
      "reconstruction": {},
      "confirmations": [],
      "narrative_unit": {
        "situation": "Context",
        "task": "Task or responsibility boundary",
        "actions": "Mechanisms and decisions",
        "verified_results": "Supported result",
        "status": "draft"
      }
    }
  ]
}
```

## Invariants

- Emit one claim for every independent supported result; never compress the complete project into one summary claim.
- Keep stable IDs when updating the same result. Remove obsolete claims from the current JSON; the archive history preserves prior versions and the index replaces the previous active claim set.
- Prefer project-scoped IDs or a stable `identity_key` for each mechanism. Reuse that identity when changing titles or wording. The deposit pipeline persists `revision`, `created_at`, and `updated_at`; these are derived from the previous archive rather than the SQLite cache. Title matching is only a legacy fallback when the previous title is unique; a changed title without an ID/key is treated as a new result.
- Source references may carry `content_hash` and `archive_source_path`. The pipeline fills these for uniquely matched submitted sources. Reusing an old reference hash after changing a source preserves a stale-evidence warning; only replace the hash after actually reviewing the changed material. Missing hashes mean freshness is unknown, not verified.
- Use relative submitted-source paths where possible. Do not cite the analysis itself when a more precise source exists.
- Put market-informed modules in `derived_optimizations` or `reconstruction`. The index also materializes every validated architecture candidate from `market-practices.json` as an independent `derived` claim.
- Do not mark inferred, designed, derived, or hypothetical work as implemented.
- Keep a Markdown review optional and secondary. Passing only Markdown is a compatibility path that preserves each bullet conservatively but cannot retain complete status, metric, narrative, or evidence structure.
