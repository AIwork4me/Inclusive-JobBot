# ADR-001: llama.cpp is the primary inference engine

- Status: accepted (change order ECO-01, 2026-11-24)
- Supersedes: the Ollama-primary route in MISSION IJ-1.0 sections 2.1, 5 and 13.2

## Context

MISSION IJ-1.0 named Ollama as the primary runtime for MiniCPM5-2B. During
M0/M1 setup, before any model inference had been run, the project owner issued
ECO-01 with a new route:

**Windows Native x AMD Ryzen AI MAX+ 395 x Radeon 8060S (gfx1151) x llama.cpp
x MiniCPM5-2B x Google Antigravity SDK**

Two findings from the Ollama work support the change and are kept as evidence:

- Ollama v0.40.17 has no MiniCPM5 tool-call parser. Its parser registry
  (`model/parsers/parsers.go` at tag v0.40.17) lists 24 parsers and none covers
  MiniCPM5; requests with tools fall back to the generic `<tool_call>` JSON
  parser, which does not match the XML format MiniCPM5 was trained on.
- Ollama's server contacted `ollama.com` at startup for model
  recommendations, which has to be controlled for the offline gate.

The Ollama GPU discovery log is archived in `evidence/M0/ollama_server_discovery.log`.
No model was loaded and no inference was run through Ollama, so there is no
Ollama inference result to carry over.

## Decision

llama.cpp `llama-server` is the primary production-oriented engine. Ollama
becomes an optional compatibility baseline (Arm G) and SGLang and Transformers
are protocol references only.

The native MiniCPM5 parser in upstream llama.cpp is used first. A private XML
parser is not developed unless evidence shows a specific upstream defect, and
then only as a minimal patch or adapter with a reproduction and a regression test.

## Upstream evidence

Full detail and SHA identities: `reports/IJ0_UPSTREAM_AUDIT.md` and
`evidence/IJ0/upstream_source_manifest.json`.

| Question | Finding |
|---|---|
| Native parser merged? | Yes. PR #24889 "chat : implement minicpm5 parser", merged 2026-06-28, commit `c818263f2a5ddab028dea5f169ea2b2266421125`. |
| Earlier implementation | PR #23802 was closed without merge. |
| Parser location | `common/parsers/minicpm5.cpp` (factory `common_chat_params_init_minicpm5`), selected in `common/chat.cpp`. |
| How it is selected | By template content: the template must contain `Tool usage guidelines:`, `<function name="` and `<param name="`. |
| In the stable release? | Yes. `v1.0.0` (2026-11-13) points through `nightly-tag.txt` to build `b12359`, commit `b1b770d9`, which contains the merge. |
| Later fixes | PR #32746 (XML recovery) closed unmerged. PR #29307 (token-aware parsing, 2026-11-22) changes two lines of the MiniCPM5 parser and is newer than the stable build. |
| 1B vs 2B templates | Same wire protocol. Templates differ in `<tool_sep>` handling and in the automatic empty `<think>` block. Both satisfy the selection rule. |
| Windows builds | `b12359` publishes `win-cpu-x64`, `win-vulkan-x64` and `win-rocm-10.0-x64`; the ROCm target list includes `gfx1151`. |

## Environment constraint found while implementing: Smart App Control

The qualification machine initially ran Windows Smart App Control in enforced
mode. Under that policy the official llama.cpp release binaries are not
Authenticode-signed and were blocked ("blocked by your organization's Device
Guard policy"). The project did not change the setting. The machine owner
turned Smart App Control off on 2026-11-24, after which the official `b12359`
binaries run:

```
version: 1.0.0-dev (build 12359, commit b1b770d90)
built with Clang 20.1.8 for Windows x86_64
```

No inference result was produced before the change, so no result carries a
different engine identity.

For other machines this stays a documented prerequisite: Smart App Control
must not block unsigned binaries for the official llama.cpp release to run.
`install_llama_cpp.ps1` detects the blocked case and reports it instead of
falling back to another engine. A machine where the owner keeps the policy on
can use the Authenticode-signed `llama-server.exe` inside Ollama v0.40.17
(upstream llama.cpp commit `17701e48d`, same MiniCPM5 parser code) only as a
clearly labelled separate engine identity, never mixed with official results.

## Consequences

- Model Gateway gains `llama_cpp_backend` (primary) and `ollama_backend`
  (optional), both behind one OpenAI-compatible contract and contract tests.
- Tool-calling qualification becomes a standalone, reusable module
  (`benchmarks/tool_calling/`) with a frozen 500-case set and parser fixtures.
- All IJ-1.0 business benchmarks run on the engine that passes IJ-0. Results
  from different engines are never pooled.
- DX-M2 remains a future backend behind the same contract. GGUF is not a
  DX-M2 deployable format.

## Acceptance conditions

IJ-0 gates G0-G14 in ECO-01 section 12. `IJ0_LLAMA_CPP_PRIMARY_ENGINE_GO` is
granted only when every required gate passes on one engine identity.
`GFX1151_DUAL_GPU_BACKEND_QUALIFIED` requires Vulkan and ROCm/HIP each verified
independently on the physical GPU.
