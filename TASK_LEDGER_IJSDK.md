# IJ-SDK-1.0 Task Ledger

Mission-specific ledger (see `MISSION_STATE_IJSDK.json`). The shared
`TASK_LEDGER.md` remains owned by the active Atlas worker; IJ-SDK-1.0 appends
only non-conflicting entries there. Status vocabulary: `PASS`, `FAIL`,
`BLOCKED`, `NOT_RUN`.

| Phase | Task | Progress | Status | Evidence |
|---|---|---|---|---|
| P0 | Live remote audit: default branch, PR #6 (58 commits, HEAD fe56f324), PRs #2/#4, issues #1/#3/#5; stale HANDOFF "no remote" noted, not edited | done | PASS | `reports/IJSDK_00_BASELINE_AUDIT.md` |
| P0 | Stacked isolation: dedicated local worktree (path withheld from evidence), branch `mission/ij-sdk-1.0-cross-sdk-agentic-benchmark` frozen at `fe56f324`, upstream tracking unset | done | PASS | `evidence/IJSDK/P0/baseline_manifest.json` |
| P0 | Suite roster verification from frozen bytes: TC-V2 500(+120 dev), MULTITOOL-V1 600(+6 diag), AGENTIC-PLAN-V1 800 worlds dual-track = 1,600 trajectories, JOB-V1 600; total 3,300 = mission expectation | done | PASS | `evidence/IJSDK/P0/baseline_manifest.json` (suite_roster_verified) |
| P0 | Prior-mission gate/verdict audit: Atlas G01-G05+G14 BLOCKED, all verdicts BLOCKED/NOT_RUN; AEVE not inherited as PASS | done | PASS | `evidence/IJSDK/P0/reusable_assets.json` |
| P0 | Reusable asset inventory + known limitations L-01..L-14 frozen | done | PASS | `evidence/IJSDK/P0/known_limitations.json` |
| P0 | Gate P0_REPOSITORY_BASELINE_FROZEN | done | PASS | `reports/IJSDK_00_BASELINE_AUDIT.md` |
| P0 | Tracking Issue #7 + Draft PR #8 created (stacked on PR #6, base codex/ij0-tool-calling) | done | PASS | https://github.com/AIwork4me/Inclusive-JobBot/issues/7, https://github.com/AIwork4me/Inclusive-JobBot/pull/8 |
| P1 | gfx1100 hardware/software fingerprint (this machine): RX 7900 XTX 0x744C, 24,560 MiB, driver 32.0.21030.2001, Vulkan 1.4.315, no C++ toolchain, redacted | done | PASS | `evidence/IJSDK/P1/environment.json`, `gpu_inventory.json` |
| P1 | llama.cpp b12359 official archives installed + SHA256-verified (cpu/vulkan/rocm) | done | PASS | `evidence/IJSDK/P1/engine_install.json` |
| P1 | ROCm runtime wheels + root-cause repair: rocBLAS TensileLibrary.dat missing for gfx1100 (crash CONFIRMED); fixed via rocm-sdk-device-gfx1100==10.0.0; wheel identity drift recorded | done | PASS | `reports/IJSDK_01_WINDOWS_GFX1100_QUALIFICATION.md` §5, `.runtime/logs/llama-server-rocm-q4-20261127-041305.stderr.log` |
| P1 | Frozen backend qualification: Vulkan full PASS (43/43 layers, 9/9 API, 5/5 smoke, counters 74% util); CPU functional (parity exception); ROCm post-fix 5/5 smoke, 85% util, parity exception | done | PASS | `evidence/IJSDK/P1/backend_qualification.json`, `backend_qualification_rocm_retry.json` |
| P1 | Matched F-vulkan vs F-rocm workload: 52/52 identical outputs; ROCm prefill 2159 vs Vulkan 1318 tok/s | done | PASS | `evidence/IJSDK/P1/gpu/` |
| P1 | Backend selection frozen: Vulkan primary (only byte-parity arm); ROCm preserved as comparator | done | PASS | `reports/IJSDK_01_WINDOWS_GFX1100_QUALIFICATION.md` §1 |
| P1 | Repair: Get-VulkanDevices implemented (was undefined); D-011 pipe trap hit twice -> Python runner replaces PowerShell orchestrator | done | PASS | `scripts/windows/common.ps1`, `scripts/tools/ij_sdk_p1_backend_qualify.py` |
| P1 | Gate P1_GFX1100_PHYSICAL_RUNTIME_GO | done | PASS | `reports/IJSDK_01_WINDOWS_GFX1100_QUALIFICATION.md` |
| P2 | Admission smokes S1 9/10, S2 9/10, S3a 7/10, S3b 8/10, S3c 5/10, S3d 9/10, R1 9/10 (dev-gen v1.0.1); F19 defect CONFIRMED + repaired (v1.0.0 preserved as diagnostic); S3=Qwen3.5-2B; R1/R2 digests verified | done | PASS | `reports/IJSDK_02_MODEL_ADMISSION.md`, `evidence/IJSDK/P2/admission/` |
| P2 | Gate P2_MODEL_IDENTITIES_AND_ADMISSION_FROZEN | done | PASS | `reports/IJSDK_02_MODEL_ADMISSION.md` |
| P3 | 10 isolated SDK venvs installed (pip freeze recorded); SEC-01 honored (agent-framework 1.26.0) | done | PASS | `evidence/IJSDK/P3/installed_artifacts.json` |
| P3 | Conformance: ALL 10 arms pass C1/C2/C3 via their own interfaces (3 sweeps; every failure root-caused) | done | PASS | `evidence/IJSDK/P3/conformance/`, `reports/IJSDK_03_SDK_SURVEY_AND_ADMISSION.md` |
| P3 | Gate P3_SDK_ADMISSION_AUDITED | done | PASS | `reports/IJSDK_03_SDK_SURVEY_AND_ADMISSION.md` |
| P4 | Wire-capture event contract (13 stages, closed vocab), AgentAdapter contract, B0 raw reference loop, deterministic fault-injectable gateway | done | PASS | `benchmarks/ij_sdk/contracts/events.py`, `adapters/base.py`, `adapters/b0_raw.py`, `gateway.py` |
| P5 | Independent business oracle + 14-control differential battery; 4 oracle defects found and fixed; 14/14 PASS; AEVE not inherited | done | PASS | `reports/IJSDK_05_EVALUATOR_QUALIFICATION.md`, `evidence/IJSDK/P5/differential_results.json` |
| P5 | Gate P5_EVALUATOR_SCOPE_QUALIFIED (E1/E3/E4/E5/E6 deterministic scopes) | done | PASS | `reports/IJSDK_05_EVALUATOR_QUALIFICATION.md` |
| P4 | Remaining SDK adapters (B2/B5 wired on conformance-verified paths) + one-command runner + conformance tests | not started | NOT_RUN | - |
| P6 | Fresh holdout authoring (>=1,200 cases, protected artifacts) + freeze | not started | NOT_RUN | - |
| P8 | Formal matrix execution (M0/M1/M2 across S1/S2/S3 x B0-B9) via resumable queue | not started | NOT_RUN | - |
| P2 | Candidate research (ModelScope): LFM3-1.7B verified live incl. official GGUF + LFM license $10M cap; Qwen3.5-2B / Granite-4.0-1b / SmolLM3-3B / Gemma-4-E2B verified; MiniCPM5-2B agent pedigree confirmed | done | PASS | research summary (to be frozen into P2 passports) |
| P2 | Admission protocol preregistered before any candidate result | done | PASS | `configs/ij_sdk/model_admission_protocol.json` |
| P2 | Admission smoke runs S1/S2/S3 + R1/R2 downloads | not started | NOT_RUN | - |
| P3 | SDK landscape research: versions/licenses/local-endpoint paths verified; MS Agent Framework 1.26.1/.2 supply-chain hijack recorded (pin 1.26.0 or isolate); Antigravity lacks documented OpenAI-compatible endpoint (project's local-loop evidence differs - reconcile) | done | PASS | research summary (to be frozen into P3 passports) |
| P3 | SDK passports + isolated installs + admission | not started | NOT_RUN | - |
