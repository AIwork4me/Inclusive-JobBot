# IJSDK_01_WINDOWS_GFX1100_QUALIFICATION — P1 Physical Runtime Report

Mission: **IJ-SDK-1.0** · Generated: 2026-11-27 · Branch: `mission/ij-sdk-1.0-cross-sdk-agentic-benchmark`
Evidence: `evidence/IJSDK/P1/` (environment.json, gpu_inventory.json, dependency_inventory.json, engine_install.json, rocm_runtime_install.json, backend_qualification.json, backend_qualification_rocm_retry.json, gpu/)

---

## 1. Verdict

| Gate item | Status |
|---|---|
| Hardware/software fingerprint frozen (this machine, redacted) | PASS |
| llama.cpp pinned b12359 (v1.0.0) reproduced from official release assets | PASS — all three archives SHA256-verified |
| Vulkan backend functional qualification (native gfx1100) | **PASS — full D-010 proof** |
| ROCm/HIP backend functional qualification (native gfx1100) | PASS after crash root-cause fix (§5); one documented transport-parity exception (§6) |
| CPU reference path | PASS (functional; stream-parity exception documented, §6) |
| Matched Vulkan vs ROCm/HIP engine-workload comparison | see `evidence/IJSDK/P1/gpu/` (§7) |
| Silent CPU fallback prevention | ENFORCED (managed start refuses 0-layer GPU arms; counters bound to the server PID) |
| Gate `P1_GFX1100_PHYSICAL_RUNTIME_GO` | **PASS — primary backend selected: Vulkan** |

**Backend selection (frozen reason):** Vulkan is the primary backend because it is the only arm that passed every functional check including byte-identical streaming/non-streaming parity under greedy decoding. ROCm/HIP is fully functional and stable after the Tensile-data fix but shows path-dependent near-tie divergence between transport modes (§6); its results are preserved independently and it remains a comparator arm. Backend results never mix within one experimental cell.

## 2. Machine fingerprint (full data in evidence/IJSDK/P1/environment.json)

| Item | Value |
|---|---|
| OS | Windows 11 Pro, build 26300 (UBR recorded), 64-bit |
| CPU | Intel Core i7-13700K, 16C/24T |
| RAM | 31.8 GB visible |
| GPU | AMD Radeon RX 7900 XTX, device 0x744C (Navi 31, gfx1100), PCI VEN_1002&DEV_744C |
| Dedicated VRAM | 25,753,026,560 bytes (registry) / 24,560 MiB reported by engine device enumeration |
| GPU driver | 32.0.21030.2001 (2025-09-25); Vulkan driver 25.10.30.02 (LLPC), API 1.4.315 |
| Other GPUs | Intel UHD Graphics 770 (iGPU), remote-display and virtual-display adapters present |
| Python | 3.12.10 (project .venv from requirements.lock, 54 packages, hash-checked) |
| git / gh | 2.56.0.windows.4 / 2.103.3 |
| C++ toolchain | **absent** (cmake, ninja, MSVC not found) → source builds and upstream `test-chat` unavailable (carries prior B-005 to this machine) |
| Power scheme | Balanced |
| Smart App Control | Off |
| Disk | 400 GB free at workspace |
| Redaction | user/host names, profile paths, serials withheld by collector + `scan_sensitive.py` (0 findings) |

Personal identifiers were redacted before publication; the worktree path is withheld from evidence.

## 3. Engine identity

| Item | Value |
|---|---|
| Release | llama.cpp v1.0.0, build **b12359**, commit `b1b770d90d94cad9e9ea5b993bdbc383a522fb28` |
| Archives | CPU 25,097,509 B / Vulkan 38,090,643 B / ROCm 280,132,437 B — every SHA256 matches the GitHub release digest (evidence/IJSDK/P1/engine_install.json) |
| Banner | `version: 1.0.0-dev (build 12359, commit b1b770d90)` on all three builds; Authenticode: NotSigned |
| exe SHA256 | `38c5affb81c9a8f88f5538c7d11bc445e13bc46a2c6eda05694b8b31a8d45995` (identical across backend directories) |
| Device enumeration | Vulkan: `Vulkan0: AMD Radeon RX 7900 XTX (24560 MiB, 23737 MiB free)`; ROCm: `ROCm0: AMD Radeon RX 7900 XTX (24560 MiB, 24411 MiB free)`; CPU: `(none)` (correct) |

## 4. Model identity (verified on this machine)

| File | Size | SHA256 | Match |
|---|---|---|---|
| MiniCPM5-2B-Q4_K_M.gguf | 1,561,318,368 | `ec2d5801640099e9…` | ✓ |
| MiniCPM5-2B-Q8_0.gguf | 2,679,710,688 | `c5415f8989bf88a8…` | ✓ |
| MiniCPM5-2B-F16.gguf | 5,039,006,688 | `0ffba3682a853295…` | ✓ |
| BF16 repo (17 files) | — | ModelScope-listed digests | ✓ (download tool: `overall: PASS, 0 failing files`) |

Weights from ModelScope only (D-006), revisions `8cc1178b…` (GGUF) and `4e7a9471…` (BF16). GGUF-embedded chat template is the default (D-007).

## 5. ROCm crash: root cause and repair (evidence preserved)

**First ROCm run:** server enumerated the GPU, processed ~50 short tasks, then **crashed mid-generation** (client saw `ConnectionResetError 10054` then `10061`). The smoke suite recorded the crash as FAIL (2/5).

