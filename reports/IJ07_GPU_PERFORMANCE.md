# IJ-0.7 Radeon 历史负载观测

全部 2,000 条历史重放采用单并发、Q8_0、8192 context。表中的时延是主要模型 HTTP 请求，排除流式额外配对请求及单独模板渲染。原生速率按实际阶段时长加权。GPU 内存是采样到的进程峰值。

| 实验臂 | HTTP P50 / P95 | 任务步骤请求时间合计 P95 | Prefill token/s | Decode token/s | GPU committed 峰值 |
|---|---:|---:|---:|---:|---:|
| R0-V | 560 / 1,370 ms | 2,603 ms | 2,106.2 | 70.5 | 3.36 GB |
| R0-R | 560 / 1,435 ms | 2,740 ms | 2,758.9 | 65.3 | 3.48 GB |
| R1-V | 555 / 1,356 ms | 2,594 ms | 2,030.2 | 71.2 | 3.36 GB |
| R1-R | 558 / 1,464 ms | 2,801 ms | 2,852.6 | 65.0 | 3.48 GB |

在该受控配置上，ROCm/HIP 加权 prefill 更高，Vulkan decode 更高。不同采集日期和会话中的现场 CPU 负载、缓存、HEAP 与驱动态可能影响时间。单一历史压力点提供配置诊断。生产端到端 P95、TTFT、功耗、迁移硬件、并发及量化间对照仍待采。 [分项原始汇总](../evidence/IJ07/performance/historical_summary.json) · [吞吐图](../evidence/IJ07/figures/historical-throughput.svg)
