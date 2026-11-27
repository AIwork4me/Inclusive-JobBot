# IJ-NANO-1.0 Blockers

Mission-specific blockers. Status values: `OPEN`, `MITIGATED`, `CLOSED`.
"Owner" is who can remove the cause. Earlier missions' `BLOCKERS.md` entries
(B-001..B-009) remain theirs; IJ-NANO inherits the still-open ones as
environment constraints (see IJN-B-004).

## IJN-B-001 The Radeon GPU is leased to IJ-SLM-1.0

- Priority: P0 for every physical phase (N02+) — **while open**
- Status: **CLOSED 2026-11-27 (N00R)** — `CROSS_HOST_GPU_LEASE_CONFLICT_RESOLVED` + `LOCAL_GPU_LEASE_AVAILABLE`
- Owner: operator (lease policy between missions)
- Found: 2026-11-27, N00 audit. Closed: 2026-11-27, N00R reconciliation.

**Resolution (N00R).** IJ-SLM-1.0's sealed physical runs bind to a different
physical device on a different host: Radeon 8060S, gfx1151, driver
32.0.22018.5, AMD Ryzen AI MAX+ PRO 395 platform, host_sha256 `8c12b292...`
(PR #9 @ `364c7ca`: `atlas/slm/v1.0/environment.json`,
`evidence/IJ073/aeve/gpu_handoff.json`, IJSLM tc-v3 run manifest). This
workstation is RX 7900 XTX, gfx1100, PCI `DEV_744C`, driver 32.0.21030.2001,
i7-13700K/B760M — the host where IJ-SDK P1 qualified gfx1100. IJ-SLM's lease
on its own host is untouched.

**Local coordination.** The existing host-wide lease protocol is reused:
`benchmarks/root_cause/gpu_lease.py` (named kernel mutex
`Global\InclusiveJobBotPhysicalGPU`, atomic acquisition, abandoned-owner
recovery, clean release). Probe 2026-11-27T11:20:07Z: `ACQUIRED_FREE`,
released cleanly. No mission-specific mutex is created. Every IJ-NANO
physical session acquires this lease.

**Evidence.** `evidence/IJNANO/N00R/gpu_identity_comparison.json`,
`evidence/IJNANO/N00R/lease_scope_decision.json`,
`reports/IJNANO_00R_RESOURCE_AND_DEPENDENCY_RECONCILIATION.md`.

## IJN-B-002 No qualified evaluator, harness or oracle is inheritable

- Priority: P0 for **formal business claims only** (scope narrowed 2026-11-27, N00R)
- Status: OPEN (narrowed)
- Owner: project (IJ-SDK-1.1 line) and IJ-NANO (own evaluator decision)
- Found: 2026-11-27, N00 audit. Narrowed: 2026-11-27, N00R.

**Evidence.** MISSION_STATE_IJSDK.json at the base commit: P3 and P5 reopened
FAIL by the P0R integrity audit; the P4 harness core reopened FAIL (D04-D07);
`formal_gpu_matrix_authorized: false`; P4A checkpoint 1 was stopped by the
operator with the gate NOT_RUN.

**Scope correction (N00R).** The IJ-SDK formal-matrix non-authorization
applies to IJ-SDK's own unqualified benchmark and evaluator scopes. It is not
a repository-wide ban on physical model inference. Not blocked: physical
runtime admission (N02), cognitive microbenchmarks (N03), protocol
diagnostics, runtime mechanism development — each under IJ-NANO's own
preregistered qualification and the host-wide lease. Blocked: formal
end-to-end business performance evaluation and product qualification claims.

**What IJ-NANO does.** Nothing from reopened-FAIL scopes is inherited as
qualified; P4A harness source stays REFERENCE_ONLY. Shared evaluation
architecture per the N00R order: one common business evaluation contract,
multiple independently qualified specialized evaluators. IJ-NANO-specific
scopes (C01-C32 cognitive primitives, context sufficiency/loss, tool
retrieval recall, dependency closure, dynamic constraints, DSL correctness,
slot-binding provenance, typed state, profile effectiveness, recovery
attribution, model×harness and cross-job transfer) get their own
deterministic controls, independent expected results and mutation tests, and
do not wait for the full IJ-SDK P5R business oracle. Formal end-to-end
business evaluation waits for either a re-audited qualified P5R evaluator or
the minimum necessary independent evaluator satisfying the same business
contract (documented why it cannot be reused). IJ-SDK-1.1 repairs are not
duplicated.

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
