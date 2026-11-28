# IJ-EVAL-ASSURANCE-1.0 — Wave B/C: Independent Semantic Qualification & Trusted Assurance Boundary

## 0. Mission Identity

- Repository: https://github.com/AIwork4me/Inclusive-JobBot
- Issue: #12
- Draft PR: #13
- Branch: `mission/ij-eval-assurance-1.0-systemic-evaluation-integrity`
- Audited HEAD: `99639262e22ed5b59b42f28983c916f8b887b8b8`
- Completed: Wave A and EA02-R.
- Next: EA03–EA08, EA09–EA11, Early Catastrophe Prevention Test.

Continue the existing mission and all previously preregistered requirements.

Preserve EA02-R evidence and sealed historical experiments.

Do not restart Wave A or create another branch.

CPU-first. No large-scale GPU experiments.

The immediate objective is to prove semantic evaluation correctness independently and establish a continuously enforced, trustworthy qualification boundary.

## 1. Resume and preserve completed work

Read AGENTS.md, the mission orders, HANDOFF_IJEVAL.md, state, task ledger and blocker ledger.

Verify local and remote identities.

Run the existing regression suites.

Preserve the EA02-R state-space results:

- 9,312 enumerated combinations.
- 24 declared invariants.
- 44 malformed-type controls.
- 68 EAE tests.
- 213 NanoAgent tests.

Do not equate these results with full semantic evaluator qualification.

Keep IJE-B-004 and IJN-B-002 open unless their actual requirements are independently satisfied.

## 2. EA-R01 — Evidence-bound certificate issuance

Address within EA05–EA08, with full lifecycle completion during EA17.

Inspect `qualification/store.py`.

Reproduce or refute:

- Certificate issuance without qualification evidence.
- Empty evidence references.
- Missing or incompatible reference-evaluator identity.
- Arbitrary caller-created certificate stores.
- Unqualified scope obtaining formal eligibility through a newly issued certificate.

Separate certificate construction from trusted issuance.

Only the qualification authority may issue a usable certificate after verifying mandatory gate evidence.

Bind certificates to:

- Exact task family and evaluation scope.
- Dataset digest.
- Public task contract digest.
- Production Parser identity.
- Independent interpreter identity.
- Production Evaluator identity.
- Reference Oracle identity.
- Golden Witness suite digest.
- Mutation qualification digest.
- Replay contract.
- Applicable protocol.
- Qualification evidence.
- Limitations and revocation state.

Use actual implementation digests rather than descriptive names alone.

Reject incomplete or incompatible certificates.

A caller-provided enum or an arbitrary CertificateStore must never be sufficient to authorize a formal result.

Document the actual trust boundary and threat model.

Do not claim cryptographic security or remote enforcement unless implemented and tested.

## 3. EA-R02 — Verified evidence must establish actual provenance

Address within EA08.

Inspect `contracts/core.py` and `adapters/n02rr.py`.

Reproduce or refute:

- Matching non-hash strings accepted as SHA256.
- Caller-supplied verification flags accepted without actual artifact verification.
- Identical claimed and expected hashes supplied from the same untrusted input.
- VerifiedEvidence constructed directly without the intended verification path.
- Provenance fields overwritten before or after envelope creation.
- Mutable envelope identity or verification-check dictionaries.

Distinguish:

A. Claimed evidence.

B. Artifact actually verified by the trusted loader.

C. Verifiable transfer of previously established qualification.

The authoritative verification path must compute the artifact hash from actual bytes or validate an independently established verification receipt.

Validate digest syntax and exact identity binding.

Require strict schema and causal validation.

Do not accept arbitrary Boolean assertions as proof of completed verification.

Bind verification receipts to the specific artifact, trial, execution identity and verification implementation.

Use immutable or defensively copied evidence snapshots.

Preserve the original artifacts and qualified N02RR replay path.

## 4. EA03 — Independent ground truth

Complete the parent mission's dataset qualification requirements.

Prioritize N02RR and actual N03 cognitive task contracts.

For every supported family independently establish expected outcomes using:

- Executable reference programs.
- Independently authored truth tables.
- Constraint checking.
- Exhaustive enumeration of bounded action spaces.
- Independent state-transition verification.

Do not reuse the production expected-answer generator as the only reference authority.

Construct controls that deliberately corrupt expected answers.

The qualification engine must detect them.

Separate objective task truth from acceptable response representations.

Protect all confirmation and formal holdout answers.

## 5. EA04/EA05 — Raw-response independent dual-path evaluation

Implement two genuinely independent semantic paths for the declared supported scopes.

Production path:

Raw response → Production Parser → Production Evaluator.

Reference path:

Raw response → Independent Interpreter → Reference Oracle.

Compare:

- Parsed action identity.
- Required and additional arguments.
- Entity bindings.
- Quantities and units.
- Predicate semantics.
- Preconditions.
- State transitions.
- Multi-stage causal consistency.
- Semantic verdict.
- Business and safety verdicts where qualified.

Do not use the same Parser as the only interpretation path for both evaluators.

Do not import production semantic comparator functions into the reference evaluator.

Provide a dependency-level independence report.

List shared components and corresponding common-mode risks.

For unsupported or ambiguous interpretations, produce NOT_EVALUABLE.

For unresolved disagreement, produce ORACLE_DISAGREEMENT and quarantine the affected scope.

Do not automatically treat the reference evaluator as infallible.

## 6. EA06/EA07 — Golden Witness and actual semantic mutation coverage

Complete the original minimum 500-control proposal, subject to preregistered rule coverage.

Organize the controls by:

