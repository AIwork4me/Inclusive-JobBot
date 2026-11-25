# IJ-0.7.2 A1 检查点

**INCOMPLETE。** 正式 A1、F0、Atlas V1.0 发布及生产就绪均为 **BLOCKED**。现有 G00–G29 门禁仍为 **1/30 PASS**。新版竞争评测依赖 A1 放行。 [正式门禁](../atlas/gates.json) · [发布门禁](../atlas/release_gates.json) · [实时队列](../atlas/physical_queue.json)

## 本轮实测和归档

| 实验 | 计划 | 有证据的试次 | PASS | FAIL | BLOCKED | NOT_RUN |
|---|---:|---:|---:|---:|---:|---:|
| Qwen3-8B PC-S TC-V2 开发面板 | 100 | 100 | 56 | 44 | 0 | 0 |
| Qwen3-8B PC-S MULTITOOL-V1 | 120 | 120 | 28 | 92 | 0 | 0 |
| Qwen3-8B PC-S Planning 双轨 | 320 | 320 | 4 | 316 | 0 | 0 |
| Qwen3-14B PC-S TC-V2 开发面板 | 100 | 100 | 66 | 34 | 0 | 0 |
| Qwen3-14B PC-S MULTITOOL-V1 | 120 | 120 | 45 | 75 | 0 | 0 |
| Qwen3-14B PC-S Planning 双轨 | 320 | 320 | 35 | 285 | 0 | 0 |
| 旧 JOB-V1 Arm A 首试 | 600 | 600 | 23 | 577 | 0 | 0 |
| 旧 JOB-V1 Arm B 首试 | 600 | 300 | 22 | 278 | 7 | 293 |

Qwen3-8B Q8_0 使用 Vulkan0、Radeon 8060S gfx1151、37/37 层卸载及 8K 上下文。每条试次绑定冻结开发集、引擎和模板哈希、运行配置、完整模型生成和 PID GPU 计数器。严格通过率为 56%，其中参数类型 0/14、顺序多工具 8/12、工具结果回传 3/12。名称为 `streaming_tool_call` 的 12 个任务使用本面板规定的非流式首试。 [运行配置](../evidence/IJ072/benchmark_validity/pc-s-tc/run.json) · [结果](../evidence/IJ072/benchmark_validity/pc-s-tc/summary.json) · [源码证据清单](../evidence/IJ072/benchmark_validity/pc-s-tc/raw-manifest.json)

Qwen3-14B Q8_0 同样使用 Radeon Vulkan 和 8K 上下文，在同一 100 条开发用例上通过 66 条。参数类型 13/14、顺序多工具 11/12、错误恢复 0/14、工具结果回传 0/12。权重规模和模型身份同时变化，此比较只描述该固定面板。MULTITOOL 和 Planning 次序见硬件队列。 [结果](../evidence/IJ072/benchmark_validity/pc-s-j-tc/summary.json) · [原始证据清单](../evidence/IJ072/benchmark_validity/pc-s-j-tc/raw-manifest.json)

旧 A/B 恢复验证了 checkpoint、SQLite 与封存会话的 SHA256。Arm A、Arm B 的已封存部分实际业务完成数均为 0。Arm B 的 7 个未封存终态保留在原目录，本轮未计入 PASS 或 FAIL。原始 JOB-V1 目录继续用于精确身份恢复。 [A/B 检查点](../evidence/IJ072/purpose_built/legacy-job-ab-checkpoint.json)

### MULTITOOL 与 Planning PC-S

120 条试次全部封存了进程 GPU 计数器和生成轨迹。通过数随深度档位变化，从 2–3 步的 10/24 降至 11–15 步和 16–20 步各 4/24。Planning 首试全部完成，Acting-first 通过 4/160，Plan-first 通过 0/160。 [MULTITOOL 结果](../evidence/IJ072/benchmark_validity/pc-s-multi/coverage.json) · [Planning 完整归档](../evidence/IJ072/benchmark_validity/pc-s-planning-full/diagnostic.json)

相同的 120 条 MULTITOOL 用例全部封存。14B 严格通过 45 条，8B 通过 28 条。两者同通过 25 条，仅 14B 通过 20 条，仅 8B 通过 3 条，两者同失败 72 条。14B 在 16–20 步通过 8/24，在 11–15 步通过 6/24。该固定面板的配对结果支持在这些任务上继续作强参照。 [14B 完整归档](../evidence/IJ072/benchmark_validity/pc-s-j-multi-full/coverage.json) · [逐配对结果和区间](../evidence/IJ072/benchmark_validity/pc-s-multitool-qwen-pair.json)

