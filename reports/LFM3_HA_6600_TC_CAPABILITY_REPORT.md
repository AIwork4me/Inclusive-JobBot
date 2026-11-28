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

## Measurement status

The 12-case Radeon development panel passed transport verification for SDK first and SDK repeat. Each recorded eligible provider request used the seeded JSON profile and returned validated SSE to the SDK. The full 6,600 compatibility queue started after the sealed 720 transfer measurements. The halfway checkpoint contains 3,300 replayed physical slots across 250 matched tasks and 75 repeat trajectories per weight. It covers single-tool, selection, binding, roundtrip and dependency tasks. The transport pilot contributes zero compatibility or core slots. [Transport receipt](../evidence/IJSLM/lfm3-ha-1.1/tc-transport-admission.json) · [3,300-trial checkpoint](../evidence/IJSLM/lfm3-ha-1.1/tc-compatibility-checkpoint-3300.json)

| Weight | Direct scoped completion | SDK first | SDK streaming | SDK repeat |
|---|---:|---:|---:|---:|
| Original | 233 / 250 | 99 / 250 | 101 / 250 | 31 / 75 |
| OpenCode | 230 / 250 | 97 / 250 | 98 / 250 | 29 / 75 |
| Pi | 221 / 250 | 125 / 250 | 123 / 250 | 43 / 75 |
| Hermes | 225 / 250 | 98 / 250 | 98 / 250 | 30 / 75 |

The table gives scoped PASS counts over covered slots. The machine-readable checkpoint retains FAIL and BLOCKED separately. All 4,030 decoded callbacks bound, with zero integer conversions in the measured cohort. Pi gained 27 SDK-first scoped PASS pairs and lost one. In Direct, Pi gained two and lost 14. These are descriptive contrasts over 250 paired tasks. The three adapted routes' median peak process GPU commitment was 85–86 MiB above Original across the 25 launch batches per weight. Parallel work, clarification, recovery, scope update and authorization remain outside the halfway replay.

The registered panel reports the original Atlas dimensions and its family, language and risk denominators, streaming consistency, repeated-seed reliability, scoped completion, termination, request and tool efficiency and per-batch peak GPU memory. The replay records gains and losses against the fresh Original baseline on adjudicated pairs. It scores the exact proposed tool argument multiset and the SDK binder separately. The binder counters record accepted and rejected callbacks, missing delivery and the number of lossless integer conversions. Direct tracks and complete SDK trials that proposed no tools have no binder opportunity. The typed callback Extension has a separate scope. The TC-V3 compatibility set measures the existing scenario families. Formal generalization requires independent tasks and business witnesses. [Registered runner](../benchmarks/slm10/ha11_panel.py) · [Atlas replay](../benchmarks/slm10/ha11_panel_report.py)
