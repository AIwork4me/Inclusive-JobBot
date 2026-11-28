# IJ-NANO-48H Blockers

Campaign-scoped blockers. Status: OPEN / MITIGATED / CLOSED.
Inherited mission blockers (IJN-B-001 CLOSED, IJN-B-002 OPEN-narrowed,
IJN-B-003 OPEN, IJN-B-004 OPEN) remain owned as recorded in
`BLOCKERS_IJNANO.md`.

## 48H-B-001 Batches C/D cognitive families not yet EAE-qualified (Batch B RELEASED)

- Batch B (C09-C16) AUTH-2B released 2026-11-28 (bffce5a): certificate
  bd41edfb6fd7c004, 480-slot roster, checksum fc4cdb2c reproduced by
  the real consumer. Batch C/D remain pending.


- Priority: P0 for E1 completion (1,440 primary slots)
- Status: OPEN
- Owner: IJEVAL session (PR #13) — EA13 extension releases
- Found: 2026-11-28, campaign init reconciliation.
- Note: AUTH-2 covers Batch A only (certificate 512efb617a9cb4c8, scope
  C01-C08 x chat x 3 models). Batch B/C/D authorization is NEVER inferred
  from the Batch A certificate. The IJEVAL 48H support mission has
  qualifying B/C/D as its Priority 0; this campaign polls the IJEVAL
  remote at safe checkpoints and consumes released scopes when published.

## 48H-B-002 Adapter weight configurations and additional protocols not covered by any released scope

- Priority: P0 for E2/E4/E5 (adapter lanes)
- Status: OPEN
- Owner: IJEVAL session (PR #13) + this campaign (asset admission)
- Found: 2026-11-28, campaign init.
- Note: W1-W3 (Pi/OpenCode/Hermes F16 GGUF LoRAs) are not downloaded
  locally yet, and no EAE scope covers them on this host. Physical
  adapter work starts only after BOTH the assets are admitted
  (scale-0/1 equivalence, selection correctness, no silent fallback,
  isolated fixed-adapter server processes, identical cache policy) AND
  IJEVAL publishes the adapter-scope qualification.

## 48H-B-003 E3 native harness task acquisition and sandbox qualification

- Priority: P0 (research priority) but asset-gated
- Status: OPEN
- Owner: this campaign
- Found: 2026-11-28, campaign init.
- Note: The 150 held-out SmolDataEnvs data-analysis tasks and 40
  traj2envs repository tasks must be identified, pinned (revisions,
  images, verifiers, reference solutions), sandboxed and
  verifier-qualified before any native harness episode. Do not assume
  the public training dataset name identifies the evaluation split.

## 48H-B-004 AUTH-3 protected confirmation BLOCKED by design

- Priority: informational
- Status: OPEN (by design)
- Owner: IJEVAL (registration) + owner (freeze decisions)
- Note: 960 confirmation slots are reported BLOCKED/NOT_RUN unless all
  order §5 conditions hold within the campaign. Never weakened.

## 48H-B-006 Production certificate 512efb617a9cb4c8 revoked by the EAE consumer-verification drill at 3cdd066

- Priority: P0 — blocks Batch A physical scopes only (E0 smoke + E1 Batch A); Batch B unblocked
- Status: OPEN
- Owner: IJEVAL session (PR #13) — requalification-only recovery
  (new authoritative generation + passing canary per their EA10/EA14
  design); this lane NEVER un-revokes or reissues on the EAE side.
- Found: 2026-11-28 ~05:00Z, consumer-side bootstrap verification.
- Evidence: pinned registry generation 2 carries `revoked_utc
  2026-11-28T04:04:08Z` reason "drill" (the AUTH-2 post-release
  consumer-verification revocation drill durably revoked the
  production certificate and that state was committed as 3cdd066);
  `evidence/IJEVAL/AUTH2/authoritative_state.json` records the same
  revocation. The AUTH-1/AUTH-2 authorizations (checksums 4a09f525… /
  a22bcc68…) were issued at 03:45/04:03Z, BEFORE the drill, and remain
  historically valid releases; fresh issuance from the pinned revision
  correctly fails closed ("no applicable certificates").
- Consumer-side verification: `tests/ij_nano/test_n03h_bootstrap.py`
  (pin digest verification + tamper refusal + fail-closed refusal +
  dual-path witness sweep 108/108 + renderer contracts). Issuance-path
  tests auto-activate when a requalified pin lands.
- Coordination: note posted on Issue #10; this campaign polls the
  IJEVAL remote at safe checkpoints and re-pins + re-verifies +
  re-authorizes the moment a requalification release is published.
- Independent work continues meanwhile (E3 CPU-side task acquisition
  study, adapter asset pinning, controller hardening).

## 48H-B-005 IJEVAL worktree strictly read-only for this lane

- Priority: standing constraint
- Status: OPEN (permanent rule)
- Note: The IJEVAL sibling session is active (48H support mission).
  Coordination ONLY through immutable git revisions (pinned snapshots
  verified by digest) and GitHub. Never write, commit, or acquire its
  GPU lease (it does not run GPU work).
