---
name: ripper-exporter
description: |
  Query Ripper's local asset library and export evidence-backed materials for a
  target need: role-specific STAR stories, resume project descriptions,
  promotion packets, yearly reviews, handovers, technical-blog outlines, or
  project introductions. Use only existing assets by default; never rescan a
  repository unless the asset library reports a concrete evidence gap.
---

# Ripper Exporter

`ripper-exporter` is the **on-demand export branch** of Ripper. It reads the shared asset library and turns discloseable, evidence-backed results from user-submitted sources into a target-specific personal view. Submitted material is treated as the user's career source by policy; evidence, implementation state, production state, and disclosure remain the factual boundaries. It does not mine repositories as its normal flow.

## Shared Asset Root

```bash
RIPPER_ROOT="$(git -C "$PWD" rev-parse --show-toplevel 2>/dev/null || pwd)"
RIPPER_OUTPUT_DIR="${RIPPER_OUTPUT_DIR:-$RIPPER_ROOT/ripper-output}"
ASSET_DB="$RIPPER_OUTPUT_DIR/assets/.cache/ripper-assets.sqlite"
EXPORT_ROOT="$RIPPER_OUTPUT_DIR/exports"
```

Before browsing or exporting, synchronize the local index from the fixed `~/Ripper/archives/` fact source. This makes a new or stale host-local index self-healing. Only report that no assets exist when both the index and archive are empty. Do not inspect arbitrary source folders as an implicit fallback.

Prefer the unified entry `../ripper/scripts/ripper.py browse` or
`../ripper/scripts/ripper.py export <type> <target>`. See
`../ripper/SKILL.md` for durable confirmations, doctor and recovery commands.
The exporter holds the archive lock for the complete selection/render/audit
operation. A lock error means another operation is active; do not bypass it.
Missing archive files cause an explicit failure and preserve the prior index.
Manifests include a claim/evidence/confirmation snapshot and archive fingerprint;
they are local audit artifacts and may contain private source paths and answers.

## Commands

| Command | Purpose | Default output |
|---|---|---|
| `browse [capability]` | List usable assets, evidence gaps, and open confirmations | chat response only |
| `star <role or JD>` | Create role-focused STAR stories | `exports/interview-stars/` |
| `resume <role or JD>` | Create concise, evidence-backed project bullets | `exports/resumes/` |
| `promotion <period>` | Create promotion evidence and narrative | `exports/promotions/` |
| `yearly-review <period>` | Create year-end summary | `exports/yearly-reviews/` |
| `handover <repo/module>` | Create operational handover material | `exports/handovers/` |
| `blog <topic>` | Create a technical-blog outline | `exports/blogs/` |

## Required Query and Safety Rules

1. Query claims through unified `browse` and resolve their `project_id`/archive manifest; filter by requested capabilities, project, period, and target where available. Use unified `export` for rendering; do not bypass its snapshot lock by composing low-level queries.
2. Consider every relevant claim from the user's submitted sources. Never discard an objective result solely because it was produced in a team context or carries a redaction note.
3. Write selected results as part of the user's submitted experience. Choose an individual or team narrative perspective as appropriate. Use `realization_status` (`implemented`, `partial`, `designed`, `derived`, `hypothetical`, `unknown`) to maximize useful wording without collapsing design or theory into completed implementation.
4. Keep the `project_id`, source asset IDs, and evidence IDs for every statement. Never invent metrics or fill a missing result with JD wording.
5. If assets are insufficient, report a structured gap: missing evidence, missing metric, or incomplete implementation. If redaction is needed, report it as a handling note rather than excluding the result.
6. Before writing an output, show the selected claims and exclusions; wait for confirmation when an export would be externally shared.

## Export Manifest

Every exported document must have an adjacent `<name>.manifest.json` containing:

```json
{
  "export_type": "star",
  "target": "AI Platform Engineer",
  "created_at": "ISO-8601",
  "claim_ids": ["claim_..."],
  "evidence_ids": ["evidence_..."],
  "excluded": [
    {"claim_id": "claim_...", "reason": "not used in this export"}
  ],
  "asset_database": "ripper-output/assets/.cache/ripper-assets.sqlite"
}
```

## Material Shapes

### STAR

Each story must retain explicit evidence boundaries:

```markdown
## <Capability / Story Title>

- Situation: verified context only.
- Task: the user's work in the submitted source, expressed from the selected individual or team perspective.
- Action: concrete mechanisms from claim evidence.
- Result: verified metric or code-verifiable result; never convert a mechanism into business impact.
- Evidence: `claim_id`, `evidence_id`, source path.
- Follow-up risk: open confirmation or disclosure concern.
```

### Resume

Use 1–3 bullets per project. Each bullet contains a mechanism, an action, and a verified result or constrained scope. Relevant results from submitted sources may be written as the user's experience. Use `--perspective team` when a team voice is preferred. Do not use `主导`, `上线生产`, percentages, user scale, or business impact without confirmed evidence fields.

### Promotion / Yearly Review / Handover / Blog

Use the same assets but change the organizing lens:

- Promotion: scope, complexity, leadership evidence, and reusable impact.
- Yearly review: time range, goals, actions, verified results, outstanding work.
- Handover: module boundary, dependencies, operations, risks, evidence links.
- Blog: problem, design decisions, mechanisms, tradeoffs, redacted examples, source-safe boundaries.

## Fast Mode

For a request such as “generate STAR for this role now”, first query the library. If required evidence is missing or stale, request approval to deposit only the referenced repository/module/documents. Deposit results must be written to the asset library before generating the requested document.
