# LFM3-HA TC-V3 compatibility panel

## Registration

`LFM3-HA-TCV3-COMPAT/1.1` allocates 6,600 supplemental trajectories. It reads the byte-verified 500-case TC-V3 set and the frozen 50-case, three-seed repeats. The new Original baseline and all three LoRAs use identical per-track settings. None of the original 1,650 LFM3 seals contributes as a strictly paired Original observation in this panel.

| Weight | Direct first | SDK first | SDK streaming | SDK repeat | Total |
|---|---:|---:|---:|---:|---:|
| Original | 500 | 500 | 500 | 150 | 1,650 |
| OpenCode | 500 | 500 | 500 | 150 | 1,650 |
| Pi | 500 | 500 | 500 | 150 | 1,650 |
| Hermes | 500 | 500 | 500 | 150 | 1,650 |

SDK first and repeat use the `SDK_MATCHED_CONTEXT_PhaseAware` provider-JSON path with validated SSE delivery to the SDK. SDK streaming uses validated provider SSE. The new tracks have separate run identities and use the pinned no-cache admission flags. The historical four paths remain available as their own compatibility record.

## Physical coverage

**6,600 of 6,600 supplemental Radeon trajectories sealed and replayed across 200 launch batches.** All physical seals bind execution commit `daa7c9fd27f26a1023ccce19e3814513ed96563b`, the same provider budget and sampling contract, the frozen task and seed identities, and the GPU, model, engine and SDK pins. The 12-case transport pilot has separate evidence. Scoped completion totals are 3,906 PASS, 2,571 FAIL, 123 BLOCKED and zero NOT_RUN. The original 36,550-trial core receives zero attribution. Strict D25 remains BLOCKED. [Full Atlas replay](../evidence/IJSLM/lfm3-ha-1.1/tc-compatibility-panel.json) · [6,600 paired records](../evidence/IJSLM/lfm3-ha-1.1/tc-compatibility-matched-trials.jsonl.gz) · [Transport receipt](../evidence/IJSLM/lfm3-ha-1.1/tc-transport-admission.json)

| Weight | Direct first P / F / B | SDK first P / F / B | SDK streaming P / F / B | SDK repeat P / F / B |
|---|---:|---:|---:|---:|
| Original | 452 / 42 / 6 | 230 / 263 / 7 | 229 / 266 / 5 | 70 / 80 / 0 |
| OpenCode | 429 / 62 / 9 | 210 / 275 / 15 | 210 / 276 / 14 | 59 / 91 / 0 |
| Pi | 428 / 65 / 7 | 275 / 209 / 16 | 269 / 215 / 16 | 88 / 62 / 0 |
| Hermes | 420 / 76 / 4 | 234 / 253 / 13 | 234 / 255 / 11 | 69 / 81 / 0 |

P, F and B give PASS, FAIL and BLOCKED counts. The machine-readable replay carries 256 Atlas strata and 128 paired views across weight, execution track, family, language and risk. It retains first choice, required arguments, entity binding, action coverage and sequence, result delivery and comprehension, termination, factual and output correctness, business completion, authorization, clarification and recovery. The per-arm ledger retains individual fact verdicts, provider request bindings and the original cost denominators per verified fact, output, execution and business completion. [Atlas metric definitions](../benchmarks/slm10/tc_capability_metrics.py) · [Replay implementation](../benchmarks/slm10/ha11_panel_report.py)

## Matched weight contrasts

| Weight versus Original | Direct first | SDK first | SDK streaming | SDK repeat |
|---|---:|---:|---:|---:|
| OpenCode | −4.69 pp / 490 | −4.12 pp / 485 | −3.92 pp / 485 | −7.33 pp / 150 |
| Pi | −4.88 pp / 492 | +9.30 pp / 484 | +8.26 pp / 484 | +12.00 pp / 150 |
| Hermes | −7.54 pp / 491 | +0.82 pp / 487 | +1.03 pp / 488 | −0.67 pp / 150 |

