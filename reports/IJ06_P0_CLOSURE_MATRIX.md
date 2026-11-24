# IJ-0.6 closure matrix

| Gate | Result | Evidence and limit |
|---|---|---|
| G-A | PASS | Six original parser observations isolated with direct C++ and original Windows GPU traces. [Root causes](IJ06_PARSER_ROOT_CAUSE_REPORT.md) |
| G-B | PASS | P4b passed 119/119 applicable native cases and 146/146 strict argument and parity checks on each GPU. Raw decoder results include five expected duplicate-key rejections. [Parser suite](IJ06_PARSER_ROOT_CAUSE_REPORT.md) |
| G-C | PASS | V2 DAG, all-step values, references, mutation and persisted-oracle regression. [Evaluator V2](IJ06_EVALUATOR_V2_REPORT.md) |
| G-D | PASS | V2 replayed all 1,000 original traces and marked unavailable persistent state. [Rescore](IJ06_BASELINE_RESCORING.md) |
| G-E | PASS | Transactional SQLite operated in software regressions and real development rehearsal. [Gateway](IJ06_SECURE_GATEWAY_REPORT.md) |
| G-F | PASS | 209/209 defensive software regression tests. Known archived malformed inputs stopped before execution. Scope is simulator and Gateway contracts. [Gateway](IJ06_SECURE_GATEWAY_REPORT.md) |
| G-G | FAIL | P4b Vulkan failed AG-06. P4b ROCm passed 11 gates. AG-11 remains blocked on both. [SDK](IJ06_ANTIGRAVITY_QUALIFICATION.md) |
| G-H | PASS | Reusable versioned SOP. Document review draft workflow ran with live SDK and synthetic transactions. Representative product and support paths have software evidence. [Rehearsal](IJ06_PURPOSE_BUILT_CAUSAL_ANALYSIS.md) |
| G-I | NOT_RUN | Independent 500-case tool-calling holdout. [Coverage](IJ06_HOLDOUT_RESULTS.md) |
| G-J | NOT_RUN | Independent 600-case, six-arm JOB-V1 causal trial. D/E/F ran three development cases. [Rehearsal](IJ06_PURPOSE_BUILT_CAUSAL_ANALYSIS.md) |
| G-K | NOT_RUN | Tier 1 and Tier 2 require their independent evidence. Original ECO-01 thresholds remain unchanged. [Coverage](IJ06_HOLDOUT_RESULTS.md) |
| G-L | NOT_RUN | Both GPUs passed P4b fixed parser replay and produced development evidence. Production workload and quantization arms are pending. [Development performance](IJ06_PERFORMANCE_REPORT.md) |
| G-M | NOT_RUN | Production backend selection awaits full workload qualification. [Engine selection](IJ06_ENGINE_SELECTION.md) |
| G-N | PASS | Windows/Linux software, protocol, security, evidence and pinned upstream C++ jobs passed for the implementation commit. [CI evidence](../evidence/IJ06/ci.json) |
| G-O | PASS | Eight hardware-independent DX-M2 contract documents delivered. Physical validation remains NOT_RUN. [Portability package](../portability/deepx-dxm2/) |

The six observations, evidence, discriminating controls and fixes are in the parser report. The immutable whitespace fixture still expects a trimmed identifier. Its added CDATA control preserves the original parameter characters. The enum fixture is a schema decision. The scoped parser changes repair terminal integrity and duplicate markup handling while retaining raw nested duplicate-key evidence for strict decoding. [Case-level root causes](IJ06_PARSER_ROOT_CAUSE_REPORT.md)

`IJ06_NATIVE_PARSER_GO` applies to the tested P4b conformance configuration. `IJ06_EVALUATOR_V2_GO` applies to evaluator implementation, mutation and historical replay. Formal Secure Execution, Antigravity, Model Admission, purpose-built, dual-backend production, engine-selection and IJ-1 product development verdicts remain ungranted.
