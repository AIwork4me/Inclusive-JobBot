# IJ-0.7 历史四臂重跑

历史数据固定为 generator 1.0.2 的 500 条输入，每臂使用同一份 MiniCPM5-2B Q8_0 ModelScope 权重和原生模板。R0 为 b12359 原始解析器加观测补丁。R1 在同一源码上加入 P4b 两个解析补丁。Vulkan 与 ROCm 使用固定官方 GPU 插件。 [运行与恢复](../benchmarks/root_cause/README.md)

同一 R0 Vulkan 二进制的 8 次采集开关配对均保留相同的协议结果，6 次非流式还逐 token ID 和原文字节一致。关闭采集时流式接口只暴露部分 token。采集开启的四个探针分别关联了 8/8 个真实请求的完整原始数据。 [控制配对](../evidence/IJ07/historical_replay/observer_control/comparison.json)

## 完整回放

| 实验臂 | 真实 GPU 案例 | V1 PASS | V2 语义通过 | V2 PASS / FAIL / BLOCKED | 源码请求捕获 |
|---|---:|---:|---:|---:|---:|
| 原版 Vulkan | 500 | 433 | 459 | 420 / 41 / 39 | 1,104/1,104 |
| 原版 ROCm/HIP | 500 | 432 | 458 | 420 / 42 / 38 | 1,107/1,107 |
| P4b Vulkan | 500 | 433 | 459 | 420 / 41 / 39 | 1,104/1,104 |
| P4b ROCm/HIP | 500 | 432 | 458 | 420 / 42 / 38 | 1,107/1,107 |

四臂全部完成。8 个会话的 GPU 分配及同 PID 活动与显存证据通过校验。每个后端 500 对任务的 V1、V2 语义与 V2 完整判定都逐案相同。各臂的完整诊断通过率为 84%，Wilson 95% CI 约为 80.5%–87.0%。同后端比较没有通过/未通过分歧，McNemar 双侧 p=1。这一组数据支持观测差为 0；总体等效需要预注册非劣界值及独立样本。 [原始归档、身份、摘要及统计](../evidence/IJ07/historical_replay/full/summary.json)

复用历史内存模拟器和合成回执以控制实验条件。V2 语义和完整结论保留历史业务状态证据不足的判定。全量 2,000 条历史推理记录为 `PASS`。包含 SQL 状态及 SDK 回调的完整 G2 仍为 `BLOCKED`。 [阻塞记录](../BLOCKERS.md) · [失败边界记录](IJ07_MULTITOOL_FAILURE_ROOT_CAUSE.md)

## 固定上游对照

GitHub release `b12675`，提交 `c212d25ad34ff1fdf775793cda07e009560cf66b`。使用按官方 SHA256 校验的 Windows Vulkan 发行包，在物理 Radeon 上运行 146 条固定夹具，106 PASS、40 FAIL。原生适用断言 87 PASS、32 FAIL、27 NOT_RUN；严格参数 138 PASS、8 FAIL；流式一致性 146 PASS。预选 15 个空 tags 案例及错误订单案例全数 V2 FAIL。该臂使用上游公开接口，原始采样未接入本地观测补丁。 [上游运行原始证据](../evidence/IJ07/historical_replay/upstream_b12675/report.json)
