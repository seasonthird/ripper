---
name: ripper-evidence-modeler
description: |
  Analyze authorized project evidence into a persistent Ripper evidence ledger:
  claims, source references, capability tags, implementation and production
  boundaries, disclosure rules, open confirmations, metrics, and reusable
  narrative units. Also models recent same-direction public practices into
  source-backed, mutually compatible reconstruction candidates without using
  job-search context or rewriting them as historical facts. It is the
  evidence-modeling layer for asset deposit; it only produces resume prose
  when an explicit export request asks for it.
---

# Ripper Evidence Modeler (`ripper-evidence-modeler`)

根据 `ripper-collector` 的候选模块、源码定位和补充文档，建立可长期复用的 Ripper 资产，并以统一 `project_id` 写入 `~/Ripper/archives/<project-slug>/` 项目档案；具体简历、STAR、晋升、交接和博客材料由 `ripper-exporter` 在用户提出具体需求时生成。

不要把 README 直接改写成简历。用户主动提交的文档、工程文件夹或仓库默认作为用户经历来源；项目成果应存尽存、应提炼尽提炼。工程事实、实现状态、生产状态、指标和披露边界仍需分别落表和核验，不能把计划或推断写成已完成结果。

## Inputs

支持单独或组合使用以下材料：

- 项目目录或本地代码仓库。
- README、docs、design、接口文档、配置、测试、部署文件和运行结果。
- 用户在项目中的真实职责、成果和补充说明。
- 实习、论文、开源贡献、平台建设、功能开发、性能优化等经历。
- `project-input` 产生的 `domain_profile`，及基于该画像检索得到的外部实践。

沉淀阶段不接收也不使用简历、JD、目标岗位、求职方向或希望条目数；这些只属于 `ripper-exporter` 的后续导出分支。

## Asset Persistence Contract

开始分析前确认两个不同层级的存储位置：

```bash
ARCHIVE_ROOT="${RIPPER_ARCHIVE_ROOT:-$HOME/Ripper/archives}"
RIPPER_ROOT="$(git -C "$PWD" rev-parse --show-toplevel 2>/dev/null || pwd)"
RIPPER_OUTPUT_DIR="${RIPPER_OUTPUT_DIR:-$RIPPER_ROOT/ripper-output}"
ASSET_DB="$RIPPER_OUTPUT_DIR/assets/.cache/ripper-assets.sqlite"  # rebuildable index only
```

对每个候选点写入或更新以下资产，而不是直接写最终简历稿：

```yaml
claim:
  id: claim_<stable-id>
  title: 可验证的工程机制
  statement: 代码或文档实际证明的事实
  status: confirmed | code-verifiable | inferred | planned | blocked | unknown
  realization_status: implemented | partial | designed | derived | hypothetical | unknown
  production_status: confirmed | unknown | not-verified
  disclosure_level: public | internal-safe-after-redaction | restricted
  capabilities: [可靠性, 工作流编排]
  evidence:
    - kind: code | doc | config | test | user | inferred
      path: 相对路径
      symbol: 函数/类/配置项
      line_range: 行范围
      claim: 该来源支持什么事实
  source_refs:
    - path: 相对路径
      symbol: 函数/类/配置项
      line_start: 起始行（可选）
      line_end: 结束行（可选）
  related_tests: [相关测试文件或测试场景]
  related_config: [相关配置、部署或运行入口]
  derived_optimizations: [基于现有材料推导的优化方向]
  reconstruction:
    mode: material-grounded-reconstruction
    basis: 方案书、PRD、现有模块或用户补充
    note: 面试准备时可采用的合理复原说明
  confirmations:
    - 该成果是否已上线、指标口径是什么、哪些信息需要脱敏？
  narrative_unit:
    situation: 背景与约束
    task: 已确认职责或待确认任务
    actions: 机制与关键决策
    verified_results: 可证结果与缺口
```

保存内容（档案是事实源，索引自动维护）：

- 项目分析、原始文档、受控源码和知识包：`$ARCHIVE_ROOT/<project-slug>/`。
- SQLite 查询索引：`$ASSET_DB`（自动创建、可删除、可由档案重建，不需要用户配置）。
- 运行中间文件：`$RIPPER_OUTPUT_DIR/ripper-collector/runs/`（可删除，不是事实源）。

