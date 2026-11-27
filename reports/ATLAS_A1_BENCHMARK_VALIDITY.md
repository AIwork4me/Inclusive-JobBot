# Atlas A1 评测有效性审计

**A1 — BLOCKED。** 软件控制可以贯通旧合同。全量独立作者 Witness、关键 Mutation 的跨评测集覆盖、双语样本审阅、真实强模型与提示因果对照仍缺证据。 [对照结果](ATLAS_POSITIVE_NEGATIVE_CONTROL.md) · [提示合同分析](ATLAS_PROMPT_CONTRACT_CAUSAL_ANALYSIS.md)

| 审计问题 | 源码与验证结果 |
|---|---|
| 1. 计划与最终指令干扰 | 首次请求同时加载计划合同与最终 JSON 合同，runner 首轮只接受计划对象。确认指令层重叠，效果大小待配对。 [合同](../benchmarks/agentic_planning_v1/contract.py#L45-L87) · [运行器](../benchmarks/agentic_planning_v1/runner.py#L151-L165) |
| 2. L0 零工具 | 作者设置预算为零且计划可为零动作。手工编写的中文零工具例由两轨完整通过，验证 runner 层可达。 [作者](../benchmarks/agentic_planning_v1/author.py#L197-L219) · [用例](../tests/regression/test_atlas_negative_controls.py) |
| 3. 合法终止 | L0 澄清、L5 权限拒绝、L7 确认拒绝均有软件 Witness。规划最终协议允许 clarify/escalate。 [Oracle](../benchmarks/agentic_planning_v1/oracle.py#L201-L220) · [全量软件记录](../evidence/IJ071/controls-reconciled.json.gz) |
| 4. 隐藏顺序 | 图的 eligible 检查真实依赖，等价独立顺序通过测试。MULTITOOL 作者参考轨迹使用同一依赖规则，未完成盲审。 [规划 Oracle](../benchmarks/agentic_planning_v1/oracle.py#L18-L22) · [参考回放](../benchmarks/multitool_v1/verify.py#L14-L33) |
| 5. 等价工具 | L2 status/status_mirror 两条路径通过真实 runner。其他等价路径的覆盖仍需受控样本。 [作者](../benchmarks/agentic_planning_v1/author.py#L222-L240) · [等价路径回归](../tests/regression/test_atlas_negative_controls.py) |
| 6. 中文编号边界 | 当前 ASCII 边界支持汉字紧邻 REF ID 并拒绝 ASCII 子串。旧失败和修复诊断保留，独立真实模型资格待测。 [边界](../benchmarks/agentic_planning_v1/runner.py#L23-L24) · [回归](../tests/regression/ij07/test_agentic_planning_v1.py#L19) |
| 7. 状态和授权 | 规划仿真与 Gateway 双重检查各有覆盖。伪造确认、提前写、重复提交被拒绝或维持一次有效写。规划 sandbox 状态为进程内。 [仿真](../benchmarks/agentic_planning_v1/sandbox.py#L37-L64) · [Gateway](../src/model_gateway/execution_policy.py#L161-L209) |
| 8. 模型可见信息 | 输入只含公开任务、工具声明与政策，动态约束来自工具/用户事件。逐任务语言和可推导性审阅尚未完成。 [合同](../benchmarks/agentic_planning_v1/contract.py#L67-L87) · [动态作者](../benchmarks/agentic_planning_v1/author.py#L256-L286) |
| 9. Oracle 隐藏信息 | 初始计划按真实私有图核算必需子目标；作者选择故障，评分排除其后节点。该策略仍需用独立计划与合理备选路径审查。 [初始计划](../benchmarks/agentic_planning_v1/oracle.py#L33-L112) |
| 10. 格式与语义 | 旧终态直接要求精确 JSON。追加两层诊断验证了围栏 JSON 和合法 JSON 错误事实两组反例。 [旧 Oracle](../benchmarks/agentic_planning_v1/oracle.py#L196-L219) · [分层回归](../tests/regression/test_atlas_scoring.py) |
| 11. 安全拒绝 | 合成权限和确认拒绝进入正常终态。旧法对无需拒绝的完成任务给 FAIL。业务解释的人工对照待补。 [终止评分](../benchmarks/agentic_planning_v1/oracle.py#L210-L220) · [Mutation](../tests/regression/test_atlas_negative_controls.py) |
| 12. 预算一致性 | MULTITOOL 非流式候选已显式用 32 上限，Gateway 及流式通用上限 16，规划同一 turn 另有限制并依赖预算。两个协议仍需要独立等价性测试。 [MULTITOOL](../benchmarks/multitool_v1/run.py#L145-L162) · [流式](../src/model_gateway/streaming.py#L68-L97) · [TC-V2](../benchmarks/tool_calling_v2/holdout/runner.py#L77-L149) |
| 13. 额外动作 | 案例由 graph 的子目标和终态决定。规划拒绝完成后超出可用路径的动作。L6 验证草稿及 L7 验证已批准交付属于明确合同内容。复核业务必要性仍需独立审阅。 [作者](../benchmarks/agentic_planning_v1/author.py#L347-L380) |
| 14. 模板近重复 | TC-V2 按模板分割并比对归一化文本，规划作者按固定场景与索引循环构造任务。唯一字符串数不足以证明结构泛化。 [TC-V2 冻结](../benchmarks/tool_calling_v2/holdout/dataset.py#L38-L89) · [规划作者](../benchmarks/agentic_planning_v1/author.py#L382-L385) |
| 15. 中英文等价 | 双语作者与分层有设计覆盖。软件回放表明协议可达，人工盲审及模型语言交互效应仍待观察。 [作者](../benchmarks/agentic_planning_v1/author.py#L167-L185) |
| 16. 共享错误假设 | 规划生成器同源生成 world、witness 与 final，MULTITOOL 参考回放显式使用 workflow，JOB 部分终态取 expected.answer。需要独立作者及对账来关闭。 [规划](../benchmarks/agentic_planning_v1/author.py#L176-L194) · [MULTITOOL](../benchmarks/multitool_v1/verify.py#L14-L33) · [JOB](../benchmarks/job_productivity_v1/holdout/verify.py#L47-L75) |

TC-V2 的 Oracle 验证审计、权限和持久状态。软件对照走了该 runner 的非流式路径，流式状态仍沿用旧归档并待独立对照。 [TC-V2 持久评分](../benchmarks/tool_calling_v2/holdout/oracle.py#L53-L126)
