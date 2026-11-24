# IJ-0.7 executive summary

- **2,000 new Radeon cases completed.** P4b and original b12359 agree on
  every complete V2 diagnostic verdict within each backend. The four arms
  each passed 420/500 overall and 77/100 dependent multi-tool cases.
  [Four-arm evidence](IJ07_HISTORICAL_REPRODUCTION.md)
- **The empty-tag defect reproduces before parsing.** Each new arm directly
  generates the same 15 empty arrays. The CPU control with a two-item schema
  minimum passed 15/15 semantic checks. F16 with the original schema passed
  1/15. [Failure analysis](IJ07_MULTITOOL_FAILURE_ROOT_CAUSE.md)
- **Independent TC-V2 fell short on both backends.** First attempts passed
  349/500 on Vulkan and 347/500 on ROCm/HIP against a 90% gate.
  [Independent tool qualification](IJ07_TC_V2_QUALIFICATION.md)
- **The multi-tool primary run passed 129/600 physical trials.** In the
  first published checkpoint, 14 correct batches exceeded the decoder's 16-call default.
  A scoped profile accepted all 14 preserved responses. Model-task scores
  remain tied to the original run. [Multi-tool results](IJ07_MULTITOOL_CAPABILITY_REPORT.md)
- **Four small or effective-scale model families passed a revised runtime
  admission probe.** Complete matched benchmarks and model rankings remain
  pending. MiniCPM5 failed its tool check in the revised configuration.
  [Admission matrix](IJ07_MODEL_ADMISSION_MATRIX.md)
- **Deterministic JOB-V1 Arm F passed 592/600 first attempts.** It completed
  342 synthetic business tasks and fell short of the 99% acceptance target.
  The remaining five arms are pending. [Purpose-built validation](IJ07_PURPOSE_BUILT_VALIDATION.md)
- **Runtime and production qualification remain open.** AG-06 passed once
  in three trials per backend. AG-11 is blocked, and the architecture still
  depends on independent validation, scoped authorization and confirmation.
  [Gate matrix](IJ07_GATE_MATRIX.md) · [Architecture](IJ07_JOBBOT_ARCHITECTURE_RECOMMENDATION.md)
