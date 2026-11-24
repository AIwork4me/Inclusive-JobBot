# Task Ledger

Status vocabulary: `PASS`, `FAIL`, `BLOCKED`, `NOT_RUN`. "Progress" says
whether work has started. Every finished task names its evidence.

## IJ-0 prerequisite mission (ECO-01)

| ID | Task | Progress | Status | Evidence |
|---|---|---|---|---|
| ECO-01 §2 | State review, Ollama discovery log preserved, Ollama server stopped | done | PASS | `evidence/M0/ollama_server_discovery.log` |
| IJ-0.1 | Upstream source audit (7 checks) | done | PASS | `reports/IJ0_UPSTREAM_AUDIT.md`, `evidence/IJ0/upstream_source_manifest.json` |
| IJ-0.2 | ModelScope acquisition, per-file SHA256 (17 of 17) | done | PASS | `models/model_manifest.json`, `evidence/IJ0/model_identity.json` |
| IJ-0.3 | Official llama.cpp b12359 install: CPU, Vulkan and ROCm builds enumerate as expected | done | PASS | `evidence/IJ0/engine_install.json`, `evidence/IJ0/rocm_runtime_install.json` |
| IJ-0.4 | Launch scripts and API checks on Vulkan, Q8_0, 8K context | done for Vulkan; other backends exercised in IJ-0.5 | PASS | `evidence/IJ0/server_api_check.json` |
| IJ-0.5 | GPU execution proof, Arms A-G | not started | NOT_RUN | - |
| TC | Native tool calling, fixtures, 500-case frozen benchmark | not started | NOT_RUN | - |
| AG | Antigravity SDK end-to-end integration (12 items) | not started | NOT_RUN | - |
| GW | Model Gateway refactor and contract tests | not started | NOT_RUN | - |
| PERF | Performance qualification and engine selection | not started | NOT_RUN | - |

Notes on IJ-0.4 (verified by running the scripts, Vulkan backend):

- `start_llama_server.ps1`: reports `43/43 layers to GPU`, records buffer
  allocations, refuses a busy port, accepts readiness only from the process it
  started, and stops a GPU run that offloads nothing.
- `stop_llama_server.ps1`: verifies the process image path before stopping;
  idempotent.
- `check_llama_server.ps1 -Probe`: first real inference returned correct
  Chinese text with the `<think>` block extracted into `reasoning_content`.
- `llama_server_api_check.py`: 9 of 9 checks pass, including byte-identical
  streaming and non-streaming output under greedy decoding.

Scripts were debugged against reality, not written blind; defects found and
fixed are listed in `DECISIONS.md` D-009.

## Gates (ECO-01 section 12)

| Gate | Requirement | Status | Evidence |
|---|---|---|---|
| G0 | Upstream parser and release identity verified | PASS | `reports/IJ0_UPSTREAM_AUDIT.md`, `evidence/IJ0/engine_install.json` |
| G1 | ModelScope source and integrity | PASS | `evidence/IJ0/model_identity.json` |
| G2 | Windows llama-server runs natively | PASS | `evidence/IJ0/server_api_check.json` |
| G3 | CPU reference path | NOT_RUN | - |
| G4 | At least one Radeon GPU backend correctness-verified | NOT_RUN | - |
| G5 | Native MiniCPM5 tool calling | NOT_RUN | - |
| G6 | 500-case tool-calling benchmark executed in full | NOT_RUN | - |
| G7 | Antigravity SDK real tool-call loop | NOT_RUN | - |
| G8 | Streaming and non-streaming protocol (plain chat only so far; tool calls pending) | NOT_RUN | - |
| G9 | Unauthorized tool and argument injection protection | NOT_RUN | - |
| G10 | Fully local operation | NOT_RUN | - |
| G11 | Performance and quantization comparison | NOT_RUN | - |
| G12 | Backend selection supported by evidence | NOT_RUN | - |
| G13 | Model Gateway contract | NOT_RUN | - |
| G14 | GitHub evidence complete and reproducible | NOT_RUN | - |

## IJ-1.0 missions

| ID | Mission | Progress | Status | Evidence |
|---|---|---|---|---|
| M0 | Environment discovery and evidence freeze | done | PASS | `evidence/M0/`, `reports/M0_ENVIRONMENT_REPORT.md` |
| M1 | Model download and engine qualification | covered by IJ-0.2 to IJ-0.5 | NOT_RUN | - |
| M2 | Antigravity SDK integration and tool calling | covered by IJ-0 TC and AG | NOT_RUN | - |
| M3 | JobBot platform and Skill Factory | not started | NOT_RUN | - |
| M4 | Three production-shaped JobBots | not started | NOT_RUN | - |
| M5 | Accessible workstation | not started | NOT_RUN | - |
| M6 | 3,000-case productivity benchmark and causal analysis | not started | NOT_RUN | - |
| M7 | Security, offline and reliability qualification | not started | NOT_RUN | - |
| M8 | DX-M2 migration readiness | not started | NOT_RUN | - |
| M9 | Open-source engineering and GitHub publication | not started | NOT_RUN | - |
| M10 | Optional model optimisation research | not started | NOT_RUN | - |
