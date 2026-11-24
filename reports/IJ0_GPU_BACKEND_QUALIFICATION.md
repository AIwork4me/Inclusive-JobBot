# IJ-0.5 GPU Backend Qualification

- Run: 2026-11-24, on the physical machine (AMD Ryzen AI MAX+ PRO 395, Radeon
  8060S, gfx1151), official llama.cpp build `b12359` (stable release `v1.0.0`)
- Workload: `benchmarks/engine_qualification/workload.json` v1.0.2, 52 items,
  frozen manifest next to it; greedy decoding, 8K context, one slot
- Evidence: `evidence/IJ0/gpu/<arm>/` (`results.jsonl`, `summary.json`,
  `launch.json`, `counters.jsonl`) and `evidence/IJ0/gpu/comparison.json`
- Harness: `benchmarks/engine_qualification/run_arm.py`

## Verdict

| Gate | Status | Basis |
|---|---|---|
| G3 CPU reference path | **PASS** | Arms A and E: CPU-only build, 0/43 layers offloaded, no GPU activity |
| G4 one Radeon GPU backend correctness-verified | **PASS** | Vulkan and ROCm/HIP each produce the same output as CPU on the same weights |

`GFX1151_DUAL_GPU_BACKEND_QUALIFIED` is **not granted yet**. Both backends
pass this workload, but tool-calling correctness still has to be shown on both
before the status is recorded.

Arm G (Ollama, optional) was **NOT_RUN**.

## Arms

| Arm | Backend | Weights | Layers on GPU | Prompt tok/s | Decode tok/s | TTFT mean | Tasks | Structured |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| A | CPU | F16 | 0/43 | 181.7 | 16.4 | 172 ms | 28/30 | 10/10 |
| B | Vulkan | F16 | 43/43 | 329.7 | 33.6 | 106 ms | 28/30 | 10/10 |
| C | Vulkan | Q8_0 | 43/43 | 811.5 | 74.0 | 52 ms | 28/30 | 10/10 |
| D | ROCm/HIP | Q8_0 | 43/43 | 1070 | 66.2 | 50 ms | 28/30 | 10/10 |
| E | CPU | Q8_0 | 0/43 | 203.3 | 25.5 | 156 ms | 28/30 | 10/10 |
| F-vulkan | Vulkan | Q4_K_M | 43/43 | 732.6 | 106.0 | 56 ms | 27/30 | 10/10 |
| F-rocm | ROCm/HIP | Q4_K_M | 43/43 | 1310 | 95.3 | 45 ms | 27/30 | 10/10 |

Decode speed-up over CPU for the same weights: Vulkan 2.0x (F16), 2.9x (Q8_0);
ROCm/HIP 2.6x (Q8_0). These are single-request numbers on this short workload,
not the engine selection; that follows the performance step.

## Correctness: same weights, different backend

| Pair | Weights | Task outputs identical | Structured outputs identical | Pass sets |
|---|---|---:|---:|---|
| A CPU vs B Vulkan | F16 | 30/30 | 10/10 | same |
| E CPU vs C Vulkan | Q8_0 | 30/30 | 10/10 | same |
| E CPU vs D ROCm/HIP | Q8_0 | 30/30 | 10/10 | same |
| C Vulkan vs D ROCm/HIP | Q8_0 | 30/30 | 10/10 | same |

On every deterministic item the GPU backends and the CPU produce the same text.
The only differences are in the long thinking generations (7 to 9 of 12 chat
items identical), where small floating-point differences grow into different
reasoning paths. No GPU arm fails an item that the CPU passes.

Repeatability: the five GPU arms were run twice; between the two runs all
52 outputs were identical on every arm (greedy decoding).

## What the failures are

They are the same on CPU and GPU, so they are model behaviour, not backend
defects:

- `task-06` fails on all seven arms: the model answers 14.40 for 13% of 120.00
  without thinking. A real arithmetic error.
- `task-26` fails on all seven arms by format: the answer `= 210.00` is correct
  but the model writes the addition out although told to output only the number.
- `task-03` fails on both Q4_K_M arms and passes on F16 and Q8_0: the number
  (1000) is correct on all weights; on Q4_K_M the model adds its working steps.
  This is a change in instruction following, not in arithmetic.
