# IJ-0.6 purpose-built development rehearsal

The Document Review Specialist now runs scoped purchase-order, supplier and catalog lookups through the Gateway. The versioned DAG validates identifiers, order status, supplier qualification, line quantities, unit prices, units and minor-unit amount totals. A prepared draft records its actor and source digests. The trusted submit path verifies the same actor and current source data and requires distinct confirmation. Product information and customer service also exercise the DAG runtime with scoped read operations. Customer service prepares a ticket recommendation.

The paired rehearsal used the same three structured delivery notes and fresh state per arm. The fixtures cover one eligible match, a quantity-plus-amount mismatch, and an unqualified supplier with a catalog unit mismatch. The real SDK extracted review intent and the order reference for D and E. The local deterministic path F used the already structured order reference. Each arm persisted three correct drafts and escalated the two exceptional cases. No pilot arm entered the final approval stage. [2B and F traces](../evidence/IJ06/performance/summary.json) · [8B and GPU evidence](../evidence/IJ06/performance/reference-qwen3-vulkan/summary.json)

| Development metric on the same Vulkan workstation | A. General agent | D. MiniCPM5-2B | E. Qwen3-8B | F. Deterministic |
|---|---:|---:|---:|---:|
| First-pass draft or escalation correct | NOT_RUN | 3/3 | 3/3 | 3/3 |
| Routine draft coverage | NOT_RUN | 1/1 | 1/1 | 1/1 |
| All-step argument accuracy | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |
| Model calls per case | NOT_RUN | 2 | 2 | 0 |
| Tokens per successful draft | NOT_RUN | 11,056/3 | 9,863/3 | 0 |
| Maximum observed latency | NOT_RUN | 41.81 s | 59.41 s | 29.96 ms |
| Correct persisted drafts | NOT_RUN | 3/3 | 3/3 | 3/3 |
| Unauthorized business effects observed | NOT_RUN | 0/3 | 0/3 | 0/3 |
| Correct escalations | NOT_RUN | 2/2 | 2/2 | 2/2 |

Arms A, B and C and the independent JOB-V1 dataset were `NOT_RUN`. These three matched examples provide no evidence for the proposed schema, orchestration or knowledge gains, the 99% target, a tenfold reduction in model calls, 15-second production P95, or model equivalence. The deterministic path suffices in these samples because the trusted attachment already provides structured values and the user request is known to be a review. The additional value of language interpretation for ambiguous or unstructured input remains unmeasured.

Qwen3-8B Q8_0 used the official Apache-2.0 ModelScope model, pinned revision `9837f991e156bf8135941d367244c34de5807b73`, SHA256 `408b955510e196121c1c375201744783b5c9a43c7956d73fc78df54c66e883d6`. The original llama.cpp Vulkan plugin offloaded 37/37 layers on Radeon 8060S. The workflow, validation and scoped tools were identical to D. [Model card](https://www.modelscope.cn/models/Qwen/Qwen3-8B-GGUF) · [Exact candidate identity](../configs/qwen3_8b_reference.json)

The software analysis CLI enforces exact paired coverage against the supplied frozen plan, reports exact McNemar and bootstrap comparisons, and fixes the repeated-case selection and seeds before execution. JOB-V1 separately requires a 600-case roster. [Statistical contract](../benchmarks/job_productivity_v1/STATISTICS.md)
