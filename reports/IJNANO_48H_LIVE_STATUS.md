# IJ-NANO-48H Live Status

Campaign clock: **2026-11-28T04:34:00Z → 2026-11-30T04:34:00Z** (48h,
never restarted). This file is continuously updated at publication
checkpoints.

## Current phase: P1 — physical admission and trusted EAE integration

- Preregistration complete: verbatim order, frozen campaign state
  (hypotheses H1-H8, experiment register, metrics, analysis methods,
  resume semantics), task ledger, blockers.
- EAE releases consumable now: AUTH-1 (48-slot diagnostic smoke) and
  AUTH-2 (480-slot Batch A development, chat protocol, S1/S2/S3) under
  certificate 512efb617a9cb4c8, compat v1.1.1 @ 3cdd066.
- Next: EAE pinned snapshot + consumer bootstrap + GPU admission → E0
  smoke → `N03_PHYSICAL_EVALUATION_INTEGRATION_GO` → E1 Batch A.

## Scope status board

| Scope | Slots | Status |
|---|---:|---|
| E0 smoke (AUTH-1) | 48 | AUTHORIZED — pending physical admission |
| E1 Batch A dev (AUTH-2) | 480 | AUTHORIZED — pending smoke + integration gate |
| E1 Batches B-D dev | 1,440 | BLOCKED — pending IJEVAL EA13 extensions |
| E1 confirmation (AUTH-3) | 960 | BLOCKED by design |
| E2 adapter atlas | 2,560 | BLOCKED — scope + assets |
| E3 native reproduction | 1,140 | BLOCKED — task acquisition/sandbox (CPU prep running) |
| E4 cross-harness | 720 | BLOCKED — E3 + scope |
| E5 runtime×adapter factorial | 480 | BLOCKED — scope + runtime |
| E6 budgets + reference | 1,400 | BLOCKED — scope |
| E7 learnability | 1,440 | BLOCKED — scope |
| E8 multi-adapter/cross-job | 1,200+ | NOT_RUN (P2) |
