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
have independent software-verified oracles. MULTITOOL completed all 600
primary trials and passed 129. Task success went from 44/120 at 2–3 steps
to 9/120 at 16–20 steps. The complete archive identifies 25 rejected batches
at the wire's 16-call limit, with a 32-proposal task budget. All 25 affected
responses passed the bounded wire-control replay. Four planning
diagnostics failed on the real Vulkan backend. The full L0–L7 first-pass
roster then scored 0/800 on each track, with all 2,719 requests source-bound.
Both tracks scored 0/480 in the complete three-seed panel and 0/160 for
both Pass@3 and Pass^3. [Planning repeat archive](../evidence/IJ07/planning/repeat-vulkan-full/)
The original profile includes a confirmed Chinese reference handling defect. SDK AG-06
passed once in three repetitions for both Radeon backends. AG-11 remains
blocked. Production readiness requires full independent qualification,
actual state effects, six-arm job comparisons, and deployment results.
 [Gate matrix](IJ07_GATE_MATRIX.md) · [Interim white paper](IJ07_AGENTIC_CAPABILITY_WHITEPAPER_EN.md)
 · [Failure ledger](../evidence/IJ07/root_causes/failure_ledger.json)

Independent TC-V2 first attempts passed 349/500 on Vulkan and 347/500 on
ROCm/HIP, both below the 90% threshold. Each backend completed 500 paired
streamed runs, 150 repeat trials and 146 fixed fixtures. Deterministic
JOB-V1 Arm F achieved 592/600 semantic passes and
342 actual business completions. A–E ran 15 Radeon diagnostics on three
matched cases, with one pass on Arm E. Their full panels remain pending.
An isolated receipt-correction change passed 600/600 on a post-hoc replay of
the same frozen JOB-V1 cases. The original profile and independent commercial
qualification retain separate outcomes.
 [Independent TC-V2](IJ07_TC_V2_QUALIFICATION.md) · [JOB-V1 Arm F](IJ07_PURPOSE_BUILT_VALIDATION.md)

Four contenders retrieved and computed the correct value on the same read-only
development task. LFM3 passed. Markdown fences caused the other three to
miss the bare-object contract, and Qwen3.5 also included prose.
Aion's separate CPU and Radeon WebGPU dependency probe found a premature,
ungrounded account balance call on both runtimes.
 [Competitive diagnostics](IJ07_COMPETITIVE_SLM_BENCHMARK.md)
 · [Prespecified comparison](../configs/ij07/tc_v2_competitive_plan.lock.json)

The branch is stacked on the exact IJ-0.6 reviewed commit
`d2e5b31aa1f0894638f7b648a4cf3591fbb71e6e`.
 [Draft PR #4](https://github.com/AIwork4me/Inclusive-JobBot/pull/4)
 · [Tracking issue #3](https://github.com/AIwork4me/Inclusive-JobBot/issues/3)
