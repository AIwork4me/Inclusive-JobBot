# LFM3 harness adapter Radeon admission milestone

All three verified GGUFs pass the fixed-adapter admission panel on Radeon
8060S/gfx1151. The tested profile uses the pinned llama.cpp Vulkan observer,
frozen LFM3 Q8_0 base, F16 LoRA, 8,192-token context, disabled prompt
cache and checkpoints, one adapter per process and a guarded SDK boundary.
The base hash matched before and after the panel. GPU counters confirmed
activity and memory for every launched server. Each LoRA allocated
62.82 MiB on Vulkan0 and loaded 306 tensors. All 25 base layers were offloaded.

| Check | OpenCode | Pi | Hermes |
|---|---|---|---|
| Scale 0 equals Original | PASS | PASS | PASS |
| Scale 1 differs and repeats | PASS | PASS | PASS |
| Scale 0 after scale 1 equals Original | PASS | PASS | PASS |
| GPU execution and Vulkan adapter placement | PASS | PASS | PASS |
| Direct native call, dependent call, result and JSON/SSE | PASS | PASS | PASS |
| Antigravity SDK 0.1.24 lookup and result | PASS | PASS | PASS |
| Wrong model and adapter rejected at the guarded SDK boundary | PASS | PASS | PASS |
| Raw native endpoint rejects unknown adapter ID | FAIL | FAIL | FAIL |

On identical input tokens, maximum shared-token log-probability differences
between Original and scale 1 ranged from 0.153 to 0.551 across the nine
adapter/prefix pairs. Each same-scale repeat and scale 0 comparison met the
frozen 1e-5 tolerance and ranking contract. The three adapters also
produced distinct numeric observations from each other. Missing files,
malformed tensor shapes, and the mismatched MiniCPM5 base were rejected
before readiness. [Portable admission evidence](../atlas/slm/v1.0/lfm3-harness-adapters/RADEON_ADMISSION.json)

With the runtime's default cache and checkpoint behavior, Original
same-prefix repeats differed. The measured failure also affected adapter
repeats and restoration to scale 0. The cache-disabled profile retested
Original and each adapter with the matching flags. The source has separate
prompt-cache and slot-checkpoint paths. The run changed both settings,
so their individual contributions remain unmeasured.
[Pinned server source](https://github.com/ggml-org/llama.cpp/blob/b1b770d90d94cad9e9ea5b993bdbc383a522fb28/tools/server/server-context.cpp) ·
[Failure registry](../atlas/slm/v1.0/lfm3-harness-adapters/FAILURE_REGISTRY.json)

An unknown native adapter ID returned HTTP 200. The pinned source builds a
request's scale list from loaded adapter indices and gives omitted indices
scale 0. For this profile, the project pins the adapter by file hash and
binds the expected alias at its SDK boundary. In the physical negative
controls the boundary refused the unknown alias and adapter override before
making a provider request. The same boundary allowed unchanged SDK requests
for the real lookup. This demonstrates a fixed guarded route. Dynamic and
concurrent adapter routing remain NOT_RUN.

Formal Core TC-V3 remains 8,250 of 36,550 across the original five models,
including 1,650 Gemma trials and 1,650 Original LFM3 trials. Any extension
that uses the changed cache profile needs its own matched Original comparison
before reusing historical outcomes. The single-lookup panel grants zero
core trials, no D25 qualification and no additional AG-11 evidence.
