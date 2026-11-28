# IJ-0.7 配对模型统计与试验范围

控制组冻结 B、D、F、G 在同一 Radeon Vulkan 实现上的六个两两比较。
每臂安排 500 条正式首轮、500 条真实流式轨迹和 150 条重复试次。
每臂使用自己的原生模板及承诺的模型身份，比较锁定相同业务任务、预算、
硬件与评分行为。计划与执行源树在正式候选样本前锁定。
 [正式比较计划](../configs/ij07/tc_v2_competitive_plan.json) · [锁定摘要](../configs/ij07/tc_v2_competitive_plan.lock.json)

模型差异使用同一 `case_id` 和配对摘要对齐的首轮结果。报告双侧精确
McNemar、10,000 次按对 bootstrap 的 95% 区间、Holm 校正、Wilson
区间，以及同时保留 `BLOCKED` 和 `NOT_RUN` 的分母和上下界。附带
类别、语言及复杂度分层。按种子报告独立重复面板，失败诊断有单独分母。
 [统计实现及输入约定](../benchmarks/competitive_slm/STATISTICS.md)

MiniCPM5 的双后端结果各具独立身份。Vulkan 的 349/500 与 ROCm/HIP 的
347/500 是该模型在原 P4b 配置上的能力估计。四候选各一案的开发证据
只覆盖书面 JSON 合同。正式候选配对效果、显著性、非劣效和综合排名均维持
`NOT_RUN`，直到完整配对验收。 [MiniCPM5 结果](IJ07_TC_V2_QUALIFICATION.md) · [候选开发结果](IJ07_COMPETITIVE_SLM_BENCHMARK.md)

LFM3 的首个封存会话覆盖按固定顺序提交的 200 条首轮，15 PASS、185 FAIL、
0 BLOCKED。该臂其余 950 个试次当时为 NOT_RUN。其中包括剩余首轮、流式和
重复。配对推断仍使用预设完整样本。 [封存快照和摘要](../evidence/IJ07/competitive_slm/tc-v2-B-first-checkpoint/)