不得把 `$RIPPER_OUTPUT_DIR/assets/` 下的派生索引或临时快照当成第二个长期档案库。

不要因为缺少岗位而停止证据建模；目标岗位只属于后续导出分支。

## Asset Deposit Decisions

资产沉淀不要求岗位、JD、输出模式或条目数量。开始前只确认：

1. `{资产范围}`：仓库、工程文件夹、模块或补充文档。
2. `{使用权限}`：用户确认对材料拥有读取和沉淀权限。
3. `{扫描深度}`：仅工程地图、模块级证据，或带关键调用链/测试/配置追踪的深度扫描。
4. `{补充信息}`：若用户愿意提供，记录职责、结果、指标和公开限制；缺失时保留证据边界，不丢弃已有成果。

没有具体岗位时，仍应完成资产建模；岗位相关性只在 `ripper-exporter` 导出阶段计算。

## Workflow

### 1. Resolve Asset Scope and Permission

按「Asset Deposit Decisions」确认范围和授权。对大仓库先生成仓库地图，再按模块处理；不得将整个仓库直接拼接为单个模型上下文。

### 2. Read Rules Progressively

**每次沉淀必读：**

- `references/asset_analysis_contract.md`

岗位、简历和导出表达规则不属于沉淀阶段，不要为普通工程沉淀加载。

**分析代码时读取：**

- `references/project_signal_patterns.md`

**存在领域增强或缺失模块重建时读取：**

- `references/domain_enrichment_contract.md`

**只有用户明确要求直接导出简历项目写法时，才读取：**

- `references/resume_bullet_patterns.md`
- `references/resume_style_rules.md`

**只有用户明确要求项目亮点素材库时，才读取：**

- `references/highlight_library_format.md`

**只有导出场景需要量化时，才读取：**

- `references/resume_quantification_rules.md`

**只有导出场景需要改写弱句时，才读取：**

- `references/weak_vs_strong_bullets.md`

`references/ripper-evidence-guide.md` 仅作为短导航，不替代任务相关规则。岗位聚焦、简历格式和亮点素材规则由导出分支负责，不是沉淀门槛。

### 3. Inspect Project Evidence

- 项目目录存在时，优先用 `rg --files` 查看结构。
- 优先读取 README、架构与设计文档、依赖文件、服务入口、API/CLI 入口、核心业务路径、配置、测试、部署和可观测性文件。
- 依赖文件包括但不限于 `package.json`、`pyproject.toml`、`requirements.txt`、`go.mod`、`pom.xml`、Dockerfile 和 CI 配置。
- 对关键能力继续追踪调用链、配置接线、状态流转、测试或运行证据，避免把只有接口、类名或规划文档的内容写成完整实现。
- 前后端或多服务项目需要检查关键契约和调用关系，不能只看单侧目录。

### 4. Build an Evidence Ledger

为候选技术点记录：

- 技术主题与解决的问题。
- 关键机制、模块和执行链路。
- 对工程、用户和系统质量的价值。
- 文件、模块、类、函数、配置、测试、运行结果或用户原话。
- `confirmed`、`code-verifiable`、`inferred`、`planned`、`blocked` 或 `unknown` 状态。
- 实现边界、上线边界、指标边界和敏感信息风险。

用户提交来源中的成果默认纳入其经历资产。代码、文档和用户说明发生冲突时，以明确的用户说明为准，并记录事实、状态或指标差异；不得因此丢弃其他有证据支持的成果。

### 5. Model Domain Enrichment Without Rewriting History

- 读取 `domain-profile.json` 与经校验的 `market-practices.json`；详细字段、一致性和候选约束见 `references/domain_enrichment_contract.md`。
- 用工程材料进行语义方向判断，禁止用简历、JD、目标岗位或求职方向改写方向。
- 外部模块卡只能进入 `reconstruction` 或 `derived_optimizations`，并标记 `historical_fact: false` 与 `realization_status: derived|hypothetical`；不得写入陈述原项目已实现事实的 `statement`。
- 至少保留两个完整候选，不将多个可能方案强行合并成一个“猜测版本”。每个候选分别说明保留的术语、相容前提、引入成本和冲突。
- 保留项目原有术语、复杂度和问题结构。只吸收能与原有控制面、数据流、一致性与运维模式共存的模块，避免拼装成互相矛盾的架构。

### 6. Select Distinct Signals

