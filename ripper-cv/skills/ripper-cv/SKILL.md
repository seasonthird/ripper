---
name: ripper-cv
description: "Generate and maintain tailored LaTeX/PDF resumes from Ripper assets. Use for Ripper resume initialization, asset synchronization, experience updates, and final CV generation."
---

# Resume — One Source, Many Tailored Resumes

## Ripper 统一产物根目录

所有运行时文件必须写入 Ripper 根目录下的 `ripper-output/ripper-cv/`，不写入当前工作目录或 Skill 源码目录。先解析：

```bash
RIPPER_ROOT="$(git -C "$PWD" rev-parse --show-toplevel 2>/dev/null || pwd)"
RIPPER_OUTPUT_DIR="${RIPPER_OUTPUT_DIR:-$RIPPER_ROOT/ripper-output}"
CV_OUTPUT_DIR="$RIPPER_OUTPUT_DIR/ripper-cv"
```

`RIPPER_OUTPUT_DIR` 必须是绝对路径或会被解析为绝对路径；它用于显式覆盖默认的统一产物根目录。

```text
$CV_OUTPUT_DIR/experiences/ → /ripper-cv generate → $CV_OUTPUT_DIR/resume.tex → make en → $CV_OUTPUT_DIR/output/Name-Title.pdf
      (素材)                    (AI 定制化)          (LaTeX源)                 (输出)
```

## Subcommand Routing

Parse `$ARGUMENTS` to determine which workflow to run:

- `init [text]` → **Init Workflow**
- `sync-assets [repository|capability]` → **Asset Sync Workflow**
- `generate [job title or JD file]` or `gen [...]` → **Generate Workflow**
- `add [description]` → **Add Experience Workflow**
- Empty or unrecognized → Show available subcommands and ask user what they want to do

---

## Prerequisites Check

Before any workflow, verify the environment:

1. Create directories if missing: `$CV_OUTPUT_DIR/experiences/work/`, `$CV_OUTPUT_DIR/jobs/`, `$CV_OUTPUT_DIR/output/`, `$CV_OUTPUT_DIR/.history/`
2. Copy `${CLAUDE_SKILL_DIR}/assets/resume.cls` to `$CV_OUTPUT_DIR/resume.cls` if missing.
3. Copy `${CLAUDE_SKILL_DIR}/assets/Makefile` to `$CV_OUTPUT_DIR/Makefile` if missing.
4. Check if `xelatex` is available: `which xelatex`. If not, warn the user: "XeLaTeX is required. Install with: brew install --cask mactex".

所有 `make` 命令必须以 `$CV_OUTPUT_DIR` 作为工作目录执行，确保 LaTeX 辅助文件和 PDF 都留在统一产物目录。

---

## Init Workflow (`/ripper-cv init [text]`)

Initialize the experience data library from scratch.

### Mode Detection

Based on `$ARGUMENTS` (after stripping "init"):

1. **User pasted large text** (resume, work history, LinkedIn export) → **Import Mode**
2. **Empty or short description** → **Q&A Mode**
3. **File path provided** (PDF/Markdown) → Read file, then **Import Mode**

### Import Mode

1. **Parse** the provided content, extracting: personal info, education, work history (company, period, department, role, projects, metrics), personal projects, skills, honors
2. **Confirm** with user — show structured result, ask about missing info or inaccurate metrics
3. **Generate files** into `$CV_OUTPUT_DIR/experiences/`:
   - `profile.md` — personal info + education
   - `work/<company>.md` — one file per company
   - `projects.md` — personal projects
   - `skills.md` — skill inventory
   - `honors.md` — honors + quantified metrics

### Q&A Mode

Walk through one question at a time. **Never ask multiple questions at once.**

1. **Basic info** → name, email, phone, wechat (optional), blog/github (optional) → write `$CV_OUTPUT_DIR/experiences/profile.md`
2. **Education** → school, degree, major, period, highlights → append to `$CV_OUTPUT_DIR/experiences/profile.md`
3. **Work history** (loop) → company, department, role, period, projects, metrics, tech stack → write `$CV_OUTPUT_DIR/experiences/work/<company>.md`. After each: "Any more work experience?" Continue or move on.
4. **Personal projects** → name, link, description, tech stack, highlights → write `$CV_OUTPUT_DIR/experiences/projects.md`
5. **Skills** → auto-generate from collected tech stacks, show for confirmation → write `$CV_OUTPUT_DIR/experiences/skills.md`
6. **Honors** → extract quantified metrics from work history + user additions → write `$CV_OUTPUT_DIR/experiences/honors.md`

### File Format Reference

**profile.md:**
```markdown
---
name: Name / English Name
email: email@example.com
phone: "+86 xxx"
wechat: xxx
blog: https://...
github: https://...
---

## Education

### School · College | Degree (Period)
- Major, highlights
```

**work/\<company\>.md:**
```markdown
---
company: Company Name
company_en: English Name
url: https://...
location: City
period: YYYY/MM -- YYYY/MM
department: Department
role: Role
tags: [tag1, tag2, ...]
---

# Project Name
> Timeline | Role

## Background
...

## Key Work
...

## Metrics
...

## Tech Stack
...
```

Key principles:
- Keep raw details in experiences — trimming happens at generation time
- Tags should cover core tech and business domain keywords
- Metrics must include specific numbers
- One file per company, filename in lowercase English (e.g., `bytedance.md`)

---

