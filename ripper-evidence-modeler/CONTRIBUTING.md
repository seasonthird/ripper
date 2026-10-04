# Contributing

Thank you for considering a contribution to Ripper Evidence Modeler. This project is a Codex skill, so most changes are improvements to instructions, reference rules, examples, or metadata.

## Contribution Principles

- Keep the skill practical and resume-focused.
- Prefer concise rules that improve output quality.
- Add examples only when they teach a reusable distinction.
- Avoid unsupported claims, exaggerated resume wording, or fabricated metrics.
- Do not add private company data, customer names, tokens, internal URLs, or unreleased project details.

## Good First Contributions

- Add a realistic weak-vs-strong resume example.
- Improve role-specific focus rules in `references/role_focus_map.md`.
- Add clearer risk wording in `references/resume_risk_rules.md`.
- Improve final resume polish rules in `references/resume_style_rules.md`.
- Clarify evidence labels in `references/project_signal_patterns.md`.

## Project Layout

```text
SKILL.md                         Core workflow and resource routing
agents/openai.yaml               UI-facing skill metadata
references/*.md                  Detailed writing rules and examples
```

Keep `SKILL.md` short. Put detailed role guidance, examples, and style rules in `references/`.

## Development Workflow

1. Fork or branch from the latest main branch.
2. Make a focused change.
3. Validate the skill structure.
4. Review whether the change creates duplicated or conflicting guidance.
5. Open a pull request with a clear explanation and, when useful, a before/after example.

If you have Codex's skill validation script available, run:

```bash
python3 /path/to/skill-creator/scripts/quick_validate.py /path/to/ripper-evidence-modeler
```

## Pull Request Checklist

Before opening a pull request, check:

- The change is scoped to resume writing or skill usability.
- `SKILL.md` still has valid YAML frontmatter.
- New guidance does not encourage fabricated metrics or overclaiming.
- Examples do not contain sensitive or proprietary information.
- Similar rules are not duplicated across multiple files.
- The README remains accurate after the change.

## Style Guide

- Use clear, direct Markdown.
- Prefer concrete examples over abstract advice.
- Use Chinese examples for resume wording when possible.
- Use English headings when they match the existing reference style.
- Avoid buzzwords unless they are being explicitly discouraged.

## Reporting Problems

Open an issue for:

- Incorrect or risky resume wording.
- Missing role directions.
- Conflicting reference rules.
- Output formats that are too verbose or too vague.
- Confidentiality or privacy concerns.

Do not include private project code or sensitive personal information in public issues.
