# IJ-0.6 development workload observations

Three paired structured document-review cases ran through the real SDK and deterministic SOP on each Q8_0 backend. Each backend used an 8K context and one slot. The paired No-LLM SOP ran against separate databases initialized with the same business rows. This is a development workload with three samples per arm. [Run identities, raw traces and counters](../evidence/IJ06/performance/summary.json)

| Backend | Arm | Correct draft or escalation | Model calls | Prompt tokens | Completion tokens | Observed latency range |
|---|---|---:|---:|---:|---:|---:|
| Vulkan | D | 3/3 | 6 | 7,023 | 4,033 | 8.96–41.81 s |
| ROCm/HIP | D | 3/3 | 6 | 6,937 | 4,268 | 18.54–37.26 s |
| Vulkan host | F | 3/3 | 0 | 0 | 0 | 28.14–29.96 ms |
| ROCm/HIP host | F | 3/3 | 0 | 0 | 0 | 28.59–33.81 ms |

The managed servers reported Radeon 8060S and offloaded 43/43 layers. Process-matched GPU memory peaked at 3,380,117,504 bytes on Vulkan and 3,478,999,040 bytes on ROCm/HIP. Compute samples peaked at 99% and 94% respectively. The offload and process counters establish live GPU activity. The original same-weight CPU reference used the IJ-0.5 workload. A same-workload CPU replay is `NOT_RUN`.

The workloads exercised one routine match and two exception-pattern drafts. All D arms needed two model calls per case. The measured durations include SDK startup, model requests, host tool calls and SQLite persistence. The request counts include SDK commentary after the intent tool call. Operator waiting time, full context/concurrency matrix, cold-start series, comparable TTFT and energy are `NOT_RUN`. The route buffers SSE for protocol checking. The three observed latencies per arm are too few for a production P95 estimate.