- Cognitive family.
- Protocol.
- Scoring rule.
- Historical defect.
- Positive and negative outcome.
- Boundary condition.
- Evidence failure.
- Causal inconsistency.

Establish expected outcomes independently before testing.

Include valid alternative solutions.

Mutate actual production logic, not only result reason codes.

Add common-mode fault injections:

- Shared Parser drops an unauthorized argument.
- Both evaluators receive a corrupted expected answer.
- Entity normalization changes identity.
- A missing predicate disappears from a typed payload.
- An incorrect stage-one action is hidden by a final response.
- Evidence is labeled VERIFIED without verification.
- Qualification is issued without supporting tests.

Require detection of all critical non-equivalent mutants within the supported qualification scope.

Report surviving mutants and unresolved risk honestly.

Do not inflate mutation or witness coverage with equivalent duplicates.

## 7. EA08 — End-to-end evidence qualification

Execute real integrated tests through:

Task → Request → Raw Response → Artifact → Trusted Loader → Production and Reference Evaluation → Typed Verdict → Assurance Boundary → Analyzer.

Require:

- Positive witnesses PASS.
- Negative witnesses receive correct failure verdicts.
- Software exceptions become NOT_EVALUABLE.
- Invalid evidence never becomes a model outcome.
- Full multi-stage reconstruction.
- Online/offline agreement.
- Independent semantic verification.
- Immutable evidence identity.
- Crash-safe persistence.
- Duplicate rejection.
- Exact resume.

Use qualified synthetic artifacts and historical raw responses.

Do not consume GPU resources for software-only checks.

Issue only scope-specific qualification evidence.

## 8. EA-R03 — Formal publication boundary hardening

Address within EA11.

Inspect `statistics/boundary.py`.

The audited implementation can assign ALLOWED whenever a certificate store exists and no rows are quarantined.

Reproduce or refute:

- Empty certificate store permits publication.
- Store with only unrelated certificates permits publication.
- Store with only revoked certificates permits publication.
- All rows are diagnostic-only yet publication is ALLOWED.
- Zero qualified rows permits formal publication.
- Missing planned trials are not detected.
- Duplicate trial identities affect the denominator.
- NOT_EVALUABLE rows containing unresolved critical defects do not block publication.
- Requested aggregation scope is not enforced.

Require the actual applicable qualification certificates.

Require exact planned-roster reconciliation.

Report every applicable planned slot, including missing and unevaluable slots.

Separate conditional semantic accuracy from evaluation coverage.

A partial qualified report is permissible only under explicit scope and coverage rules.

Never describe a partial report as full experiment closure.

Any unresolved critical evaluation-integrity fault must block formal qualification of its affected scope.

## 9. EA-R04 — Qualification revocation and time-of-check integrity

Address within EA10 and EA17.

Inspect:

- Mutable EvaluationResult objects.
- Mutable dictionaries inside frozen envelopes.
- CertificateStore persistence.
- Certificate issuance and revocation.
- Analyzer consumption.
- Publication receipts.

Test mutation after validation.

Test certificate revocation between aggregation and publication.

Test stale certificate stores, restart recovery and corrupted persistent registry data.

Test concurrent publication and qualification revocation.

Implement a versioned immutable qualification snapshot or equivalent mechanism.

Recheck applicable certificate validity and evidence identity at every formal consumption boundary.

Preserve durable revocation history.

Use atomic persistence and appropriate synchronization.

A revoked scope must not be reauthorized by stale state or by issuing an equivalent certificate without requalification.

## 10. Wave C — Continuous self-verification

Complete EA09–EA11 according to the original mission order.

Run Golden Witness canaries through the actual production evaluation pipeline.

Do not implement a separate simplified canary-only evaluation path.

Use preregistered control cadence and bounded dispatch windows.

Inject errors:

- Immediately after a successful canary.
- During normal evaluation.
- During resume.
- During aggregation.
- During publication.

Measure actual detection latency and contamination window.

Include already-dispatched concurrent trials in the accounting.

Automatically stop new affected dispatch.

Preserve raw evidence.

Quarantine affected records.

Revoke affected qualification.

Prevent formal publication.

Recover through validated replay and independent requalification.

## 11. Early Catastrophe Prevention Test

Before Wave D, demonstrate the following cases in a CPU-only integrated campaign:

1. Original dictionary-unpacking defect.
2. Exception masking.
3. Semantic false-positive defect.
4. Corrupted reference answer.
5. Forged or unsupported evidence qualification.
6. Empty or incompatible certificate store.
7. Revoked qualification.
8. Direct Analyzer bypass.

Execute these faults against the actual integrated assurance pipeline.

For each fault publish:

- Activation point.
- Detection mechanism.
- Detection latency.
- Trials dispatched after activation.
- Contamination range.
- Quarantined evidence count.
- Whether publication was blocked.
- Recovery result.
- Relevant permanent regression controls.

Require zero known critical injected defects to escape into qualified publication within the tested scope.

Do not use the early pilot as a substitute for EA14's full stress campaign.

## 12. Delivery and continuation

Continue with Issue #12 and Draft PR #13.

Update milestone status, including the EA02-R completion and scoped limitations.

Deliver an independent-evaluation report, Golden Witness coverage matrix, qualification evidence, continuous canary results and early catastrophe prevention report.

Run all relevant regression suites.

Use the new publication gate.

Verify staged content and final remote SHA.

Do not merge, force-push or modify unrelated mission branches.

Then proceed to EA12, EA13 and EA14 in the existing mission.

Do not authorize full N03 GPU execution until its actual task families and end-to-end evaluation paths have passed the required qualification and acceptance gates.

The mission succeeds when invalid evaluation results cannot silently become scientific conclusions within the qualified system boundary.

Execute now.
