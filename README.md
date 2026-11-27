# Inclusive JobBot

Purpose-built Edge AI for Accessible Employment.

Inclusive JobBot turns a small local language model (OpenBMB MiniCPM5-2B) into a
job assistant that an employee with accessibility needs can understand, control
and audit. The model only proposes; deterministic business rules, schema
validation, permission checks and human confirmation decide.

- Inference: llama.cpp `llama-server` on Windows AMD Radeon (gfx1151), fully local.
- Agent orchestration: Google Antigravity Python SDK.
- Weights: MiniCPM5-2B from ModelScope, SHA256 verified.

Status: mission `IJ-0` (engine and native tool-calling qualification) in progress.
The IJ-0.7 archival audit reproduced the two historical 500-case runs' scores
from the saved records. Each backend had 84/100 semantically valid multi-tool
traces and 77/100 complete diagnostic passes. See the
[IJ-0.7 audit](reports/IJ07_INITIAL_INDEPENDENT_AUDIT.md).
The new four-arm history replay completed 2,000 real Radeon cases. P4b
preserved the full diagnostic verdict of every case on each backend.
Independent TC-V2 first attempts passed 349/500 on Vulkan and 347/500 on
ROCm/HIP, below the 90% gate. The deterministic JOB-V1 Arm F passed
592/600 cases, with 342 verified business completions in synthetic worlds.
MULTITOOL-V1 passed 129/600 on the original Vulkan profile. Both planning
tracks completed L0–L7 and passed 0/800 each under the original
run configuration. [Independent planning](reports/IJ07_AUTONOMOUS_PLANNING_BENCHMARK.md)
Independent tests, SDK results and production gates are tracked in the
[IJ-0.7 stage report](reports/IJ07_FINAL_REPORT_EN.md).
Production readiness is `BLOCKED`. The measured business workloads use
synthetic data. DEEPX DX-M2 physical validation is `NOT_RUN`.

IJ-0.7.2 Atlas status is **INCOMPLETE**. The benchmark validity and release gates
remain **BLOCKED**. The checkpoint includes both completed physical reference
panels (Qwen3-8B and Qwen3-14B), the four-model prompt experiment, historical
failure diagnostics and verified legacy JOB-V1 checkpoints.
[Progress dashboard](reports/ATLAS_PROGRESS_DASHBOARD.md) ·
[A1 checkpoint report](reports/ATLAS_IJ072_CHECKPOINT_CN.md) ·
[Prompt ablation results](reports/ATLAS_PROMPT_CAUSAL_ABLATION_FINAL.md) ·
[Prompt experiment checkpoint](evidence/IJ072/benchmark_validity/pc-p-factorial-progress.json) ·
[Reproduce the A1 evidence](docs/ATLAS_A1_REPRODUCIBILITY.md) ·
[Model passports](evidence/IJ07/model_passports/) ·
[Release gates](atlas/release_gates.json)

See [AGENTS.md](AGENTS.md) for the working rules, [HANDOFF.md](HANDOFF.md) for
the current state, and [reports/](reports/) for evidence-backed reports.

## License

Apache-2.0 for original code in this repository. Third-party components keep
their own licenses; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
