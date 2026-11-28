# IJ-0.6 initial audit

The checkout and GitHub default branch `codex/ij0-tool-calling` resolved to `0592c319ab341f70bda979874697386e33ccc680` before changes. The checkout was clean. GitHub listed zero PRs, issues and Actions runs. No llama-server or Python benchmark process was observed. The mission branch was created from this revision.

The generator v1.0.2 reproduced both committed splits, 120 development and 500 diagnostic cases. The original dataset, evaluator, traces, fixture expectations and reports are the preserved DIAGNOSTIC_BASELINE_V1. The original 433/500 Vulkan and 432/500 ROCm scores remain tied to that rubric. Re-scoring those traces provides diagnostic evidence under a different rubric.

| Finding | Existing evidence | Initial interpretation |
|---|---|---|
| Native fixtures 20/26 on both backends | `evidence/IJ0/protocol/parser_fixtures_strict_{vulkan,rocm}/fixtures.json` | Whitespace, structural recovery, duplicate keys and enum validation require separate checks. |
| Sequential score 58/100 on both backends | `evidence/IJ0/protocol/tool_calling_test_{vulkan,rocm}/` | V1 checks earlier arguments and an execution prefix. The magnitude of the order and later-argument effects requires trace replay. |
| Stand-in write receipts | `benchmarks/tool_calling/runner/tool_simulators.py` | Ticket and follow-up IDs can be generated without persisted rows. Historical traces cannot establish persistent state. |
| SDK read-only loop | `evidence/IJ0/antigravity/` | The transcript establishes the smoke behavior. Full SDK gates require distinct evidence. |
| Dirty run metadata | Baseline run manifests | Historical source identity has the limits recorded in those manifests. |

Local Q8_0 bytes match SHA256 `c5415f8989bf88a8288f1b55a3cc371af53c07b0faa220a63bd7a990cfaba078`. Both launcher binaries hash to `38c5affb81c9a8f88f5538c7d11bc445e13bc46a2c6eda05694b8b31a8d45995`. Runtime DLLs distinguish the backends. The installed SDK is 0.1.24. Live GPU and full binary/template verification belongs to the execution evidence.

Follow-up verification checked all 17 local GGUF and BF16 files by size and SHA256. ModelScope's current repository heads matched `8cc1178b0a5cee98872ca3f2f88d49b3d3fa6f59` and `4e7a94716d4526da493d68962f475390e852954b` respectively.

GitHub lists [llama.cpp v1.0.0](https://github.com/ggml-org/llama.cpp/releases/latest) as the latest stable release, with release target `2d8a32502909ca065c41c4cf5f2fb1c427c047fc`. The pinned Windows binaries use build commit `b1b770d90d94cad9e9ea5b993bdbc383a522fb28`. The build and release identities must be tracked separately. PR [#24889](https://github.com/ggml-org/llama.cpp/pull/24889) merged. PR [#23802](https://github.com/ggml-org/llama.cpp/pull/23802) and PR [#32746](https://github.com/ggml-org/llama.cpp/pull/32746) closed unmerged.
