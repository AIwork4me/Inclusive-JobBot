# IJ-EVAL-ASSURANCE-1.0 — EA02-R Contract Hardening, Wave B Independent Qualification & Wave C Continuous Protection

## 0. Mission Identity

- Repository: https://github.com/AIwork4me/Inclusive-JobBot
- Tracking Issue: #12
- Draft PR: #13
- Branch: `mission/ij-eval-assurance-1.0-systemic-evaluation-integrity`
- Audited HEAD: `3fff13535e52bd0fd9929c1ef82fd0b4208ac5a4`
- Parent mission: IJ-EVAL-ASSURANCE-1.0
- Execution strategy: CPU-first.

Act as a Principal Software Reliability Engineer, Benchmark Scientist, Formal Verification Engineer and independent adversarial reviewer.

Continue the existing mission.

Preserve completed Wave A evidence.

Do not restart the repository audit or create another mission branch.

The immediate objective is to close the remaining evaluation-contract bypasses, then establish independent qualification and continuous fault containment.

Read the original mission order, AGENTS.md, state, ledger, blockers and HANDOFF_IJEVAL.md.

Verify the actual local and remote identities before making changes.

## 1. EA02-R — Mandatory Contract Requalification

A source-level review of Wave A identified six residual concerns.

Reproduce each concern before modifying its implementation.

Do not assume that a typed interface is sufficient to enforce runtime correctness.

### EA-D01 — Qualification and eligibility bypass

Inspect:

- `src/eval_assurance/contracts/eligibility.py`
- `src/eval_assurance/contracts/validator.py`

The current statistical eligibility function does not require qualification status, publication eligibility or a valid qualification certificate.

Reproduce:

- REVOKED result remains statistically eligible.
- UNQUALIFIED result remains statistically eligible.
- PENDING result remains statistically eligible.
- Invalid state combinations bypass the central validator.
- A previously qualified result remains eligible after certificate revocation.

Implement separate eligibility concepts:

1. Diagnostic eligibility.
2. Qualified semantic-statistics eligibility.
3. Qualified business-statistics eligibility.
4. Formal publication eligibility.
5. Valid RL reward eligibility.

All formal consumers must use the relevant eligibility authority.

Formal eligibility must require the actual applicable qualification certificate and verified scope binding, not merely a caller-provided enum.

Until the complete certificate system exists, formal eligibility must fail closed.

### EA-D02 — Unsafe Boolean coercion

Inspect:

- `src/eval_assurance/contracts/legacy.py`
- `src/eval_assurance/adapters/n02rr.py`
- `EvaluationResult.evaluated()`
- Legacy export interfaces.

Reproduce behavior for:

- True.
- False.
- None.
- Missing semantic verdict.
- Strings "False", "True", "FAIL", "PASS".
- Integer 0 and 1.
- Empty and nonempty containers.
- Unknown failure classes.
- Missing error classifications.
- Contradictory HTTP or replay metadata.

Require strict runtime type validation.

Remove implicit Boolean coercion from all formal semantic-result conversion paths.

Only a genuine Boolean from a validated legacy schema may map to a decisive semantic verdict.

Malformed, unknown or ambiguous data must become NOT_EVALUABLE or a separately classified contract error.

Unknown legacy failure classes must never silently become ordinary model outcomes.

Legacy export must validate the complete record before returning a Boolean.

### EA-D03 — Illegal evaluation state combinations

Audit the full typed contract state space.

At minimum reproduce or refute:

- MODEL_OUTPUT_INVALID + CORRECT.
- NOT_EVALUABLE + ELIGIBLE.
- Qualification PENDING + ELIGIBLE.
- Business PASS + EVALUATOR_ERROR.
- Business PASS + invalid world.
- Business PASS + missing required safety verification.
- REPLAY_ERROR + decisive semantic verdict.
- ORACLE_DISAGREEMENT + formal eligibility.
- REVOKED + formal statistical eligibility.
- String or integer values substituted for Enum instances.

Separate cognitive-only and business-evaluation invariants.

Do not require irrelevant business fields for cognitive-only tasks.

Use strict runtime validation of all enum and scalar types.

