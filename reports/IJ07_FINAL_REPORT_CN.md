# IJ-0.7 阶段交付报告

## A. 执行结论

完成四臂 2,000 条真实历史重跑。原版与 P4b 的逐案 V2 结论在各后端相同。每臂
420/500 完整诊断通过，100 条多工具中 84 条语义通过、77 条完整通过。研究结论与
生产资格分开记录。 [门禁与七项结论](IJ07_GATE_MATRIX.md)

## B. Git 与工程状态

任务分支 `mission/ij-0.7-agentic-capability-qualification` 从 PR #2 的
`d2e5b31aa1f0894638f7b648a4cf3591fbb71e6e` 建立。历史 2,000 条的运行代码
冻结在 `617b871`，各完整身份和运行 ID 位于归档。
 [草稿 PR #4](https://github.com/AIwork4me/Inclusive-JobBot/pull/4)
 · [跟踪议题 #3](https://github.com/AIwork4me/Inclusive-JobBot/issues/3)

## C. 物理环境

Windows 11 build 26200、AMD Ryzen AI MAX+ PRO 395、Radeon 8060S gfx1151、
128 GiB 安装内存，Radeon 驱动 32.0.22018.5。真机归档对应非零层卸载和
启动进程的 GPU 计数。 [环境](../evidence/IJ07/environment/windows.json)

## D. 历史多工具复现

4,422 次请求关联至解析前输出和采样 token。四臂各 15 个历史空 tags 案例
在解析前复现，合计 60。模型的错误订单最终回答也重复出现。
 [四臂与上游对照](IJ07_HISTORICAL_REPRODUCTION.md)

## E. 独立原生工具调用

TC-V2 Vulkan 首试 349/500，ROCm/HIP 首试 347/500，均低于 90% 门槛。
两个后端各完成 500 次流式配对、150 次重复和 146 条固定夹具。 [独立准入](IJ07_TC_V2_QUALIFICATION.md)
MULTITOOL-V1 的 Vulkan 首轮 600 条全部完成，129 条通过。2–3 步为 44/120，
16–20 步为 9/120。首个检查点发现 14 个正确批次被 16 调用的 wire 上限拒绝。
对同一字节的解码复验保留了原有业务判定。 [TC-V2 运行](../benchmarks/tool_calling_v2/holdout/README.md)
 · [多工具实测](IJ07_MULTITOOL_CAPABILITY_REPORT.md)

## F. 自主规划

L0–L7 各 100 条，Plan-first 与 Acting-first 的全量首轮均完成且分别为 0/800。
原配置的所有等级均未通过。2,719 次请求均绑定解析前输出。Acting-first
记录 1,422 个模型动作，Plan-first 的首轮计划均未达到执行合同。
中文引用校验的修订使用独立证据身份。 [规划结果](IJ07_AUTONOMOUS_PLANNING_BENCHMARK.md)

## G. 同规模竞争

第二轮统一 Vulkan 探针中，LFM3、Qwen3.5、Ministral 和 Gemma 在该配置下通过。
MiniCPM5 在该配置的原生调用检查失败。四个候选在同一开发案例均算出正确结果，
LFM3 通过，其余三个因 Markdown 围栏未满足纯 JSON 约定。Aion 的 CPU 和 Radeon WebGPU 普通对话通过，依赖工具
探针均在获得账号前使用了错误的账号参数。完整配对和可靠性排名待跑。
 [候选矩阵](IJ07_MODEL_ADMISSION_MATRIX.md) · [竞争诊断](IJ07_COMPETITIVE_SLM_BENCHMARK.md)

## H. 源码根因

证实旧 API 对对象型 `tool_choice` 的隐式回退。最小补丁将错误返回为 HTTP 400，
CPU RED/GREEN 和实测 Vulkan 拒绝已留档。空 tags 的源码记录把第一次差异定位到
生成层。CPU 单变量对照中，加入 `minItems: 2` 后 15/15 语义通过，F16 仅通过 1/15。
历史原文和训练成因仍无法确定。 [源码调查](IJ07_SOURCE_LEVEL_ROOT_CAUSE_MASTER_REPORT.md)

## I. SDK 和权限

AG-06 在 Vulkan、ROCm/HIP 分别 1 PASS、2 FAIL。AG-11 缺完整进程出站观察。
安全软件回归与模拟业务状态保留在独立证据中。 [SDK 运行](../evidence/IJ07/antigravity/)

## J. 岗位系统价值

600 条 JOB-V1 跨文档审核、商品信息和售后。无模型 F 臂为 592/600 首试通过，
342 条实际业务完成。A–E 真机诊断 15 条，E 通过 1/3，其余四臂各 0/3。
六组全量配对贡献与调用比待测。 [岗位阶段结果](IJ07_PURPOSE_BUILT_VALIDATION.md)

## K. GPU 与端侧约束

Radeon 的历史负载数据支持两后端可执行性与资源估算。并发、量化损失、
端到端 TTFT、实测能耗及长时稳定性待采。 [性能](IJ07_GPU_PERFORMANCE.md)
 · [DX-M2 迁移规格](../portability/deepx-dxm2/IJ07_DEPLOYMENT_REQUIREMENTS.md)

## L. 能力档案

各候选身份、比较臂和状态保存在九份机器可读档案。 [档案](../evidence/IJ07/model_passports/)

## M. JobBot 技术路线

模型负责提出方案或字段。根据输入结构和风险选用确定性规则、专业知识、SOP、
模型或人工审查。所有写操作继续使用严格的权限及确认边界。
 [架构分层](IJ07_JOBBOT_ARCHITECTURE_RECOMMENDATION.md)

## N. 剩余验证

独立样本的准入、六组因果实验、完整竞争统计、终端及长运行证据均有单独恢复条件。
 [剩余风险](IJ07_OPEN_RISKS.md) · [白皮书阶段版](IJ07_AGENTIC_CAPABILITY_WHITEPAPER_CN.md)
