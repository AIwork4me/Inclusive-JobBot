# Blockers

## IJ-SLM-1.0 continuation

- Mechanical qualification covers nine scoped TC-V3 components. D25, native parser semantics, affirmative authorization writes, persisted state and conditional planning lack the applicable independent credentials. Synthetic read-only physical dispatch uses the scoped TC-V3 gate.
- AG-11 stays BLOCKED for all three priority models. Runtime engineering owns complete process-tree and egress observation. The published diagnostic provider endpoint is loopback. [P0 controls](evidence/IJSLM/p0/manifest.json)
- The current workstation token cannot start the temporary Windows kernel network trace. The direct ETW session attempt returned access denied (HRESULT 0x80070005). The machine owner owns authorization for a temporary collector capable of attributing short-lived TCP and UDP events. [Microsoft ETW permissions](https://learn.microsoft.com/en-us/windows/win32/etw/controlling-event-tracing-sessions)
- The historical Qwen3.5 AG-02 ValueError remains UNVERIFIED. A new real SDK failure reproduced a different 512 KiB aggregate SSE limit and a same-byte replay isolated that failure. MiniCPM5 now calls the expected tool on both Direct modes in the matched controls. Its historical discrepancy remains open. [Root cause evidence](reports/SLM10_P0_EXECUTION.md)

- The frozen TC-V3 controller owns the Radeon schedule. Physical F/G admission is gated on all 4,950 priority captures. The new LFM3 adapter holdout and Extension need the same Radeon slot after the baseline. [Admission records](evidence/IJSLM/tc-v3-admissions/manifest.json) · [Adapter holdout](atlas/slm/v1.0/sdk-adapter-lfm3-holdout.json)

- Formal MULTITOOL-V2 dispatch requires blind validation of the candidate partition, persisted write and approval witnesses, and physical SDK and Direct transport. Formal AGENTIC-PLAN-V2 requires the independent 800-case world and witness bundle, end-to-end runtime qualification and the D12/D23/D25 credentials. Benchmark and evaluation engineering own these gates. [MULTITOOL candidate](atlas/slm/v1.0/multitool-v2-candidate/manifest.json) · [Planning source bundle](docs/SLM10_PLANNING_ROSTER.md)

## IJ-0.7.3 frozen Q2 follow-up

- Q2 energy and electricity cost remain NOT_RUN. The frozen captures measured request time, native inference time, tokens and process GPU memory. No power and tariff measurements are available.
- Q3, full historical Judge routing and independent human blind review remain open. The GPU handoff preserved their recovery commands and frozen inputs.


## IJ-0.7.3

- Q3 evaluator credentials are absent for all 600 historical family, dimension and risk combinations. Evaluation engineering owns the independent roster freeze and replay of complete routes. The Gold source replay is in-scope development evidence. [Route matrix](evidence/IJ073/aeve/historical_route_matrix.json)

- The four initial local Judge families failed the frozen thresholds on all 3,228 completed Gold assessments. Evaluation engineering owns fresh qualification of revised configurations and independent families. The full historical review requires enough admitted independent families for each subject and an independent third family on disagreement. Status, counts and pinned inputs are in [the qualification report](reports/IJ073_JUDGE_QUALIFICATION.md).
- The original reviewed archives lack sufficient decision evidence for 36 historical physical trials. Preserve them in the completeness denominator. The remaining 17,458 have citable stage projections. [Coverage](evidence/IJ073/aeve/history/coverage.json)

- Benchmark engineering owns the open Oracle qualification. In 81 of 128 originally rejected plans the archived independent path cannot be expressed using the proposed nodes even with relaxed guards. Repaired V2 witnesses now pass on all 800 frozen worlds. Remaining engineering gates include independent transaction, rollback and audit checks and end-to-end model transport. See the [per-case analysis](reports/IJ073_CONDITIONAL_PLAN_ORACLE_ROOT_CAUSE.md).
- Independent reviewers own formal human calibration after the AEVE and review-packet freezes. The original 22-case packet remains unreviewed. Formal benchmark validity and new physical qualification depend on the specified gates.

## IJ-0.7.1 Atlas

| ID | Status | Owner | Condition |
|---|---|---|---|
| B-IJ071-01 | BLOCKED | Benchmark engineering | The frozen Plan-first initial gate fails on 128/800 independent software witnesses. The revised scorer freeze and cross-suite qualification depend on the discrepancy review and the independent human assessments. Both 540-trial PC-S controls and all 1,152 PC-P physical trials are sealed. |
| B-IJ071-02 | BLOCKED | Benchmark engineering | The legacy JOB-V1 controller yielded the Radeon slot. Arm A is sealed, and Arm B has seven unsealed records. The A1 reference and prompt queues and the matched draft authorization diagnostic are sealed. Further qualification depends on the A1 gate. See `atlas/physical_queue.json`. |
| B-IJ071-03 | CLOSED | Runtime engineering | The pinned Qwen3-8B launchers completed the frozen Planning and MULTITOOL PC-S trials with raw wire and GPU evidence. |
| B-IJ072-01 | BLOCKED | Independent human reviewers | The 22-case score-blind packet is ready. Independent assessments and reconciliation are pending. See `reports/ATLAS_A1_BLIND_REVIEW.md`. |
| B-IJ072-02 | BLOCKED | Benchmark engineering and independent reviewers | The frozen initial plan evaluator accepts 602 contradictory action-condition mutations. The original traces and scores are preserved. A revised condition contract needs blind validation against the ambiguous public cases and independent positive and negative witnesses. See `evidence/IJ072/benchmark_validity/planning-precondition-controls.json`. |

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
- Status: CLOSED (closed 2026-11-24 by IJ-0.5)
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

**Closure.** Arm D (ROCm/HIP, Q8_0) and Arm F-rocm (Q4_K_M) pass: 43/43 layers on the GPU, Compute engine median 81% and 73%, and the same 30/30 task and 10/10 structured outputs as the CPU on the same weights. Evidence: `reports/IJ0_GPU_BACKEND_QUALIFICATION.md`.

## B-004 Long-running qualification exceeds one working session

- Priority: P1
- Status: OPEN
- Owner: project
- Found: 2026-11-24

The 24-hour and 168-hour soak tests and large benchmark runs need real elapsed
time. They are launched as resumable background jobs with checkpoints and are
reported with the real completed duration only.

## B-005 Upstream parser unit tests require the native C++ build

- Priority: P1
- Status: CLOSED (2026-11-24)
- Owner: project
- Found: 2026-11-24, IJ-0 tool-calling step

The initial PATH probes found no toolchain. IJ-0.6 located an existing Visual
Studio Community 2026 installation via `vswhere`, with MSVC 19.52, CMake
4.3.1 and Ninja. Use its process-local developer environment. The pinned
`test-chat` and the direct probe both built and ran. [Windows test-chat evidence](evidence/IJ06/parser/p0-windows-upstream-test-chat.log)

**Workaround in use.** The fixture runner reaches the native parser through
the public API via assistant prefix continuation. It verifies that successful
replies sampled only EOS. Upstream `test-chat` can also run in GitHub-hosted
Linux CI.

## B-006 Energy per successful task cannot be measured

- Priority: P2
- Status: OPEN
- Owner: machine owner
- Found: 2026-11-24

There is no power meter and no trustworthy whole-machine power telemetry.
Energy per task stays `NOT_RUN`; GPU TDP is not used as a substitute. If the
owner has a wall-plug power meter, the measurement can be added.

## B-007 Soak tests need the machine awake for seven days

- Priority: P1 (for the 24 h and 168 h gates only)
- Status: OPEN
- Owner: machine owner
- Found: 2026-11-24

The 168-hour soak test needs real elapsed time with the machine awake and the
remote session undisturbed. Sleep and hibernation settings are the owner's to
change; the project does not touch power settings.

The IJ-0.7 read-only power query showed timeout 0 for both AC and DC idle
sleep in the active scheme. The uninterrupted test interval and single-GPU
availability remain unverified. No power policy change was applied.

## B-008 The original ECO-01 SDK checklist was unavailable in the checkout

- Priority: P0 for full SDK acceptance
- Status: CLOSED (2026-11-24)
- Owner: project

The owner provided the twelve gates in the IJ-0.6 mission. The restored
requirements are in `docs/ANTIGRAVITY_SDK_ACCEPTANCE_SPEC.md`. Technical
qualification is tracked independently.

## B-009 The pinned MiniCPM5 native parser fails the fixed fixtures

- Priority: P0 for native tool-calling qualification
- Status: MITIGATED
- Owner: project

The official llama.cpp b12359 native parser fails fixed expectations.
Observed failures cover whitespace in a typed value, incomplete structured
arguments, out-of-enum values and duplicate JSON keys. P4b closes the measured
native defects in fixture conformance on the separate CPU/Vulkan/ROCm candidate.
The original pinned binary still fails the frozen suite. Independent model
admission and production selection are pending. [Parser report](reports/IJ06_PARSER_ROOT_CAUSE_REPORT.md)

## B-010 SDK process egress has no trusted observation or isolation

- Priority: P0 for AG-11
- Status: OPEN
- Owner: project and machine owner if machine-level changes are needed

Both SDK suites target a verified loopback inference service with API keys
cleared. Full process egress isolation or complete trusted traffic observation
is still needed. Preserve the network and remote session during this test.

## B-011 Historical V1 data lacks confirmed stateful write inputs

- Priority: P0 for IJ-0.7 transactional and SDK replay evidence
- Status: OPEN
- Owner: project

The frozen generator 1.0.2 tool signatures and in-memory synthetic receipts
preserve experimental comparability. Some schemas omit resource and approval
inputs required by the SQLite Gateway. Record the original diagnostic as
executed and exercise the validated stateful path with independent, explicit
inputs. [Historical replay](reports/IJ07_HISTORICAL_REPRODUCTION.md)

## B-012 MiniCPM5 fails independent sequential tool qualification

- Priority: P0 for IJ-0.7 model and production qualification
- Status: OPEN
- Owner: project

The P4b observer candidate passed 25/100 independent sequential cases on
each Radeon backend. Both full TC-V2 first-pass rates were below 90%.
Trace the omitted calls, incorrect arguments and final facts through the
preserved raw requests and checkpoint hashes before testing any revised
model profile. Keep the completed holdout immutable.
[TC-V2 qualification](reports/IJ07_TC_V2_QUALIFICATION.md)
