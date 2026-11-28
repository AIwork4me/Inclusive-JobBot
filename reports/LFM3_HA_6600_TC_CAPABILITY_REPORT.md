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

The 12-case Radeon development panel passed transport verification for SDK first and SDK repeat. Each recorded eligible provider request used the seeded JSON profile and returned validated SSE to the SDK. The full 6,600 compatibility queue started after the sealed 720 transfer measurements. The latest published checkpoint contains 2,244 replayed physical slots across the same first 170 tasks and 51 repeat trajectories for each weight. This roster prefix covers a subset of the scenario families. The transport pilot contributes zero compatibility or core slots. [Transport receipt](../evidence/IJSLM/lfm3-ha-1.1/tc-transport-admission.json) · [2,244-trial checkpoint](../evidence/IJSLM/lfm3-ha-1.1/tc-compatibility-checkpoint-2244.json)

| Weight | Direct scoped completion | SDK first | SDK streaming | SDK repeat |
|---|---:|---:|---:|---:|
| Original | 155 / 170 | 50 / 170 | 52 / 170 | 16 / 51 |
| OpenCode | 151 / 170 | 50 / 170 | 50 / 170 | 14 / 51 |
| Pi | 153 / 170 | 73 / 170 | 73 / 170 | 23 / 51 |
| Hermes | 149 / 170 | 49 / 170 | 49 / 170 | 15 / 51 |

The table gives scoped PASS counts over covered slots. The machine-readable checkpoint retains FAIL and BLOCKED separately. The SDK binder accepted all 2,551 decoded callback proposals in the prefix. There were no integer conversions in this cohort. Pi gained 23 SDK-first scoped PASS pairs and lost zero across the 170 matched tasks. The remaining task families are required for suite-level estimates. The three adapted routes' median peak process GPU commitment was 83–86 MiB above Original across the 17 launch batches per weight. Resource fields include attempt and scoped-success percentiles.

The registered panel reports the original Atlas dimensions and its family, language and risk denominators, streaming consistency, repeated-seed reliability, scoped completion, termination, request and tool efficiency and per-batch peak GPU memory. The replay records gains and losses against the fresh Original baseline on adjudicated pairs. It scores the exact proposed tool argument multiset and the SDK binder separately. The binder counters record accepted and rejected callbacks, missing delivery and the number of lossless integer conversions. Direct tracks and complete SDK trials that proposed no tools have no binder opportunity. The typed callback Extension has a separate scope. The TC-V3 compatibility set measures the existing scenario families. Formal generalization requires independent tasks and business witnesses. [Registered runner](../benchmarks/slm10/ha11_panel.py) · [Atlas replay](../benchmarks/slm10/ha11_panel_report.py)
