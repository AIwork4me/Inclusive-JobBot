# IJ-0.7.2 A1 检查点

**INCOMPLETE。** 正式 A1、F0、Atlas V1.0 发布及生产就绪均为 **BLOCKED**。现有 G00–G29 门禁仍为 **1/30 PASS**。新版竞争评测依赖 A1 放行。 [正式门禁](../atlas/gates.json) · [发布门禁](../atlas/release_gates.json) · [实时队列](../atlas/physical_queue.json)

## 本轮实测和归档

| 实验 | 计划 | 有证据的试次 | PASS | FAIL | BLOCKED | NOT_RUN |
|---|---:|---:|---:|---:|---:|---:|
| Qwen3-8B PC-S TC-V2 开发面板 | 100 | 100 | 56 | 44 | 0 | 0 |
| Qwen3-8B PC-S MULTITOOL-V1 | 120 | 120 | 28 | 92 | 0 | 0 |
| Qwen3-8B PC-S Planning 双轨 | 320 | 320 | 4 | 316 | 0 | 0 |
| Qwen3-14B PC-S TC-V2 开发面板 | 100 | 100 | 66 | 34 | 0 | 0 |
| 旧 JOB-V1 Arm A 首试 | 600 | 600 | 23 | 577 | 0 | 0 |
| 旧 JOB-V1 Arm B 首试 | 600 | 300 | 22 | 278 | 7 | 293 |

Qwen3-8B Q8_0 使用 Vulkan0、Radeon 8060S gfx1151、37/37 层卸载及 8K 上下文。每条试次绑定冻结开发集、引擎和模板哈希、运行配置、完整模型生成和 PID GPU 计数器。严格通过率为 56%，其中参数类型 0/14、顺序多工具 8/12、工具结果回传 3/12。名称为 `streaming_tool_call` 的 12 个任务使用本面板规定的非流式首试。 [运行配置](../evidence/IJ072/benchmark_validity/pc-s-tc/run.json) · [结果](../evidence/IJ072/benchmark_validity/pc-s-tc/summary.json) · [源码证据清单](../evidence/IJ072/benchmark_validity/pc-s-tc/raw-manifest.json)

Qwen3-14B Q8_0 同样使用 Radeon Vulkan 和 8K 上下文，在同一 100 条开发用例上通过 66 条。参数类型 13/14、顺序多工具 11/12、错误恢复 0/14、工具结果回传 0/12。权重规模和模型身份同时变化，此比较只描述该固定面板。MULTITOOL 和 Planning 次序见硬件队列。 [结果](../evidence/IJ072/benchmark_validity/pc-s-j-tc/summary.json) · [原始证据清单](../evidence/IJ072/benchmark_validity/pc-s-j-tc/raw-manifest.json)

旧 A/B 恢复验证了 checkpoint、SQLite 与封存会话的 SHA256。Arm A、Arm B 的已封存部分实际业务完成数均为 0。Arm B 的 7 个未封存终态保留在原目录，本轮未计入 PASS 或 FAIL。原始 JOB-V1 目录继续用于精确身份恢复。 [A/B 检查点](../evidence/IJ072/purpose_built/legacy-job-ab-checkpoint.json)

### MULTITOOL 与 Planning PC-S

120 条试次全部封存了进程 GPU 计数器和生成轨迹。通过数随深度档位变化，从 2–3 步的 10/24 降至 11–15 步和 16–20 步各 4/24。Planning 首试全部完成，Acting-first 通过 4/160，Plan-first 通过 0/160。32 调用预算已通过流式和非流式软件回归，物理流式配对待测。 [MULTITOOL 结果](../evidence/IJ072/benchmark_validity/pc-s-multi/coverage.json) · [Planning 完整归档](../evidence/IJ072/benchmark_validity/pc-s-planning-full/diagnostic.json)

## RC-02 四候选报价回传

