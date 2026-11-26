# Task Ledger

## IJ-0.7.3

All 64 paired planning-development requests are sealed (2 PASS, 62 FAIL). The first 32 independent Gold qualification responses cover Qwen, Gemma, Ministral and LFM. See reports/IJ073_QWEN3_14B_PLANNING_DEVELOPMENT.md and reports/IJ073_JUDGE_QUALIFICATION.md. Primary judgments on physical and software histories await admission.

Executable AEVE resumes from the local queue or restores original portable attempts. Stage-bound primary voting, third-family resolution and independent citation-entailment checks run only after the frozen admission. The E00-E19 ledger is in atlas/ij073/progress.json.

Indexed 1,341 reviewed archive assets into 42,987 records. Of 17,494 physical trials, 17,458 support at least one stage-specific judgment. The 36 others retain their missing-evidence reasons. The physical semantic roster covers 155,383 distinct trial/dimension pairs. See evidence/IJ073/aeve/history/coverage.json.

The portable development meta-evaluation replays 60 physical judgments and their raw answers. Four matched sets of 14 bias interventions across four families are specified in evaluation/aeve/robustness.py. See reports/IJ073_META_EVALUATION.md.

Both P0 CLI failures on 04dc9ab reproduce and pass on the repaired branch (evidence/IJ073/aeve/entrypoint_regression.json). Four locally pinned Judges have a frozen qualification configuration, 807 independent cases each, and cross-process GPU exclusion. See evaluation/aeve/qualification_freeze.json. Ten Qwen3-14B physical A/B outputs are replayed in evidence/IJ073/oracle/clarification_ab.json.

The 25-dimension AEVE contract, deterministic veto, blind citations and split-aware metrics are implemented. The revision-1 rule-derived GOLD roster contains 1,615 packets. Physical development evidence is indexed under `evaluation/aeve/results/sessions/`; sealed evaluator qualification remains NOT_RUN.

Oracle differential replay passed 800 frozen worlds and nine independent event controls. The 235 legacy divergences are accounted for individually in `evidence/IJ073/oracle/differential_closure.json`.

AEVE local runtime and restartable queue implemented. The pinned family routing excludes the candidate family. Physical verdicts are recorded separately from model admission. See `evaluation/aeve/controller.py` and `evaluation/aeve/judge_registry.json`.

| Task | Status | Evidence |
|---|---|---|
| Recount historical witness, physical reference and job panels | PASS | `evidence/IJ073/baseline.json` |
| Replay historical synthetic calls, compare observed model traces and run necessary-effect interventions | PASS | `evidence/IJ073/oracle/` |
| Execute V2 witness graphs on 800 worlds, verify 13 equivalent groups and 602 paired interventions | PASS | `evidence/IJ073/oracle/executable_witness.json`, `evidence/IJ073/oracle/guard_controls.json` |
| Check public reply boundary and 21 finite counterfactual worlds | PASS | `evidence/IJ073/oracle/public_worlds.json` |
| Recheck installed MiniCPM artifacts and enumerate pinned backends | PASS | `evidence/IJ073/machine_inventory.json` |
| Qwen3-14B paired V2 planning protocol, zero-tool development case | FAIL | `evidence/IJ073/transport/initial/` |
| Matched public-field correction, native and constrained | FAIL | `evidence/IJ073/transport/paired_result.json` (four archived requests across both treatments) |
| Qualify the complete conditional Oracle | NOT_RUN | `reports/IJ073_CONDITIONAL_PLAN_ORACLE_VALIDATION.md` |
| Qualify AEVE and perform full new model runs | NOT_RUN | `atlas/ij073/progress.json` |

## IJ-0.7.2 Atlas

