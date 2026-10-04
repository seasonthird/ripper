# Resume Quality Rules

Use these rules to score candidate technical signals before routing them into either direct-resume wording or the detailed highlight library.

## High-Quality Technical Signals

A good candidate usually includes at least two of these elements:

- **Technical object**: module, API, scheduler, executor, cache, retrieval pipeline, Agent workflow, DAG, task queue, evaluation script, adapter, connector, state machine.
- **Technical action**: design, implement, refactor, optimize, abstract, package, integrate, evaluate, debug, govern, instrument, automate.
- **Problem or goal**: reduce call cost, improve task traceability, avoid repeated computation, support multi-tool orchestration, improve API stability, make configuration maintainable.
- **Method**: cache, async execution, retry, timeout, fallback, state machine, batch processing, configuration, plugin interface, context compression.
- **Result**: support a capability, reduce manual configuration, improve maintainability, strengthen observability, make failures recoverable, make experiments comparable.

Quality check: a candidate should answer at least one interview question naturally: "What did you build?", "Why was it hard?", "How did it work?", "How did you know it helped?"

Mode-specific standard:

- **Direct resume**: compress the selected signal into one contribution-focused bullet without losing its mechanism or boundary.
- **Highlight library**: expand the signal into problem, mechanism, engineering value, evidence, candidate wording, interview angles, and any uncertainty. Detail is useful only when each statement remains evidence-backed.

## Weak Bullet Signals

Do not use these as core resume bullets or numbered library highlights:

- Only explains what the project is.
- Only lists tech stack.
- Only says "completed a feature".
- Only says "participated in development" without contribution.
- Uses vague phrases such as "提升效率", "优化体验", "赋能业务" without mechanism.
- Claims "主导", "独立负责", "上线生产环境", or "提升 xx%" without evidence.
- Packages ordinary CRUD as complex system design.
- Packages a simple third-party API call as algorithm or Agent capability.
- Writes broad project background as personal contribution.

## Technical Resume Principles

- A direct resume is a contribution statement, not a project manual.
- A highlight library may be detailed, but it is an evidence inventory for later selection, not indiscriminate documentation of every feature.
- Prefer "what problem I solved" over "what technology I used".
- A tech stack is valuable only when tied to a concrete implementation action.
- If metrics are missing, describe observable results but do not invent numbers.
- Every bullet should be defensible in an interview follow-up.
- Prefer a specific small contribution over a vague large achievement.

## Quantification Quality

- Prefer evidence-backed outcome metrics, scale metrics, test results, and latency/throughput/cost measures.
- When production metrics are unavailable, code-verifiable counts can show engineering scope if they are tied to role-relevant value.
- Do not force numbers into every bullet. One meaningful, defensible number is stronger than several vanity counts.
- AI estimates are brainstorming aids, not resume facts. Keep them outside direct-resume output until the user confirms them.
- A quantified bullet should answer: what was measured, over what scope/time, from which source, and whether the number represents personal contribution or project capability.

## Practical Scoring

Use this quick score for candidate signals:

| Score | Meaning |
| --- | --- |
| High | Has clear technical object, action, method, and value; aligns with target role; implementation evidence is strong; contribution boundary is clear; any numbers are evidence-backed. |
| Medium | Has real technical content but lacks metric, method detail, wiring evidence, or contribution boundary. Can be used with cautious wording or kept as a secondary library item. |
| Low | Mostly project description, stack list, or unsupported claim. Do not emphasize. |
