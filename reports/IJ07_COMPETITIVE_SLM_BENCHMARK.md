# IJ-0.7 competitive model diagnostics

LFM3, Qwen3.5, Ministral and Gemma ran the same frozen read-only development
case `TCV2-D-0001` on the common strict Vulkan build. All four called the
expected tool with the correct argument. All four computed 216 free units.
LFM3 returned a bare JSON object. Qwen3.5 added prose and a Markdown fence,
while Ministral and Gemma enclosed the object in a Markdown fence. The
frozen bare-object contract caused the three failures.

| Candidate | Required tool and arguments | Final answer | Case |
|---|---|---|---|
| B · LFM3 | PASS | PASS | PASS |
| D · Qwen3.5 | PASS | FAIL | FAIL |
| F · Ministral | PASS | FAIL | FAIL |
| G · Gemma | PASS | FAIL | FAIL |

The development records retain the exact runtime, template, model, prompt,
source generation, HTTP responses and SQLite state digests. The full matched
holdouts, seed panels, confidence intervals and competitive verdict remain
`NOT_RUN`. [Development records](../evidence/IJ07/competitive_slm/dev/)
· [Comparison protocol](../benchmarks/competitive_slm/STATISTICS.md)

On the separate official Aion ONNX INT4 path, CPU and Radeon WebGPU generated
matching tokens. Both proposed `lookup_balance` using the company name before
receiving the account ID. The harness stopped before executing either
proposal. Incremental decoding matches whole-sequence decoding for this
generation. Independent streaming and a successful tool-result round trip
remain pending. [Aion dependency probe](../evidence/IJ07/model_identity/aion_tools/)
