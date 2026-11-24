# IJ-0.7 历史四臂重跑

历史数据固定为 generator 1.0.2 的 500 条输入，每臂使用同一份 MiniCPM5-2B Q8_0 ModelScope 权重和原生模板。R0 为 b12359 原始解析器加观测补丁。R1 在同一源码上加入 P4b 两个解析补丁。Vulkan 与 ROCm 使用固定官方 GPU 插件。 [运行与恢复](../benchmarks/root_cause/README.md)

同一 R0 Vulkan 二进制的 8 次采集开关配对均保留相同的协议结果，6 次非流式还逐 token ID 和原文字节一致。关闭采集时流式接口只暴露部分 token。采集开启的四个探针分别关联了 8/8 个真实请求的完整原始数据。 [控制配对](../evidence/IJ07/historical_replay/observer_control/comparison.json)

回放复用历史内存模拟器和合成回执以控制实验条件。附加 V2 语义评分保留历史业务状态证据不足的判定。历史协议对照使用的 SQL 状态及 SDK 回调范围仍需独立试验。全面历史回放证据由四臂完整归档后更新。 [失败边界记录](IJ07_MULTITOOL_FAILURE_ROOT_CAUSE.md)