另完成 10 对 14B 现场流式对照，覆盖五个深度档和两种语言。HTTP JSON 和 SSE 的严格结果、动作顺序、参数、回传和终答全部一致。两臂现场单轮最大观察值为 20 个工具调用，配置预算均为 32，32 调用边界由软件回归覆盖。 [物理配对](../evidence/IJ072/benchmark_validity/pc-s-j-multitool-streaming-pairs.json) · [SSE 原始归档](../evidence/IJ072/benchmark_validity/pc-s-j-multi-stream/coverage.json)

320 条 PC-S Planning 已形成分层诊断。Acting-first 的已执行动作中，有 129 个用例可评估工具名称和参数，工具名称通过 96/129，参数通过 76/129。45 个用例进入可评估的动态重规划，0 个通过。Plan-first 没有可评估的实际工具名称或参数。零工具场景与阶段未执行各自记录。 [诊断及分母](../evidence/IJ072/benchmark_validity/pc-s-planning-layered.json)

Qwen3-14B 已封存全部 320 条 Planning 试次。Acting-first 严格通过 35/160，Plan-first 为 0/160。Acting-first 的 20 条 L6 无严格通过，L7 为 2/20。分层评估中，Acting-first 有 38/160 达到可验证业务结果，26 条到达可评估的动态重规划，其中 7 条通过。原 Plan-first 首轮协议 0/160，通过不了首轮的任务没有可评估的终答。两种强参照模型的 540 条冻结试次均已封存。 [14B 完整归档](../evidence/IJ072/benchmark_validity/pc-s-j-planning-full/diagnostic.json) · [14B 分层诊断](../evidence/IJ072/benchmark_validity/pc-s-j-planning-layered.json)

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

P1 在 Plan-first 首轮只要求计划对象，计划被接受后改用执行和终答合同。保持冻结输入、权限、工具、模型预算和评估器。Acting-first 的提示保持原样。软件 RED/GREEN 验证了 P0/P1 的差异。Qwen3-8B 在冻结的 20 条 L0 Plan-first 配对中，P1 把初始协议通过从 0/20 提高到 7/20。严格端到端和业务结果均保持 0/20，P1 的 3 条虚报完成被安全评分识别。四模型 L0 配对共 80 对。MiniCPM5 初始协议通过从 0/20 到 3/20，LFM3 从 1/20 到 3/20，Gemma 从 0/20 到 1/20。两臂的严格通过均为 0/80。覆盖限于 L0。 [配对证据](../evidence/IJ072/benchmark_validity/pc-p-l0-model-comparison.json) [运行器](../benchmarks/agentic_planning_v1/runner.py) · [回归](../tests/regression/ij07/test_agentic_planning_v1.py)

后续 PC-P 面板已预注册 1,152 条 Plan-first 试次，覆盖四种模型、L0–L7 中英文共 32 个固定用例。P2 增加纯格式示例，P3 请求首轮原生 JSON Schema，P4 精简公开只读工具描述，P5 增加三种两因子组合及完整组合。动作参数、权限检查和评估规则沿用冻结版。 [面板](../atlas/benchmarks/pc_p_factorial.json) · [可恢复运行器](../scripts/tools/atlas_pc_p.py)

Qwen3-8B P3 五次 Radeon 线路探测均通过格式校验，原始采样记录确认首轮使用相同的原生语法。四个 L0 用例计划超出零动作限制，一个 L1 用例提交了空的条件列表，五次严格结果均为 FAIL。归档操作使探测工作树在配置采样时被标记为 dirty，因此保留为线路诊断。运行器已在配置采样时增加干净工作树校验。 [线路审计](../evidence/IJ072/benchmark_validity/pc-p-h-p3-wire-probe.json) · [GPU 轨迹](../evidence/IJ072/benchmark_validity/pc-p-h-factorial-p3-005/diagnostic.json)

正式分层面板当前封存 423/1,152 条，累计 4 PASS、419 FAIL。MiniCPM5、LFM3、Gemma 和 Qwen3-8B 均在相同的四条 L0 和一条 L1 上运行了全部九个配置。含 Schema 的 80 次首轮均由采样日志证明启用了原生语法，并通过 Schema 结构校验。该首块 180 条严格端到端均为 FAIL。首块只有一条匹配用例提供工具定义。 [四模型首块及交互对照](../evidence/IJ072/benchmark_validity/pc-p-factorial-first-five-four-models.json)

Qwen3-8B 的 P0–P4 各完成全部 32 条 L0–L7。初始协议分别通过 0、2、7、32、2 条。P2 得到一个可验证业务结果，其他四配置均为 0，严格端到端合计为 0/160。P3 的 32 条原生采样已逐条验明。P4 的 28 条工具用例保持请求结构、工具参数和结果字段，描述精简使首轮减少 4–44 个词元。 [完整 P3 原生采样证据](../evidence/IJ072/benchmark_validity/pc-p-h-p3-wire-full.json) · [完整 P4 工具定义检查](../evidence/IJ072/benchmark_validity/pc-p-h-p4-tool-definition-check.json)