- 按技术深度、证据强度、成果价值和可追问性排序；岗位相关性留给导出器计算。
- 合并同一机制的重复描述。
- 只有当问题、实现和面试展开均独立时，才把一个宽泛主题拆成多个条目。
- 不用普通 CRUD、框架名称、文件数量、代码行数或依赖数量凑条目。
- 请求数量超过可靠证据上限时，宁可少写并说明原因，也不编造或重复。

### 7. Model Assets Instead of Drafting Resume Prose

- 将每个独立机制写为 `claim`，并关联来源 `evidence`、能力标签、实现状态、上线状态、指标状态、披露级别和待确认问题。
- 为可讲述的机制创建 `narrative_unit`：情境、任务、动作、可证结果、证据引用和风险缺口。
- 按 `references/asset_analysis_contract.md` 生成完整 `project-analysis.json` 作为唯一机器主产物；可另行生成审阅 Markdown，但不得用 Markdown 代替结构化主张。SQLite 只是该 JSON 与档案的可重建索引。
- 直接简历项目写法、项目亮点库和面试展开属于 `ripper-exporter` 的导出视图，只有用户明确请求具体用途时才生成。

### 8. Handle Metrics

- 主动寻找监控、Benchmark、测试报告、正式文档、用户确认数据和代码可核证范围。
- 每个数字记录统计口径、证据与适用范围。
- 已确认指标可以进入正式表达。
- 代码可核证数字只能表达项目覆盖范围，不能冒充业务收益。
- AI 估算只能进入 `AI 估算候选（待核验，禁止直接投递）`，用户确认前不得写入可直接投递稿。
- 缺少真实数字时，使用非数字结果或 `[待补充具体数据]`，不要为了量化堆砌无价值计数。

### 9. Asset Quality Review

写入资产前检查：

- 每个主张是否独立、有证据且可被后续目标筛选。
- 是否完整记录了用户提交来源中有证据支持的全部成果，没有因团队环境而删除、降级或跳过。
- 是否把规划、推断或未接线能力误写成已完成成果。
- 已实现、部分接线、规划、阻塞和真实环境未验证是否分开。
- 技术名词是否通过实际机制展开，而不是堆栈罗列。
- 指标是否可核证，AI 估算是否被隔离。
- 是否泄露内部域名、凭证、账号、客户名或未公开代号。
- 领域方向是否仅由项目材料推断，外部来源是否在近 365 天且可追溯。
- 外部模块是否与历史实现分层，并保留了至少两个不冲突的架构候选。

## Default Rule for Submitted Sources

当用户提交文档、工程文件夹或仓库时：

- 模块设计、工程实现、测试、部署、优化和已记录结果全部作为用户经历候选素材。
- 应存尽存、应提炼尽提炼，再由导出器根据岗位相关性、证据强度和亮点价值选择。
- 无法确认的上线、规模、指标和实现完整性标记为待确认，但不影响其他成果入库。
- “主导”“从 0 到 1”“生产上线”“提升 xx%”或“服务百万用户”等具体强度与结果仍需材料证据支持。

## Output Contracts

### Asset Ledger Contract

每次资产沉淀必须生成 `project-analysis.json`，字段见 `references/asset_analysis_contract.md`。可选的人类审阅文档至少包含：

```markdown
# <项目/模块> 资产审阅摘要

## 仓库与模块范围
...

## 已入库主张
- `claim_id`：工程事实、能力标签、证据链接、状态

## 状态、指标与披露待确认
- ...

## 披露和脱敏限制
- ...

## 可复用叙事原子
- `narrative_id`：背景、动作、可证结果、风险
```

资产与项目档案是后续导出材料的事实来源；不得将分析摘要误称为可直接投递简历。

### Export handoff

项目档案只保存结构化工程事实、证据、状态和叙事原子。简历项目写法、项目亮点素材库、
岗位聚焦和多版本导出由 `ripper-exporter` 或 `ripper-cv` 读取档案后生成；不要在沉淀阶段
提前生成这些派生文案，也不要把派生文案写回 `project-analysis.json` 取代事实记录。

## Resources

- `references/project_signal_patterns.md`：从代码和文档中识别简历信号。
- `references/domain_enrichment_contract.md`：领域增强和市场实践候选约束。
- `references/asset_analysis_contract.md`：结构化分析主产物和字段契约。
- `references/ripper-evidence-guide.md`：短导航摘要。
