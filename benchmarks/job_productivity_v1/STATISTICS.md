# JOB-V1 paired analysis

Freeze the case roster and repetition schedule before observing candidate results. Every planned case has `case_id`, `category` and `pairing_sha256`. The pairing digest should bind the common task input, seeded business state, shared knowledge and permissions, and comparable budget. Each arm records its distinct treatment and runtime identity in the experiment manifest. Equality of pairing digests verifies row alignment. Freeze and independently validate the manifest inputs to establish experimental equivalence.

```powershell
python -m benchmarks.job_productivity_v1.statistics select-repeats --input planned-cases.json --seed 23001 --trial-seeds 17 31 83 --output repeat-selection.json
python -m benchmarks.job_productivity_v1.statistics analyze --input measured-arms.json --plan planned-cases.json --seed 23001 --output paired-analysis.json
python -m benchmarks.job_productivity_v1.statistics summarize-repeats --selection repeat-selection.json --input repeated-arms.json --output repeat-analysis.json
```

The first input is a JSON array of planned case rows. The measured and repeated inputs are JSON objects with six arrays keyed by A through F. Each measured row has its three identity fields and the following observations.

| Fields | Meaning |
|---|---|
| `status` | Independent semantic verdict of PASS or FAIL. The analysis requires exact roster coverage and refuses an incomplete experiment. |
| `routine`, `first_pass_success`, `completed` | Booleans for the preassigned routine cohort, correctness before an error-driven retry and actual successful business completion. |
| `machine_ms` | Finite observed machine duration excluding human wait. |
| `model_calls`, `prompt_tokens`, `completion_tokens` | Observed costs including retries and failed tasks. |
| `argument_correct`, `argument_total` | Correct and required arguments from the independent scorer. |
| `invalid_calls`, `tool_calls` | Invalid proposals and all tool proposals, with retries included. |
| `correct_escalations` | Zero or one. An independently correct escalation counts for semantic task success and is tracked separately from actual business completion. |
| `unauthorized_effects`, `unconfirmed_commits`, `duplicate_commits`, `false_approvals` | Explicit observed safety counters. |
| `business_writes`, `correct_business_writes` | Optional paired counters for actual and verified-correct persisted writes. An arm lacking a measurement on any row reports no write rate. |
| `trial_seed` | Required on repeat rows. Each selected case must carry each of the three exact seeds in the frozen selection document. |

The analysis reports exact case counts, Wilson 95% intervals for case-level proportions, and a one-sided exact 95% binomial upper bound for case-level safety events after zero observations. Argument counts are aggregated across cases and avoid a confidence interval that assumes independent argument fields. Routine latency uses observed machine durations for the complete routine cohort.

The five contrasts use identical paired cases. McNemar's two-sided exact test uses discordant pairs. The percentile bootstrap resamples paired case outcomes within each category while preserving category sizes. The report includes old-only and new-only counts, per-case differences, percentage-point gain, relative improvement and the bootstrap seed and sample count. Ratios of total calls or tokens per successful task divide the full measured arm cost by independently confirmed actual business completions, including the work spent on failed trials in the numerator. An undefined rate or ratio is reported as JSON null.

Repeat selection allocates proportionally by category and ranks within a category by a seed-derived digest. Freeze the selection, its source roster digest and trial seeds before the runs. The repeat report requires all three trials on each selected case for each arm and reports the proportion succeeding in all three, with exact counts and a Wilson interval.

Tests under `tests/job_productivity/` use synthetic rows to verify the analysis mechanics. Actual JOB-V1 experimental results require the measured trial evidence.
