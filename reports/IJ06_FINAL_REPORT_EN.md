# IJ-0.6 technical report

## A. Executive verdict

P4b closes the measured native parser defects and passes fixed conformance on both Windows GPU backends. Evaluator V2 and the SQLite Gateway pass their software regressions. The SDK full-suite result is FAIL and the independent TC-V2 and JOB-V1 results are NOT_RUN. Retain the scope of `IJ06_NATIVE_PARSER_GO` and `IJ06_EVALUATOR_V2_GO`. Production and IJ-1.0 admission remain pending. [Gate matrix](IJ06_P0_CLOSURE_MATRIX.md)

## B. Git state

The immutable baseline is `0592c319ab341f70bda979874697386e33ccc680`. The P4b clean replay implementation is `fa50525ebf99fff98149746c05fadc472c8462ec`. The mission landed on `mission/ij-0.6-root-cause-and-purpose-built-execution` for independent review against `codex/ij0-tool-calling`. [Draft PR #2](https://github.com/AIwork4me/Inclusive-JobBot/pull/2) · [Issue #1](https://github.com/AIwork4me/Inclusive-JobBot/issues/1)

## C. Hardware and frozen runtime

Native Windows on Ryzen AI MAX+ PRO 395 and Radeon 8060S gfx1151. The original inference engine is b12359 at `b1b770d90d94cad9e9ea5b993bdbc383a522fb28`. The MiniCPM5-2B Q8_0 SHA256 is `c5415f8989bf88a8288f1b55a3cc371af53c07b0faa220a63bd7a990cfaba078`. The observed ModelScope GGUF and BF16 heads matched the frozen revisions, and all 17 baseline files verified. The real SDK is 0.1.24. Candidate patches, binaries, DLLs, template and process identities are attached to their run records. [Initial audit](IJ06_INITIAL_AUDIT.md) · [P4b build](../evidence/IJ06/parser/p4b-windows-dynamic-build.json)

## D. Six native parser root causes

Whitespace follows preserved string content. The original test expected a trim. The enum value is a schema violation. Duplicate XML names and the three incomplete forms were isolated in native terminal parsing. P4b checks completion and XML name uniqueness and validates nested JSON syntax before the mapper. Strict decoding rejects preserved nested duplicate keys. A private XML parser was unnecessary for these fixes. [Root causes and tests](IJ06_PARSER_ROOT_CAUSE_REPORT.md)

## E. Evaluator V2 and historical rescoring

V2 replayed 500 traces on each backend. For each original sequential 58/100 score, 41 of 42 failures were order or grouping rubric false failures and one final answer named the wrong order. V1 also passed 15 later calls with empty ticket tags. The raw model-versus-parser origin of those tags remains unresolved. Each backend had 794/821 required argument fields correct, or 96.71%. The sequential trace check passed 84/100, with overall diagnostic verdicts of 77 PASS, 16 FAIL, 7 BLOCKED per backend. [Historical analysis](IJ06_BASELINE_RESCORING.md)

## F. Secure stateful execution

The Gateway and SQLite regressions passed 209/209. Strict parsing and policy blocked 12/12 archived failure replays before a handler. Draft persistence and final confirmation use distinct capabilities and guarded transactions. Live tool and draft evidence uses synthetic storage. Production connectors, real operator confirmation and the full attack-surface qualification remain open. [Gateway](IJ06_SECURE_GATEWAY_REPORT.md)

## G. Antigravity SDK

The clean P4b runs show Vulkan 10 PASS, one FAIL on structured field content, and one BLOCKED. ROCm shows 11 PASS and one BLOCKED. AG-11 requires complete process egress observation or isolation. Original b12359 results and read-only smoke remain separately available. [SDK matrix and transcripts](IJ06_ANTIGRAVITY_QUALIFICATION.md)

## H. Independent 500-case tool-calling holdout

TC-V2 remains NOT_RUN on each backend. Tier 1 and the original ECO-01 high reliability gates remain unevaluated against an independent holdout. [Holdout status](IJ06_HOLDOUT_RESULTS.md)

## I. Purpose-built six-arm trial

The versioned SOP and scoped tool prototype ran on real model intent and synthetic delivery-note data. D/E/F completed all three development draft tasks per reported arm. A–C and the 600-case paired trial remain NOT_RUN. The outcome justifies running the full study. It supplies no measured causal uplift or evidence for 99% first-pass accuracy or a tenfold call reduction. [Development executive scorecard](IJ06_PURPOSE_BUILT_CAUSAL_ANALYSIS.md)

## J. MiniCPM5-2B versus Qwen3-8B

On three structured Vulkan cases, each model required six calls in total and produced three correct drafts. The deterministic SOP had the same observed outcome and zero model calls. Full-model equivalence and added value for ambiguous inputs remain unmeasured. [Paired rehearsal](IJ06_PURPOSE_BUILT_CAUSAL_ANALYSIS.md)

## K. Vulkan versus ROCm/HIP

Both backends have real process-counter and offload evidence. P4b parser conformance matches. The D pilot maximum was 41.81 seconds on Vulkan and 37.26 on ROCm/HIP across three cases each. Overall selection, same-workload CPU comparison, full context/concurrency and quantization trials, and actual energy remain NOT_RUN. [Performance](IJ06_PERFORMANCE_REPORT.md) · [Selection status](IJ06_ENGINE_SELECTION.md)

## L. GitHub and reproduction

The PR contains five software and upstream parser checks and a manifest validator with negative tests. Model runs use the native workstation. Hosted tests report their software scope. Replay commands and raw artifact digests are linked below. [CI and gate status](IJ06_P0_CLOSURE_MATRIX.md) · [Artifact manifest](IJ06_ARTIFACT_MANIFEST.json)

## M. DX-M2 migration readiness

The admission and execution contracts, rubric, trace schema and paired statistics transfer independently of the hardware. NPU and power evidence require physical DX-M2. `DXM2_PHYSICAL_VALIDATION_NOT_RUN`. [Portability contracts](../portability/deepx-dxm2/)

## N. Remaining work

Resolve structured-output variability and process egress. Freeze the independent roster and the complete causal configurations, execute the tiered studies, then measure the production load matrix. No full production holdout runner was delivered in this increment. `CUSTOMER_POC_PENDING_USER_AND_SITE_VALIDATION` and `PTMF_PENDING_CUSTOMER_AND_USER_VALIDATION` remain in force. [Open risks](IJ06_OPEN_RISKS.md)
