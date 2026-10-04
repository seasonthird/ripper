# Direct Resume Style Rules

Use this file only when producing **直接简历项目写法**. These rules control the copy-ready resume shape, not the project analysis or the detailed highlight-library mode.

Read `output_mode_rules.md` first to determine the user-selected or scale-recommended bullet count.

## Direct Resume Shape

For a concise resume entry, prefer:

```markdown
**{项目名称}｜{技术栈}｜{角色/时间，如已提供}**
一句话概述：用 25-50 个中文字符说明项目解决的问题或建设的能力。

- Bullet 1
- Bullet 2
- Bullet 3
```

If role, time, or technology stack is unknown, omit that field instead of inventing it.

## Bullet Constraints

- Output the exact or approximate bullet count agreed with the user.
- When the user delegates the decision, use the scale-based recommendation in `output_mode_rules.md`; a normal direct-resume entry will usually contain 2-6 bullets.
- Each bullet should usually be 35-90 Chinese characters.
- Each bullet should express one main contribution; do not pack unrelated modules into one sentence.
- Do not use first-person wording such as "我" or "本人".
- Avoid starting several bullets in the same project with the same verb.
- Tie every technology stack mention to a concrete action, module, mechanism, or result.
- Use `[待补充具体数据]` for unconfirmed metrics; never invent percentages, traffic scale, launch scope, or business impact.
- If the user chooses AI-assisted estimation, show candidate ranges only in `AI 估算候选（待核验，禁止直接投递）`; keep placeholders or non-numeric wording in the direct-resume entry until confirmation.
- Prefer 1-2 meaningful quantified points per project. Do not force every bullet to contain a number.
- Keep placeholders in the final resume entry only when they help the user fill real missing data. Put broader uncertainty in "需确认/可量化补充" or "表达风险提醒".
- If the requested count is too high for a one-page resume but enough evidence exists, label the output as a `候选 bullet 池` and identify the strongest 3-6 bullets for actual use.
- If there is not enough distinct evidence for the promised count, do not create paraphrased duplicates; disclose the evidence ceiling and return fewer strong bullets.

The 35-90 Chinese-character guidance does not apply to `项目亮点素材库`. Use `highlight_library_format.md` for that mode.

## Preferred Verbs

Prefer concrete, defensible verbs:

- 负责
- 参与
- 围绕
- 设计
- 实现
- 优化
- 抽象
- 封装
- 接入
- 补充
- 拆分
- 重构
- 验证
- 沉淀
- 支持

Use "主导", "独立负责", "从 0 到 1", "上线", "高并发", or "海量数据" only when the user explicitly provides evidence.

## One-Sentence Summary Rules

- Focus on the project's problem, system capability, or role-relevant value.
- Keep it factual; do not write marketing copy.
- Keep the summary grounded in the user's submitted source and available implementation evidence.

Good:

- 面向异步任务执行场景，建设任务编排、状态追踪和失败恢复能力。

Weak:

- 本项目是一个功能强大的智能平台，极大提升业务效率。

## Final Polish Checklist

Before final output, check:

- Does the entry read like a resume, not a README?
- Does the number of main bullets match the agreed count or disclose why it cannot?
- Can each bullet support an interview follow-up?
- Are contribution boundaries clear?
- Are metrics sourced or explicitly marked as placeholders?
- Are all AI estimate candidates outside the direct-resume section?
- Is any sensitive internal name, URL, token, account, or customer name removed?
