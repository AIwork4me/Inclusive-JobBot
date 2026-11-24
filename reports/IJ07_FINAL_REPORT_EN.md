# IJ-0.7 stage report

Real Radeon execution completed all 2,000 historical replay tasks and
correlated 4,422 captured model requests to source generation. On both
Vulkan and ROCm/HIP, original b12359 and P4b had identical per-case V2
outcomes. Each arm achieved 420/500 complete diagnostic passes and
77/100 dependent multi-tool complete passes. The native parser conformance
and historical task observations provide distinct evidence.
 [Historical reproduction](IJ07_HISTORICAL_REPRODUCTION.md)

All four arms reproduced the same 15 original empty-ticket-tag cases at
the generation boundary. The candidate release b12675 passed 106/146
fixed fixtures and 0/16 selected historical failing tasks. An exact
before/after HTTP experiment confirmed that a local patch removes the
silent malformed `tool_choice` fallback. The common Radeon admission
track passed four small or effective-scale families on the revised
configuration, with two additional reference configurations. The official
Aion ONNX build passed ordinary text generation on CPU and Radeon WebGPU.
 [Causal report](IJ07_SOURCE_LEVEL_ROOT_CAUSE_MASTER_REPORT.md)
 · [Admissions](IJ07_MODEL_ADMISSION_MATRIX.md)

The independent TC-V2, MULTITOOL-V1, AGENTIC-PLAN-V1 and JOB-V1 rosters
have independent software-verified oracles. Four multi-tool diagnostics
and four planning trials failed on the real Vulkan backend. SDK AG-06
passed once in three repetitions for both Radeon backends. AG-11 remains
blocked. Production readiness requires full independent qualification,
actual state effects, six-arm job comparisons, and deployment results.
 [Gate matrix](IJ07_GATE_MATRIX.md) · [Interim white paper](IJ07_AGENTIC_CAPABILITY_WHITEPAPER_EN.md)

The independent Vulkan TC-V2 first pass achieved 349/500, below the 90%
threshold. Deterministic JOB-V1 Arm F achieved 592/600 semantic passes and
342 actual business completions. The remaining five JOB-V1 arms are pending.
 [Independent TC-V2](IJ07_TC_V2_QUALIFICATION.md) · [JOB-V1 Arm F](IJ07_PURPOSE_BUILT_VALIDATION.md)

The branch is stacked on the exact IJ-0.6 reviewed commit
`d2e5b31aa1f0894638f7b648a4cf3591fbb71e6e`.
 [Draft PR #4](https://github.com/AIwork4me/Inclusive-JobBot/pull/4)
 · [Tracking issue #3](https://github.com/AIwork4me/Inclusive-JobBot/issues/3)
