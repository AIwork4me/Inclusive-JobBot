# IJ-NANO-48H Live Status

Campaign clock: **2026-11-28T04:34:00Z → 2026-11-30T04:34:00Z** (48h,
never restarted). This file is continuously updated at publication
checkpoints.

## Current phase: P1 integration complete; physical dispatch BLOCKED on EAE requalification (48H-B-006)

**Consumer-side integration is done and verified.** The pinned EAE
snapshot (3cdd066, 84 files, digest-manifested) bootstraps, the
real-consumer provider re-pins to compat v1.1.1, and the full
controller (balanced blocks, dispatch limits, per-dispatch revocation
recheck, canaries, persistent breaker, exact resume, seal/verify) is
in place. 276/276 tests green.

**Blocker found and verified fail-closed:** the EAE's post-release
consumer-verification revocation drill durably revoked production
certificate `512efb617a9cb4c8` (registry generation 2, reason
"drill", 2026-11-28T04:04:08Z — committed as part of 3cdd066). Fresh
ExecutionAuthorization issuance therefore refuses with "no applicable
certificates" — exactly the designed fail-closed behavior. The
AUTH-1/AUTH-2 releases (03:45Z/04:03Z) predate the drill and remain
historically valid. Recovery is requalification-only and belongs to
the IJEVAL lane (their support mission is active — Batch B
qualification in flight). Coordination note on Issue #10; this
campaign polls the IJEVAL remote and fires E0 immediately when the
requalified release lands.

Meanwhile: E3 CPU-side preparation (official task-set study, harness
pinning) and adapter asset pinning proceed as independent AUTH-0 work.

## Scope status board

| Scope | Slots | Status |
|---|---:|---|
| E0 smoke (AUTH-1) | 48 | RELEASED authorization; issuance blocked by 48H-B-006 |
| E1 Batch A dev (AUTH-2) | 480 | RELEASED authorization; issuance blocked by 48H-B-006 |
| E1 Batches B-D dev | 1,440 | BLOCKED — pending IJEVAL EA13 extensions (Batch B in flight) |
| E1 confirmation (AUTH-3) | 960 | BLOCKED by design |
| E2 adapter atlas | 2,560 | BLOCKED — scope + assets |
| E3 native reproduction | 1,140 | BLOCKED — task acquisition/sandbox (CPU prep RUNNING) |
| E4 cross-harness | 720 | BLOCKED — E3 + scope |
| E5 runtime×adapter factorial | 480 | BLOCKED — scope + runtime |
| E6 budgets + reference | 1,400 | BLOCKED — scope |
| E7 learnability | 1,440 | BLOCKED — scope |
| E8 multi-adapter/cross-job | 1,200+ | NOT_RUN (P2) |

