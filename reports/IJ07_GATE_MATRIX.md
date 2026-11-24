# IJ-0.7 gate matrix

| Gate | Status | Evidence and remaining work |
|---|---|---|
| G0 | PASS | Independent baseline freeze, full archived recalculation and exact baseline CI. [Audit](IJ07_INITIAL_INDEPENDENT_AUDIT.md) |
| G1 | FAIL | Initial shared b12359 anomaly gate failed. Six models including the 8B reference passed the revised Vulkan probe. MiniCPM5 failed the revised native call. Aion passed ordinary reference inference. [Admission](IJ07_MODEL_ADMISSION_MATRIX.md) |
| G2 | BLOCKED | 2,000/2,000 historical model cases complete. The historical host supplies synthetic receipts, leaving independent SQLite effects and SDK phases pending. [Replay](IJ07_HISTORICAL_REPRODUCTION.md) |
| G3 | PASS | Source capture for 4,422/4,422 requests; same-build observer control verified. [Observer](../evidence/IJ07/historical_replay/observer_control/comparison.json) |
| G4 | FAIL | Independent first attempts passed 349/500 on Vulkan and 347/500 on ROCm/HIP. All 500 stream pairs and 150 repeat trials ran per backend. [TC-V2](IJ07_TC_V2_QUALIFICATION.md) |
| G5 | NOT_RUN | Full 600-case qualification is pending. Four live diagnostic cases fail. [Multi-tool](IJ07_MULTITOOL_CAPABILITY_REPORT.md) |
| G6 | NOT_RUN | Full L0–L7 execution is pending. Four diagnostic track trials fail. [Planning](IJ07_AUTONOMOUS_PLANNING_BENCHMARK.md) |
| G7 | BLOCKED | Historical verdict layers have case-linked investigations. TC-V2 failures are indexed to raw captures. Further source controls remain outstanding. [Historical ledger](../evidence/IJ07/root_causes/failure_ledger_full.jsonl) · [TC-V2 index](../evidence/IJ07/tc_v2/holdout/failure_index.jsonl) |
| G8 | BLOCKED | Tool-choice defect has source and CPU RED/GREEN evidence plus Vulkan anomaly retests. Additional confirmed or suspected failure families need controlled regressions. [Root causes](IJ07_SOURCE_LEVEL_ROOT_CAUSE_MASTER_REPORT.md) |
| G9 | FAIL | AG-06 passed 1/3 per backend. AG-11 remains blocked on trusted egress observation. [SDK runs](../evidence/IJ07/antigravity/) |
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
| IJ07_AUTONOMOUS_PLANNING_VERDICT | FAIL | Actual two-track diagnostic failed 4/4; complete grade assignment pending. |
| IJ07_COMPETITIVE_BENCHMARK_VERDICT | NOT_RUN | Shared comparative benchmarking and statistical ranking pending on exact matched rosters. |
| IJ07_RUNTIME_QUALIFICATION_VERDICT | FAIL | Repeated AG-06 failures plus outstanding AG-11. |
| IJ07_PURPOSE_BUILT_VALIDATION_VERDICT | NOT_RUN | Paired six-arm measurement pending. |
| IJ07_PRODUCTION_READINESS_VERDICT | BLOCKED | Independent model and runtime gates, real authorization requirements, and deployment evidence remain open. |
