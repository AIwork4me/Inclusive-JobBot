# IJ-0.7.2 A1 检查点

**INCOMPLETE。** 正式 A1、F0、Atlas V1.0 发布及生产就绪均为 **BLOCKED**。现有 G00–G29 门禁仍为 **1/30 PASS**。新版竞争评测依赖 A1 放行。 [正式门禁](../atlas/gates.json) · [发布门禁](../atlas/release_gates.json) · [实时队列](../atlas/physical_queue.json)

## 本轮实测和归档

| 实验 | 计划 | 有证据的试次 | PASS | FAIL | BLOCKED | NOT_RUN |
|---|---:|---:|---:|---:|---:|---:|
| Qwen3-8B PC-S TC-V2 开发面板 | 100 | 100 | 56 | 44 | 0 | 0 |
| 旧 JOB-V1 Arm A 首试 | 600 | 600 | 23 | 577 | 0 | 0 |
| 旧 JOB-V1 Arm B 首试 | 600 | 300 | 22 | 278 | 7 | 293 |

Qwen3-8B Q8_0 使用 Vulkan0、Radeon 8060S gfx1151、37/37 层卸载及 8K 上下文。每条试次绑定冻结开发集、引擎和模板哈希、运行配置、完整模型生成和 PID GPU 计数器。严格通过率为 56%，其中参数类型 0/14、顺序多工具 8/12、工具结果回传 3/12。名称为 `streaming_tool_call` 的 12 个任务使用本面板规定的非流式首试。 [运行配置](../evidence/IJ072/benchmark_validity/pc-s-tc/run.json) · [结果](../evidence/IJ072/benchmark_validity/pc-s-tc/summary.json) · [源码证据清单](../evidence/IJ072/benchmark_validity/pc-s-tc/raw-manifest.json)

旧 A/B 恢复验证了 checkpoint、SQLite 与封存会话的 SHA256。Arm A、Arm B 的已封存部分实际业务完成数均为 0。Arm B 的 7 个未封存终态保留在原目录，本轮未计入 PASS 或 FAIL。原始 JOB-V1 目录继续用于精确身份恢复。 [A/B 检查点](../evidence/IJ072/purpose_built/legacy-job-ab-checkpoint.json)

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

P1 在 Plan-first 首轮只要求计划对象，计划被接受后改用执行和终答合同。保持冻结输入、权限、工具、模型预算和评估器。Acting-first 的提示保持原样。软件 RED/GREEN 验证了 P0/P1 的差异。真实模型的效应大小及 P2–P5 仍无完整数据。 [运行器](../benchmarks/agentic_planning_v1/runner.py) · [回归](../tests/regression/ij07/test_agentic_planning_v1.py)

## A1 独立事实校验范围

报价 witness 对全部 80 个用例使用公开提示、公开工具和实际工具返回生成答复，其中中英文各 40 条。复核程序直接从 SQLite 读取目录，并确认业务表未变化。字段重排通过。错误工具、错误参数、缺少动作、重复动作、错误报价、额外字段和围栏终答由原严格评分拒绝。这是报价单一任务族的软件证据，覆盖其余 TC-V2、MULTITOOL-V1、AGENTIC-PLAN-V1、JOB-V1 的独立 witness 和盲审仍是 F0 未完成项。 [Witness](../benchmarks/atlas_validity/quote_witness.py) · [80 条结果](../evidence/IJ072/benchmark_validity/quote-controls.json)

## 候选资料核对

原有候选均保留。Microsoft 已提供 Aion 2.3B 的官方 WebGPU INT4 权重和运行说明，AMD 物理结果尚待验证。IBM 的 Granite 4.2 3B 模型卡确认支持原生工具定义，现有固定 llama.cpp 版本的现场准入仍待确认。LFM2.5-1.2B-Instruct 可作为同家族更低计算成本的扩展对照。Qwen3.8-27B 为 14B–32B 本地强对照候选，须单独冻结权重、运行时和提示后才可报告。 [Aion WebGPU 模型卡](https://huggingface.co/microsoft/Aion-1.0-Instruct-2.3B-ONNX-WebGPU) · [Granite 模型卡](https://huggingface.co/ibm-granite/granite-4.2-3b) · [LFM2.5 模型卡](https://huggingface.co/LiquidAI/LFM2.5-1.2B-Instruct) · [Qwen3.8 模型卡](https://huggingface.co/Qwen/Qwen3.8-27B)
