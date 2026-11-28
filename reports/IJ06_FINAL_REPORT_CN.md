# IJ-0.6 技术报告

## A. 结论

P4b 在 Windows 的 Vulkan 和 ROCm/HIP 上通过固定解析回归。Evaluator V2 和 SQLite Gateway 通过软件回归。SDK 全量验收为 `FAIL`。TC-V2、JOB-V1 和生产后端选型为 `NOT_RUN`。`IJ06_NATIVE_PARSER_GO` 适用于本次 P4b 解析一致性验证，`IJ06_EVALUATOR_V2_GO` 适用于评分器及历史重评分。生产与 IJ-1.0 准入尚未通过。 [门禁矩阵](IJ06_P0_CLOSURE_MATRIX.md)

## B. Git 状态

原始基线为 `0592c319ab341f70bda979874697386e33ccc680`。P4b 双后端干净重跑使用 `fa50525ebf99fff98149746c05fadc472c8462ec`。任务分支为 `mission/ij-0.6-root-cause-and-purpose-built-execution`，目标分支为 `codex/ij0-tool-calling`。 [草稿 PR #2](https://github.com/AIwork4me/Inclusive-JobBot/pull/2) · [任务 Issue #1](https://github.com/AIwork4me/Inclusive-JobBot/issues/1)

## C. 硬件、模型与运行时

使用原生 Windows、Ryzen AI MAX+ PRO 395 和 Radeon 8060S gfx1151。原版 llama.cpp 为 b12359，提交 `b1b770d90d94cad9e9ea5b993bdbc383a522fb28`。MiniCPM5-2B Q8_0 SHA256 为 `c5415f8989bf88a8288f1b55a3cc371af53c07b0faa220a63bd7a990cfaba078`。本地 17 个 MiniCPM5 文件与 ModelScope 固定清单一致。实测 SDK 为 0.1.24。补丁、二进制、DLL、有效模板和进程身份见各次运行记录。 [审计](IJ06_INITIAL_AUDIT.md) · [候选构建](../evidence/IJ06/parser/p4b-windows-dynamic-build.json)

## D. 六项原生解析问题

字符串空白应保留。原夹具要求去除标识符首尾空白，字段格式由业务边界验证。枚举越界由 Schema 拒绝。重复 XML 参数、缺失参数闭合、缺失函数闭合、未闭合 CDATA 均已在原生解析路径上定位。P4b 在最终映射前要求完整语法并检查重复 XML 参数和嵌套 JSON 词法。五条含嵌套重复键的原始参数由 Gateway 拒绝。已有修复继续使用 llama.cpp 原生解析器。 [逐项因果证据](IJ06_PARSER_ROOT_CAUSE_REPORT.md)

## E. 评分器及历史重分

每个后端原有多工具 58/100。42 个失败中，41 个在允许等价顺序和分组后通过可观测 Trace 检查。1 个最终答案报错订单。另有 15 个原通过案例提交空标签，缺少模型解析前输出，无法区分生成与原生解析原因。两边全步骤参数均为 794/821（96.71%）。多工具 Trace 成功均为 84/100。计入持久状态证据后，每边为 77 PASS、16 FAIL、7 BLOCKED。 [重评分](IJ06_BASELINE_RESCORING.md)

## F. 安全 Gateway 与状态

209/209 软件回归通过。12/12 历史失败输出在工具处理前被拦截。草稿持久化、正式提交确认、事务回滚和重放保护各有单独验证。当前执行证据来自合成业务状态。生产连接器和真实员工确认仍需验收。 [Gateway](IJ06_SECURE_GATEWAY_REPORT.md)

## G. Antigravity SDK

P4b Vulkan 为 10 PASS、1 FAIL、1 BLOCKED，AG-06 的结构化字段错误地包含序列化对象。P4b ROCm/HIP 为 11 PASS、1 BLOCKED。两边的 AG-11 均缺少完整进程出站验证。保留原版 SDK 与只读 Smoke 证据。 [双后端 SDK](IJ06_ANTIGRAVITY_QUALIFICATION.md)

## H. 500 条独立 Holdout

TC-V2 在两边均为 `NOT_RUN`。Tier 1 与 ECO-01 原高可靠性目标需要各自的独立验收结果。 [Holdout 状态](IJ06_HOLDOUT_RESULTS.md)

## I. 六组因果实验

已实现真实 SDK 入参识别、确定性审核、异常升级、持久草稿与独立确认的文档审核链路。开发集实跑 D/E/F。每组在三条结构化案例上均得到正确草稿和升级结果。A–C 和 600 条六组实验均为 `NOT_RUN`，当前无法量化工具 Schema、SOP 或专业知识各自的提升。99% 一次性正确率和模型调用降至十分之一均未验证。 [管理层开发试验评分卡](IJ06_PURPOSE_BUILT_CAUSAL_ANALYSIS.md)

## J. 2B 与 8B 参考

同一 Vulkan 开发负载下，MiniCPM5-2B 和 Qwen3-8B 各完成 3/3，分别调用模型 6 次。确定性 SOP 同样完成 3/3，模型调用为 0。结构化送货单已提供关键字段。LLM 对模糊或非结构化输入的额外价值与模型能力差距仍待正式测量。 [配对试验](IJ06_PURPOSE_BUILT_CAUSAL_ANALYSIS.md)

## K. 后端选择

两个 GPU 后端均有真实设备、卸载与进程计数证据。P4b 固定夹具结果一致。三个开发任务上的最慢耗时分别为 Vulkan 41.81 秒、ROCm/HIP 37.26 秒。生产选型、同负载 CPU 参考、多上下文与并发、量化、功耗均未完成。 [性能](IJ06_PERFORMANCE_REPORT.md) · [选型](IJ06_ENGINE_SELECTION.md)

## L. GitHub 与复现

草稿 PR 包含五项软件与 upstream parser CI 工作流。证据校验器检查原始基线、文件摘要、运行身份、样本与状态一致性。原生 GPU 运行来自当前工作站。 [CI 与门禁](IJ06_P0_CLOSURE_MATRIX.md) · [文件摘要](IJ06_ARTIFACT_MANIFEST.json)

## M. DX-M2

可直接复用模型准入规范、工具协议、安全边界、业务评测和统计工具。NPU 执行与功耗仍需实体测量。当前为 `DXM2_PHYSICAL_VALIDATION_NOT_RUN`。 [迁移包](../portability/deepx-dxm2/)

## N. 剩余风险

待解决结构化输出稳定性与出站隔离。待冻结独立数据与完整六组配置，并完成性能矩阵。本阶段未交付完整的正式 Holdout 执行脚本。客户站点、员工验证和商业达标仍待验证。保持 `CUSTOMER_POC_PENDING_USER_AND_SITE_VALIDATION` 和 `PTMF_PENDING_CUSTOMER_AND_USER_VALIDATION`。 [风险清单](IJ06_OPEN_RISKS.md)