| Task | Status | Evidence |
|---|---|---|
| PC-S TC-V2 frozen development roster and resumable launch | PASS | Software only. `tests/regression/ij07/test_tc_v2_batch.py` |
| PC-S TC-V2 physical coverage | PASS | 100/100 assessed, 56 strict PASS and 44 FAIL. `evidence/IJ072/benchmark_validity/pc-s-tc/summary.json` |
| JOB-V1 legacy A/B checkpoint reconciliation | PASS | `evidence/IJ072/purpose_built/legacy-job-ab-checkpoint.json` |
| Planning P1 and separate protocol and execution diagnostic | PASS | Software regression only. `tests/regression/ij07/test_agentic_planning_v1.py` and `tests/regression/test_atlas_scoring.py` |
| TC-V2 quote public-input software witnesses | PASS | 80/80, with SQLite state checks and seven rejected mutations. `evidence/IJ072/benchmark_validity/quote-controls.json` |
| Source trace diagnostics for RC-01 and RC-02 | PASS | 2,880 indexed historical failed trials. Causal closure remains BLOCKED. `atlas/root_causes/failure_ledger.jsonl` |
| MULTITOOL explicit 32-call streaming and non-streaming decoder budget | PASS | Software only. `tests/regression/ij07/test_batch_wire_profile.py` and `tests/regression/ij07/test_multitool_v1.py` |
| PC-S MULTITOOL-V1 physical coverage | PASS | 120/120 assessed, 28 strict PASS and 92 FAIL. `evidence/IJ072/benchmark_validity/pc-s-multi/coverage.json` |
| L0 public-input intent witness and three mutations | PASS | 100/100 Acting-first exact matches. `evidence/IJ072/benchmark_validity/planning-intent-controls.json` |
| Qwen3-8B PC-S physical Planning coverage | PASS | 320/320 sealed with 4 strict PASS and 316 FAIL. `evidence/IJ072/benchmark_validity/pc-s-planning-full/diagnostic.json` |
| PC-P paired L0 Plan-first pilot for MiniCPM5, LFM3, Gemma and Qwen3-8B | FAIL | 80 matched pairs. Initial protocol improved across the four models. Strict results remain 0/80 in each arm. `evidence/IJ072/benchmark_validity/pc-p-l0-model-comparison.json` |
| PC-P P2-P5 interventions and fixed factorial roster | PASS | Software verification. 32 matched cases spanning L0-L7 and both languages. `atlas/benchmarks/pc_p_factorial.json` |
| PC-P P0-P5 factorial physical coverage | PASS | All 1,152 sealed on Radeon. Strict results are 4 PASS and 1,148 FAIL. Four passes come from two Qwen3-8B L2 cases in two arms. `reports/ATLAS_PROMPT_CAUSAL_ABLATION_FINAL.md` |
| PC-P Gemma first-response attribution | PASS | All 288 physical trials sealed. Native grammar recovered all 128 initial envelopes. Gemma obtained 40 verified business outcomes, 37 with fenced endings, and zero strict passes. `evidence/IJ072/benchmark_validity/pc-p-g-factorial-wire.json` |
| PC-P LFM3 first-response attribution | PASS | All 288 physical trials sealed. Native grammar restored 128/128 initial envelopes. Four verified business outcomes and zero strict passes. The P3 arm exposed reasoning tags in 16/32 downstream captures. `evidence/IJ072/benchmark_validity/pc-p-b-factorial-wire.json` |
| PC-P MiniCPM5 first-response attribution | PASS | All 288 physical trials sealed. P0 initial gate rejected all 32, including 27 native tool-call responses. The schema arms restored 128/128 initial envelopes. Four met the frozen execution checks and none of those four matched the frozen goal. `evidence/IJ072/benchmark_validity/pc-p-a-factorial-wire.json` |
| PC-P Qwen3-8B first-response attribution | PASS | All nine arms audited against 288 first responses. P0 submitted eight final envelopes and 24 native tool call batches before the initial plan. `evidence/IJ072/benchmark_validity/pc-p-h-factorial-wire.json` |
| Physical MULTITOOL prior-turn draft coverage | PASS | All 74 Qwen3-14B trials sealed. Both arms strictly pass the same four tasks and preserve the same four verified draft rows. `evidence/IJ072/benchmark_validity/pc-s-j-multitool-draft-guard-pairs.json` |
| Physical early-draft denial | NOT_RUN | The reference model made four prior-reviewed draft calls in each arm and zero early draft calls. The deterministic guards exercised all 37 early cases. `evidence/IJ072/benchmark_validity/multitool-observed-draft-controls.json.gz` |
| Draft authorization after user scope update | PASS | The software control verifies that a delivered update invalidates the previous review and that a fresh prior-turn review permits one draft. `tests/regression/ij07/test_multitool_v1.py` |
| MULTITOOL extended independent mutation controls | PASS | 3,149 negative mutations rejected, 675 equivalent trace/output mutations accepted and 75 unverified audit variants blocked. `evidence/IJ072/benchmark_validity/multitool-extended-controls.json.gz` |
| MULTITOOL Unicode and Chinese reference adjacency | PASS | 600 equivalent JSON key escapes passed. All 263 applicable public witness task variants produced identical tool calls and outcomes with directly adjoining Han text and ASCII reference IDs. `evidence/IJ072/benchmark_validity/multitool-unicode-controls.json.gz` |
| Planning initial action precondition mutation | FAIL | The frozen evaluator accepted all 562 contradictory first-action conditions and 40 contradictory approval conditions. Actual sandbox authorization controls have separate evidence. `evidence/IJ072/benchmark_validity/planning-precondition-controls.json` |
| Full-level Qwen3-8B P3 sampler and P4 input verification | PASS | Native grammar on all 32 P3 trials. P4 changed tool descriptions only and reduced first-turn prompt tokens by 4–44 on 28 tool-applicable cases. `evidence/IJ072/benchmark_validity/pc-p-h-p3-wire-full.json` and `evidence/IJ072/benchmark_validity/pc-p-h-p4-tool-definition-check.json` |
| Qwen3-8B P3 native schema wire probe | PASS | Applied and schema-valid in 5/5 physical probe trials, with 0/5 strict PASS. The probe's dirty checkout excludes it from the formal factorial panel. `evidence/IJ072/benchmark_validity/pc-p-h-p3-wire-probe.json` |
| TC-V2 holdout public-input witness | PASS | 500/500 with actual synthetic tool execution and independently read SQLite state. `evidence/IJ072/benchmark_validity/tc-holdout-witness.json` |
| TC-V2 expanded authorization, identifier and duplicate controls | PASS | All 1,500 trace mutations rejected. Actual synthetic sandbox denied 500 unseen IDs and 50 unsigned writes, and prevented 50 repeated write effects. `evidence/IJ072/benchmark_validity/tc-holdout-extended-controls.json.gz` |
| MULTITOOL-V1 public-input witness | PASS | 600/600 with tool events and 75 direct SQLite draft-state checks. `evidence/IJ072/benchmark_validity/multitool-witness.json.gz` |
| MULTITOOL observed-review draft guard | PASS | 37 legacy early drafts reproduced. The opt-in profile denied all 37 early and same-turn attempts, accepted the prior-turn controls and replayed 600/600 public witnesses. Software only. `evidence/IJ072/benchmark_validity/multitool-observed-draft-controls.json.gz` |
| Planning L1-L7 public-input Acting-first witness | PASS | 700/700 software trials with independent action selection. `evidence/IJ072/benchmark_validity/planning-read-controls.json` and `evidence/IJ072/benchmark_validity/planning-advanced-controls.json` |
| Planning L4-L7 synthetic safety and scorer mutation controls | PASS | 3,933/3,933 mutated traces rejected. The live synthetic sandbox denied 360 early, forged or duplicate write calls without changing state. `evidence/IJ072/benchmark_validity/planning-advanced-mutations.json.gz` |
| Planning L0-L7 public-input Plan-first witness | FAIL | 672/800 strict PASS and 128 FAIL. Actual sandbox actions, business facts and state passed for all 800. The initial plan gate rejected 85 at L4 and 43 at L7. `evidence/IJ072/benchmark_validity/planning-plan-controls.json.gz` |
| Planning public contract and conditional route audit | PASS | 13 groups covering 29 L4/L7 cases share a normalized public contract and plan shape within group, execute different paths, and fail the frozen plan gate. `evidence/IJ072/benchmark_validity/planning-public-ambiguity.json` |
| JOB-V1 primary public-input witness | PASS | 600/600 with independent answer construction, typed sandbox actions and SQLite verification. `evidence/IJ072/benchmark_validity/job-witness.json.gz` |
| JOB-V1 expanded audit, business state and semantic controls | PASS | 2,650 negative mutations rejected, 725 equivalent outputs accepted, 600 missing audit snapshots BLOCKED and 600 unauthorized synthetic writes denied. `evidence/IJ072/benchmark_validity/job-extended-controls.json.gz` |
| A1 bilingual and mixed-language human review | NOT_RUN | Prepared 22 score-blind cases spanning the four suites. `reports/ATLAS_A1_BLIND_REVIEW.md` |
| Larger Qwen3-14B reference artifact and runtime admission | PASS | CPU identity and Radeon Vulkan native-tool probes. `evidence/IJ072/model_identity/admission/J/report.json` |
| Qwen3-14B PC-S TC-V2 physical coverage | PASS | 100/100 sealed with 66 strict PASS and 34 FAIL. `evidence/IJ072/benchmark_validity/pc-s-j-tc/summary.json` |
| Qwen3-14B PC-S MULTITOOL physical coverage | PASS | All 120 sealed with 45 strict PASS and 75 FAIL. `evidence/IJ072/benchmark_validity/pc-s-j-multi-full/coverage.json` |
| Qwen3 PC-S MULTITOOL matched model comparison | PASS | 120 matched first attempts. Qwen3-8B passed 28 and Qwen3-14B passed 45. `evidence/IJ072/benchmark_validity/pc-s-multitool-qwen-pair.json` |
| Qwen3-14B MULTITOOL physical streaming comparison | PASS | 10/10 matching strict results, ordered actions and final payloads over HTTP JSON and SSE, with up to 20 calls in an observed turn. `evidence/IJ072/benchmark_validity/pc-s-j-multitool-streaming-pairs.json` |
| Qwen3-14B PC-S Planning physical coverage | PASS | All 320 sealed with 35 strict PASS and 285 FAIL. `evidence/IJ072/benchmark_validity/pc-s-j-planning-full/diagnostic.json` |
| Qwen3-14B Planning expanded diagnostic dimensions | PASS | All 320 exact-source trials audited by track and case with separate applicability. `evidence/IJ072/benchmark_validity/pc-s-j-planning-layered.json` |
| PC-S Planning expanded diagnostic dimensions | PASS | 320 sealed physical trials rescored with separate applicability denominators and unchanged historical scoring. `evidence/IJ072/benchmark_validity/pc-s-planning-layered.json` |
| Deterministic gateway timeout rollback regression | PASS | A Windows push check expired before the handler. The regression now advances its clock after the staged write and asserts rollback and audit state. `tests/security/test_gateway_execution.py` |
| A1 evaluator qualification and stronger reference | BLOCKED | `atlas/physical_queue.json` |

