# IJ-NANO-48H Experiment Coverage

Machine-readable source: `evidence/IJNANO/N03H/coverage.json`
(regenerate: `python scripts/ij_nano/n03h/coverage_report.py --out …`).

| Scope | Planned | Executed | Status |
|---|---:|---:|---|
| E1 Batch A dev (AUTH-2A-RQ) | 480 | 480 | **COMPLETE** (seal 2cd631fa) |
| E1 Batch B dev (AUTH-2B) | 480 | 480 | **COMPLETE** (seal cb4303b4) |
| E1 Batch C dev (AUTH-2C) | 480 | 480 | **COMPLETE** (seal 25ffffa9) |
| E1 Batch D dev (AUTH-2D) | 480 | 480 | **COMPLETE** (seal b4028e38) |
| E1 confirmation (AUTH-3) | 960 | 0 | BLOCKED (by design; protection never weakened) |
| E2 adapter atlas (AUTH-2W) | 1,920 | 1,920 | **COMPLETE** (seal cb5e8b8a) |
| E3 native reproduction | 1,140 | 0 | BLOCKED (task acquisition + no docker/WSL; sources study frozen) |
| E4 cross-harness | 720 | 0 | BLOCKED (requires E3) |
| E5 runtime × adapter factorial | 480 | 0 | BLOCKED (scope not released) |
| E6 reasoning budget | 1,080 | 0 | BLOCKED (scope not released) |
| E6 larger-model reference | 320 | 0 | BLOCKED (scope not released) |
| E7 learnability | 1,440 | 0 | BLOCKED (scope not released) |
| E8 multi-adapter / cross-job | 1,200+ | 0 | NOT_RUN (P2) |

**Executed: 3,840 / planned 9,980 across all scopes** — every
authorization ever released for this host was fully executed; every
unexecuted scope is BLOCKED with the blocking cause recorded
(`BLOCKERS_IJNANO_48H.md`). Attempt accounting: 3,840 physical
attempts = 3,840 recorded trials (zero transport failures, zero
retries consumed, zero quarantine). E2's W0 arm is EXACT REUSE of the
E1 LFM3-1.7B arms (identity-verified: protocol, renderer, sampling,
roster) — counted once as E1 executions, never double-counted.
