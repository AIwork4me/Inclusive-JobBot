# IJ-EVAL-ASSURANCE-1.0 — N03 Batch A Intake & Execution Authorization Closure

## 0. Resume Identity

- Repository: https://github.com/AIwork4me/Inclusive-JobBot
- Owner lane: IJEVAL.
- Tracking Issue: #12.
- Draft PR: #13.
- Last audited IJEVAL HEAD: `f8acbe625bf2135aa266b20f207cf1e75516a5a3`.
- N03 owner: IJ-NANO, Issue #10, Draft PR #11.
- Latest observed IJ-NANO HEAD: `d23de5abe596e43743a5a2c7437ccd1b5e7de7f9`.
- Compatibility contract: v1.0.0.
- Current N03 authorization: AUTH-0.

Continue the existing IJEVAL mission.

Do not restart completed EA00–EA02-R or EA-R01–R04 work.

Do not create a new mission branch.

The immediate objective is to qualify the actual N03 Batch A measurement pipeline and complete the shared assurance protections required for progressive physical execution.

## 1. Consume the actual Batch A dataset immediately

The IJ-NANO lane has delivered Batch A.

Read the pinned revision:

`d23de5abe596e43743a5a2c7437ccd1b5e7de7f9`

Inspect:

- `evaluation/ij_nano/n03/taxonomy.json`
- `evidence/IJNANO/N03/dataset/build_manifest.json`
- `evidence/IJNANO/N03/dataset/verification_report.json`
- `evidence/IJNANO/N03/dataset/schema_conformance.json`
- `evidence/IJNANO/N03/dataset/slot_manifest.json`

Discover the actual committed public dataset, development expectations and qualification-package paths from the manifest and repository tree.

The delivered Batch A contains:

- C01–C08.
- 160 development cases.
- 80 protected confirmation cases.
- 240 total cases.
- Balanced Chinese and English coverage.

Expected public dataset digest:

`93c585660b756bcaa2c52f960aa276abcf12b0991103bf488cadc64c61ae99d9`

Verify actual bytes and identities.

Do not construct a competing dataset.

Do not modify the IJNANO worktree or its Git index.

Do not treat the IJ-NANO verification report as independent EAE qualification.

## 2. EA03 — Independent ground-truth qualification

Retain the six historical N02RR cognitive families as the regression and historical-recovery foundation.

Prioritize actual N03 Batch A intake in parallel.

Qualify all eight cognitive operations:

- C01 Intent classification.
- C02 Goal extraction.
- C03 Single instruction understanding.
- C04 Multiple constraint understanding.
- C05 Boolean decision.
- C06 Enumerated choice.
- C07 Natural-language action selection.
- C08 Tool-name selection.

Independently verify task semantics and expected answers.

Pay special attention to the limitations reported for C01, C02 and C07.

For construction-authored semantic labels, investigate:

- Ambiguous intent.
- Multiple legitimate goals.
- Multiple acceptable natural-language actions.
- Missing information.
- Contradictory instructions.
- Entity or label ambiguity.
- Chinese/English semantic equivalence.

Do not assume that two independently coded implementations establish independent truth if both consume the same incorrect expected labels.

Where objective truth cannot be established, require adjudication or mark the affected case NOT_EVALUABLE.

Do not silently remove difficult cases.

Verify the protected confirmation manifest without exposing protected answers to model-facing or optimizer-facing processes.

Document the actual isolation boundary.

## 3. EA04–EA05 — Independent raw-response dual-path evaluation

Implement the production and reference paths for the actual Batch A contracts.

Production:

Raw response → Production Parser → Production Evaluator.

Reference:

Raw response → Independent Interpreter → Reference Oracle.

Do not reuse production answer-generation or semantic-comparison logic in the independent reference path.

Compare:

- Semantic intent.
- Goal identity.
- Required instructions.
- Constraint satisfaction.
- Boolean decisions.
- Enumerated choices.
- Action identity.
- Tool identity.
- Valid alternatives.
- Failure classification.

Treat unresolved disagreements as NOT_EVALUABLE.

Provide an independence and common-mode risk report.

Use historical N02RR artifacts to preserve EA12 replay readiness.

## 4. EA06–EA08 — Qualification witnesses, mutation and evidence

Complete the original minimum 500-control proposal across the declared supported scopes.

Prioritize rule-complete Batch A coverage.

Include:

- Correct and incorrect raw responses.
- Legitimate alternatives.
- Contradictory answers.
- Multiple competing answers.
- Incorrect expected answers.
- Substring collisions.
- Unauthorized fields.
- Missing constraints.
- Negation.
- Invalid evidence.
- Software exceptions.

Mutate actual scoring logic.

Verify the full integrated evidence-to-verdict pipeline.

Require strict raw artifact identity, independently verified semantic outcomes and immutable evidence binding.

