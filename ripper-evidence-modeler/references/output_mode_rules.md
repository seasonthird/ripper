# Output Mode and Item Count Rules

Use this file before deep project analysis whenever the user has not already fixed both the deliverable mode and the number of main items.

## Required Decisions

Before drafting, determine three things:

1. `{目标岗位方向}`
2. `{输出模式}`
3. `{条目数量}`

The two primary output modes are:

- **直接简历项目写法**：copy-ready project entry with concise resume bullets.
- **项目亮点素材库**：a detailed, evidence-backed inventory of reusable technical highlights for later resume selection and interview preparation.

`完整分析版` is an analysis depth or presentation wrapper, not a third primary mode. It can wrap either deliverable.

## Infer Explicit Intent Before Asking

Do not ask again when the user's wording already resolves a decision.

Treat these as strong signals for **直接简历项目写法**:

- `直接投递版`
- `可直接放进简历`
- `给我 3 条/4 条简历 bullet`
- `简历项目经历`
- `控制篇幅`

Treat these as strong signals for **项目亮点素材库**:

- `项目亮点素材库`
- `技术亮点清单`
- `尽可能详细地罗列`
- `先不考虑简历篇幅`
- `列 15-20 条亮点`
- `给后续简历筛选和面试准备用`

If the user explicitly requests both, produce the highlight library first and then select the strongest evidence-backed items into a direct resume entry.

## Lightweight Scale Scan

When a readable project path is available but the user has not chosen a count:

1. Inspect the top-level structure with `rg --files`.
2. Identify meaningful services, packages, layers, entry points, workflows, integrations, configuration, tests, and deployment assets.
3. Read only enough key files to estimate how many distinct role-relevant technical signals probably exist.
4. Recommend an item range before performing the full evidence pass.

Do not use raw file count, lines of code, dependency count, or repository size as the scale decision. A large generated repository can still contain few resume-worthy signals.

## Scale Rubric

| Scale | Evidence-based characteristics | Direct resume recommendation | Highlight library recommendation |
| --- | --- | --- | --- |
| Small | 1-2 role-relevant capability groups; one main workflow; little cross-system integration | 2-3 bullets, default 3 | 6-10 highlights, default 8 |
| Medium | 3-5 meaningful capability groups; several layers or 1-2 external integrations; useful test/config evidence | 3-4 bullets, default 4 | 10-15 highlights, default 12 |
| Large | 6-10 distinct strong signals; multiple workflows or integrations; architecture plus reliability, governance, or operations evidence | 4-6 bullets, default 5 | 15-20 highlights, default 18 |
| Extra-large / multi-system | More than 10 distinct strong signals across services or layers; orchestration, data/AI, integration, governance, and operations can each support follow-up | 5-6 bullets, default 6 | 20-30 highlights, default 24 |

A capability group is a distinct mechanism or engineering responsibility, not every class, API, page, or configuration file.

## Combined Question

Ask one compact combined question instead of serially asking for role, mode, and count.

When scale can be estimated:

```text
这段经历希望投递什么岗位？输出希望选择：
① 直接简历项目写法，还是 ② 项目亮点素材库？
我初步判断这是{规模}项目，建议前者约 {直接条数} 条、后者约 {素材库条数} 条。你希望大概写多少条？
```

When the role is already known:

```text
你希望输出 ① 直接简历项目写法，还是 ② 项目亮点素材库？
按当前项目规模，我建议前者约 {直接条数} 条、后者约 {素材库条数} 条；你希望大概写多少条？
```

When no inspectable project is available:

```text
你希望输出 ① 直接简历项目写法，还是 ② 项目亮点素材库？前者通常 3-4 条，后者通常 10-15 条；你希望大概写多少条？
```

The recommendation must be labeled as a recommendation, never as a verified project metric.

## When Not to Pause

Continue without asking when:

- the user already supplied role, mode, and count;
- the user says `你决定`、`按项目规模推荐`、`直接生成` or otherwise delegates the choice;
- the host environment explicitly allows a useful non-blocking question but requires continued progress.

In these cases, choose the scale-based default and state the selected mode and count near the start of the answer.

If the user supplies a mode but no count and asks to proceed immediately, use the scale-based default.

## Count Semantics

- Count only the main resume bullets or numbered project highlights.
- Do not count headings, project summaries, confirmation questions, risk reminders, evidence rows, or metric suggestions.
- An exact request such as `写 18 条` means exactly 18 main items when 18 independent, defensible signals exist.
- A range such as `15-20 条` means choose a suitable number inside the range and report the final count.
- `大概十几条` allows a reasonable count such as 12-15 based on evidence density.
- Never split one mechanism into near-duplicate items merely to satisfy the number.
- Never pad the library with ordinary CRUD, dependency names, file counts, or unsupported claims.
- If the requested count exceeds the credible evidence, output fewer strong items and explain the evidence ceiling.
- If the user requests an unusually long direct-resume list and enough evidence exists, provide it as a candidate bullet pool, then identify the strongest 3-6 items for an actual one-page resume.

## Mode Changes During the Conversation

Treat a later mode or count request as an explicit revision:

- `再展开成素材库`：retain the evidence ledger and expand the selected project into the highlight-library format.
- `压缩成 4 条`：rank the existing highlights, then rewrite the strongest four as direct resume bullets.
- `方向不变`：reuse the previously confirmed target role.
- `条目太少`：look for genuinely distinct evidence before increasing the count; do not paraphrase existing items.

## Quality Gate

Before drafting, verify:

- The selected mode matches the user's actual downstream use.
- The recommended count comes from capability density, not repository size.
- Every planned item has a distinct technical theme and at least one evidence source or explicit user statement.
- The set covers the role's strongest signals instead of distributing space evenly across all modules.
- Planned or incomplete work is separated from implemented capability.
