# IJ-0.7 gate matrix

| Gate | Status | Evidence and remaining work |
|---|---|---|
| G0 | PASS | Independent baseline freeze, full archived recalculation and exact baseline CI. [Audit](IJ07_INITIAL_INDEPENDENT_AUDIT.md) |
| G1 | FAIL | Initial shared b12359 anomaly gate failed. Six models including the 8B reference passed the revised Vulkan probe. MiniCPM5 failed the revised native call. Aion passed ordinary reference inference. [Admission](IJ07_MODEL_ADMISSION_MATRIX.md) |
| G2 | BLOCKED | 2,000/2,000 historical model cases complete. The historical host supplies synthetic receipts, leaving independent SQLite effects and SDK phases pending. [Replay](IJ07_HISTORICAL_REPRODUCTION.md) |
| G3 | PASS | Source capture for 4,422/4,422 requests; same-build observer control verified. [Observer](../evidence/IJ07/historical_replay/observer_control/comparison.json) |
| G4 | FAIL | Vulkan completed 500/500 independent first attempts, with 349 passing. ROCm/HIP is in progress. [TC-V2](IJ07_TC_V2_QUALIFICATION.md) |
| G5 | NOT_RUN | Full 600-case qualification is pending. Four live diagnostic cases fail. [Multi-tool](IJ07_MULTITOOL_CAPABILITY_REPORT.md) |
| G6 | NOT_RUN | Full L0–L7 execution is pending. Four diagnostic track trials fail. [Planning](IJ07_AUTONOMOUS_PLANNING_BENCHMARK.md) |
| G7 | BLOCKED | Both historical verdict layers have case-linked investigations. New suite failures and further source controls remain outstanding. [Ledger](../evidence/IJ07/root_causes/failure_ledger_full.jsonl) |
| G8 | BLOCKED | Tool-choice defect has source and CPU RED/GREEN evidence plus Vulkan anomaly retests. Additional confirmed or suspected failure families need controlled regressions. [Root causes](IJ07_SOURCE_LEVEL_ROOT_CAUSE_MASTER_REPORT.md) |
| G9 | FAIL | AG-06 passed 1/3 per backend. AG-11 remains blocked on trusted egress observation. [SDK runs](../evidence/IJ07/antigravity/) |
| G10 | NOT_RUN | Competitive statistics are verified in software; complete matched inference remains pending. [Statistics](../benchmarks/competitive_slm/STATISTICS.md) |
| G11 | NOT_RUN | Preselected repeat panels are frozen; full reliability scoring remains pending. |
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
| IJ07_NATIVE_TOOL_CALLING_VERDICT | FAIL | Observed V2 historical failures and revised MiniCPM5 native admission failure; independent TC-V2 pending. |
| IJ07_AUTONOMOUS_PLANNING_VERDICT | FAIL | Actual two-track diagnostic failed 4/4; complete grade assignment pending. |
| IJ07_COMPETITIVE_BENCHMARK_VERDICT | NOT_RUN | Shared comparative benchmarking and statistical ranking pending on exact matched rosters. |
| IJ07_RUNTIME_QUALIFICATION_VERDICT | FAIL | Repeated AG-06 failures plus outstanding AG-11. |
| IJ07_PURPOSE_BUILT_VALIDATION_VERDICT | NOT_RUN | Paired six-arm measurement pending. |
| IJ07_PRODUCTION_READINESS_VERDICT | BLOCKED | Independent model and runtime gates, real authorization requirements, and deployment evidence remain open. |