Do not grant all-32 cognitive qualification from Batch A results.

## 5. Separate execution authorization from publication authorization

Inspect:

`src/eval_assurance/compat/authorization.py`

The current `authorize_runner()` depends on an AggregationReport and publication verdict.

This is appropriate for post-execution authorization, but may introduce a circular dependency for the first physical benchmark.

Reproduce or refute the startup dependency problem.

Implement two distinct authorization contracts.

### A. ExecutionAuthorization

Required before GPU dispatch.

Bind:

- Authorization level: AUTH-1, AUTH-2 or AUTH-3.
- Exact cognitive primitive and protocol scope.
- Frozen trial roster digest.
- Applicable model and runtime identities.
- Dataset and evaluator identities.
- EAE compatibility version.
- Active qualification certificate digests.
- Shared-core acceptance evidence.
- Applicable EA13 and EA18 scope evidence.
- Canary readiness.
- Circuit-breaker readiness.
- Current revocation state.
- Authorized dispatch limits.

Execution authorization must not require completed results from the experiment being authorized.

It must not depend on model accuracy.

A model may perform poorly in a scientifically valid experiment.

### B. PublicationAuthorization

Required after evaluation and aggregation.

Bind:

- Actual qualified result digest.
- Planned-roster reconciliation.
- Qualified evaluation coverage.
- Independent evaluator agreement.
- Quarantine status.
- Analysis identity.
- Certificate identities and current revocation status.
- Formal publication decision.

Reuse the existing RunnerAuthorization implementation where its semantics are appropriate.

Do not silently change a published compatibility contract.

Version the affected interfaces and publish the exact integration revision.

## 6. Mandatory authorization bypass controls

Test:

1. First benchmark authorization with no existing model results.
2. Missing required shared-core qualification.
3. Wrong cognitive family.
4. Wrong protocol.
5. Modified planned roster.
6. Manually constructed AggregationReport.
7. Mutated qualified counts.
8. Empty certificate collection.
9. Untrusted certificate store.
10. Revoked certificate.
11. Stale authorization after revocation.
12. Authorization reused for a different experiment.
13. Serialized authorization with modified fields.
14. AUTH-1 used to dispatch a formal AUTH-2 benchmark.
15. AUTH-2 used to access protected confirmation execution.
16. Test-double authorization used against the physical runner.

The actual physical dispatch and publication boundaries must reject unauthorized cases.

Do not claim security merely from a private Python constructor or an unkeyed checksum.

Document the actual supported trust model.

## 7. EA09–EA11 — Continuous operational protection

Complete:

- Production-path Canary scheduler.
- Persistent circuit breaker.
- Automatic dispatch suspension.
- Quarantine.
- Recovery authorization.
- Qualification revocation.
- Qualified Analyzer.
- Publication gate.

Preserve the preregistered initial Canary cadence:

- Every 25 benchmark trials or five minutes, whichever occurs first.
- Before execution.
- Before configuration changes.
- After resume.
- Before sealing and publication.

Test stale authorization and revocation during active dispatch.

Do not permit an authorization issued before a critical fault to remain valid afterward.

## 8. Shared-core acceptance and Batch A release

Continue:

- Early catastrophe prevention pilot.
- EA12 historical N02RR revalidation.
- EA14 full shared-core fault containment.
- Applicable EA13 Batch A qualification.
- Applicable EA18 independent adversarial acceptance.
- Minimum required EA17 certificate lifecycle.

Preserve all original acceptance requirements.

Defer unrelated cross-mission integrations, Dashboard and RL extensions.

Publish machine-readable qualification evidence that the actual IJ-NANO authorization controller can independently verify.

Do not issue formal GPU authorization until the required shared-core and scoped qualification evidence exists.

## 9. Cross-session coordination

Keep strict single-writer ownership.

PR #13 owns EAE.

PR #11 owns N03 datasets and physical execution.

Exchange only pinned committed artifacts and trusted local protected-data handoffs.

Do not modify the other session's worktree, Git index or active experiment implementation.

Publish the updated compatibility contract and exact integration instructions as soon as the Batch A interfaces are ready.

## 10. Required next milestone report

Report:

- Batch A cases independently qualified / 240.
- Cognitive primitives independently qualified / 8.
- Applicable protocols qualified.
- Independent evaluator disagreements.
- Critical mutation escapes.
- Canary scheduler readiness.
- Circuit-breaker readiness.
- Execution authorization readiness.
- Publication authorization readiness.
- Shared-core acceptance status.
- Exact remaining blockers to AUTH-1 and AUTH-2.

Update Issue #12 and Draft PR #13.

Use the actual fail-closed pubgate.

Verify local and remote SHA.

Do not merge or force-push.

Continue the existing mission without unnecessary pauses.

The next meaningful milestone is a genuinely qualified N03 Batch A execution scope, not another abstract interface milestone.

Execute now.
