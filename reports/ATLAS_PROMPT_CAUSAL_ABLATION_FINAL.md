# IJ-0.7.2 PC-P 提示消融实验

**物理实验覆盖 PASS。** 预注册的 1,152 条 Radeon Vulkan 试次全部封存，严格端到端为 4 PASS、1,148 FAIL、0 BLOCKED、0 NOT_RUN。四次通过出现在 Qwen3-8B 的同两个 L2 用例，各在两个配置下通过。A1 Benchmark Validity 仍为 BLOCKED。 [完整逐例结果](../evidence/IJ072/benchmark_validity/pc-p-factorial-full-four-models.json) · [验收状态](../atlas/gates.json)

## 固定设计

MiniCPM5-2B、LFM3-1.7B、Gemma-4-E2B 和 Qwen3-8B 在同一组 32 个 Plan-first 用例上各跑九个配置。L0–L7 每层各取两个英文和两个中文用例。冻结的 Case ID、种子、工具预算及数据与原始评分关联。四模型均使用干净实验源码 `876ee84baa86f86399a5ae46bd7721671e16a090`。每个配置保留独立 Run ID、模型和运行时身份、首轮请求、采样日志及 GPU 进程证据。 [预注册设计](../atlas/benchmarks/pc_p_factorial.json) · [运行索引](../evidence/IJ072/benchmark_validity/pc-p-factorial-progress.json)

下表每格为“初始协议通过 / 业务结果通过 / 严格端到端通过”。每个模型和配置的分母为 32。各评分维度的适用与已评估分母、各层级与语言分组、配对变化及因子交互保存在完整矩阵。 [矩阵及分母](../evidence/IJ072/benchmark_validity/pc-p-factorial-full-four-models.json)

| 配置 | MiniCPM5-2B | LFM3-1.7B | Gemma-4-E2B | Qwen3-8B |
|---|---:|---:|---:|---:|
| P0 原合同 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| P1 分阶段 | 0 / 0 / 0 | 1 / 0 / 0 | 0 / 0 / 0 | 2 / 0 / 0 |
| P2 示例 | 1 / 0 / 0 | 2 / 0 / 0 | 0 / 0 / 0 | 7 / 1 / 0 |
| P3 首轮原生 Schema | 32 / 1 / 0 | 32 / 1 / 0 | 32 / 11 / 0 | 32 / 0 / 0 |
| P4 精简工具描述 | 0 / 0 / 0 | 1 / 0 / 0 | 0 / 0 / 0 | 2 / 0 / 0 |
| P5-es 示例和 Schema | 32 / 0 / 0 | 32 / 2 / 0 | 32 / 11 / 0 | 32 / 1 / 0 |
| P5-ec 示例和精简 | 1 / 0 / 0 | 2 / 0 / 0 | 0 / 0 / 0 | 8 / 3 / 2 |
| P5-sc Schema 和精简 | 32 / 0 / 0 | 32 / 0 / 0 | 32 / 9 / 0 | 32 / 0 / 0 |
| P5 三项组合 | 32 / 0 / 0 | 32 / 1 / 0 | 32 / 9 / 0 | 32 / 3 / 2 |

## 首轮与下游失败

- P0 的 128 条首轮全部停止在工具执行前。107 条返回原生工具调用，10 条直接返回终答对象，11 条属于其他响应形态。运行器以初始计划不符拒绝 126 条，以可见推理标记拒绝另外 2 条。P1 同时移除了首轮终答指令并推迟了行动提示，首轮通过 3/128，业务结果通过 0/128。 [冻结合同](../benchmarks/agentic_planning_v1/contract.py) · [运行器](../benchmarks/agentic_planning_v1/runner.py) · [逐例首轮证据](../evidence/IJ072/benchmark_validity/pc-p-factorial-full-four-models.json)
- 每个带 Schema 的配置都在物理日志中验证了原生采样语法。四种配置共 512/512 首轮通过、49 次业务结果通过、2 次严格通过。其余五种配置共 27/640 首轮通过、4 次业务结果通过、2 次严格通过。Schema 仅施加在首轮。P3 单项得到 13/128 次业务结果通过，严格端到端为 0/128。 [采样与分层结果](../evidence/IJ072/benchmark_validity/pc-p-factorial-full-four-models.json)
- MiniCPM5 在四种 Schema 配置下有四份计划满足冻结执行要求。其中两份含正确编号及额外名称，两份使用了冻结枚举外的目标措辞。这四份均未匹配冻结目标。MiniCPM5 的唯一业务结果通过来自 P3 的 L1 读取。 [MiniCPM5 逐例证据](../evidence/IJ072/benchmark_validity/pc-p-a-factorial-wire.json) · [目标字段核对](../evidence/IJ072/benchmark_validity/pc-p-factorial-full-four-models.json)
- LFM3 的 P3 有 16 个合格首轮之后的响应触发可见推理标记拒绝。请求关闭了推理，渲染后的提示以空的推理块结束。这 16 次的新增采样字节、解析前字节和助手线路内容均含推理标记。 [LFM3 P3 原始归档](../evidence/IJ072/benchmark_validity/pc-p-b-clean-p3-032/bundle.json) · [逐例采样检查](../evidence/IJ072/benchmark_validity/pc-p-factorial-full-four-models.json)
- Gemma 的四种 Schema 配置共 40 次业务结果通过，其中 37 次终答带 Markdown 代码围栏，且所有 40 次严格结果均为 FAIL。业务结果通过分布在 L1、L2、L3 及 L5。Qwen3-8B 的四次严格通过来自 `AP1-L2-023` 和 `AP1-L2-070` 在 P5-ec 和 P5 下的读取请求。 [Gemma 逐例证据](../evidence/IJ072/benchmark_validity/pc-p-g-factorial-wire.json) · [Qwen3-8B 逐例证据](../evidence/IJ072/benchmark_validity/pc-p-h-factorial-full.json)

这些结果针对固定诊断面板。冻结 Plan-first 软件见证有 128/800 严格失败，另有 602 个矛盾条件变异在原始规划评分中未被拒绝。独立人工盲审仍为 NOT_RUN。 [独立计划见证](../evidence/IJ072/benchmark_validity/planning-plan-controls.json.gz) · [条件变异](../evidence/IJ072/benchmark_validity/planning-precondition-controls.json) · [盲审说明](ATLAS_A1_BLIND_REVIEW.md)

从归档重算运行 `python -m scripts.tools.atlas_compare_pc_p_factorial --full-matrix --check`。 [从新 clone 复现](../docs/ATLAS_A1_REPRODUCIBILITY.md)
