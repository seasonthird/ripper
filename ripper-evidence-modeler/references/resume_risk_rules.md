# Resume Risk Rules

Use this file before final output to prevent inflated or unsafe resume writing.

## Evidence-Required Wording

Do not generate these expressions unless the submitted materials contain supporting evidence:

- 主导
- 独立负责
- 从 0 到 1
- 上线生产环境
- 支撑百万级用户
- 提升 xx%
- 降低 xx%
- 显著提升
- 大幅优化
- 行业领先
- 完整闭环
- 赋能业务
- 深度参与核心架构

## Cautious Rewrites

When the submitted source shows a capability but not its implementation or production scope, write:

- 围绕……完成模块开发
- 构建……能力
- 实现……机制
- 基于提交材料提炼为用户经历，但需明确实现、上线和指标边界

If concrete data is missing, write:

- 支持……
- 改善……
- 减少……人工配置
- 提升……可维护性
- 具体指标待补充
- 可补充响应时间、吞吐量、准确率、召回率、成本、失败率等指标

## Evidence Risk Levels

| Risk | Condition | Action |
| --- | --- | --- |
| Low | User stated contribution and code/docs support it | Write normally with concrete wording. |
| Medium | Code supports capability but implementation or production scope is unclear | Use cautious wording and add to "需要用户确认的信息". |
| High | Claim requires metrics, production launch, award, or scale but no evidence exists | Do not write as fact; use `[待补充具体数据]` or risk reminder. |

## Estimated Metric Boundary

- If concrete metrics are missing, ask whether the user wants placeholders or an AI-estimated candidate range for review.
- AI-estimated values must be labeled `AI 估算候选，禁止直接投递` and kept outside direct-resume bullets.
- Never convert an estimate into a resume fact merely because it appears plausible or matches an industry average.
- After the user confirms a value matches real monitoring, reports, or personal experience, treat it as `user-confirmed` and record the confirmation boundary.
- If the user asks to insert invented metrics directly, refuse that part and offer placeholders, code-verifiable counts, or a clearly labeled estimate worksheet.

## Confidentiality

Do not include:

- Internal tokens, API keys, account names, private URLs.
- Customer names or unreleased product names unless user explicitly wants them.
- Sensitive architecture details that are not needed for a resume.

## Final Risk Reminder

Final output must include a risk section: use `表达风险提醒` for direct-resume mode and `当前验证状态与表达风险` for highlight-library mode. It should state:

- Which claims need confirmation.
- Which metrics are placeholders.
- Which wording should stay cautious.
- Whether any AI estimate candidates remain unverified and excluded from the direct-resume version.
