# IJ-0.6 independent holdout results

| Run | Status | Runs counted |
|---|---|---:|
| TC-V2 500 independent cases, Vulkan Q8_0 | NOT_RUN | 0/500 |
| TC-V2 500 independent cases, ROCm/HIP Q8_0 | NOT_RUN | 0/500 |
| JOB-V1 600 independent cases, arms A–F | NOT_RUN | 0/600 per arm |
| Prespecified three-run reliability panel | NOT_RUN | 0 |

The patched parser candidate needs independently verified GPU wire behavior before a dual-backend candidate freeze. The development rehearsal and V1 replay use separate evidence labels. They supply zero independent holdout cases. The candidate data freeze and full causal run are pending.

The paired statistics implementation checks six complete arms, common case identities, a frozen repeat panel, exact McNemar and stratified paired bootstrap intervals. Its tests use synthetic data. [Statistics specification](../benchmarks/job_productivity_v1/STATISTICS.md)
