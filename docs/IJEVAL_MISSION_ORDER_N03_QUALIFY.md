# IJ-EVAL-ASSURANCE-1.0 — Execute the N03 Batch A Critical Path to Qualification

## 1. Resume

- Repository: https://github.com/AIwork4me/Inclusive-JobBot
- Owner lane: IJEVAL.
- Issue #12, Draft PR #13.
- Audited IJEVAL HEAD: `f251eda52b67e6f3a1043f67d29c3217831d318d`.
- Pinned Batch A source: `d23de5abe596e43743a5a2c7437ccd1b5e7de7f9`.
- Latest observed IJ-NANO HEAD: `c772a9a0febf64ae08329cdcdadd2853422cbb74`.

The IJ-NANO lane has now delivered all 960 cognitive cases and completed its dataset preparation and verification gates. It is proceeding to N03-B4/B5.

Continue the existing IJEVAL mission from the completed Batch A intake.

Do not restart completed audit, compatibility-contract or intake work.

Do not create another mission or branch.

The immediate objective is to complete the actual independent evaluation pipeline and all applicable shared-core protections required to authorize N03 Batch A.

## 2. Implement the independent Oracle immediately

Start with:

`src/eval_assurance/reference/oracle.py`

Consume the pinned Batch A task specifications and handoff requirements.

Implement and qualify C01–C08.

Distinguish two independent obligations:

A. Ground-truth validity: whether the expected answer is actually correct for the task.

B. Response evaluation validity: whether the model response satisfies the independently established task truth.

Do not confuse these obligations.

For C03/C04/C05/C06, independently recompute task outcomes from the public instructions, rules and facts wherever possible.

For C08, independently verify capability matching, tool eligibility and uniqueness using the actual available task specification. Do not claim public recomputability when protected construction information is necessary.

For C01/C02/C07, independently validate construction-authored semantics, ambiguity and legitimate alternatives. Two implementations comparing against the same stored label are insufficient to establish independent ground truth.

Retain explicit NOT_EVALUABLE outcomes where semantic truth cannot be established.

Do not silently remove cases.

Preserve the exact pinned Batch A identity.

If genuine dataset defects are discovered, publish a precise correction request to the IJ-NANO lane instead of modifying its worktree.

## 3. Complete EA03–EA08

Execute the existing requirements for:

- Independent ground-truth qualification.
- Production Parser qualification.
- Independent raw-response interpretation.
- Production/reference differential verification.
- Golden Witness Library.
- Actual logic mutation testing.
- End-to-end evidence integrity.

Use the actual Batch A dataset as the primary integration target.

Retain the six historical N02RR families for EA12 historical recovery.

Execute the originally required minimum 500-control proposal with rule-complete coverage.

For every supported cognitive family, demonstrate correct and incorrect raw responses through the complete actual evaluation path.

Do not report qualification based only on isolated comparator tests.

Do not grant all-32 qualification from Batch A.

Publish precise per-case, per-primitive and per-protocol qualification coverage.

## 4. Deliver compatibility v1.1.0

Complete the previously assigned authorization separation:

- ExecutionAuthorization: before and during actual inference.
- PublicationAuthorization: after qualified evaluation and aggregation.

Execute the existing 16 authorization bypass controls.

A first physical experiment must be authorizable without fabricating previous benchmark results.

Bind authorization to actual applicable certificates, frozen roster, cognitive scope, protocol, implementation identities and current revocation state.

Publish the exact committed compatibility revision for the IJ-NANO B4/B5 integration.

Do not implement another parallel qualification authority.

## 5. Complete EA09–EA11

Implement and verify:

- Continuous production-path canaries.
- Persistent circuit breaker.
- Automatic suspension of new affected dispatch.
- Quarantine and recovery.
- Revocation.
- Qualified aggregation.
- Fail-closed publication.

Maintain the preregistered initial cadence of 25 trials or five minutes, whichever occurs first.

Measure actual detection latency and contamination windows.

Use CPU-based synthetic execution wherever possible.

## 6. Complete the shared-core acceptance

Proceed directly through:

1. Early catastrophe prevention pilot.
2. EA12 historical N02RR revalidation of all 2,184 logical slots.
3. EA14 full shared-core systemic fault containment, preserving the original 10,000 synthetic trials and 1,000 controlled fault instances.
4. Applicable EA13 Batch A qualification.
5. Applicable EA18 independent adversarial acceptance.
6. Minimum trustworthy certificate lifecycle required from EA17.

Do not delay N03 for unrelated EA15, EA16, EA17 Dashboard or EA19 extensions.

Do not weaken mandatory qualification requirements.

Do not create new infrastructure tasks unless a concrete defect blocks the current critical path.

## 7. Continuous execution

Do not stop after implementing the Oracle merely to request permission for the already authorized next task.

Continue through every independently executable critical-path phase.

Commit and publish evidence at meaningful milestones.

When a defect occurs:

Preserve → Reproduce → Root Cause → Repair → Regression → Requalification → Continue.

When an external dependency blocks one scope, continue independent work.

Do not modify the IJNANO worktree, Git index or running processes.

Use immutable committed snapshots and trusted protected-data handoffs.

## 8. Required final milestone

Report:

- Batch A cases independently qualified / 240.
- Cognitive primitives independently qualified / 8.
- Applicable protocols qualified.
- Unresolved ground-truth disagreements.
- Critical mutation escapes.
- Canary detection latency.
- Maximum observed contamination window.
- Invalid evidence admission.
- Invalid publication escapes.
- ExecutionAuthorization status.
- Shared-core acceptance.
- Exact remaining AUTH-1 and AUTH-2 blockers.

Deliver machine-readable qualification evidence consumable by the actual IJ-NANO runner.

Continue on Issue #12 and Draft PR #13.

Use pubgate, push normally and verify the exact remote SHA.

Do not merge or force-push.

The next meaningful milestone is a trustworthy, independently qualified N03 Batch A execution scope.

Scientific integrity first. Avoid unnecessary infrastructure expansion.

Execute now.