Qwen3-8B 全部九个配置共封存 288 条。示例加精简工具与 P5 全组合分别通过 2/32，严格通过出现在相同两个 L2 用例。四个含 Schema 的配置都达到 32/32 首轮协议通过，P3 单独使用时业务结果为 0/32，P5 全组合为 3/32。剩余 729 条属于另外三个模型的分层扩展面板。 [Qwen3-8B 完整九配置及交互对照](../evidence/IJ072/benchmark_validity/pc-p-h-factorial-full.json)

Qwen3-8B 的原始 P0 首轮在 8 条用例直接输出终答对象，在另外 24 条发起原生工具调用。运行器在执行任何工具前拒绝了全部 32 条。移除首轮终答指令后，P1 仍有 28 条直接发起工具调用，只有 2 条按原冻结协议进入执行。逐条记录包含首轮响应形态、停止原因、运行器首个拒绝原因、各层级和语言的独立分母及配对变化。 [首轮线路与分层证据](../evidence/IJ072/benchmark_validity/pc-p-h-factorial-wire.json)

| 配置 | 初始协议通过 | 计划可执行性通过 | 可验证业务结果 | 严格端到端 |
|---|---:|---:|---:|---:|
| P0 | 0/20 | 0/20 | 0/20 | 0/20 |
| P1 | 3/20 | 0/20 | 0/20 | 0/20 |
| P2 | 6/20 | 0/20 | 1/20 | 0/20 |
| P3 | 20/20 | 1/20 | 2/20 | 0/20 |
| P4 | 3/20 | 0/20 | 0/20 | 0/20 |
| P5 全组合 | 20/20 | 0/20 | 3/20 | 0/20 |

## A1 独立事实校验范围

报价 witness 对全部 80 个用例使用公开提示、公开工具和实际工具返回生成答复，其中中英文各 40 条。复核程序直接从 SQLite 读取目录，并确认业务表未变化。字段重排通过。错误工具、错误参数、缺少动作、重复动作、错误报价、额外字段和围栏终答由原严格评分拒绝。报价变异结果单列为该任务族的软件证据。独立人工盲审仍待完成。 [Witness](../benchmarks/atlas_validity/quote_witness.py) · [80 条结果](../evidence/IJ072/benchmark_validity/quote-controls.json)

TC-V2 的 500/500 条和 MULTITOOL-V1 的 600/600 条公开输入 witness 全部通过原评分。前者独立读取 500 份 SQLite 业务状态，后者校验 75 份有持久化的审核任务。两套评测均拒绝了缺动作、错参数和错业务事实的变异。MULTITOOL 另外拒绝了缺失用户更新的试次变异。 [TC-V2 见证](../evidence/IJ072/benchmark_validity/tc-holdout-witness.json) · [MULTITOOL 见证](../evidence/IJ072/benchmark_validity/multitool-witness.json.gz)

TC-V2 扩展控制拒绝了 1,500 条不可用工具、未见业务编号、虚报成功或重复写入的轨迹变异。实际合成沙箱拒绝了 500 次未授权 ID、50 次无签名写请求，并阻止了 50 次重复写请求产生第二次业务变更。 [扩展授权和状态控制](../evidence/IJ072/benchmark_validity/tc-holdout-extended-controls.json.gz)

在 37 个允许草拟的 MULTITOOL 用例中，原合成沙箱都允许先草拟后读取审核。新增显式的 `--require-observed-draft` 配置只在存在上一轮的有效审核观测时授权草拟。新配置拒绝了全部 37 个提前及同轮请求，允许随后合法草稿，重复调用没有产生第二次业务变化。600 个独立软件见证均通过。模型 GPU 回归暂为 NOT_RUN，已为同一批 37 条用例登记 Qwen3-14B 配对回归，并规定单独统计实际出现的提前草拟及持久化状态。 [根因与回归证据](../evidence/IJ072/benchmark_validity/multitool-observed-draft-controls.json.gz) · [GPU 队列](../atlas/physical_queue.json)

L0 公开提示 witness 在 Acting-first 的 100 条零动作任务全部匹配冻结 Oracle。错误对象、错误终止动作和错误事实各测试 100 次，均被评分拒绝。 [L0 见证结果](../evidence/IJ072/benchmark_validity/planning-intent-controls.json)

