# IJ-NANO-48H Live Status

Campaign clock: **2026-11-28T04:34:00Z → 2026-11-30T04:34:00Z** (48h,
never restarted). Updated at publication checkpoints.

## Current phase: PHYSICAL EXECUTION LIVE (checkpoint H+~4)

- **E1 Batch B (AUTH-2B, 480 slots) executing** — blocks 0-1 sealed
  (120 trials, 120/120 offline dual-path replays match, seal
  f1990515); remaining blocks dispatching now.
- **`N03_PHYSICAL_EVALUATION_INTEGRATION_GO` GRANTED** on the verified
  first-block evidence, including a production fault-recovery drill
  (controller canary-leg defect caught at preflight with zero trials
  affected; requalification-only breaker recovery exercised).
- **E1 Batch C (AUTH-2C, 480 slots) wired and checksum-verified**
  (a50c3c5 pin) — queued immediately after Batch B on the GPU lease.
- First findings (H2 signal): LFM3-1.7B 40/40 on C09/C10; Qwen3.5-2B
  32/40 EMPTY_OUTPUT all `finish_reason=length` (thinking exhausts the
  frozen 1024-token chat budget); MiniCPM5-2B 34/40.
- Batch A scopes remain blocked (48H-B-006: drill-revoked certificate;
  requalification owned by IJEVAL; Issue #10 coordination posted).
- Adapter assets W1-W3 acquired + digest-verified; E3 official-sources
  study frozen; E3 sandbox constrained (no docker/WSL on host).

## Scope status board

| Scope | Slots | Status |
|---|---:|---|
| E0 smoke (AUTH-1) | 48 | SUPERSEDED by AUTH-2B first-block verification |
| E1 Batch A dev (AUTH-2) | 480 | BLOCKED — 48H-B-006 (drill-revoked cert) |
| E1 Batch B dev (AUTH-2B) | 480 | EXECUTING (sealed 120+/480) |
| E1 Batch C dev (AUTH-2C) | 480 | AUTHORIZED — queued after Batch B |
| E1 Batch D dev | 480 | BLOCKED — pending IJEVAL release |
| E1 confirmation (AUTH-3) | 960 | BLOCKED by design |
| E2 adapter atlas | 2,560 | assets pinned; scope pending |
| E3 native reproduction | 1,140 | sources frozen; sandbox constrained |
| E4-E8 | — | BLOCKED/NOT_RUN per register |

