# IJ-0.6 historical baseline rescoring

Evaluator V2 processed 500 Vulkan and 500 ROCm/HIP traces from the frozen `DIAGNOSTIC_BASELINE_V1`. The results are `RESCORED_DIAGNOSTIC_V2`. The historical baseline artifacts and scores are preserved. The replay used the original post-parser wire arguments, execution outcomes and final text. See the [source identities, result digests and counts](../evidence/IJ06/rescoring/summary.json).

## What the original 58% measured

Of the original **42 failed multi-tool cases on each backend, 41 passed the V2 trace checks** after allowing equivalent independent lookup plans. All 41 were penalized by order or first-turn grouping. Four of the Vulkan cases and three of the ROCm cases also had the expected amount formatted with valid thousands separators that V1 missed. The one remaining original failure, `tc-seq-0043`, completed both lookups and named the wrong order in the final answer. The tool results carry `PO-2026-3780` and the answer names `PO-2026-3782`.

**V1 also passed 15 incorrect later tool proposals on each backend.** In each, the wire arguments to `create_ticket` have an empty `tags` list even though the frozen prompt specifies two tags. The earlier customer lookup and the synthetic ticket ID were enough to pass V1. The traces preserve the erroneous wire arguments. The raw generation before the native parser was not captured for these cases, so the origin of each missing tag is UNVERIFIED.

| Sequential metric | Vulkan | ROCm/HIP |
|---|---:|---:|
| V1 historical success | 58/100 | 58/100 |
| V1 FAIL, V2 trace PASS | 41 | 41 |
| V1 FAIL, V2 trace FAIL | 1 | 1 |
| V1 PASS, V2 trace FAIL | 15 | 15 |
| V1 PASS, V2 trace PASS | 43 | 43 |
| V2 strict SOP trace adherence | 43/100 | 43/100 |
| V2 semantic call and answer trace PASS | 84/100 | 84/100 |
| V2 required all-step arguments correct | 251/266 | 251/266 |
| Historical sequential state evidence insufficient | 22 | 22 |
| V2 sequential verdict, PASS / FAIL / BLOCKED | 77 / 16 / 7 | 77 / 16 / 7 |

Each of the 22 ticket cases lacks persisted business state. Seven have a correct observed call-and-answer trace and a BLOCKED verdict. The other 15 retain FAIL for proven argument errors. The approval, customer association and committed ticket fields cannot be reconstructed from a V1 stand-in receipt. Per-case findings are available for [Vulkan](../evidence/IJ06/rescoring/vulkan.jsonl) and [ROCm/HIP](../evidence/IJ06/rescoring/rocm.jsonl).

## All original cases

| Metric | Vulkan | ROCm/HIP |
|---|---:|---:|
| V1 historical success | 433/500 | 432/500 |
| V2 semantic call and answer trace PASS | 459/500 | 458/500 |
| V2 required all-step arguments correct | 794/821 (96.71%) | 794/821 (96.71%) |
| Historical state evidence insufficient | 63 | 63 |
| V2 diagnostic verdict, PASS / FAIL / BLOCKED | 420 / 41 / 39 | 420 / 42 / 38 |

The 63 insufficient-state findings per backend include cases with trace failures. The verdict column assigns a single status per case. Diagnostic PASS establishes the available trace checks. New transactional and independent holdout evidence is required to qualify business execution.