Introduce systematic state-combination testing.

Use exhaustive enumeration of relevant finite dimensions, pairwise and higher-order combinations, and property-based tests where justified.

The environment currently uses stdlib unittest. Do not silently introduce an unavailable dependency.

If Hypothesis is unavailable, implement reproducible seeded generation and exhaustive bounded state checks using the standard library.

Define the expected validity rules independently from the production validator.

Do not generate expected outcomes by calling the validator under test.

Report:

- State combinations generated.
- Valid combinations.
- Invalid combinations.
- Rejected malformed types.
- Escaping invalid combinations.
- Coverage of every declared invariant.

### EA-D04 — Evidence must default to unverified

Inspect default evidence states and provenance construction.

Replace default trust with explicit unverified or pending evidence.

Evidence may become VERIFIED only after the actual verification path completes.

Require:

- Verified artifact identity.
- Actual artifact hash verification.
- Strict schema validation.
- Verified trial identity.
- Applicable experiment and evaluator identity.
- Evidence provenance verification.

Distinguish:

- Claimed provenance.
- Recorded provenance.
- Verified provenance.

Do not allow a caller-provided dictionary to overwrite verified identity fields without detection.

Bind evidence to the actual model, dataset, parser, evaluator and replay identities.

Avoid claiming complete provenance solely because several nonempty string fields exist.

Introduce a versioned verified-evidence object or equivalent validated envelope.

The supported threat model and trust boundaries must be explicit.

### EA-D05 — Mandatory formal Analyzer boundary

Inspect:

`scripts/ij_nano/n02rr_analyze.py`

The historical analyzer still reads Boolean verdicts directly.

Implement the smallest real integration boundary required to prevent formal statistics from consuming invalid results.

The full statistical Analyzer remains an EA11 deliverable.

Preserve historical analyzers and sealed output artifacts.

If legacy diagnostic tools must remain available, explicitly identify them as diagnostic-only.

Require formal aggregation and publication paths to consume validated, scope-bound records.

Do not expose an alternate formal entry point that accepts arbitrary Boolean dictionaries.

Reproduce the EA00 injected corruption:

- Original corrected corpus: 870/2184.
- One replay exception incorrectly represented as False.
- One causally inconsistent two-stage result incorrectly represented as True.
- Historical analyzer incorrectly produces 871/2186.

The qualified pipeline must:

- Preserve 870 genuine successes.
- Identify the two invalid injected records.
- Report them separately as NOT_EVALUABLE or quarantined evidence.
- Prevent a formal publication claiming the contaminated 871/2186 result.
- Preserve the original qualified corpus unchanged.

Run this regression against the actual aggregation entry point, not just the adapter.

### EA-D06 — Publication process gate enforcement

The previous session observed that piping a publication check into tail could mask its nonzero exit status.

Do not rely on persistent memory or operator discipline as the only mitigation.

Implement and test a repository-compatible publication wrapper or equivalent automated gate that:

- Captures the publication process exit code directly.
- Verifies parsed finding counts.
- Rejects missing or malformed gate output.
- Binds the check to the actual staged content identity.
- Detects staged content changes after a successful check.
- Prevents authorized publication when the gate is BLOCKED.
- Records an auditable gate result.

Where appropriate, add CI verification and a reproducible local gate entry point.

Do not install or modify hooks outside the authorized repository scope without permission.

Do not claim remote branch protection is enforced unless verified.

Inject:

- Nonzero process exit.
- Zero exit with sensitive-data findings.
- Truncated output.
- Piped command failure.
- Changed staged content after qualification.
- Missing gate receipt.

All must fail closed at the implemented publication boundary.

## 2. EA02-R Acceptance

Deliver:

- `reports/IJEVAL_02R_CONTRACT_HARDENING.md`
- `evidence/IJEVAL/EA02R/defect_ledger.json`
- Red/green reproduction evidence.
- Systematic state-space validation results.
- Legacy schema negative controls.
- Mandatory aggregation boundary tests.
- Publication bypass tests.

Grant:

`EA02R_EVALUATION_CONTRACT_INVARIANTS_GO`

only when all critical concerns are repaired or explicitly refuted.