**Failure mechanism (CONFIRMED, source-level):** the official ROCm b12359 build calls into **rocBLAS**, which reads per-architecture Tensile kernel data from `…\bin\rocblas\library\TensileLibrary.dat`. The ROCm 10.0.0 runtime wheels served by `stable.repo.amd.com/rocm/whl-next/` on 2026-11-27 install `rocblas.dll` **without any `library/` data directory** — zero `*.dat`/Tensile files in the entire 2.8 GB tree. Small prompts exercised GEMM paths that did not need the Tensile host; the first larger prefill initialized it → hard abort. stderr preserved in `.runtime/logs/llama-server-rocm-q4-20261127-041305.stderr.log`:

```
rocBLAS error: Cannot read …\bin\/rocblas/library/TensileLibrary.dat: No such file or directory for GPU arch : gfx1100
rocBLAS error: Could not initialize Tensile host: directory_iterator … "…\bin\/rocblas/library"
```

**Identity-drift finding:** decision D-009 pinned `rocm[libraries]==10.0.0` by **version**, and the previous gfx1151 machine passed IJ-0.5 with that spec on 2026-11-24. The same version spec served different bytes three days later (moving wheel index) — same-version-different-bytes. From now on the runtime is pinned by **package digest**, not version string.

**Repair (version-preserving):** the index also carries per-architecture wheels. `rocm-sdk-device-gfx1100==10.0.0` installs the missing `hipblaslt/library/gfx1100/` (47 kernel objects) and `rocblas/library/` (150 gfx1100 Tensile files) plus `.kpack` blobs. Installed into the same venv tree (3.2 GB total); no system change. A pip quirk silently skipped files targeting an existing namespace without `--upgrade` — recorded as a defect note.

**Post-fix ROCm run:** 249 tasks, zero errors in server log, smoke 5/5 PASS, 43/43 layers offloaded, counters: max utilization 85%, 2.11 GB dedicated VRAM. Evidence: `backend_qualification_rocm_retry.json`.

## 6. Transport-parity exception (documented, not hidden)

The 9-check API surface check requires byte-identical streaming vs non-streaming output under greedy decoding (temperature 0). Results on this machine:

| Backend | Result | Observed difference |
|---|---|---|
| Vulkan | PASS (byte-identical) | — |
| CPU | FAIL | `购买所需物资` vs `采购所需物资` (one near-tie token diverges) |
| ROCm/HIP | FAIL | `购买所需商品` vs `购买所需物资` (one near-tie token diverges) |

Mechanism (PROBABLE): llama.cpp batch-composition differences between the streaming and non-streaming paths change floating-point reduction order; at near-tie logits the argmax flips. Vulkan's kernel schedule happens to be bit-consistent between the two paths here; CPU and ROCm/HIP are not. Greedy decoding removes sampling randomness but not kernel-scheduling non-determinism. This is a property of the engine+backend, not of the harness; the harness records it rather than lowering the bar. Consequence: benchmark cells that compare transports must use the same transport on both sides; Vulkan is the only backend safe for byte-parity-sensitive checks on gfx1100.

## 7. Matched Vulkan vs ROCm/HIP engine workload

Frozen 52-item parity workload v1.0.2 (SHA `9442652900c46a90…`, greedy, stream=true, Q4_K_M, ctx 8192), identical prompts on both GPU arms (`evidence/IJSDK/P1/gpu/`):

| Metric | F-vulkan | F-rocm |
|---|---:|---:|
| Execution | PASS (0 request errors) | PASS (0 request errors) |
| Chat items | 12/12 | 12/12 |
| Structured items | 10/10 | 10/10 |
| Literal tasks | 27/30 | 27/30 |
| Prefill throughput | 1,318 tok/s | **2,159 tok/s** |
| Decode throughput | 224 tok/s | **249 tok/s** |
| TTFT mean | 33 ms | **27 ms** |
| Compute engine median | 84% | 75% |

**Cross-backend output determinism: 52/52 outputs are text-identical between Vulkan and ROCm/HIP.** The task misses (3/30 on each) are identical literal-grading items (D-13 workload semantics), not backend divergence. ROCm/HIP is faster on prefill (+64%) and decode (+11%) on this machine — consistent with the prior machine's IJ-0.5 pattern (ROCm prefill lead), but Vulkan is still the primary backend per the functional-parity rule in §1/§6; the performance edge is recorded for A10/A14 trade-off analysis and the backend decision stays frozen for the benchmark matrix.

## 8. Deliverables and reproduction

- `scripts/windows/ij_sdk_p1_backend_qualify.py` — one-command frozen protocol runner (Python; the PowerShell predecessor hung twice on the documented D-011 pipe trap and was replaced; its lessons are encoded in the Python runner).
- `scripts/windows/common.ps1` — repaired `Get-VulkanDevices` (was referenced but undefined; multiline-safe parser; regression-verified against live `vulkaninfo`).
- `configs/ij_sdk/engine_profiles/profile_vulkan_q4.json`, `profile_rocm_q4.json` — frozen engine profiles (identity, device, launch, sampling defaults, D-010 proof rule).
- Reproduction: bootstrap → `install_llama_cpp.ps1` → `install_rocm_runtime.ps1` + `pip install rocm-sdk-device-gfx1100==10.0.0` → `python -I scripts/tools/ij_sdk_p1_backend_qualify.py --backends cpu,vulkan,rocm --model q4`.

## 9. Carry-forward items

1. **C++ toolchain absent** — carries B-005 to this machine; parser-fix debug builds remain unavailable without owner action.
2. **ROCm wheel pinning** — P1 evidence pins the wheel set by digest; `install_rocm_runtime.ps1` should be extended to record package hashes (follow-up).
3. **GPU counter `engine_type` mapping** — rows record utilization and memory correctly; the engine-type string needs schema alignment with `counters.py` (cosmetic; utilization/memory evidence unaffected).
4. Stream-parity exception (§6) feeds F-layer taxonomy for the harness (A11 transport/parser ablation).
