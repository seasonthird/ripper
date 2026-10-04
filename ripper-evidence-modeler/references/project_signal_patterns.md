# Project Signal Patterns

Use this file to identify resume-worthy signals from code and docs. Do not rely only on directory names; inspect actual implementation where possible.

## Strong Signals

If the project contains these terms or implementations, analyze them further:

- `scheduler` / `dispatcher` / `executor` / `planner` / `router`
- `workflow` / `pipeline` / `DAG` / `graph`
- `retry` / `timeout` / `fallback` / `rate limit`
- `cache` / `queue` / `batch` / `async`
- `plugin` / `tool` / `adapter` / `connector`
- `skill` / capability registry / prompt package / tool catalog
- `sandbox` / isolation / quota / snapshot / runtime lifecycle
- `state machine` / `status transition`
- approval / policy / permission / allowlist / audit
- `evaluation` / `benchmark` / `metrics`
- `trace` / `log` / `monitor` / `observability`
- Dockerfile / Kubernetes / serverless / CI/CD
- tests / integration tests / e2e tests
- config-driven workflow
- compression / indexing / batching / profiling
- RAG / retrieval / embedding / vector / rerank
- prompt template / tool schema / agent memory / context budget
- MCP / function calling / model gateway / guardrail
- Kubernetes controller / reconciler / operator / informer
- ETL / ELT / stream / batch / data quality / lineage
- component / hook / state / form validation / route guard
- IaC / deploy / rollback / health check / alert
- mock / fixture / coverage / test report

## Weak Signals

These cannot directly become resume highlights:

- Boilerplate framework initialization
- Ordinary CRUD
- Simple form page
- Unused dependency
- Capability described in README but not reflected in code
- Simple third-party API wrapper
- Demo script without engineering boundary
- Static page style changes without interaction or reusable component logic
- Manual deployment notes without automation or reliability mechanism
- SQL or scripts without data model, quality, scheduling, or scale context

## Signal Judgement Rules

For every candidate technical point, judge:

1. Is there actual implementation in code?
2. Does it reflect core capability for `{目标岗位方向}`?
3. Can it be written as user contribution?
4. Can it support an interview follow-up?
5. Does it require user confirmation?
6. Is it implemented and wired, or only declared/planned?

## Evidence Labels

Use evidence labels in the value judgement table:

- `code`: directly seen in source code.
- `doc`: from README/design/API docs only.
- `config`: from dependency, deployment, or CI config.
- `test`: from tests or benchmarks.
- `user`: from user-provided work notes.
- `inferred`: reasonable inference, must be phrased cautiously.

When possible, append a precise trace after the label, such as `code: src/scheduler/runner.ts`, `test: tests/e2e/task.spec.ts`, or `config: .github/workflows/ci.yml`. If only a broad project-level signal exists, mark it as `inferred` or add it to the confirmation list.
