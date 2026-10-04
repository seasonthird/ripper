# GOLDEN_FIXTURES (legacy PDF compatibility fixtures)

These fixtures belong to the retained PDF/resume compatibility implementation;
they are not examples for the active project-deposit flow. The active Collector
accepts project `.md`/`.pdf` documents and optional source code, then writes a
project archive under `~/Ripper/archives/`.

A sample MS Business Analytics student portfolio, used for:
- ripper-collector end-to-end testing
- Demoing the skill to students before they use their own data
- Regression testing when a future change might affect output quality

## Contents

- `resume.md` — Ana Müller's base resume (intentionally uses non-ASCII characters
  in the name to exercise the Unicode path).
- `sample-jd.md` — a Deloitte Vienna Data Analyst job description, representative
  of what analytics MSc graduates see on the Vienna / DACH market.
- `projects/` — three sample projects (capstone, ML final, text mining) with
  READMEs, notebooks, Python files, and a generated PDF report (created on
  demand by the dogfood test).

## Using the fixture

For the legacy renderer regression suite, run:

```bash
/ripper-collector sample-jd.md
```

and verify three PDFs land in `./applications/deloitte-<date>/`.

## Why Ana Müller

Made-up person. The umlaut is deliberate, so the skill's DejaVu Sans font path
gets exercised on every fixture run. If we ever ship a version where "Müller"
renders as "M ller" in the PDF, tests catch it before students do.