| 候选 | 原严格通过 | 正确工具结果出现在后续渲染提示 | 最终对象包含两项正确事实 | 仅有 JSON 围栏对应的严格失败 |
|---|---:|---:|---:|---:|
| LFM3-1.7B | 0/80 | 80/80 | 56/80 | 0/80 |
| Qwen3.5-2B | 0/80 | 80/80 | 80/80 | 55/80 |
| Ministral-3-3B | 0/80 | 79/80 | 39/80 | 39/80 |
| Gemma-4-E2B | 0/80 | 80/80 | 80/80 | 80/80 |

在 Qwen3.5、Ministral 和 Gemma 的 240 个报价试次中，终答围栏已出现在原生解析前的模型输出。Qwen3.5 的其余 25 个试次还被标为额外轨迹动作等失败。LFM3 有 19 条终答包含正确事实及附加字段。Ministral 有 41 条未同时复现两项正确事实。原评价器对围栏外观、键集合、事实和执行轨迹有严格要求，原始判定保留。字段诊断可识别有用信息，模板或提示调整的实际增益仍须配对实测。 [逐条对账](../evidence/IJ072/root_causes/rc02-quote-diagnostic.json) · [源码失败索引](../atlas/root_causes/failure_ledger.jsonl)

## RC-01 双轨规划零分

复查 1,600 条首试和 960 条重复。Plan-first 共 1,280 条在首轮计划校验处失败，终答阶段未执行。Acting-first 首试有 560 条在提议边界被拒，240 条进入终态评分。进入终态的 240 条中有 69 条符合终答结构，业务验证仍为 0/800。首试每轨有 110 条无适用工具执行指标。 [分层结果](../evidence/IJ072/root_causes/rc01-diagnostic.json)

P1 在 Plan-first 首轮只要求计划对象，计划被接受后改用执行和终答合同。保持冻结输入、权限、工具、模型预算和评估器。Acting-first 的提示保持原样。软件 RED/GREEN 验证了 P0/P1 的差异。Qwen3-8B 在冻结的 20 条 L0 Plan-first 配对中，P1 把初始协议通过从 0/20 提高到 7/20。严格端到端和业务结果均保持 0/20，P1 的 3 条虚报完成被安全评分识别。四模型 L0 配对共 80 对。MiniCPM5 初始协议通过从 0/20 到 3/20，LFM3 从 1/20 到 3/20，Gemma 从 0/20 到 1/20。两臂的严格通过均为 0/80。覆盖限于 L0，P2–P5 尚未执行。 [配对证据](../evidence/IJ072/benchmark_validity/pc-p-l0-model-comparison.json) [运行器](../benchmarks/agentic_planning_v1/runner.py) · [回归](../tests/regression/ij07/test_agentic_planning_v1.py)

后续 PC-P 面板已预注册 1,152 条 Plan-first 试次，覆盖四种模型、L0–L7 中英文共 32 个固定用例。P2 增加纯格式示例，P3 请求首轮原生 JSON Schema，P4 精简公开只读工具描述，P5 增加三种两因子组合及完整组合。动作参数、权限检查和评估规则沿用冻结版。当前验证为软件测试，P3 和相关组合还需从实际模板与生成记录核实约束有没有应用。 [面板](../atlas/benchmarks/pc_p_factorial.json) · [可恢复运行器](../scripts/tools/atlas_pc_p.py)

## A1 独立事实校验范围

报价 witness 对全部 80 个用例使用公开提示、公开工具和实际工具返回生成答复，其中中英文各 40 条。复核程序直接从 SQLite 读取目录，并确认业务表未变化。字段重排通过。错误工具、错误参数、缺少动作、重复动作、错误报价、额外字段和围栏终答由原严格评分拒绝。报价变异结果单列为该任务族的软件证据。独立人工盲审仍待完成。 [Witness](../benchmarks/atlas_validity/quote_witness.py) · [80 条结果](../evidence/IJ072/benchmark_validity/quote-controls.json)

