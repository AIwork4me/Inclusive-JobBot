# IJ-0.7 自主规划验证记录

AGENTIC-PLAN-V1 冻结 800 个任务，L0–L7 各 100 个。每个等级有 50 个英文及 50 个中文案例。独立图 oracle 验证参考依赖、等价顺序、信任确认、最终事实和持久业务状态。Plan-first 与 Acting-first 使用同一任务，但按各自协议判断。160 个预选重复案例固定三个种子。 [任务及运行说明](../benchmarks/agentic_planning_v1/README.md)

已验证档案将 4 条诊断轨迹、5 次源码观察和正式队列的 1,600 个计划试次分开。
各级别完整准入仍待实测。 [诊断档案完整性及分级数据](../evidence/IJ07/planning/diagnostic_verified_summary.json)

| 小样诊断 | Acting-first | Plan-first | 首个可观测偏差 |
|---|---|---|---|
| AP1-L2-001 | FAIL | FAIL | Acting-first 的最终事实不满足；Plan-first 首回合未提供要求的计划字段。 |
| AP1-L7-001 | FAIL | FAIL | Acting-first 使用尚未获得的业务引用；Plan-first 首回合未提供要求的计划字段。 |

四条记录都来自真实 Radeon Vulkan。四次诊断观察到实际未授权变更、未经确认提交及重复提交各为零。该样本只验证选定的两任务；L0–L7 连续能力等级、语言差、长链衰减和置信区间待独立全量运行。 [逐条诊断](../evidence/IJ07/planning/diagnostic/)
