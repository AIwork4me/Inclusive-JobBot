# Gemma-4-E2B Radeon admission

**Physical admission PASS** for the frozen TC-V3 JSON and SDK paths on Windows Radeon 8060S/gfx1151. This independent development run used nine traces and contributes zero formal trials. The original run is `ijslm-tcv3-dev-8907ae5ba02741ae9df3a6dfda8518e7`, captured at source commit `dac08d28e9d6dcea2dbd16af220a0dbc026f6601`. [Admission seal](../evidence/IJSLM/tc-v3-admissions/manifest.json)

| Identity | Admission evidence |
| --- | --- |
| Registered GGUF | `ggml-org/gemma-4-E2B-it-GGUF` revision `a46a64bc56bba8e20162f2468221aeda036256bb` |
| Artifact | `gemma-4-E2B-it-Q8_0.gguf` at 4,967,491,520 bytes, SHA256 `c36d5e6be0d91124d8b995f5ad4e1ab0d307f6d95cdd08308820350dbd96ad15` |
| Architecture | Gemma4ForConditionalGeneration and per-layer embeddings. The source inventory contains 5,123,178,051 parameters. Google reports 2.3B effective and about 5.1B including embeddings. |
| License | Apache 2.0 |
| Context | 8,192 tokens in the frozen runtime. Google advertises 128K for the model family member. |
| Physical execution | Vulkan, 36 of 36 layers offloaded, provider port attributed to the spawned llama.cpp process. Its GPU counters recorded a 3,232,743,424-byte peak process-committed sample. |
| SDK | Actual Antigravity 0.1.24 harness, runtime, binary and effective template hashes sealed with the trace. |

The file size measures weight bytes on disk. The process counter measures sampled GPU commitment for the admission session and cannot isolate weight allocations. It also cannot characterize the deployment memory requirements of an ordinary dense 2B model. [Pinned source identity](../evidence/IJ07/model_identity/G.json) · [Google documentation](https://gemma.ai/models/gemma-4/model-card/)

| Admission path | Traces | Native-linked provider requests | Recorded callbacks |
| --- | ---: | ---: | ---: |
| Direct provider JSON | 3 | 7 | 5 |
| SDK with provider JSON | 3 | 7 | 5 |
| SDK with provider SSE | 3 | 7 | 5 |

The archive retains parsed proposals, SDK callback records, result delivery in provider requests and terminal responses by trace. The dev roster uses dependency, parallel and authorization cases. All nine traces reached capture without a recorded runner failure. Inspect the [portable report](../evidence/IJSLM/tc-v3-admissions/G/report.json) for per-case model outcomes. The formal planned repeat cohort and strict D25 remain independently governed.
