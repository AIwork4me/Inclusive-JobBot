# IJ-NANO-48H Blockers

Campaign-scoped blockers. Status: OPEN / MITIGATED / CLOSED.
Inherited mission blockers (IJN-B-001 CLOSED, IJN-B-002 OPEN-narrowed,
IJN-B-003 OPEN, IJN-B-004 OPEN) remain owned as recorded in
`BLOCKERS_IJNANO.md`.

## 48H-B-001 Batches B/C/D cognitive families not yet EAE-qualified

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

## 48H-B-005 IJEVAL worktree strictly read-only for this lane

- Priority: standing constraint
- Status: OPEN (permanent rule)
- Note: The IJEVAL sibling session is active (48H support mission).
  Coordination ONLY through immutable git revisions (pinned snapshots
  verified by digest) and GitHub. Never write, commit, or acquire its
  GPU lease (it does not run GPU work).