Each cell is the scoped PASS difference and number of adjudicated pairs. For Pi, SDK first had 50 gains and five losses. Direct had eight gains and 32 losses. These contrasts show negative transfer to JobBot Direct for all three LoRAs and positive scoped transfer for Pi in the corrected SDK paths. OpenCode's exact termination improved by 3.31 points in SDK first while scoped completion fell by 4.12 points. It also emitted more provider output-limit failures than Original on both SDK first-attempt paths. Hermes had small first-attempt SDK gains and the largest Direct decline. The pair counts describe the frozen TC-V3 fixtures and their repeat seeds. Independent business transfer remains unmeasured.

Pi passed exact SDK-first termination on 313 of 500 trials, compared with 252 for Original. The paired difference was +12.60 points across 484 adjudicated pairs. Exact proposed tool arguments passed on 331 for Pi and 279 for Original. The typed binder accepted all 8,489 decoded SDK callback proposals with zero conversion events in this roster. The binder opportunity verdict was BLOCKED on 103 SDK trajectories with incomplete provider evidence. The Extension covers integer conversion separately. The replay classified 129 trajectories as reaching the 768-token output limit with the native stop reason and usage recorded. It separately classified 39 model-request limit outcomes. [Typed Extension](SDK_TYPED_CALLBACK_BINDER_QUALIFICATION.md)

## Streaming, repeats and safety

| Weight | Streaming verdict agreement PASS / FAIL / BLOCKED | All-three-seed scoped completion PASS / FAIL |
|---|---:|---:|
| Original | 458 / 34 / 8 | 21 / 19 |
| OpenCode | 435 / 44 / 21 | 17 / 23 |
| Pi | 441 / 43 / 16 | 22 / 18 |
| Hermes | 448 / 38 / 14 | 21 / 19 |

Streaming agreement covers 500 JSON/SSE pairs per weight and includes matching failures. The reliability metric applies to 40 of the 50 repeated tasks and requires all three seeds to pass. The other ten are outside that read-only scope. Among 600 first-attempt authorization slots, 569 passed the synthetic authorization component and 31 were BLOCKED. All 60 repeated authorization slots passed. The synthetic authorization component recorded zero FAIL. External writes and role-level authorization remain outside this evaluation.

| Clarification path, all four weights | Exact no-tool | Extra tool proposal | Same-shaped noncanonical answer |
|---|---:|---:|---:|
| Direct first | 197 | 3 | 0 |
| SDK first | 16 | 89 | 95 |
| SDK streaming | 19 | 92 | 89 |
| SDK repeat | 2 | 50 | 8 |

The diagnostic groups distinguish actual tool proposals from a terminal answer with the expected JSON keys and types but a different value. The latter includes questions in natural language where the fixture expected a literal. Semantic adequacy for those responses requires its own witness contract.

## Resources and efficiency

| SDK first weight | Requests per scoped success | Executed tools per scoped success | Tokens per scoped success | Wall time per scoped success | Attempt p95 wall time |
|---|---:|---:|---:|---:|---:|
| Original | 5.85 | 4.15 | 6,528 | 9.80 s | 5.48 s |
| OpenCode | 6.18 | 4.23 | 6,901 | 11.74 s | 6.12 s |
| Pi | 4.65 | 3.09 | 5,165 | 8.70 s | 5.71 s |
| Hermes | 5.68 | 4.00 | 6,337 | 10.34 s | 5.67 s |

Per-success cost charges all 500 SDK-first attempts against the scoped successes. In decoded, complete SDK-first evidence, Pi made 110 excess proposals among 819 proposals compared with 197 among 940 for Original. The same counts applied to repeated executions in those observed subsets. Sixteen Pi and seven Original trials were unavailable for the repeat-event rate. The SDK-first Pi p95 shows its latency trade-off despite lower amortized cost. In Direct, Pi raised wall time per success to 1.54 seconds from 1.18 and lost scoped passes. Median peak process GPU commitment for each LoRA was about 86 MiB above Original across 50 launch batches per weight. The replay retains route-level timing and attempt and success percentiles. Native TTFT, energy and monetary cost are NOT_RUN.
