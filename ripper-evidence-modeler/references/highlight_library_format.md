# Project Highlight Library Format

Use this file when the selected output mode is **项目亮点素材库**. This mode builds a reusable evidence-backed material pool; it is intentionally more detailed than a one-page resume entry.

## Purpose

The library should help the user:

- see the full technical value of a project before compressing it;
- select different highlights for different jobs;
- prepare interview explanations and likely follow-up questions;
- distinguish implemented capability from production and metric claims that still need confirmation;
- later convert the strongest items into a concise direct-resume version.

Do not apply the direct-resume 35-90 Chinese-character limit to this mode.

## Required Output Structure

Use this overall structure unless the user asks for a narrower artifact:

```markdown
# {项目名称}——项目亮点素材库

## 一、项目简历价值判断
| 技术方向 | 简历价值 | 代码/材料证据 | 适配岗位 | 判断 |
| --- | --- | --- | --- | --- |

## 二、项目定位
**推荐项目名称：** ...
**目标岗位：** ...
**一句话概述：** ...
**核心技术栈：** ...
**本次规模判断与条目数：** {规模}，共 {N} 条

## 三、项目亮点素材库

### 1. {清晰、可追问的技术主题}

**亮点价值：**
说明它解决了什么问题、为什么对目标岗位重要，以及它比普通功能开发更有技术含量的原因。

**详细素材：**
用完整段落解释技术对象、关键机制、设计选择、执行链路、异常或降级处理，以及形成的工程价值。

**技术拆解：**
- ...
- ...
- ...

**代码证据：**
- `{path / module / class / function / config / test}`：它能证明什么。

**可用于简历的素材表达：**
> 一条信息密度较高、但尚未受一页简历篇幅约束的候选表达。

**面试可展开：**
- ...
- ...

**边界与待确认：**
- 仅在存在个人归属、上线状态、指标或实现完整性风险时填写。

### 2. ...

## 四、正式简历优先选材建议
| 优先级 | 推荐亮点 | 适用原因 | 可组合方向 |
| --- | --- | --- | --- |

## 五、可补充的量化指标
- ...

## 六、不建议重点写的内容
- ...

## 七、当前验证状态与表达风险
- ...
```

If the user only asks for the highlight list, sections one, two, and four through seven may be shortened, but the detailed numbered library must remain.

## Anatomy of One Highlight

Each numbered highlight must represent one distinct engineering mechanism or responsibility. It should normally contain:

1. **Technical theme** — a specific title such as `混合检索与重排链路`, not `RAG 功能`.
2. **Problem or objective** — what uncertainty, bottleneck, risk, or product need the mechanism addresses.
3. **Implementation mechanism** — components, flow, state transitions, algorithms, policies, or fallback behavior.
4. **Engineering value** — reliability, maintainability, safety, quality, cost, debuggability, extensibility, or user value.
5. **Evidence** — exact paths, modules, symbols, configuration, tests, runtime output, or explicit user statements.
6. **Resume candidate wording** — a reusable long-form sentence that can later be compressed.
7. **Interview expansion** — two to five concrete follow-up angles.
8. **Boundary** — any unverified production status, performance result, or incomplete wiring.

Do not repeat the same fact in `亮点价值`, `详细素材`, and `可用于简历的素材表达`. The first explains selection value, the second explains the mechanism, and the third turns it into career-oriented wording.

## Detail Target

- For most highlights, the combined `亮点价值 + 详细素材 + 可用于简历的素材表达` should usually contain roughly 150-350 Chinese characters.
- Complex architecture, RAG, memory, Agent orchestration, sandbox, security, scheduling, or distributed-state topics may be longer when the evidence supports the detail.
- `技术拆解` should normally contain 2-5 mechanism-level points.
- `面试可展开` should normally contain 2-5 questions or angles that can be answered from the inspected evidence.
- Prefer one or two precise evidence locations over a long undifferentiated file list.

These are detail targets, not quotas. Never add generic prose solely to reach a length.

## Coverage Strategy

Choose categories according to the project and target role. Typical high-value categories include:

- system architecture and service boundaries;
- Agent planning, execution, verification, state, and human approval;
- RAG retrieval, reranking, evaluation, fallback, and traceability;
- prompt, context, token budget, and memory management;
- Skill, tool, MCP, plugin, or capability-registry foundations;
- sandbox isolation, lifecycle, resource quota, snapshot, and runtime control;
- workflow, async task, queue, lease, retry, idempotency, and recovery;
- data modeling, caching, indexing, persistence, and consistency;
- Kubernetes, cloud platform, observability, database, or third-party system integration;
- security, permission, allowlist, audit, desensitization, and risk governance;
- logging, metrics, tracing, health checks, testing, deployment, and operations.

Do not force every category into every project. Role relevance and evidence strength take priority over category completeness.

For large libraries, group highlights under category headings while keeping a single continuous item number:

```markdown
### A. Agent 与智能编排
#### 1. ...
#### 2. ...

### B. RAG、记忆与上下文
#### 3. ...
```

Category headings do not count toward the requested item total.

## Evidence Rules

- Submitted documents and project folders are treated as the user's career source. When implementation scope is unknown, label the content as `候选素材` and use evidence-bounded language.
- A class name alone is not enough if the important behavior is only declared but not wired. Check call sites, configuration, tests, or runtime evidence where practical.
- Separate `implemented`, `partially wired`, `planned`, `blocked`, and `not verified`.
- README and design documents can explain intent, but implementation claims need code, configuration, tests, or user confirmation.
- Production scale, uptime, accuracy, latency, cost reduction, or business improvement requires supporting evidence.
- AI-estimated metrics remain outside resume-ready wording until the user validates them.

## Selection and De-duplication

Before numbering the library:

1. Build an internal evidence ledger with `theme`, `role value`, `mechanism`, `evidence`, `status`, and `risk`.
2. Merge candidates that describe the same underlying mechanism.
3. Split a broad candidate only when each child item has an independent problem, implementation, and interview path.
4. Rank by role relevance, technical depth, evidence strength, result value, and distinctiveness.
5. Select the requested number or the credible evidence ceiling.

Weak splits:

- `接入 Elasticsearch`
- `使用向量检索`
- `完成 RAG`

Better distinct items when supported:

- `关键词与向量召回的 Hybrid RAG`
- `RRF 融合与 Cross Encoder 重排`
- `检索降级、Trace 与效果评估`

The better split is valid only if each item has separate implementation evidence and enough detail.

## Final Resume Selection

End the library with a practical selection recommendation:

- identify the strongest 3-6 highlights for a normal resume;
- explain which items can be merged into one bullet;
- provide alternate selections for materially different target roles when relevant;
- avoid producing a second complete direct-resume version unless the user requested both modes.

## Library Quality Checklist

Before final output, check:

- Does the answer contain exactly the promised number of numbered highlights, unless an evidence ceiling is disclosed?
- Does every item add a distinct mechanism or engineering value?
- Is the detail materially richer than a direct-resume bullet?
- Can every implementation claim be traced to code, documentation, tests, runtime evidence, or a user statement?
- Are `Skill`, `Agent`, `RAG`, `sandbox`, `Kubernetes`, or other fashionable terms explained through actual mechanisms rather than name-dropped?
- Are implemented work, planned work, and unverified real-environment acceptance clearly separated?
- Is the final selection advice useful for compressing the library into a real resume?
