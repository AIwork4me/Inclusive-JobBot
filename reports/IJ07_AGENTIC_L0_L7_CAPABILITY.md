# IJ-0.7 自主规划 L0–L7 资格判定

MiniCPM5-2B Q8_0 在固定 P4b Vulkan 配置中完成 800 个任务的双轨首轮，
真实执行覆盖为 `PASS`，自主规划资格为 `FAIL`。每个单轨等级的估计为
0/100，Wilson 95% 上限为 3.70%。连续等级规则在 L0 停止。
 [正式分级结果](../evidence/IJ07/planning/primary-vulkan-full/diagnostic.json)

| 等级 | 门槛 | Plan-first | Acting-first | 单轨结论 |
|---|---:|---:|---:|---|
| L0 | 95% | 0/100 | 0/100 | FAIL |
| L1 | 95% | 0/100 | 0/100 | FAIL |
| L2 | 95% | 0/100 | 0/100 | FAIL |
| L3 | 85% | 0/100 | 0/100 | FAIL |
| L4 | 85% | 0/100 | 0/100 | FAIL |
| L5 | 80% | 0/100 | 0/100 | FAIL |
| L6 | 75% | 0/100 | 0/100 | FAIL |
| L7 | 90% | 0/100 | 0/100 | FAIL |

每个等级包含 50 条中文和 50 条英文，两个语言分层各完成 400 条单轨样本。
Plan-first 有 800 次初始计划拒绝，Acting-first 有 1,422 个模型动作。
参考边界修复使 100 条原始中文提议通过局部校验，两条修订真机轨迹均仍然
未通过全任务。修订配置的完整等级资格为 `NOT_RUN`。
 [双轨完整报告](IJ07_AUTONOMOUS_PLANNING_BENCHMARK.md) · [局部修复](../evidence/IJ07/root_causes/planning_reference_boundary_control.json)

每个等级另在预选 20 条任务上执行三个固定种子。16 个等级及轨道组合均为
0/60，Pass@3 和 Pass^3 均为 0/20。 [双轨重复统计](../evidence/IJ07/planning/repeat-vulkan-full/diagnostic.json)
