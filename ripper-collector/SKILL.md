---
name: ripper-collector
description: Analyze and deposit one project's Markdown/PDF documents and optional source code into Ripper's fixed archive. Use when the user submits project materials, updates a deposited project, or asks what projects have already been deposited. Infer project direction only from submitted project material; do not require job-search context.
---

# Ripper Collector

把用户提交的单个工程材料沉淀到 `~/Ripper/archives/`。输入可以是一个或多个
`.md`/`.pdf` 文档，也可以在这些文档之外附带同一工程的源码目录或核心源码文件。
沉淀阶段不读取、不请求简历、JD、目标岗位、求职方向或期望条目数。

所有已提交成果都应完整记录并充分提炼，不按个人/团队归属过滤。实现状态仍需区分，
以便后续导出时选择准确的“我”或“团队”措辞。

## Entrypoints

- `/ripper-collector <materials...>`：分析并沉淀一个工程。
- `/ripper-collector`：缺少材料时只询问材料路径或项目名。
- 用户询问“已经沉淀了什么”：直接运行 `list-archives`，不重新扫描原文件。
- 用户要求简历、面试、晋升等材料：停止本流程并转交 `ripper-exporter` 或
  `ripper-cv`；Collector 不直接生成求职材料。

## Resolve the Runtime

每次新的 shell 调用都重新解析路径；不要依赖上一次调用里的环境变量：

```bash
SKILL_ROOT=""
REPO_ROOT="$(git -C "$PWD" rev-parse --show-toplevel 2>/dev/null || true)"
for candidate in \
  "$PWD/ripper-collector" \
  "$REPO_ROOT/ripper-collector" \
  "$HOME/.claude/skills/ripper-collector" \
  "$PWD/.claude/skills/ripper-collector" \
  "$HOME/.codex/skills/ripper-collector" \
  "$PWD/.codex/skills/ripper-collector" \
  "$HOME/.gemini/skills/ripper-collector" \
  "$PWD/.gemini/skills/ripper-collector" \
  "$HOME/.opencode/skills/ripper-collector" \
  "$PWD/.opencode/skills/ripper-collector"; do
  if [ -f "$candidate/SKILL.md" ]; then
    SKILL_ROOT="$candidate"
    break
  fi
done
if [ -z "$SKILL_ROOT" ]; then
  echo "ERROR: ripper-collector is not installed." >&2
  exit 1
fi
RS="$SKILL_ROOT/bin/ripper-collector-exec"
if [ ! -x "$RS" ]; then
  echo "ERROR: run: bash $SKILL_ROOT/install.sh" >&2
  exit 1
fi
```

所有确定性操作经由包装器执行：

```bash
"$RS" orchestration <subcommand> [arguments]
```

不得直接调用系统 Python，也不得要求用户配置 SQLite。文件档案是事实源，SQLite 只是
程序自动建立、可以重建的查询索引。

## Deposit Workflow

以下步骤按顺序执行。任何失败都应停在当前阶段并保留此前生成的本地分析文件；不得绕过
验证或重复确认门禁。

### 1. Normalize One Project Package

1. 验证所有路径均由用户提交或明确授权读取。
2. 将多个文档和可选源码归并为一个项目，不把不同工程混入同一次沉淀。
3. 文档只接受存在的 `.md`/`.pdf`；源码目录应先建立有界工程地图，不整库拼进一个提示。
4. 从材料中推断稳定项目名。无法可靠推断时，只询问项目名。
5. 为本次运行建立 Skill 外部的临时分析目录，例如
   `ripper-output/ripper-collector/runs/<project-slug>/`。不得把运行产物写入用户源码目录。

### 2. Inspect Every Submitted Source

对每个文档执行：

```bash
"$RS" orchestration document-map /absolute/path/to/document.md
"$RS" orchestration document-context /absolute/path/to/document.md
```

PDF 必须审阅提取出的正文；关键词统计只能作为候选，不能代替语义判断。提取失败或扫描型
PDF 无可选文本时，明确报告该文件尚未被分析，不得假装已读。

对源码目录执行：

```bash
"$RS" orchestration repository-map /absolute/path/to/source
```

根据地图优先检查 README/设计、依赖、入口、核心链路、接口、配置、测试、部署和可观测性。
只把高信号核心文件作为 `--core` 输入；依赖、构建物、缓存、二进制、密钥和大数据文件不得
归档。对遗漏内容记录原因。

### 3. Build the Project-Only Domain Profile

用全部文档路径作为重复的 `--source`，用选中的核心源码作为重复的 `--core`：

