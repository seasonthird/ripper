# Resume Bullet Patterns

Patterns are quality checks, not fixed templates. Use them to test whether a bullet has enough technical substance. Do not mechanically fill every slot.

## Pattern 1: Problem - Action - Method - Result

Best for engineering optimization.

```text
围绕 [问题/目标]，设计/实现/优化 [技术对象]，通过 [方法] 支持/实现/降低/提升 [结果]。
```

Quality check:

- Is the problem specific?
- Is the technical object concrete?
- Is the method visible in code or user notes?
- Is the result cautious if no metric exists?

## Pattern 2: Module - Responsibility - Mechanism - Engineering Value

Best for backend and platform projects.

```text
负责 [模块/能力] 的设计与实现，基于 [技术机制] 完成 [核心逻辑]，提升 [可维护性/可追踪性/稳定性]。
```

Quality check:

- Does the module map to the target role?
- Does the mechanism explain how the work was done?
- Is the value more specific than "提升效率"?

## Pattern 3: Abstraction - Orchestration - Reuse

Best for AI Agent, FaaS, and platform engineering.

```text
将 [复杂流程] 抽象为 [统一对象/节点/接口]，支持 [组合/编排/复用]，降低 [配置/开发/调用] 成本。
```

Quality check:

- Is there real abstraction, or only a wrapper?
- Does orchestration include state, inputs, outputs, retry, or ordering?
- Is reuse supported by code structure, config, plugin, or API?

## Pattern 4: Experiment - Metric - Conclusion

Best for algorithms, evaluation, and research projects.

```text
设计 [实验/评测流程]，围绕 [指标] 对比 [方法/模型/参数]，分析 [结果] 并用于指导 [优化方向]。
```

Quality check:

- Are data, metrics, and methods named?
- Are results evidence-backed, user-confirmed, or left as `[待补充具体数据]`?
- If a number is AI-estimated, is it excluded from the direct-resume bullet and placed in a labeled review section?
- Does the conclusion guide a real optimization decision?

## Pattern 5: Cautious Expression

Best when data or contribution boundary is unclear.

```text
参与 [模块/能力] 建设，围绕 [技术问题] 完成 [具体实现/验证/优化]，[待补充具体数据或上线情况]。
```

Quality check:

- Does it avoid overclaiming?
- Does it mark missing evidence?
- Can the user later replace placeholders with confirmed facts?

## Final Bullet Review

Before final output, reject or rewrite bullets that:

- Only list stack names.
- Only describe project background.
- Use "主导/独立负责/从 0 到 1/上线" without user confirmation.
- Include metrics without source.
- Present AI estimates or industry averages as project facts.
- Cannot support an interview follow-up.
