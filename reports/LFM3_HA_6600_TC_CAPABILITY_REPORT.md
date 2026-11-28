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

The 12-case Radeon development panel passed transport verification for SDK first and SDK repeat. Each recorded eligible provider request used the seeded JSON profile and returned validated SSE to the SDK. The full 6,600 compatibility queue started after the sealed 720 transfer measurements. The latest checkpoint contains 5,028 replayed physical slots across 380 matched tasks and 117 repeat trajectories per weight. It covers seven full families and the first 30 of 50 recovery tasks. Scope update and authorization lie later in the roster. The transport pilot contributes zero compatibility or core slots. [Transport receipt](../evidence/IJSLM/lfm3-ha-1.1/tc-transport-admission.json) · [5,028-trial checkpoint](../evidence/IJSLM/lfm3-ha-1.1/tc-compatibility-checkpoint-5028.json)

| Weight | Direct scoped completion | SDK first | SDK streaming | SDK repeat |
|---|---:|---:|---:|---:|
| Original | 356 / 380 | 147 / 380 | 147 / 380 | 49 / 117 |
| OpenCode | 336 / 380 | 139 / 380 | 143 / 380 | 41 / 117 |
| Pi | 335 / 380 | 189 / 380 | 187 / 380 | 66 / 117 |
| Hermes | 329 / 380 | 151 / 380 | 152 / 380 | 48 / 117 |

The table gives scoped PASS counts over covered slots. The checkpoint retains FAIL and BLOCKED separately. All 6,568 decoded callbacks bound. The typed callback verdict remained BLOCKED on 96 SDK trajectories with incomplete provider evidence. Pi gained 43 SDK-first scoped PASS pairs and lost one among 364 adjudicated pairs. In Direct, Pi gained six and lost 27 across 380 pairs. The four weights together passed 197 of 200 clarification slots on Direct, 16 of 200 in SDK first and 19 of 200 in SDK streaming. Full-suite inference and authorization coverage await the remaining sealed batches.

The registered panel reports the original Atlas dimensions and its family, language and risk denominators, streaming consistency, repeated-seed reliability, scoped completion, termination, request and tool efficiency and per-batch peak GPU memory. The replay records gains and losses against the fresh Original baseline on adjudicated pairs. It scores the exact proposed tool argument multiset and the SDK binder separately. The binder counters record accepted and rejected callbacks, missing delivery and the number of lossless integer conversions. Direct tracks and complete SDK trials that proposed no tools have no binder opportunity. The typed callback Extension has a separate scope. The TC-V3 compatibility set measures the existing scenario families. Formal generalization requires independent tasks and business witnesses. [Registered runner](../benchmarks/slm10/ha11_panel.py) · [Atlas replay](../benchmarks/slm10/ha11_panel_report.py)