```bash
"$RS" orchestration project-domain-profile "<project-name>" \
  --source /absolute/path/design.md \
  --source /absolute/path/report.pdf \
  --core /absolute/path/src/core.py \
  --output /absolute/run/path/domain-profile.json
```

方向判断只能依据以上工程材料。保留原有术语、复杂度、问题结构、控制面、数据流和约束；
若存在多个合理方向，保留多个带置信度的方向候选，不强行收敛为一个低级通用项目。

### 4. Research Same-Direction Practices When Available

依据 `domain-profile.json` 生成检索关键词，而不是要求用户提供求职信息。检索执行时最近
365 天内、国内互联网大中小厂公开且可归因的同方向落地方案。对每个来源记录标题、URL、
发布日期、组织规模和适配关系。

知识不足、不能联网或某规模无公开材料时，记录覆盖缺口后继续沉淀已有材料。不得编造
来源、日期或落地事实。至少保留两个内部自洽的架构候选（通常为 `conservative` 和
`enhanced`），不要把冲突模块拼成一个“猜测版本”。外部模块属于重建或优化候选，不能写成
历史上已实现。

将结果保存为 `market-practices.json`，并在沉淀前验证：

```bash
"$RS" orchestration validate-domain-knowledge \
  --profile /absolute/run/path/domain-profile.json \
  --knowledge /absolute/run/path/market-practices.json
```

验证返回非零时修正知识包；无法修正则省略 `--knowledge`，不得带病写入档案。

### 5. Produce Canonical Analysis

使用 `ripper-evidence-modeler` 的 `asset_analysis_contract.md` 生成
`project-analysis.json`。至少包含：

- `schema_version`、`project_id`、`project_name` 和完整 `claims`；
- 每个独立成果的稳定 ID、事实陈述、能力、证据和源码引用；
- `status`、`realization_status`、`production_status` 和 `disclosure_level`；
- 指标口径、相关测试/配置、待确认项和可复用叙事单元；
- 缺源码时基于方案书、PRD、接口、流程和现有术语形成的重建；
- 来自公开实践的模块仅进入 `derived_optimizations`/`reconstruction`，并标记
  `historical_fact: false`。

不要因为成果来自团队而省略。也不要把 `designed`、`derived` 或 `hypothetical` 改写成
`implemented`。可另外生成审阅 Markdown，但 JSON 是唯一机器主产物。

### 6. Deposit Through the Transactional Gate

只用完整入口写档案和同步索引：

```bash
"$RS" orchestration deposit-project "<project-name>" \
  --analysis /absolute/run/path/project-analysis.json \
  --source /absolute/path/design.md \
  --source /absolute/path/report.pdf \
  --core /absolute/path/src/core.py \
  --knowledge /absolute/run/path/market-practices.json
```

如果没有合格的外部知识包，省略 `--knowledge`。命令返回
`status: confirmation_required` 和退出码 2 时，尚未修改任何档案：展示命中的已有工程名，
询问是否更新该工程。只有得到明确确认后才能重试：

```bash
"$RS" orchestration deposit-project "<submitted-project-name>" \
  --analysis /absolute/run/path/project-analysis.json \
  --source /absolute/path/design.md \
  --core /absolute/path/src/core.py \
  --update --update-project-name "<confirmed-existing-project-name>"
```

更新流程会保留历史快照。不得手工复制到档案目录、静默覆盖或跳过重复门禁。

### 7. Report the Result

成功时给出：项目名、`project_id`、档案绝对路径、文档数、核心源码数、claims 数、是否保存
外部知识包和索引同步结果。档案固定在：

```text
~/Ripper/archives/<project-slug>/
├── archive-manifest.json
├── analysis/project-analysis.json
├── analysis/history/
├── knowledge/domain-profile.json
├── knowledge/market-practices.json
└── sources/{documents,core-source}/
```

## List Existing Deposits

用户只想查看已沉淀内容时执行：

```bash
"$RS" orchestration list-archives
```

按项目列出名称、更新时间、输入类型与数量、主要方向、claims 概览和可用架构候选。不重新
扫描源码，不要求数据库配置，也不触发导出。

## Non-negotiable Boundaries

- 不使用 JD、简历或岗位信息来推断项目方向。
- 不因团队归属丢弃成果；归属不再是沉淀筛选维度。
- 不把推导、设计、假设冒充历史实现；后续导出可以按场景充分利用它们并选择合适主语。
- 不保存凭证、密钥、私有依赖、大型构建物或无界源码副本。
- 不绑定任何预设 GitHub 仓库、遥测端点或远程数据控制者。
- 默认本地执行；遥测只有部署方显式配置端点且用户主动选择后才可启用。
