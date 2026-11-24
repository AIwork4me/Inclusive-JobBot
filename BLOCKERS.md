# Blockers

Status values: `OPEN`, `MITIGATED` (workaround in use, cause still present),
`CLOSED`. "Owner" is who can remove the cause.

## B-001 Official llama.cpp release binaries were blocked by Smart App Control

- Priority: P0 when open
- Status: CLOSED
- Owner: machine owner
- Found: 2026-11-24, IJ-0.3. Closed: 2026-11-24.

**Symptom.** `llama-server.exe` from the `b12359` release failed to start:
"blocked by your organization's Device Guard policy" / "application control
policy has blocked this file".

**Cause.** Windows Smart App Control was on and enforced
(`UsermodeCodeIntegrityPolicyEnforcementStatus = 2`). The release assets are
not Authenticode-signed.

**What the project did.** Nothing to the policy. It recorded the blocker and
continued with work that did not depend on it. No inference ran meanwhile, so
no result belongs to a different engine.

**Closure.** The machine owner turned Smart App Control off. Verified state:
`SmartAppControlState = Off`, `UsermodeCodeIntegrityPolicyEnforcementStatus = 0`,
and the official binaries report `1.0.0-dev (build 12359, commit b1b770d90)`.

**Still true for other machines.** `install_llama_cpp.ps1` detects a blocked
binary and reports it. Changing the policy remains the owner's decision.

## B-002 `modelscope.exe` launcher was blocked by the same policy

- Priority: P2
- Status: CLOSED (owner action above); scripts keep the robust call
- Found: 2026-11-24, model download

The pip-generated launcher is unsigned and was blocked. Scripts call
`python -m modelscope.cli.cli` regardless, so they do not depend on that.

## B-003 Official ROCm build ships without hipBLAS; math libraries must be added

- Priority: P0 for the ROCm/HIP arm
- Status: OPEN (libraries installed; enumeration verified; Arm D of IJ-0.5 pending)
- Owner: project
- Found: 2026-11-24, IJ-0.3

**Symptom.** `runtime/llama-cpp/rocm/llama-server.exe --list-devices` prints
`Available devices: (none)` with no error at the default log level.

**Root cause.** `ggml-hip.dll` fails to load because its import `hipblas.dll`
is missing. The ROCm release zip is a complete build (56 entries: the CPU
build plus `ggml-hip.dll`, `amdhip64_7.dll`, `rocm_kpack.dll`,
`amd_comgr.dll`) but contains no hipBLAS, rocBLAS or hipBLASLt. The release
workflow states that rocBLAS and hipBLASLt resolve through `PATH`, and this
machine has no ROCm SDK. Evidence: `evidence/IJ0/rocm_pe_imports.json`.

**Fix.** The same source upstream CI uses: ROCm 10.0.0 runtime wheels
(`rocm[libraries]==10.0.0` from AMD's wheel index) installed into an isolated
virtual environment at `runtime/llama-cpp/rocm-libs`. No system install; the
library directory is added to `PATH` only for the llama-server process.
Installation script: `scripts/windows/install_rocm_runtime.ps1`.

**Observed after the fix.** With the library directories on `PATH`, the ROCm
build reports `ROCm0: AMD Radeon(TM) 8060S Graphics`.

**Closure condition.** Arm D of IJ-0.5 (correctness on ROCm/HIP) passes.
Until then `GFX1151_DUAL_GPU_BACKEND_QUALIFIED` cannot be granted.

## B-004 Long-running qualification exceeds one working session

- Priority: P1
- Status: OPEN
- Owner: project
- Found: 2026-11-24

The 24-hour and 168-hour soak tests and large benchmark runs need real elapsed
time. They are launched as resumable background jobs with checkpoints and are
reported with the real completed duration only.