TC-V2 的 500/500 条和 MULTITOOL-V1 的 600/600 条公开输入 witness 全部通过原评分。前者独立读取 500 份 SQLite 业务状态，后者校验 75 份有持久化的审核任务。两套评测均拒绝了缺动作、错参数和错业务事实的变异。MULTITOOL 另外拒绝了缺失用户更新的试次变异。 [TC-V2 见证](../evidence/IJ072/benchmark_validity/tc-holdout-witness.json) · [MULTITOOL 见证](../evidence/IJ072/benchmark_validity/multitool-witness.json.gz)

L0 公开提示 witness 在 Acting-first 的 100 条零动作任务全部匹配冻结 Oracle。错误对象、错误终止动作和错误事实各测试 100 次，均被评分拒绝。 [L0 见证结果](../evidence/IJ072/benchmark_validity/planning-intent-controls.json)

L1–L3 的 300 条读取见证和 L4–L7 的 400 条执行见证均通过。全体 800 条 Acting-first 软件试次使用公开输入决定动作，并在旧沙箱中检查实际响应和终态。L4–L7 的状态检查覆盖动态修订、草稿、确认和交付，存储范围为沙箱进程内。 [L1–L3](../evidence/IJ072/benchmark_validity/planning-read-controls.json) · [L4–L7](../evidence/IJ072/benchmark_validity/planning-advanced-controls.json)

Plan-first 在启动沙箱前仅用公开输入生成条件计划，执行见证独立根据实际工具反馈选取动作。全 800 条执行事实和沙箱状态通过，严格试次 672 PASS、128 FAIL。L4 仅 15/100 严格通过，L7 为 57/100，其余各层均为 100/100。53 条初始计划超过动作数上限，75 条未覆盖评估器要求的初始子目标。移除初始计划的 800 个变异均被拒绝。该对照定位了冻结初始计划门槛的剩余差异，计划的可执行性资格仍未关闭。 [初始计划和实际轨迹](../evidence/IJ072/benchmark_validity/planning-plan-controls.json.gz)

JOB-V1 冻结的 600 条主面板使用 Arm B 的公开工具定义，独立生成事实和草稿，通过实际工具与 SQLite 交叉校验。600/600 通过，其中 350 条完成业务，其余 250 条正确拒绝、澄清或转交。错误业务回答，以及适用用例中缺失的用户更新和持久化草稿，均由原评分拒绝。 [JOB-V1 独立见证](../evidence/IJ072/benchmark_validity/job-witness.json.gz)

## 候选资料核对

原有候选均保留。Microsoft 已提供 Aion 2.3B 的官方 WebGPU INT4 权重和运行说明，AMD 物理结果尚待验证。IBM 的 Granite 4.2 3B 模型卡确认支持原生工具定义，现有固定 llama.cpp 版本的现场准入仍待确认。LFM2.5-1.2B-Instruct 可作为同家族更低计算成本的扩展对照。已选用 Qwen3-14B Q8_0 作为进一步的同家族强对照，已逐字节验证 ModelScope 权重，共通过 10/10 项 CPU 与 Radeon Vulkan 准入检查，GPU 实际卸载 41/41 层。完整强参照任务资格仍待实测。Qwen3.8-27B 为另一个待核验候选。 [14B 权重身份](../atlas/benchmarks/pc_s_qwen3_14b.json) [Aion WebGPU 模型卡](https://huggingface.co/microsoft/Aion-1.0-Instruct-2.3B-ONNX-WebGPU) · [Granite 模型卡](https://huggingface.co/ibm-granite/granite-4.2-3b) · [LFM2.5 模型卡](https://huggingface.co/LiquidAI/LFM2.5-1.2B-Instruct) · [Qwen3.8 模型卡](https://huggingface.co/Qwen/Qwen3.8-27B)