## IJ-0.7.1 Atlas

| Task | Status | Evidence |
|---|---|---|
| IJ071-A0 | PASS | [Baseline audit](reports/ATLAS_A0_BASELINE_AUDIT.md) and [generated dashboard](reports/ATLAS_PROGRESS_DASHBOARD.md) |
| IJ071-A0-REVIEW | PASS | Separate historical scores, preserve missing seed outcomes, and recheck archived controls and candidate bindings in CI |
| IJ071-A1-SOURCE | PASS | [Source audit](reports/ATLAS_A1_BENCHMARK_VALIDITY.md) |
| IJ071-A1-REFERENCE | PASS | [3,300 software control trials](reports/ATLAS_POSITIVE_NEGATIVE_CONTROL.md) |
| IJ071-A1-GATE | BLOCKED | [Open validity requirements](reports/ATLAS_A1_BENCHMARK_VALIDITY.md) |
| IJ071-A2 through A11 | NOT_RUN | [Phase and gate records](atlas/progress.json) |

## IJ-0.7

| ID | Task | Status | Evidence |
|---|---|---|---|
| IJ07-M0 | Independent archival audit of IJ-0.6 and current Windows inventory | PASS | `reports/IJ07_INITIAL_INDEPENDENT_AUDIT.md` |
| IJ07-M1 | Official source identity and Q8_0 digest verification | PASS | `evidence/IJ07/model_identity/` |
| IJ07-M1-GPU | Initial seven GGUF admission runs and anomaly checks | FAIL | `reports/IJ07_MODEL_ADMISSION_MATRIX.md` |
| IJ07-M2-OBSERVER | Source observer on/off and both Radeon backends | PASS | `evidence/IJ07/historical_replay/observer_control/` |
| IJ07-M2 | Four-arm historical replay with persisted state and SDK capture | BLOCKED | `reports/IJ07_HISTORICAL_REPRODUCTION.md` |
| IJ07-M5-WIRE | Initial full archived failure indexing and protocol investigation | PASS | `reports/IJ07_SOURCE_LEVEL_ROOT_CAUSE_MASTER_REPORT.md` |
| IJ07-M3-TC-FREEZE | TC-V2 holdout, distinct development split, state oracle and software replay | PASS | `benchmarks/tool_calling_v2/holdout/manifest.json` |
| IJ07-M3-MT-FREEZE | MULTITOOL-V1 600 case freeze and synthetic verification | PASS | `benchmarks/multitool_v1/frozen/manifest.json` |
| IJ07-M4-FREEZE | AGENTIC-PLAN-V1 800 case freeze and synthetic witness verification | PASS | `benchmarks/agentic_planning_v1/datasets/manifest.json` |
| IJ07-M7-FREEZE | JOB-V1 600 case roster and stateful synthetic verification | PASS | `benchmarks/job_productivity_v1/holdout/frozen/manifest.json` |
| IJ07-M3-TC | Dual-backend TC-V2 qualification, 2,592 physical trial records | FAIL | `reports/IJ07_TC_V2_QUALIFICATION.md` |
| IJ07-M3-MT | MULTITOOL-V1 physical primary panel and stratified measurement, 600/600 | PASS | `reports/IJ07_MULTITOOL_CAPABILITY_REPORT.md` |
| IJ07-M3-MT-OUTCOMES | MULTITOOL-V1 primary task outcomes, 129 PASS and 471 FAIL | FAIL | `evidence/IJ07/multitool/primary-vulkan-full/coverage.json` |
| IJ07-M3-MT-REPEAT | MULTITOOL-V1 physical 100-case three-seed panel, 300/300 | PASS | `evidence/IJ07/multitool/repeat-vulkan-full/reliability.json` |
| IJ07-M3-MT-CHECKPOINT | Verify and archive first 213 of 600 Radeon Vulkan trials | PASS | `evidence/IJ07/multitool/primary-vulkan-checkpoint/coverage.json` |
| IJ07-M5-MT-WIRE-BUDGET | Isolate and verify the decoder batch control on 14 unchanged raw responses | PASS | `evidence/IJ07/root_causes/multitool_batch_limit_control.json` |
| IJ07-M5-MT-IJ06-COMPAT | Preserve the exact frozen gateway and isolate the batch profile in IJ-0.7 | PASS | `benchmarks/root_cause/wire_profiles.py` |
| IJ07-M5-MT-WIRE-FULL | Reprocess all 25 known wire limit rejections on unchanged raw responses | PASS | `evidence/IJ07/root_causes/multitool_batch_limit_full_control.json` |
| IJ07-M5-MT-WIRE-LIVE | Two corrected Vulkan wire-profile diagnostics' business scores | FAIL | `evidence/IJ07/multitool/wire-fix-diagnostic/` |
| IJ07-M4 | Full physical two-track L0–L7 first-pass study and archive | PASS | `evidence/IJ07/planning/primary-vulkan-full/diagnostic.json` |
| IJ07-M4-REPEAT | 960 original-profile Vulkan trials, 160 cases with three seeds in both tracks | PASS | `evidence/IJ07/planning/repeat-vulkan-full/diagnostic.json` |
| IJ07-M4-REPEAT-OUTCOMES | Repeated planning task success across both original tracks | FAIL | `evidence/IJ07/planning/repeat-vulkan-full/diagnostic.json` |
| IJ07-M4-LEVEL | Original Vulkan profile continuous level qualification | FAIL | `reports/IJ07_AUTONOMOUS_PLANNING_BENCHMARK.md` |
| IJ07-M4-L0-EXECUTION | Both tracks' real L0 roster and archived source proof | PASS | `evidence/IJ07/planning/primary-l0-checkpoint/diagnostic.json` |
| IJ07-M4-L0-CAPABILITY | Both tracks' L0 research threshold | FAIL | `reports/IJ07_AUTONOMOUS_PLANNING_BENCHMARK.md` |
| IJ07-M5-PLANNING-REFERENCE | Correct the Chinese reference boundary and replay 100 exact first-turn proposals | PASS | `evidence/IJ07/root_causes/planning_reference_boundary_control.json` |
| IJ07-M5-PLANNING-PROMPT | CPU development control for the first-turn plan contract | FAIL | `evidence/IJ07/root_causes/planning_prompt_stage_cpu.json` |
| IJ07-M5-PRIMARY-FAILURE-INDEX | Link 2,071 MULTITOOL and planning failures to exact captures and available controls | PASS | `evidence/IJ07/root_causes/physical_primary_failure_index.jsonl` |
| IJ07-M5-FAILURE-REGISTER | Index historical, TC-V2, MULTITOOL and planning fault records under the requested taxonomy | PASS | `evidence/IJ07/root_causes/failure_ledger.json` |
| IJ07-M7 | Six-arm JOB-V1 causal validation | NOT_RUN | `benchmarks/job_productivity_v1/holdout/README.md` |
| IJ07-M3-MT-RUNNER | MULTITOOL-V1 Radeon runner and exact-resume software tests | PASS | `benchmarks/multitool_v1/README.md` |
| IJ07-M6-STATISTICS | Independent paired comparison and repeat statistics software | PASS | `benchmarks/competitive_slm/STATISTICS.md` |
| IJ07-M6-DEVELOPMENT | Same-case Vulkan development diagnostics for four contenders | FAIL | `reports/IJ07_COMPETITIVE_SLM_BENCHMARK.md` |
| IJ07-M6-TC-BATCH | Shared Vulkan TC-V2 roster runner and exact-resume software checks | PASS | `benchmarks/competitive_slm/TC_V2_BATCH.md` |
| IJ07-M6-TC-PLAN | Freeze six B/D/F/G contrasts and verify archive export software | PASS | `configs/ij07/tc_v2_competitive_plan.lock.json` |
| IJ07-M6-TC-B-CHECKPOINT | Verify the first 200 ordered B trials and sealed Radeon evidence | PASS | `evidence/IJ07/competitive_slm/tc-v2-B-first-checkpoint/archive.json` |
| IJ07-M6-MT-PLAN-RUNNERS | B/D/F/G multi-tool and two-track planning runner preflights with local weights | PASS | `benchmarks/agentic_planning_v1/README.md` |
| IJ07-M4-ARCHIVE | Verify planning run journals, model captures and level summaries | PASS | `scripts/tools/archive_ij07_planning.py` |
| IJ07-M7-MODEL-RUNNER | Five model treatments, frozen identity and executable preflight | PASS | `benchmarks/job_productivity_v1/holdout/MODEL_ARMS.md` |
| IJ07-M7-MODEL-DIAGNOSTIC | All 15 matched model treatment diagnostics assessed | PASS | `evidence/IJ07/job_ablation/model_diagnostic/coverage.json` |
| IJ07-M7-F-CORRECTION | Reproduce and verify explicit mixed-language receipt correction in Arm F intake | PASS | `tests/regression/ij07/test_job_v1_arm_f.py` |
| IJ07-M7-F-CONTROL | Paired post-hoc source-controlled original and repaired job panels | PASS | `evidence/IJ07/job_ablation/F/receipt-correction/comparison.json` |
| IJ07-M7-F-CORRECTED-QUAL | Independent commercial measurement on a new frozen roster | NOT_RUN | `reports/IJ07_BUSINESS_VALUE_VALIDATION.md` |
| IJ07-M1-AION-SERIAL-CONTROL | Same-token CPU and Radeon explicit serial instruction control | PASS | `evidence/IJ07/model_identity/aion_tools/` |
| IJ07-M1-AION-DEPENDENCY | Official CPU and Radeon WebGPU dependent tool diagnostic | FAIL | `evidence/IJ07/model_identity/aion_tools/` |
| IJ07-M2-LIVE | Exact four-arm history, 2,000/2,000 physical GPU inference cases | PASS | `evidence/IJ07/historical_replay/full/summary.json` |
| IJ07-M2-UPSTREAM | Pinned b12675 fixtures and prior-failure checks | FAIL | `evidence/IJ07/historical_replay/upstream_b12675/report.json` |
| IJ07-M3-MT-DIAGNOSTIC | Four initial physical multi-tool cases | FAIL | `reports/IJ07_MULTITOOL_CAPABILITY_REPORT.md` |
| IJ07-M4-DIAGNOSTIC | Four physical trials in planning and acting modes | FAIL | `reports/IJ07_AUTONOMOUS_PLANNING_BENCHMARK.md` |
| IJ07-M5-API | Tool-choice validation patch RED/GREEN and candidate rerun | PASS | `reports/IJ07_SOURCE_LEVEL_ROOT_CAUSE_MASTER_REPORT.md` |
| IJ07-M8-AG06 | Repeated real SDK structured output test on both backends | FAIL | `evidence/IJ07/antigravity/` |
| IJ07-M8-AG06-PROMPT | Real SDK CPU control of explicit result-field extraction | PASS | `evidence/IJ07/antigravity/ag06_prompt_cpu_control.json` |
| IJ07-M8-GPU | Historical Radeon diagnostic performance/resource profiles | PASS | `reports/IJ07_GPU_PERFORMANCE.md` |
| IJ07-M7-F | Deterministic Arm F first-pass commercial target | FAIL | `reports/IJ07_PURPOSE_BUILT_VALIDATION.md` |

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
| IJ-0.5 | GPU execution proof, Arms A-F (G optional, NOT_RUN) | done | PASS | `reports/IJ0_GPU_BACKEND_QUALIFICATION.md`, `evidence/IJ0/gpu/` |
| TC | Qualify native tool calling on pinned b12359 | done for current candidate | FAIL | `reports/IJ0_TOOL_CALLING_BENCHMARK.md` |
| TC-BASELINE | Execute the original 500-case frozen suite on both backends | done | PASS | `evidence/IJ0/protocol/tool_calling_test_vulkan/`, `evidence/IJ0/protocol/tool_calling_test_rocm/` |
| TC-ACCEPT | Research and establish versioned tool-calling acceptance thresholds | done | PASS | `docs/decisions/ADR-002-IJ0-TOOL-CALLING-ACCEPTANCE.md` |
| TC-HOLDOUT | Freeze and qualify a fresh holdout under ADR-002 | not started | NOT_RUN | - |
| AG | Full Antigravity SDK integration checklist | checklist restored. P4b still has one structured-output failure and a blocked offline gate | FAIL | `reports/IJ06_ANTIGRAVITY_QUALIFICATION.md` |
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
| G3 | CPU reference path | PASS | `reports/IJ0_GPU_BACKEND_QUALIFICATION.md` |
| G4 | At least one Radeon GPU backend correctness-verified | PASS | `evidence/IJ0/gpu/comparison.json` |
| G5 | Native MiniCPM5 tool calling | FAIL | Strict fixtures 20/26 on each backend. `reports/IJ0_TOOL_CALLING_BENCHMARK.md` |
| G6 | 500-case tool-calling benchmark executed in full | PASS | Both original 500-case runs complete. `reports/IJ0_TOOL_CALLING_BENCHMARK.md` |
| G7 | Antigravity SDK real tool-call loop | PASS | Both local read-only smoke tests. `evidence/IJ0/antigravity/` |
| G8 | Streaming and non-streaming protocol | PASS | 50/50 tool-call parity and 30/30 thinking-separation cases on each backend. `reports/IJ0_TOOL_CALLING_BENCHMARK.md`, `evidence/IJ0/server_api_check.json` |
| G9 | Unauthorized tool and argument injection protection | NOT_RUN | - |
| G10 | Fully local operation | NOT_RUN | - |
| G11 | Performance and quantization comparison | NOT_RUN | - |
| G12 | Backend selection supported by evidence | NOT_RUN | - |
| G13 | Model Gateway contract | NOT_RUN | - |
| G14 | GitHub evidence complete and reproducible | NOT_RUN | - |