Do not claim the entire assurance system is qualified at this stage.

## 3. Wave B — Independent Qualification

Complete EA03–EA08 according to the original mission order.

Do not reduce the original acceptance requirements.

### EA03 — Dataset and ground truth

Prioritize actual N02RR and N03 cognitive task contracts.

For every supported family:

- Independently verify expected answers.
- Establish executable positive witnesses.
- Establish critical negative witnesses.
- Verify alternative legitimate solutions.
- Reject contradictory, impossible or malformed tasks.
- Verify public task information and hidden-answer boundaries.

Where generator logic and expected-answer construction share implementation, establish independently authored checks.

Add ground-truth corruption mutants.

### EA04 — Parser semantic integrity

Qualify the complete raw-response-to-typed-action transformation.

Test:

- Duplicate keys.
- Extra fields.
- Missing fields.
- Contradictory answers.
- Negation.
- Invalid identifiers.
- Numeric and unit boundaries.
- Multiple tool calls.
- Unknown tools.
- Invalid causal sequences.

Preserve raw response evidence and every normalization.

Distinguish invalid model-generated output from parser implementation failure.

### EA05 — Independent dual-path evaluation

Implement a genuinely independent reference evaluation path.

Production path:

- Existing qualified N05AR comparators and relevant production evaluation logic.

Reference path:

- Independently authored truth tables.
- Direct executable assertions.
- Independent predicate evaluation.
- Independent numeric and unit semantics.
- Independently reconstructed state transitions.
- Bounded action-space enumeration where appropriate.

Do not call production comparator functions from the reference implementation.

Do not share a defective parser as the only interpretation path.

Provide independence evidence at the function and dependency levels.

Shared public contracts and data types are acceptable; shared decision logic requires a reduced qualification claim.

Every unresolved disagreement must become NOT_EVALUABLE.

Determine the root cause of disagreements instead of assuming one evaluator is correct.

### EA06 — Golden Witness Library

Create the proposed minimum 500 independently verified controls.

Cover:

- Every historical critical defect.
- Every supported scoring rule.
- Every supported protocol representation.
- Correct and incorrect answers.
- Valid alternatives.
- Critical boundaries.
- Software exceptions.
- Evidence corruption.
- Invalid causal traces.

Do not inflate coverage through duplicate paraphrases.

Freeze witness identities, independently verified expectations and scope bindings.

These are controls of the measurement instrument, not model benchmark trials.

### EA07 — Mutation and metamorphic verification

Reintroduce historical defects through isolated mutants.

Add new mutants corresponding to EA-D01–EA-D06.

Mandatory additional mutants:

- Remove qualification verification.
- Ignore certificate revocation.
- Restore Boolean coercion.
- Default missing evidence to VERIFIED.
- Overwrite verified provenance.
- Bypass central validation.
- Directly aggregate raw Boolean results.
- Convert Oracle disagreement to INCORRECT.
- Accept malformed enum values.

Require detection of every critical non-equivalent mutant within the declared supported scope.

Use independent metamorphic relations.

Preserve surviving mutants and their dispositions.

### EA08 — End-to-end evidence integrity

Integrate the actual pipeline:

Task → Request → Raw Response → Artifact Writer → Artifact Loader → Parser → Production Evaluator → Independent Reference Evaluator → Assurance Boundary → Analyzer.

Test both correct and incorrect witnesses through the complete pipeline.

Require strict agreement where independently verified semantics exist.

Do not label online/offline agreement alone as independent correctness.

Preserve execution identity separately from analysis identity.

Demonstrate crash recovery, exact resume, duplicate prevention and artifact corruption detection.

Verify full causal reconstruction for multi-stage traces.

Reject non-finite numeric telemetry.

Publish separate qualification certificates for supported task families and protocol scopes.

## 4. Wave C — Continuous Protection

After applicable Wave B gates qualify, implement EA09–EA11.

### EA09 — Continuous Canary

Execute mandatory controls through the same actual evaluation path as benchmark results.

Require preflight controls:

- Before every experiment.
- Before configuration changes.
- After every resume.

Initial proposed in-flight cadence:

- Every 25 trials or 5 minutes, whichever occurs first.

Include pre-seal and pre-publication controls.

Preregister the maximum detection window and account for concurrent in-flight trials.

Do not execute canaries through a privileged evaluation bypass.

Do not count controls as model benchmark observations.

### EA10 — Automatic containment

Implement a persistent, explicit circuit-breaker state machine.

Hard-stop new affected dispatch on:

- Incorrect Canary verdict.
- Oracle disagreement.
- Evaluator exception.
- Evidence corruption.
- Unexpected identity change.
- Replay divergence.
- Revoked qualification.

Preserve completed raw evidence.

Quarantine the suspected contaminated scope.

Trace dependent results and reports.

Revoke affected certificates.

Do not assume the previous successful Canary proves every earlier result was valid.

Demonstrate restart-safe quarantine and recovery.

### EA11 — Qualified Analyzer and publication

Complete the production-quality formal statistics implementation.

Every formal statistic must consume records through the mandatory assurance boundary.

Report independently:

- Planned logical slots.
- Unique physical attempts.
- Applicable trials.
- Verified evaluable trials.
- Correct trials.
- Incorrect trials.
- NOT_EVALUABLE.
- Quarantined.
- BLOCKED.
- NOT_RUN.
- Canary controls.

Always report evaluation coverage together with conditional semantic accuracy.

No unresolved critical evidence defect may enter a qualified publication.

Verify that every formal report references the exact active qualification certificate.

Use paired and task-family-aware statistics where appropriate.

Never count missing telemetry as zero.

## 5. Mandatory Early Catastrophe Prevention Test

Before moving to Wave D, execute a CPU-only pilot of the historical catastrophe.

Inject:

1. The original dictionary-unpacking defect.
2. An exception-masking defect.
3. A semantic false-positive defect.
4. A revoked-certificate defect.
5. A corrupted-reference-answer defect.
6. A direct Analyzer bypass.

Insert defects after several healthy batches have executed.

Demonstrate:

- Detection.
- Suspension of new affected dispatch.
- Quarantine.
- Publication rejection.
- Exact preservation of original evidence.
- Replay-based recovery.
- Requalification.

This is an early integration test.

It does not replace the full EA14 10,000-trial and 1,000-fault stress campaign.

Do not grant N03 full physical authorization from this pilot alone.

## 6. Cross-mission Blocker Management

Preserve IJE-B-004.

IJ-SDK D01/D02/D03 remain a separate unresolved evaluator dependency.

Do not modify PR #8 without explicit authorization.

Publish a concise technical handoff containing:

- Exact affected source revisions.
- Minimal reproductions.
- Required repairs.
- EAE compatibility requirements.
- Regression controls.
- Requalification criteria.

Do not claim that EAE automatically qualifies IJ-SDK's business Oracle.

Continue independent EAE and NanoAgent cognitive qualification work.

## 7. GitHub Delivery

Continue on the existing branch and Draft PR #13.

Update Issue #12 at every qualified milestone.

Preserve sealed evidence and historical experiment identities.

Run all relevant regression suites, including:

- tests/ij_eval_assurance
- tests/ij_nano
- Relevant IJ-SDK compatibility tests.

Report any existing dependency failures separately.

Do not suppress failures.

Use the automated fail-closed publication check.

Do not pipe gate commands in a way that hides exit status.

Push normally and verify the exact remote SHA.

Do not merge or force-push.

## 8. Execution Directive

Execute:

EA02-R → EA03–EA08 → EA09–EA11 → Early Catastrophe Prevention Test.

Then continue the original mission's Wave D:

EA12 historical revalidation, EA13 N03 qualification and EA14 full systemic fault containment.

Do not start large-scale N03 GPU measurements until the applicable evaluation scopes have passed their required gates.

Use CPU-based synthetic evidence and offline replay wherever possible.

Do not spend GPU resources to rediscover preventable scoring software defects.

Every reported PASS must bind to actual qualification evidence.

Every newly discovered defect must become a permanent regression asset.

The evaluation infrastructure must actively prevent invalid research conclusions, rather than merely provide optional validation utilities.

Scientific integrity first.

Execute now.