## Asset Sync Workflow (`/ripper-cv sync-assets [repository|capability]`)

将共享资产库中**已确认个人归因**且**允许公开表达**的工程主张同步到 `$CV_OUTPUT_DIR/experiences/`，作为简历素材视图；不把未确认、受限或仅有代码存在证据的内容混入简历。

1. 解析 `$RIPPER_OUTPUT_DIR/assets/.cache/ripper-assets.sqlite`；若不存在，先从 `~/Ripper/archives/` 重建索引，而不是扫描任意源码目录。
2. 不按 `ownership_status` 过滤用户提交的成果；团队成果也属于用户可选经历素材。根据 `realization_status`、`production_status` 和 `disclosure_level` 保留表达边界，必要时改用团队主语或添加脱敏提示。
3. 将每条主张的 `claim_id`、能力标签、证据路径、待确认项保留在工作经历/项目素材的 HTML 注释或“Evidence”段中，便于内部追溯；最终 `/ripper-cv generate` 时按目标场景选择内容。
4. 按仓库或能力标签将内容追加到 `$CV_OUTPUT_DIR/experiences/projects.md`，避免覆盖手工维护内容；先展示 diff，再等待用户确认写入。
5. 同步完成后报告：新增素材数、跳过的未确认或受限主张数、仍缺少的个人职责或指标。

---

## Generate Workflow (`/ripper-cv generate [target]`)

Generate a tailored resume for a specific job target.

### Step 1: Read All Materials

Read all files:
- `$CV_OUTPUT_DIR/experiences/profile.md`
- All `.md` files under `$CV_OUTPUT_DIR/experiences/work/`
- `$CV_OUTPUT_DIR/experiences/projects.md`
- `$CV_OUTPUT_DIR/experiences/skills.md`
- `$CV_OUTPUT_DIR/experiences/honors.md`

Read `${CLAUDE_SKILL_DIR}/assets/resume-example.tex` to understand the LaTeX structure and available commands.

If the argument is a file path, also read that JD file.

### Step 2: Analyze Job Requirements

Based on JD or job title, determine:
1. **Core technical requirements** — what skills matter most
2. **Experience priority** — which work experiences are most relevant
3. **Framing angle** — how to present the same experience differently for this role
4. **Content selection** — include/omit personal projects section, which experiences to trim

### Step 3: Present the Plan

Before generating .tex, show the user:
1. Target positioning (one sentence)
2. Content selection (which experiences to include/omit)
3. Key differentiation (how this resume differs from a generic one)

**Wait for user confirmation before proceeding.**

### Step 4: Generate LaTeX

Generate `$CV_OUTPUT_DIR/resume.tex` following these rules:

1. **Use resume.cls commands strictly**:
   - `\name{}`, `\basicInfo{}`, `\email{}`, `\phone{}`, `\wechat{}`, `\homepage[]{}`
   - `\section{}`, `\datedsubsection{}{}`, `\role{}{}`, `\rolewithdate{}{}{}`
   - `itemize` with `[parsep=0.25ex]`

2. **Keep to 1 page** (critical for Chinese version):
   - 5-6 sections: positioning, education, work, (projects), skills, honors
   - 3-5 bullet points per project
   - Trim early internships to 1-2 lines each
   - If too long, cut early internships and low-relevance bullets first

3. **LaTeX header for Chinese**:
   ```latex
   \documentclass{resume}
   \usepackage{xeCJK}
   \setCJKmainfont{SourceHanSerifSC-Medium}
   \setCJKsansfont{SourceHanSerifSC-Medium}
   \setCJKmonofont{SourceHanSerifSC-Medium}
   ```
   For English version: remove the three xeCJK lines.

4. **Formatting**:
   - Use `\textbf{【keyword】}` to mark each bullet's keyword
   - Escape: `&` → `\&`, `%` → `\%`
   - Use `\href{url}{text}` for hyperlinks

### Step 5: Build

1. Backup current `$CV_OUTPUT_DIR/resume.tex` to `$CV_OUTPUT_DIR/.history/resume_$(date +%Y%m%d%H%M%S).tex`
2. Write generated content to `$CV_OUTPUT_DIR/resume.tex`
3. Run `cd "$CV_OUTPUT_DIR" && make en` to build PDF
4. Copy PDF to `$CV_OUTPUT_DIR/output/` with job-specific name

### Step 6: English Version (if requested)

1. Remove xeCJK lines
2. Translate all content to English
3. Build PDF

---

## Add Experience Workflow (`/ripper-cv add [description]`)

Add or update experience data incrementally.

### Step 1: Classify Input

Determine what the user is adding:
- **New work experience** → create/update `$CV_OUTPUT_DIR/experiences/work/*.md`
- **New personal project** → update `$CV_OUTPUT_DIR/experiences/projects.md`
- **New skill** → update `$CV_OUTPUT_DIR/experiences/skills.md`
- **New honor/certification** → update `$CV_OUTPUT_DIR/experiences/honors.md`
- **Personal info change** → update `$CV_OUTPUT_DIR/experiences/profile.md`

### Step 2: Read Existing File

Read the target file to understand current content and format.

### Step 3: Update

Apply updates following the file format conventions above. Keep raw details — don't trim prematurely.

### Step 4: Confirm

Show the diff to the user, confirm before writing.

### Step 5: Remind

After updating: "Experience updated. Run `/ripper-cv generate [target]` to regenerate your resume."
