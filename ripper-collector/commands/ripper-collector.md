---
description: Deposit project documents and optional source into Ripper
---

Run the **ripper-collector** skill against `$ARGUMENTS` as project material. Accept one or more `.md`/`.pdf` documents and optional source folders or files.

Infer the project direction only from those materials, create `project-analysis.json`, optionally research and validate recent same-direction practices, then use `orchestration deposit-project` so duplicate gating, archive mutation and index synchronization remain one transaction. Do not request or use a resume, JD, target role or career direction during deposit.

If `$ARGUMENTS` is empty or the project name cannot be inferred safely, ask only for the missing project material or project name. If duplicate detection returns `confirmation_required`, ask whether to update the named archive before rerunning with `--update`.
