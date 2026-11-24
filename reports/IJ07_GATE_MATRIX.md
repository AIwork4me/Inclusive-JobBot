# IJ-0.7 gate matrix

| Gate | Status | Evidence and remaining work |
|---|---|---|
| G0 | PASS | Independent baseline freeze, full archived recalculation and exact baseline CI. [Audit](IJ07_INITIAL_INDEPENDENT_AUDIT.md) |
| G1 | FAIL | Initial shared b12359 anomaly gate failed. Six models including the 8B reference passed the revised Vulkan probe. MiniCPM5 failed the revised native call. Aion passed ordinary reference inference. [Admission](IJ07_MODEL_ADMISSION_MATRIX.md) |
| G2 | BLOCKED | 2,000/2,000 historical model cases complete. The historical host supplies synthetic receipts, leaving independent SQLite effects and SDK phases pending. [Replay](IJ07_HISTORICAL_REPRODUCTION.md) |
| G3 | PASS | Source capture for 4,422/4,422 requests; same-build observer control verified. [Observer](../evidence/IJ07/historical_replay/observer_control/comparison.json) |
| G4 | PASS | Both TC-V2 backend experiments and independent verdicts are complete. The model failed both capability gates at 349/500 Vulkan and 347/500 ROCm/HIP. [TC-V2](IJ07_TC_V2_QUALIFICATION.md) |
| G5 | PASS | All 600 physical primary cases and the stratified analysis are complete. The original profile passed 129 cases and failed 471. The repeat panel belongs to G11. [Multi-tool](IJ07_MULTITOOL_CAPABILITY_REPORT.md) |
| G6 | PASS | The original L0–L7 roster assessed all 1,600 physical trials. Both tracks failed every level and remain unqualified. [Planning](IJ07_AUTONOMOUS_PLANNING_BENCHMARK.md) |
| G7 | BLOCKED | Historical, TC-V2, MULTITOOL and planning primary failures have case-linked records. Further single-case controls and comparisons remain outstanding. [Failure taxonomy](IJ07_FAILURE_TAXONOMY.md) · [Machine-readable ledger](../evidence/IJ07/root_causes/failure_ledger.json) |
| G8 | BLOCKED | Tool-choice and batch-limit defects have controlled regressions. Additional failure families and the repaired batch profile's full business results remain open. [Root causes](IJ07_SOURCE_LEVEL_ROOT_CAUSE_MASTER_REPORT.md) |
| G9 | BLOCKED | The AG-06 test failed with 1/3 passing per backend. A full SDK qualification also requires trusted egress observation for AG-11. [SDK runs](../evidence/IJ07/antigravity/) |
| G10 | NOT_RUN | B has a verified 200/1,150 checkpoint. Complete matched holdout inference remains pending. [Competitive diagnostics](IJ07_COMPETITIVE_SLM_BENCHMARK.md) |
| G11 | NOT_RUN | MiniCPM5 completed TC-V2, MULTITOOL and both original planning repeat tracks. F completed JOB-V1 repeats. Complete competitive and job-model reliability remain pending. [Planning repeats](../evidence/IJ07/planning/repeat-vulkan-full/diagnostic.json) |
| G12 | NOT_RUN | F measured 600/600 primary cases and 150 repeats. A–E completed 15 matched diagnostics. Full six-arm measurement is pending. [Purpose-built](IJ07_PURPOSE_BUILT_VALIDATION.md) |
| G13 | BLOCKED | Four Radeon historical resource profiles recorded. Controlled quantization, concurrency, real end-to-end timing, energy and soak remain open. [Performance](IJ07_GPU_PERFORMANCE.md) |
| G14 | BLOCKED | Exact evidence hashes, coverage checks, and statistical software verified. Independent live evaluator and comparison scope remains incomplete. |
| G15 | PASS | Software safety regression and staged privacy scan passed within the published artifact scope. |
| G16 | BLOCKED | Bilingual stage reports provide the measured scope and unresolved research items. Full capability white paper requires independent full runs. |
| G17 | NOT_RUN | Latest exact-head CI is checked after the stage commit, with status recorded on the draft PR and tracking issue. |

## Qualified verdicts

| Verdict | Status | Basis |
|---|---|---|
| IJ07_RESEARCH_COMPLETION_VERDICT | BLOCKED | Historical goal complete within the diagnostic protocol; independent baselines remain unfinished. |
| IJ07_NATIVE_TOOL_CALLING_VERDICT | FAIL | Both independent TC-V2 profiles fell short of the 90% mark. [TC-V2](IJ07_TC_V2_QUALIFICATION.md) |
| IJ07_AUTONOMOUS_PLANNING_VERDICT | FAIL | Original Vulkan tracks passed 0/800 each. The continuous level rule fails at L0. The repaired reference profile has a separate identity. |
| IJ07_COMPETITIVE_BENCHMARK_VERDICT | NOT_RUN | Shared comparative benchmarking and statistical ranking pending on exact matched rosters. |
| IJ07_RUNTIME_QUALIFICATION_VERDICT | FAIL | Repeated AG-06 failures plus outstanding AG-11. |
| IJ07_PURPOSE_BUILT_VALIDATION_VERDICT | NOT_RUN | Paired six-arm measurement pending. |
| IJ07_PRODUCTION_READINESS_VERDICT | BLOCKED | Independent model and runtime gates, real authorization requirements, and deployment evidence remain open. |