## IJ-0.6 mission

| ID | Task | Progress | Status | Evidence |
|---|---|---|---|---|
| IJ-0.6 audit | Verify local and remote baseline and restore SDK gates | done | PASS | `reports/IJ06_INITIAL_AUDIT.md`, `evidence/IJ06/baseline_manifest.json`, `docs/ANTIGRAVITY_SDK_ACCEPTANCE_SPEC.md` |
| IJ-0.6A | Six parser root causes and P4b native fixture conformance on CPU and both GPU backends | done | PASS | `reports/IJ06_PARSER_ROOT_CAUSE_REPORT.md`, `evidence/IJ06/parser/` |
| IJ-0.6B | Evaluator V2 DAG and transactional oracle mutations | done | PASS | `reports/IJ06_EVALUATOR_V2_REPORT.md`, `evidence/IJ06/evaluator_v2/` |
| IJ-0.6B rescore | Replay 1,000 archived diagnostic traces | done | PASS | `reports/IJ06_BASELINE_RESCORING.md`, `evidence/IJ06/rescoring/` |
| IJ-0.6C software | Strict protocol, policy, and SQLite transaction regression | done | PASS | `reports/IJ06_SECURE_GATEWAY_REPORT.md`, `evidence/IJ06/security/` |
| IJ-0.6D Vulkan | Real SDK, 11 exercised gates | offline blocked | BLOCKED | `evidence/IJ06/antigravity/vulkan.json` |
| IJ-0.6D ROCm | Real SDK, 9 pass and 2 fail | offline also blocked | FAIL | `evidence/IJ06/antigravity/rocm.json` |
| IJ-0.6D P4b Vulkan | Clean real SDK run, 10 pass and 1 fail | AG-11 blocked | FAIL | `evidence/IJ06/antigravity/p4b-vulkan.json` |
| IJ-0.6D P4b ROCm | Clean real SDK run, 11 pass | AG-11 blocked | BLOCKED | `evidence/IJ06/antigravity/p4b-rocm.json` |
| IJ-0.6E development | Document review draft and representative skill execution | done | PASS | `tests/sop/`, `evidence/IJ06/performance/summary.json` |
| IJ-0.6E reference | Qwen3-8B Q8_0 on the same three development cases | done | PASS | `evidence/IJ06/performance/reference-qwen3-vulkan/summary.json` |
| IJ-0.6F | Independent TC-V2 and JOB-V1 | pending freeze and full runs | NOT_RUN | `reports/IJ06_HOLDOUT_RESULTS.md` |
| IJ-0.6G development | Dual-backend structured document-review rehearsal and GPU counters | done | PASS | `reports/IJ06_PERFORMANCE_REPORT.md` |
| IJ-0.6G production | Full production workload comparison and default | pending | NOT_RUN | `reports/IJ06_ENGINE_SELECTION.md` |
| IJ-0.6H CI | Hosted software and upstream C++ checks | complete for P4b implementation commit | PASS | `evidence/IJ06/ci.json` |
| IJ-0.6 DX-M2 | Migration interface specifications | done | PASS | `portability/deepx-dxm2/` |

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
