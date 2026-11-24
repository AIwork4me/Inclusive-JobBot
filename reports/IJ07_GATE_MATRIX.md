# IJ-0.7 gate matrix

| Gate | Status | Evidence and remaining work |
|---|---|---|
| G0 | PASS | Independent baseline freeze, full archived recalculation and exact baseline CI. [Audit](IJ07_INITIAL_INDEPENDENT_AUDIT.md) |
| G1 | FAIL | Initial shared b12359 anomaly gate failed. Six models including the 8B reference passed the revised Vulkan probe. MiniCPM5 failed the revised native call. Aion passed ordinary reference inference. [Admission](IJ07_MODEL_ADMISSION_MATRIX.md) |
| G2 | BLOCKED | 2,000/2,000 historical model cases complete. The historical host supplies synthetic receipts, leaving independent SQLite effects and SDK phases pending. [Replay](IJ07_HISTORICAL_REPRODUCTION.md) |
| G3 | PASS | Source capture for 4,422/4,422 requests; same-build observer control verified. [Observer](../evidence/IJ07/historical_replay/observer_control/comparison.json) |
| G4 | PASS | Both TC-V2 backend experiments and independent verdicts are complete. The model failed both capability gates at 349/500 Vulkan and 347/500 ROCm/HIP. [TC-V2](IJ07_TC_V2_QUALIFICATION.md) |
| G5 | PASS | All 600 physical primary cases and the stratified analysis are complete. The original profile passed 129 cases and failed 471. The repeat panel belongs to G11. [Multi-tool](IJ07_MULTITOOL_CAPABILITY_REPORT.md) |
| G6 | NOT_RUN | L0's 200 physical trials are complete and fail both track thresholds. The remaining levels are still running. [Planning](IJ07_AUTONOMOUS_PLANNING_BENCHMARK.md) |
| G7 | BLOCKED | Historical verdict layers have case-linked investigations. TC-V2 failures are indexed to raw captures. Further source controls remain outstanding. [Historical ledger](../evidence/IJ07/root_causes/failure_ledger_full.jsonl) · [TC-V2 index](../evidence/IJ07/tc_v2/holdout/failure_index.jsonl) |
| G8 | BLOCKED | Tool-choice and batch-limit defects have controlled regressions. Additional failure families and the repaired batch profile's full business results remain open. [Root causes](IJ07_SOURCE_LEVEL_ROOT_CAUSE_MASTER_REPORT.md) |
| G9 | BLOCKED | The AG-06 test failed with 1/3 passing per backend. A full SDK qualification also requires trusted egress observation for AG-11. [SDK runs](../evidence/IJ07/antigravity/) |
| G10 | NOT_RUN | Four contenders ran one matched development case. Complete matched holdout inference remains pending. [Competitive diagnostics](IJ07_COMPETITIVE_SLM_BENCHMARK.md) |
| G11 | NOT_RUN | MiniCPM5 completed the TC-V2 repeats and F the JOB-V1 repeats. Full reliability scoring remains pending. |
| G12 | NOT_RUN | F measured 600/600 primary cases and 150 repeats from the frozen roster. Full six-arm measurement is pending. [Purpose-built](IJ07_PURPOSE_BUILT_VALIDATION.md) |
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
| IJ07_AUTONOMOUS_PLANNING_VERDICT | FAIL | Both tracks passed 0/100 complete L0 cases. The continuous level rule fails at the entry level. The full L0–L7 research remains in progress. |
| IJ07_COMPETITIVE_BENCHMARK_VERDICT | NOT_RUN | Shared comparative benchmarking and statistical ranking pending on exact matched rosters. |
| IJ07_RUNTIME_QUALIFICATION_VERDICT | FAIL | Repeated AG-06 failures plus outstanding AG-11. |
| IJ07_PURPOSE_BUILT_VALIDATION_VERDICT | NOT_RUN | Paired six-arm measurement pending. |
| IJ07_PRODUCTION_READINESS_VERDICT | BLOCKED | Independent model and runtime gates, real authorization requirements, and deployment evidence remain open. |