- Three thinking chat items (`chat-07` to `chat-09`) often do not finish their
  `<think>` block within 800 tokens under greedy decoding. They are reported as
  truncated, not as failures.

## Evidence that the GPU really executes

Each GPU arm rests on four independent sources; the CPU arms show the contrast.

| Arm | Server log | GPU engine busy | Compute engine, median | Process CPU, mean | GPU memory of the process |
|---|---|---:|---:|---:|---:|
| A CPU F16 | `CPU_Mapped model buffer 4800.66 MiB` | 0.0 | - | 49.3% | none |
| B Vulkan F16 | `Vulkan0 model buffer 4290.66 MiB` | 0.99 | 92% | 1.3% | 4782 MiB |
| C Vulkan Q8 | `Vulkan0 model buffer 2279.73 MiB` | 1.00 | 89% | 1.9% | 2762 MiB |
| D ROCm Q8 | `ROCm0 model buffer 2279.73 MiB` | 1.00 | 81% | 2.5% | 2939 MiB |
| E CPU Q8 | `CPU_Mapped model buffer 2550.66 MiB` | 0.0 | - | 49.2% | none |
| F-vulkan Q4 | `Vulkan0 model buffer 1340.64 MiB` | 0.98 | 86% | 2.0% | 1820 MiB |
| F-rocm Q4 | `ROCm0 model buffer 1340.64 MiB` | 1.00 | 73% | 3.0% | 1996 MiB |

- **Server log**: `offloaded 43/43 layers to GPU`, per-layer device assignment,
  model, KV (336 MiB) and compute buffer sizes on `Vulkan0` or `ROCm0`.
- **Windows GPU counters** (CIM, about two samples per second): engine
  utilization and GPU memory of the server process. On this driver Vulkan work
  is reported under the `Compute` engine type.
- **Process CPU time**: 1.3 to 3.0% of the machine on GPU arms against 49% on
  CPU arms, so the arithmetic is not done by the CPU.
- **Same output as CPU**, which rules out a backend that computes something
  different.

## Limits of this evidence

- **Not all weights sit in the device buffer.** The log says 43/43 layers, and
  every layer is assigned to the GPU, but the output layer's weights are in the
  backend's host-visible buffer: 270.94 MiB of 2551 MiB for Q8_0, 510 MiB for
  F16, 143 MiB for Q4_K_M. Compute for them still runs on the GPU backend. The
  correct statement is "all layers on the GPU backend, with about 11% of the
  Q8_0 weights in host-visible memory", not "100% in VRAM".
- **"Offloaded N/N layers" alone proves nothing.** A CPU-only build prints
  `offloaded 43/43 layers to GPU` for `-ngl 99` without having any GPU backend.
  The launch script now requests 0 GPU layers for such builds, which is why
  arms A and E show 0/43.
- **Counter artifacts on Arm B.** The F16 Vulkan run produced 14 engine samples
  outside 0 to 100% (9 in the first run), from rounding (101) up to one
  uninitialised value. They are excluded from the statistics, counted in
  `summary.json` (`counter_quality: INVALID_SAMPLES_PRESENT`) and left in the
  raw file. All other arms: 0 invalid samples.
- **Integrated GPU, unified memory.** The 8060S is the APU's GPU. Nothing here
  is a Ryzen AI NPU or a DEEPX DX-M2 result.
- **Short workload, single request.** Concurrency, long contexts, cold and warm
  start under load and long-running stability are measured in the performance
  step, not here.
- Arm G (Ollama with Q8_0) was not run; it is optional and does not block the
  llama.cpp path.

## What was found and fixed while building this

Defects that produced wrong evidence before they were caught are recorded in
`DECISIONS.md` D-010 and D-011. The two that matter most:

- Reading a non-existent `Utilization` property in PowerShell 5.1 gave `$null`
  and recorded a plausible 0% for every sample. The sampler now requires the
  real `UtilizationPercentage` property and records a sampling error otherwise.
- Two manually started servers were left on port 8080 and answered the health
  check of a later launch, producing a false "ready". The launch script now
  refuses a busy port and accepts readiness only from the process it started.
