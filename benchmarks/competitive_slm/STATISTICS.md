# IJ-0.7 competitive comparison statistics

Use a separate frozen statistics plan for each suite. The analyzer reads the
canonical TC-V2, MULTITOOL-V1 and AGENTIC-PLAN-V1 artifact digests, exact case
identities, task strata and preselected repeat panels. The commands below
generate the roster and compute a canonical plan digest.

```powershell
python -m benchmarks.competitive_slm.statistics suite-profile TC-V2 > .runtime/tcv2-profile.json
python -m benchmarks.competitive_slm.statistics plan-digest .runtime/tcv2-statistics-plan.json
python -m benchmarks.competitive_slm.statistics analyze --plan .runtime/tcv2-statistics-plan.json --plan-sha256 PREDECLARED_SHA256 --evidence .runtime/tcv2-trials.json --output .runtime/tcv2-statistics.json
```

Before inference, extend the suite profile with the following plan fields and
retain its digest with the experimental configuration.

| Field | Contents |
| --- | --- |
| `schema_version` | Integer 1 |
| `first_seed` | Prespecified integer seed. The TC-V2 profile already pins it. |
| `bootstrap` | Integer `seed` and `samples`. Use 10,000 samples for formal reporting. |
| `arms` | Map arm names to `model`, `backend`, `device`, `track`, `quantization`, `thinking`, `protocol`, `controls_sha256` and `configuration_sha256`. |
| `comparisons` | List of objects with `id`, `left`, `right` and `vary`. Optional `business_minimum_gain_pp` specifies a practical target in percentage points. |

An arm's controls digest identifies the shared experimental contract, including
tools, worlds and permissions, evaluator, fault schedule, confirmation simulation,
turn and time budgets, and the context resource class. The arm configuration
digest identifies the complete arm-specific configuration, including executable,
libs, model source, artifact digest, native template, decoding and SDK identity.
Use `controlled` or `best_practice` as `track`, a Boolean for `thinking` and
the experiment's wire mode for `protocol`. Each prespecified comparison varies
exactly one of model, backend, quantization, thinking or protocol. In a model
comparison, arm-specific native templates and tool-call encodings can vary as
part of the model configuration.

The normalized evidence bundle has `schema_version` 1, `evidence_class`, a `runs`
map keyed by run ID and a `rows` array. Use `local_model` for admitted real
trials and `synthetic_software_test` for software verification fixtures.

- A run binds `arm`, the planned arm `configuration_sha256`, the original
  runner's `run_configuration_sha256`, `dataset_sha256` and the applicable
  `phases` array containing `first`, `repeat`, or both. Each arm has one run
  identity for each phase. Server restarts stay in the original run journal.
  An arm uses one planned configuration across phases. The original run
  configuration can also bind phase-specific details such as the run roster.
- A trial binds `arm`, `case_id`, `pairing_sha256`, `phase`, `repeat_index`,
  `attempt`, `seed`, `run_id`, both configuration digests, `evidence_sha256`,
  `status` and `failure_class`. The primary phase uses a null repeat index.
  Repeat indexes 1, 2 and 3 correspond to the three frozen seeds in order.
  Every trial uses attempt 1. Task failures require a failure class.
- Normalize from the admitted immutable run journals and keep those journals
  with the report. The analyzer validates the supplied identity links and
  reports the normalized bundle digest. The journals supply the physical
  provenance and first-attempt attestation.

Every rate uses its planned denominator. An absent row appears as `NOT_RUN`.
An interrupted or unassessable trial recorded as `BLOCKED` remains visible.
An incomplete comparison omits its effect estimate, CI and p-value. Its
status matrix shows which observations were available. The per-arm
`rate_bounds` give the range compatible with unresolved statuses.

The report gives case-level Wilson 95% intervals and exact two-sided
McNemar p-values for complete scopes. Bootstrap draws resample entire paired
cases inside the joint task-type, complexity and language strata, retaining
the original stratum weights. Scopes include the overall suite and each
marginal stratum. Singleton cells contribute no within-cell variation.
The Holm family includes every prespecified contrast and scope, including
withheld tests. Report the absolute gain and its interval alongside the
adjusted p-value and any prespecified business threshold.

The independent repeat report uses the first frozen repeat, any of three
passes, all three passes, the population variance of the three full-panel
seed rates, and adjacent-seed status and failure-class transitions. The
repeat roster remains distinct from the primary cohort. Task verdict
rates cover the suite's success criterion, which can include a correct
refusal or escalation. Business completions and measured efficiency
require their own metrics.
