# IJ-0.7 模型选择与路由边界

当前有物理证据支持将明确、结构化的低风险任务优先路由到确定性业务流程。
F 臂首次判定 592/600，较 99% 目标低 0.33 个百分点。八条
混合语言更正在写入前请求澄清。涉及真实写入、审批和敏感资源时，按 Gateway
授权、确定性校验和可信人工确认处理。
 [业务结果](IJ07_BUSINESS_VALUE_VALIDATION.md) · [架构及恢复路径](IJ07_JOBBOT_ARCHITECTURE_RECOMMENDATION.md)

| 路由候选 | 已测边界 | 资格决定 |
|---|---|---|
| MiniCPM5-2B Q8_0 | 双后端顺序工具各 25/100，双轨规划各 0/800 | 独立工具调用和自主规划 `FAIL`。保留受限只读研究用途。 |
| LFM3、Qwen3.5、Ministral、Gemma | 同一条开发任务正确调用工具及计算结果。仅 LFM3 满足裸 JSON 合同 | 四臂正式资格和选型排序 `NOT_RUN`。 |
| Aion ONNX INT4 | 显式串行指令在 CPU 和 Radeon WebGPU 上完成一个同 token 依赖链 | 独立任务准入 `NOT_RUN`。 |
| Qwen3-8B 参考 | 同三案中的一案正确持久化文档草稿 | 岗位层面的模型增量 `NOT_RUN`。 |

每种模型的权重、模板、测试后端及边界保存在独立护照中。Radeon 观测支持
当前计算容量估计，DX-M2 仅有迁移要求和算子清单，物理适配结论为 `NOT_RUN`。
 [九个模型护照](../evidence/IJ07/model_passports/) · [边缘部署约束](IJ07_EDGE_DEPLOYMENT_SUITABILITY.md)
