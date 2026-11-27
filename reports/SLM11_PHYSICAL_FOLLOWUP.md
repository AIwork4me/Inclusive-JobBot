# IJ-SLM-1.1 Radeon follow-up

The scheduled LFM3 holdout, P0-E preflight and SDK Extension captured all 81
development trajectories. The ten run reports bind 260 native completions to
their provider requests and carry process-linked Vulkan telemetry. All ten use
the frozen execution commit `821a8ae34a113c4fe6d3f4972430e7b5eba5a3e8`
and Antigravity SDK 0.1.24. Core attribution is zero.
[Evidence manifest](../evidence/IJSLM/physical-followup/manifest.json) ·
[Per-run and per-trial summary](../evidence/IJSLM/physical-followup/summary.json)

| Experiment | Radeon captures | Scoped result |
| --- | ---: | --- |
| LFM3 compact-result holdout | 24 of 24 | 12 paired cases, exploratory result indeterminate |
| P0-E development preflight | 42 of 42 | 8 PASS, 34 BLOCKED |
| SDK Extension 0.2 | 15 of 15 | 10 FAIL, 5 BLOCKED |

## LFM3 compact-result holdout

Compact delivery was observed in all 12 treatment trajectories. Reference and
treatment each completed 6 of 12 scoped tasks. One case improved and one
regressed. The one-sided exact paired sign test gave (p=0.75), and the 95%
interval for the paired scoped completion difference was −42.6 to +42.6
percentage points. Output contract regressed in three pairs, process in one,
and termination in one. Business facts were unresolved in three pairs and
output contract in three. The three incomplete terminations ended at a
tool-call turn without a captured terminal stop.

The mean treatment-minus-reference difference was −344 input tokens
(95% interval −805 to +122) and −163 ms end-to-end (95% interval −560 to
+239). All 12 pairs contribute to both estimates. The result leaves
the adapter's exploratory acceptance criterion indeterminate.
[Paired intervals and dispositions](../evidence/IJSLM/physical-followup/lfm3-paired-analysis.json)

## P0-E preflight

| Candidate | Direct PASS | Direct BLOCKED | SDK PASS | SDK BLOCKED |
| --- | ---: | ---: | ---: | ---: |
| MiniCPM5-2B (A) | 5 | 2 | 0 | 7 |
| LFM3-1.7B (B) | 1 | 6 | 0 | 7 |
| Qwen3.5-2B (D) | 2 | 5 | 0 | 7 |

All 21 SDK action requests carried `tool_choice: "none"` alongside the tool
definitions. Each reached an HTTP 200 provider stop with zero tool proposals
or callbacks and recorded `GatewayError: invalid JSON syntax`. All 21 first
Direct action requests carried `tool_choice: "auto"` and proposed tools. Five
Direct attempts reached the same terminal JSON error after live callbacks.
Five other Direct attempts exceeded the current phase or tool-call budget.
Three attempted a synthetic commit without the current trusted grant and
were rejected.

The 12 applicable SQLite readback receipts match the captured final snapshots.
The confirmed Direct runs for A and B each persisted one authorized synthetic
release before their extra proposals hit the budget check. Every declined arm
had zero releases. The B Direct decline persisted an explicit denial and then
rejected the attempted commit. All 12 draft task assessments are BLOCKED under
the recorded end-to-end criteria.
[A captures](../evidence/IJSLM/physical-followup/p0e/A/report.json) ·
[B captures](../evidence/IJSLM/physical-followup/p0e/B/report.json) ·
[D captures](../evidence/IJSLM/physical-followup/p0e/D/report.json)

## SDK Extension 0.2

| Candidate | Development FAIL | Holdout FAIL | Holdout BLOCKED |
| --- | ---: | ---: | ---: |
| MiniCPM5-2B (A) | 1 | 3 | 1 |
| LFM3-1.7B (B) | 1 | 2 | 2 |
| Qwen3.5-2B (D) | 1 | 2 | 2 |

The ten failures include seven terminal answer mismatches, two out-of-scope
or invalid tool-call failures, and one action multiplicity failure. The
BLOCKED A and B layout cases each proposed one tool and ended with a provider
stop but recorded zero callbacks. The B rescan, D rescan and D layout cases
ended on tool-call responses without a terminal provider stop after 16,
13 and 16 requests, respectively. In all five BLOCKED cases, the SDK's first
tool result recorded `SDK callback does not match one validated wire proposal`.

The publication verified each original Extension trial digest and reran the
frozen scorer against the exact private trial before checking its redacted
copy. Offline review verifies the portable digest, scoped trial identity,
provider responses, finish reason, callback count and native archive linkage.
The exact scorer additionally requires original request bytes and prompt
token IDs. Portable exact scorer replay is BLOCKED because those fields are
redacted or omitted.
[Extension captures](../evidence/IJSLM/physical-followup/sdk-extension)

## Reproduction

From the repository root, set `PYTHONPATH` to the repository root, `src`, and
`benchmarks/tool_calling/runner`, using the platform's path separator. Use the
repository Python environment.

```sh
python -m benchmarks.slm10.physical_followup
```

The optional `--publish-from RUNTIME_ROOT` argument checks the existing
private reports, counter bytes, original native trace digest, redaction and
Extension scorer before publishing. `RUNTIME_ROOT` is
`.runtime/ij-slm-1.0` under the common workstation assets. Both commands work
offline with the GPU lease in use. This publication consumed no Radeon time.

The next eligible work is a scripted P0-E SDK action-phase control with an
explicit tool-choice comparison and an Extension replay that captures typed
callback arguments at the proposal-matching boundary.
Any follow-up physical comparison needs a dedicated Radeon lease after the
owner's AG-11 window and a separately versioned cohort.
