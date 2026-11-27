# IJ-NANO-1.0 Blockers

Mission-specific blockers. Status values: `OPEN`, `MITIGATED`, `CLOSED`.
"Owner" is who can remove the cause. Earlier missions' `BLOCKERS.md` entries
(B-001..B-009) remain theirs; IJ-NANO inherits the still-open ones as
environment constraints (see IJN-B-004).

## IJN-B-001 The Radeon GPU is leased to IJ-SLM-1.0

- Priority: P0 for every physical phase (N02+)
- Status: OPEN
- Owner: operator (lease policy between missions)
- Found: 2026-11-27, N00 audit

**Evidence.** PR #9 (codex/ij-slm-1.0, IJ-SLM-1.0) states it gives
MiniCPM5-2B, LFM3-1.7B and Qwen3.5-2B first access to the Radeon after frozen
Q2 is sealed and the GPU handoff is verified. The branch records
`gpu_handoff: PASS` and Q2 sealed; `physical_progress.json` at the audited
head already contains executed arm-A direct-runtime trials against a
36,550-trial formal plan. No IJ-SLM process was running on this workstation
at audit time, but the reservation is respected regardless of momentary
idleness.

**What IJ-NANO does.** Software-only work now (N00, N01, protocol design,
pure-software SDK development). Physical phases stay BLOCKED. When the
operator releases or shares the lease, N02 starts with a preregistered
qualification protocol of its own.

## IJN-B-002 No qualified evaluator, harness or oracle is inheritable

- Priority: P0 for formal business claims (N05, N08+)
- Status: OPEN
- Owner: project (IJ-SDK-1.1 line) and IJ-NANO (own evaluator decision)
- Found: 2026-11-27, N00 audit

**Evidence.** MISSION_STATE_IJSDK.json at the base commit: P3 and P5 reopened
FAIL by the P0R integrity audit; the P4 harness core reopened FAIL (D04-D07);
`formal_gpu_matrix_authorized: false`; P4A checkpoint 1 was stopped by the
operator with the gate NOT_RUN.

**What IJ-NANO does.** Nothing from those scopes is inherited as qualified.
The P4A harness source is classified REFERENCE_ONLY. N05 proceeds either by
re-auditing a future qualified IJ-SDK P5R scope or by building an independent
evaluator under the E0-E6 architecture with its own qualification. The
original 14-control oracle is never relied on. IJ-SDK-1.1 repairs are not
duplicated or interfered with.

## IJN-B-003 S2 (LFM3-1.7B) commercial-deployment license is revenue-conditioned

- Priority: P1 for commercial eligibility conclusions only (research unaffected)
- Status: OPEN
- Owner: project owner
- Found: 2026-11-27, N00 audit (models/ij_sdk/model_manifest.json)

**Evidence.** LFM Open License v1.0: commercial use only below USD 10M annual
revenue; research use permitted. S2 remains a fully valid research arm
(N02-N15). Any commercial-deployment statement about an S2-based JobBot
requires the owner's separate licensing decision. Apache-2.0 models
(S1, S3, R1, R2) are unaffected.

## IJN-B-004 Inherited environment blockers (B-004..B-009 of BLOCKERS.md)

- Priority: P1/P2 depending on phase
- Status: OPEN (inherited)
- Owner: machine owner / project
- Found: 2026-11-27, N00 audit

Long runs exceed one session (resumable design mandatory); no C++ toolchain
(no local llama.cpp debug builds or `test-chat`); no power meter (energy stays
NOT_MEASURED, never estimated from TDP); soak tests need the machine awake
(owner power settings); original SDK checklist unavailable; pinned MiniCPM5
native parser fails fixed fixtures (B-009 - directly relevant to M03/M04
action-representation design; any parser fix qualifies as a separate engine
identity).

## IJN-B-005 Network constraints on this workstation

- Priority: P2 (workaround in place)
- Status: MITIGATED
- Owner: environment
- Found: 2026-11-27 (observed again during N00: `git fetch` to github.com
  reset twice while `gh api` succeeded)

Workarounds per DECISIONS.md D-002: `gh api` for GitHub reads, Tsinghua PyPI
mirror for packages, `scripts/tools/parallel_fetch.py` for large assets.
Raw `git push` may need retries.
