# IJ-NANO-48H Live Status

Campaign clock: **2026-11-28T04:34:00Z → 2026-11-30T04:34:00Z** (48h,
never restarted). Updated at publication checkpoints.

## Current phase: PHYSICAL EXECUTION LIVE (checkpoint H+7.9)

- **E1 Batch B COMPLETE** (480/480, seal cb4303b4): LFM3 .625 /
  MiniCPM .5875 / Qwen .0875 (S3 87.5% EMPTY, all finish=length).
- **E1 Batch C COMPLETE** (480/480, seal 25ffffa9): LFM3 .025 /
  MiniCPM .0375 / Qwen .0 — root-caused: EVERY EMPTY trial exhausts
  the frozen 1024-token budget (finish=length, empty final content)
  on plan-structured primitives; hits ALL models (RQ2 finding).
- **E1 Batch D COMPLETE** (seal b4028e38) and **E1 Batch A-RQ
  COMPLETE** (seal 2cd631fa): **E1 primary development complete —
  1,920/1,920 slots, zero integrity problems.**
- **Adapter admission battery PASS** (two real defect fixes on the
  way: Windows path colon vs --lora-scaled; distribution-level scale-1
  evidence via logprob deltas 10.68/3.64 reproduced across processes).
- **E2 adapter atlas EXECUTING: 1,235/1,920** (412/412/411 balanced).
  Interim paired vs W0: W1 +2.9pp (p=.012), W2 +1.5pp (ns),
  W3 +4.9pp (p=.0002) — exploratory, finalizes at seal.
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