L1–L3 的 300 条读取见证和 L4–L7 的 400 条执行见证均通过。全体 800 条 Acting-first 软件试次使用公开输入决定动作，并在旧沙箱中检查实际响应和终态。L4–L7 的状态检查覆盖动态修订、草稿、确认和交付，存储范围为沙箱进程内。 [L1–L3](../evidence/IJ072/benchmark_validity/planning-read-controls.json) · [L4–L7](../evidence/IJ072/benchmark_validity/planning-advanced-controls.json)

独立 L4–L7 见证的 3,933 个轨迹变异全部被冻结评分拒绝，包含错误依赖、缺失业务状态、遗漏新增范围、忽略工具异常、提前写入、伪造审批和重复提交。另向合成沙箱提交了 360 次提前、伪造或重复写调用。每次均被拒且状态没有变化。范围限于该 400 个规划用例的软件控制。 [逐条变异结果](../evidence/IJ072/benchmark_validity/planning-advanced-mutations.json.gz)

Plan-first 在启动沙箱前仅用公开输入生成条件计划，执行见证独立根据实际工具反馈选取动作。全 800 条执行事实和沙箱状态通过，严格试次 672 PASS、128 FAIL。L4 仅 15/100 严格通过，L7 为 57/100，其余各层均为 100/100。53 条初始计划超过动作数上限，75 条未覆盖评估器要求的初始子目标。移除初始计划的 800 个变异均被拒绝。该对照定位了冻结初始计划门槛的剩余差异，计划的可执行性资格仍未关闭。 [初始计划和实际轨迹](../evidence/IJ072/benchmark_validity/planning-plan-controls.json.gz)

对 L4 和 L7 的 200 条见证仅归一化公开任务中的不透明编号。13 组共 29 条在组内拥有相同的公开合同和计划结构，实际合法路径随工具反馈变化。所列 29 条全部未通过冻结计划门槛。该结果提供了审查条件计划表示与动作预算的具体用例。 [条件路径审计](../evidence/IJ072/benchmark_validity/planning-public-ambiguity.json)

JOB-V1 冻结的 600 条主面板使用 Arm B 的公开工具定义，独立生成事实和草稿，通过实际工具与 SQLite 交叉校验。600/600 通过，其中 350 条完成业务，其余 250 条正确拒绝、澄清或转交。错误业务回答，以及适用用例中缺失的用户更新和持久化草稿，均由原评分拒绝。 [JOB-V1 独立见证](../evidence/IJ072/benchmark_validity/job-witness.json.gz)

JOB-V1 扩展控制拒绝了 2,650 个含越权 ID、伪造审批、错误读取或重复草稿收据的变异。600 份缺失审计的用例均保留 BLOCKED。600 个字段重排和 125 个中文等价主题全部通过。实际 SQLite 沙箱拒绝了 600 个契约外提交请求，业务表与审批表未发生变化。 [扩展控制](../evidence/IJ072/benchmark_validity/job-extended-controls.json.gz)

已准备 22 个独立盲审用例，覆盖四套评测、中英文与混合语言、范围修订、工具故障、权限和条件计划。审阅包仅提供模型可见信息与记录的动作和答案。人工初评和一致性复核状态为 NOT_RUN。 [中英文盲审说明](ATLAS_A1_BLIND_REVIEW.md)

Windows CI 曾在进入写处理器前先到达超时点，导致回滚测试读取不到预期的写审计字段。回归现在先暂存写入，再推进测试时钟，并检查已回滚的暂存写和持久化终态。历史测试文件继续通过原归档提交校验。 [安全回归](../tests/security/test_gateway_execution.py)

## 候选资料核对

原有候选均保留。Microsoft 已提供 Aion 2.3B 的官方 WebGPU INT4 权重和运行说明，AMD 物理结果尚待验证。IBM 的 Granite 4.2 3B 模型卡确认支持原生工具定义，现有固定 llama.cpp 版本的现场准入仍待确认。LFM2.5-1.2B-Instruct 可作为同家族更低计算成本的扩展对照。已选用 Qwen3-14B Q8_0 作为进一步的同家族强对照，已逐字节验证 ModelScope 权重，共通过 10/10 项 CPU 与 Radeon Vulkan 准入检查，GPU 实际卸载 41/41 层。完整强参照任务资格仍待实测。Qwen3.8-27B 为另一个待核验候选。 [14B 权重身份](../atlas/benchmarks/pc_s_qwen3_14b.json) [Aion WebGPU 模型卡](https://huggingface.co/microsoft/Aion-1.0-Instruct-2.3B-ONNX-WebGPU) · [Granite 模型卡](https://huggingface.co/ibm-granite/granite-4.2-3b) · [LFM2.5 模型卡](https://huggingface.co/LiquidAI/LFM2.5-1.2B-Instruct) · [Qwen3.8 模型卡](https://huggingface.co/Qwen/Qwen3.8-27B)
