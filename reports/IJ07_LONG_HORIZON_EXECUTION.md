# IJ-0.7 长链路执行及恢复能力

MULTITOOL-V1 首轮覆盖 600 条真机任务，129 条完整通过。每个复杂度档有
120 条。2–3 步通过 44 条，4–5 步通过 32 条，6–10 步通过 26 条，
11–15 步通过 18 条，16–20 步通过 9 条。首末档从 36.67% 降至 7.50%。
 [复杂度分项及置信区间](IJ07_MULTITOOL_COMPLEXITY_DECAY.md)

AGENTIC-PLAN-V1 的 L3–L7 共 1,000 条双轨试次，无完整通过。Acting-first
在这些等级记录 1,190 个模型动作。全套适用分母中，每轨动态重新规划
0/250，变化后恢复 0/228。两个系统的安全停止和业务完成使用不同指标。
 [规划分级统计](../evidence/IJ07/planning/primary-vulkan-full/diagnostic.json)

原 MULTITOOL 非流式解码上限是 16，任务总预算是 32。25 条原始响应在
显式放宽批次上限的字节复验中通过解码。另两条修订 Vulkan 轨迹执行了
17 和 18 个调用，任务分别在最终结构和任务动作预算处失败。完整修订版
曲线及其他候选的同负载长链路排名均为 `NOT_RUN`。
 [25 条解码对照](../evidence/IJ07/root_causes/multitool_batch_limit_full_control.json) · [两条真机修订轨迹](../evidence/IJ07/multitool/wire-fix-diagnostic/)
