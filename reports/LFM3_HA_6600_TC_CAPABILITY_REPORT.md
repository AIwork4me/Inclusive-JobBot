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

The 12-case Radeon development panel passed transport verification for SDK first and SDK repeat. Each recorded eligible provider request used the seeded JSON profile and returned validated SSE to the SDK. The full 6,600 compatibility queue started after the sealed 720 transfer measurements. The latest published checkpoint contains 1,704 replayed physical slots across the same first 130 tasks and 36 repeat trajectories for each weight. This roster prefix covers only a subset of the scenario families. The transport pilot contributes zero compatibility or core slots. [Transport receipt](../evidence/IJSLM/lfm3-ha-1.1/tc-transport-admission.json) · [1,704-trial checkpoint](../evidence/IJSLM/lfm3-ha-1.1/tc-compatibility-checkpoint-1704.json)

| Weight | Direct scoped completion | SDK first | SDK streaming | SDK repeat |
|---|---:|---:|---:|---:|
| Original | 119 / 130 | 48 / 130 | 50 / 130 | 15 / 36 |
| OpenCode | 115 / 130 | 49 / 130 | 47 / 130 | 14 / 36 |
| Pi | 117 / 130 | 63 / 130 | 60 / 130 | 18 / 36 |
| Hermes | 114 / 130 | 47 / 130 | 48 / 130 | 15 / 36 |

The table gives scoped PASS counts over covered slots. The machine-readable checkpoint retains FAIL and BLOCKED separately. Peak process GPU commitment medians across the 13 matched launch batches per weight were about 83–88 MiB above Original for the three adapted routes. Resource fields include attempt and scoped-success percentiles. The queue remains active and the final tracker covers the full rotation of task families before reporting suite-level estimates.

The registered panel reports the original Atlas dimensions and its family, language and risk denominators, streaming consistency, repeated-seed reliability, argument binding, scoped completion, termination, request and tool efficiency and per-batch peak GPU memory. The typed callback Extension has a separate scope. The TC-V3 compatibility set measures the existing scenario families. Formal generalization requires independent tasks and business witnesses. [Registered runner](../benchmarks/slm10/ha11_panel.py) · [Atlas replay](../benchmarks/slm10/ha11_panel_report.py)
