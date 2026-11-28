# LFM3-HA 720-trajectory transfer panel

The registered development comparison crosses four weight configurations with three execution paths and 60 tasks drawn from ten existing TC-V3 scenario families. It carries forward the original 480 Direct and Original SDK slots and adds 240 phase-aware SDK slots. Each task shares its world, schema contract and seed across weights. Weight order rotates in 15-task periods and runtime order is balanced within each period. Every SDK trajectory uses a fresh session. The panel adds zero core trials.

| Arm | Effective runtime |
|---|---|
| Direct | Native provider JSON with pinned tool schemas and sampling, cache and token limits |
| Original SDK | Real original SDK harness, legacy tool choice preserved, matched external provider limits and public tool schemas |
| Corrected SDK | `SDK_MATCHED_CONTEXT_PhaseAware` with the same external provider limits, phase-aware grants and typed callback binding |

The two SDK arms retain the real harness transcript and result wrapper. Phase-aware grants may reduce the exposed tool list. This difference belongs to the model-visible runtime treatment. The replay publishes matched weight differences, runtime differences, their interaction, exact arguments, output and termination, duplicate proposals, redundant executions and available provider costs.

## Protocol reconciliation

An initial diagnostic run sealed 270 trajectories before the effective budget audit showed that the SDK emitted a model-visible 65,535-token limit while Direct sent 768. Those sealed trials and the interrupted reservation are retained in the diagnostic archive. Their effective limits and cache controls do not satisfy the matched panel contract. The matched runner now checks the effective provider request before sealing and during replay. [Diagnostic seal manifest](../evidence/IJSLM/lfm3-ha-1.1/legacy-budget-diagnostic.json)

## Full matched result

All 720 trajectories sealed and replayed across 16 Radeon batches. Each table cell lists PASS / FAIL / BLOCKED for exact scoped completion out of 60. All NOT_RUN counts are zero. The earlier balanced checkpoint remains available. [Full paired replay](../evidence/IJSLM/lfm3-ha-1.1/transfer-panel.json) · [180-trial checkpoint](../evidence/IJSLM/lfm3-ha-1.1/transfer-checkpoint-180.json)

| Weight | Direct | Original SDK | Phase-aware SDK | Phase-aware paired weight gain |
|---|---:|---:|---:|---:|
| Original | 53 / 6 / 1 | 2 / 58 / 0 | 26 / 33 / 1 | Reference |
| OpenCode | 50 / 9 / 1 | 2 / 58 / 0 | 24 / 35 / 1 | −3.4 pp on 59 adjudicated pairs |
| Pi | 52 / 7 / 1 | 4 / 56 / 0 | 35 / 23 / 2 | +15.5 pp on 58 adjudicated pairs |
| Hermes | 51 / 8 / 1 | 4 / 56 / 0 | 28 / 30 / 2 | +3.4 pp on 58 adjudicated pairs |

Pi gained 53.4 points from the phase-aware SDK treatment versus its Original SDK arm. The same runtime treatment gained 40.7 points on Original weights. Pi's weight-by-runtime interaction was +12.1 points on the 58 fully adjudicated four-arm comparisons. Pi's Direct weight contrast was −1.7 points against Original. All phase-aware arms trailed their own Direct arms. The public replay reports the pairing denominator for each contrast and retains separate tool selection, exact argument, exact execution, result delivery, comprehension and termination metrics.

| Phase-aware weight | First tool choice PASS | Exact arguments and execution PASS | Exact termination PASS | Excess proposals and executions in observed trials | Requests / tools / tokens per scoped success |
|---|---:|---:|---:|---:|---:|
| Original | 56 | 32 | 29 | 27 / 118 proposal and execution opportunities | 6.31 / 4.62 / 7,057 |
| OpenCode | 57 | 33 | 30 | 19 / 109 | 6.63 / 4.63 / 7,406 |
| Pi | 57 | 42 | 40 | 14 / 96 | 4.34 / 2.86 / 4,835 |
| Hermes | 57 | 33 | 31 | 26 / 113 | 5.79 / 4.18 / 6,497 |

Pi reduced repeated calls and exact termination failures most clearly in the phase-aware scope. OpenCode reduced observed repeat events, with one additional exact termination pass and two fewer scoped completions than Original. Hermes had a similar repeat rate to Original, with two additional exact termination passes. Repeat opportunities exclude one or two unresolved cases per phase-aware arm. The report keeps the unresolved rate status and gives only the observed numerators and denominators.

Six phase-aware and four Direct trajectories reached the native 768-token cap. The native proof distinguishes cap exhaustion from an SDK transport defect even where the SDK reported HTTP 502. The frozen scorer retains its original dispositions for incomplete terminal evidence. This panel supports a Pi phase-aware hypothesis for independent review. It leaves production role qualification and final model selection open.
