# IJ-0.7 自主规划验证记录

AGENTIC-PLAN-V1 冻结 800 个任务，L0–L7 各 100 个。每个等级有 50 个英文及 50 个中文案例。独立图 oracle 验证参考依赖、等价顺序、信任确认、最终事实和持久业务状态。Plan-first 与 Acting-first 使用同一任务，但按各自协议判断。160 个预选重复案例固定三个种子。 [任务及运行说明](../benchmarks/agentic_planning_v1/README.md)

已验证档案将 4 条诊断轨迹、5 次源码观察和正式队列的 1,600 个计划试次分开。
各级别完整准入仍待实测。 [诊断档案完整性及分级数据](../evidence/IJ07/planning/diagnostic_verified_summary.json)

## 双轨首个全量等级

MiniCPM5-2B 完成 L0 的 200 个真实 Vulkan 试次。两种轨道均为 0/100，
对各自 95% 门槛为 `FAIL`。同 PID GPU 采样和 200/200 个请求的源码输出均
可核验。当前归档只覆盖首个闭合会话，完整的 L0–L7 研究仍在执行。
 [L0 检查点、原始日志和清单](../evidence/IJ07/planning/primary-l0-checkpoint/)

Acting-first 的 100 个输出中 90 个选择澄清，10 个返回任务理解，独立判定均失败。
Plan-first 的 100 个首轮均未达到计划合同，其中 96 个对象使用错误字段，
4 个计划缺失或无法解析。样例 `AP1-L0-001` 的 Acting-first 输出把已给定的
只读发票目标当作信息不足。Plan-first 输出直接使用终态澄清字段。两种实际
输出都存在于相关请求的源观察，提示合同的独立影响仍待控制。
 [双轨研究数据](../evidence/IJ07/planning/primary-l0-checkpoint/diagnostic.json)

L1/L2 另定位到一个中文输入的运行时缺陷。原正则使用 Unicode 单词边界，
导致相邻的汉字遮蔽了请求中的 ASCII 引用。在 100 条进入此边界的原始首轮
响应上，修复前均拒绝，修复后均通过提议校验。带 ASCII 后缀的标识片段仍被
拒绝。全量原运行和修订后的任务结果继续使用各自身份。
 [100 条原样提议对照](../evidence/IJ07/root_causes/planning_reference_boundary_control.json)

| 小样诊断 | Acting-first | Plan-first | 首个可观测偏差 |
|---|---|---|---|
| AP1-L2-001 | FAIL | FAIL | Acting-first 的最终事实不满足；Plan-first 首回合未提供要求的计划字段。 |
| AP1-L7-001 | FAIL | FAIL | Acting-first 使用尚未获得的业务引用；Plan-first 首回合未提供要求的计划字段。 |

四条记录都来自真实 Radeon Vulkan。四次诊断观察到实际未授权变更、未经确认提交及重复提交各为零。该样本只验证选定的两任务；L0–L7 连续能力等级、语言差、长链衰减和置信区间待独立全量运行。 [逐条诊断](../evidence/IJ07/planning/diagnostic/)
