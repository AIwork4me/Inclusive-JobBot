# MISSION IJ-EVAL-ASSURANCE-1.0 — Systemic Evaluation Integrity & Continuous Self-verification

## 0. Mission Identity and Engineering Authority

- Repository: https://github.com/AIwork4me/Inclusive-JobBot
- Related PRs:
  - PR #6: Agentic Capability Atlas.
  - PR #8: IJ-SDK Cross-SDK Benchmark.
  - PR #9: IJ-SLM Cognitive Capability Benchmark.
  - PR #11: IJ-NANO SLM-native Agentic Runtime.
- Previously audited IJ-NANO HEAD: `bc4555ecb6db989beefaeeba452c1c160283da2c`
- Corrected N02RR replay identity: `6701a6a6a08b34d9`.
- Proposed branch: `mission/ij-eval-assurance-1.0-systemic-evaluation-integrity`.
- Primary validation environment: native Windows.
- Available physical platform: AMD Radeon RX 7900 XTX 24GB, gfx1100.
- Execution strategy: CPU-first, GPU only when necessary.
- Priority: P0 — Research Infrastructure and Scientific Integrity.

Act as a Principal Software Reliability Engineer, Benchmark Scientist, Formal Verification Engineer, Statistical Methodologist, AI Infrastructure Architect and independent adversarial reviewer.

Your responsibility is to establish a trustworthy evaluation infrastructure that prevents evaluation defects from silently contaminating model capability measurements, SDK comparisons, Runtime optimization, business qualification and future reinforcement learning.

Treat the evaluation system as a scientific measurement instrument requiring calibration, independent verification, continuous monitoring and fault containment.

The governing principle is:

**It is better to execute fewer GPU experiments than to publish thousands of scientifically invalid results.**

Execute this mission to engineering completion.

Do not stop after producing a design document, a collection of unit tests or an architectural proposal.

Implement the infrastructure, reproduce historical failures, inject new failures, demonstrate automatic containment, independently validate scoring and publish reproducible evidence.

---

## 1. North Star and Mandatory Engineering Invariants

Build a reusable Evaluation Assurance Engine, abbreviated EAE.

The EAE must support:

1. Prevention of known evaluation defects.
2. Detection of previously unseen evaluation defects within the implemented detection scope.
3. Independent verification of semantic verdicts.
4. Continuous qualification during experiment execution.
5. Automatic containment of contaminated evidence.
6. Reproducible recovery from original artifacts.
7. Fail-closed statistical analysis.
8. Scoped, evidence-bound qualification certificates.
9. Safe reward generation for future Agentic RL.
10. Long-term reuse across Inclusive-JobBot research missions.

The following invariants are non-negotiable.

### INV01 — Unknown is not incorrect

A software exception, parser crash, malformed evaluator input, missing artifact or unverifiable result must never become an ordinary model semantic failure.

### INV02 — Unknown is not correct

Missing evidence, unsupported semantics or partially evaluated output must never become a PASS.

### INV03 — Evidence integrity is not semantic correctness

A correct SHA256 proves artifact byte integrity relative to its recorded hash. It does not prove that the artifact was interpreted correctly.

### INV04 — Agreement is not truth

Online/offline agreement is necessary but insufficient when both paths share the same defective implementation.

### INV05 — No unqualified publication

No formal research conclusion may be published from an unqualified evaluation scope.

### INV06 — No hidden answer leakage

Production models, Runtime policies, optimizers and training agents must not access protected expectations, reference answers or private verification logic beyond their explicitly declared public task contracts.

### INV07 — Historical evidence is immutable

A correction must create a new analysis or experiment identity. Never silently rewrite sealed evidence.

### INV08 — Qualification is scoped

Qualification of one task family, Parser, model protocol or evaluation contract must not automatically qualify another.

### INV09 — Safety overrides performance

A business action involving unauthorized effects, violated invariants or invalid approvals cannot become successful merely because the final textual answer appears correct.

### INV10 — Failure must remain observable

Never suppress a software failure simply to keep a benchmark running.

Unexpected exceptions must stop or quarantine the affected evaluation scope.

### INV11 — Coverage is not correctness

Executing every planned trial establishes coverage, not scientific validity.

### INV12 — Qualification can be revoked

A discovered defect must invalidate the affected qualification scope and its dependent results until independently repaired and revalidated.

---

# PART I — AUDIT AND UNIFIED EVALUATION CONTRACT

## 2. EA00 — Repository Audit and Historical Evaluation Defect Inventory

Begin by inspecting the actual repository state.

Read:

- `AGENTS.md`.
- Existing mission orders.
- Mission state files.
- Task ledgers.
- Blocker ledgers.
- Handoff documents.
- Evaluation contracts.
- Benchmark runners.
- Artifact loaders.
- Replay implementations.
- Statistical analyzers.
- Business Oracles.
- AEVE-related qualification evidence.
- Publication and sensitive-data checks.

Inspect the latest remote identities of PR #6, #8, #9 and #11.

Do not assume the previous audited commits are still current.

Respect all repository rules, active worktrees, GPU leases and other mission owners.

Create a dedicated research branch from an explicitly audited compatible base.

Prefer the qualified IJ-NANO code as the initial implementation reference, but do not assume that every component is reusable without qualification.

Create a dedicated tracking issue and Draft PR for this infrastructure mission when repository permissions permit.

Do not modify, merge, force-push or rewrite unrelated active mission branches.

### 2.1 Mandatory historical defect audit

At minimum inspect the following known defect families.

| Defect family | Historical observation |
|---|---|
| Artifact loading | Persisted dictionary unpacked as tuple |
| Exception masking | Software exception converted into PARSE_INVALID |
| Semantic false negatives | 588 correct responses incorrectly classified |
| Semantic false positives | Wrong or incomplete answers accepted |
| State predicates | Missing predicates not detected |
| Predicate semantics | Expression equivalence confused with truth |
| Argument validation | Extra unauthorized arguments discarded |
| Identifier handling | Incorrect normalization and collisions |
| Unit handling | Missing units silently inherited |
| Parser ambiguity | Multiple answers resolved by candidate ordering |
| Duplicate keys | Invalid JSON or DSL silently accepted |
| Protocol mismatch | Request and response contracts incompatible |
| Tool exposure | Different experimental arms receive unequal information |
| Transaction state | Incorrect rollback or authorization behavior |
| Evidence identity | Incomplete binding of model, engine and evaluator |
| Statistics | Unmatched task sets compared directly |
| Telemetry | Missing data treated as empty or zero |
| Coverage | Duplicate, reused or inapplicable trials miscounted |

Include the known IJ-NANO defects:

- EV01–EV07.
- NA-D01–NA-D08 where relevant to evaluation.
- PR-D01–PR-D10.
- RS01–RS08.

Include relevant IJ-SLM, IJ-SDK and Atlas evaluation defects found during source inspection.

Do not blindly trust prior PASS statuses.

For every defect record:

- Defect identity.
- Affected mission.
- Exact source revision.
- Affected file and function.
- Original incorrect behavior.
- Root cause.
- Existing repair.
- Existing regression coverage.
- Residual risk.
- Applicable EAE control.
- Current verification status.

### 2.2 Mandatory N02RR residual audit

Inspect:

- `scripts/ij_nano/n02rr_replay_lib.py`.
- `scripts/ij_nano/n02r_rescore.py`.
- `scripts/ij_nano/n02rr_rescore.py`.
- Existing N02RR analyzer and qualification tests.

Investigate the remaining risk where:

```python
except Exception as e:
    replay_error = ...
    scored = None
```

is followed by:

```python
semantic_correct = False
```

when no valid score exists.

Determine whether any current or downstream analyzer can still count a replay exception as a model failure.

Also investigate whether a multi-stage causal inconsistency can retain `semantic_correct=True` while only its failure classification indicates invalid evidence.

Reproduce the actual behavior before making changes.

Do not assume that an exception classification alone makes the system fail-closed.

Deliver:

- `reports/IJEVAL_00_HISTORICAL_EVALUATION_AUDIT.md`
- `evidence/IJEVAL/EA00/historical_defect_inventory.json`
- Cross-mission evaluator inventory.
- Exact repository and dependency identities.

Gate:

`EA00_EVALUATION_BASELINE_AUDITED`

---

## 3. EA01 — Evaluation Threat Model and Failure Model

Construct a comprehensive failure model for the entire evidence-to-verdict pipeline.

Cover at least these layers:

1. Task specification.
2. Dataset generation.
3. Reference answer generation.
4. Business world initialization.
5. Task applicability.
6. Prompt rendering.
7. Model request generation.
8. Inference transport.
9. Response decoding.
10. Raw artifact capture.
11. Artifact serialization.
12. Artifact loading.
13. Parser behavior.
14. Semantic normalization.
15. Typed response construction.
16. Reference Oracle.
17. Production evaluator.
18. Business state verification.
19. Multi-stage causal reconstruction.
20. Resource accounting.
21. Trial identity.
22. Resume and deduplication.
23. Statistical aggregation.
24. Report generation.
25. Qualification issuance.
26. Reward generation.
27. Publication.

For every layer identify:

- Accidental implementation defects.
- Common-mode evaluator defects.
- False positives.
- False negatives.
- Silent data loss.
- Corrupted evidence.
- Version incompatibility.
- Hidden-answer leakage.
- Reward hacking.
- Unauthorized state effects.
- Incorrect recovery.
- Malicious or malformed inputs.

Create a Failure Mode and Effects Analysis.

Prioritize defects by:

- Severity.
- Potential affected trial count.
- Detectability.
- Recoverability.
- Downstream contamination risk.

Every critical failure mode must map to:

- Preventive control.
- Detection mechanism.
- Containment action.
- Regression test.
- Qualification requirement.

Deliver:

- `reports/IJEVAL_01_EVALUATION_THREAT_MODEL.md`
- `evidence/IJEVAL/EA01/failure_mode_matrix.json`

Gate:

`EA01_EVALUATION_FAILURE_MODEL_COMPLETE`

---

## 4. EA02 — Unified Strongly Typed Evaluation Contract

Design and implement a common versioned evaluation contract.

Reuse qualified existing components where possible.

Suggested package:

```text
src/eval_assurance/
    contracts/
    qualification/
    witnesses/
    provenance/
    parsers/
    evaluators/
    differential/
    replay/
    canary/
    circuit_breaker/
    statistics/
    publication/
    adapters/
    cli/
```

The package layout is a proposed starting point. Revise it only with documented architectural justification.

Do not build another general-purpose Agentic SDK.

### 4.1 Separate independent dimensions

The result contract must distinguish:

- Execution status.
- Evidence integrity status.
- Parser status.
- Evaluator status.
- Semantic verdict.
- Business verdict.
- Safety verdict.
- Qualification status.
- Publication eligibility.

A single Boolean must not represent all these dimensions.

Use typed enums or equivalent discriminated unions.

Suggested semantic verdict:

```python
class SemanticVerdict(Enum):
    CORRECT = "CORRECT"
    INCORRECT = "INCORRECT"
    NOT_EVALUABLE = "NOT_EVALUABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
```

Suggested evaluation integrity status:

```python
class EvaluationStatus(Enum):
    VALID = "VALID"
    ARTIFACT_ERROR = "ARTIFACT_ERROR"
    TRANSPORT_ERROR = "TRANSPORT_ERROR"
    PARSER_ERROR = "PARSER_ERROR"
    EVALUATOR_ERROR = "EVALUATOR_ERROR"
    REPLAY_ERROR = "REPLAY_ERROR"
    ORACLE_DISAGREEMENT = "ORACLE_DISAGREEMENT"
    INVALID_DATASET = "INVALID_DATASET"
    UNSUPPORTED_CONTRACT = "UNSUPPORTED_CONTRACT"
```

These are conceptual interfaces, not an instruction to duplicate existing definitions unnecessarily.

### 4.2 Invalid model output versus evaluator failure

Explicitly distinguish:

A. The model emits an answer violating a qualified output contract.

B. The Parser or Evaluator crashes or misinterprets a valid answer.

Case A may become a qualified model failure.

Case B must become NOT_EVALUABLE.

Do not conflate malformed model output with malformed evaluation artifacts.

### 4.3 Enforce valid status combinations

Examples:

- EVALUATOR_ERROR + CORRECT: invalid.
- REPLAY_ERROR + INCORRECT: invalid.
- Missing mandatory provenance + qualified semantic verdict: invalid.
- Invalid business world + published business PASS: invalid.
- Oracle disagreement + qualified conclusion: invalid.

Implement a central validator that rejects illegal combinations before persistence, aggregation or publication.

Do not rely only on developer discipline.

### 4.4 Compatibility

Existing Boolean `semantic_correct` fields may be supported through explicit legacy adapters.

A legacy Boolean must never silently erase NOT_EVALUABLE.

If a legacy consumer cannot represent the new status, fail closed rather than automatically mapping it to False.

### 4.5 Metric eligibility

Define an explicit derived eligibility function:

```python
eligible_for_semantic_statistics(result)
```

The Analyzer must use this contract.

Do not allow every caller to independently decide which rows are valid.

Deliver:

- Versioned contract specification.
- Implementation.
- Compatibility adapters.
- Contract tests.
- Invalid-state mutation tests.

Gate:

`EA02_TYPED_EVALUATION_CONTRACT_GO`

---

# PART II — INDEPENDENT QUALIFICATION

## 5. EA03 — Dataset and Ground Truth Qualification

Build a reusable Dataset Qualification Engine.

Every dataset family must be qualified before physical benchmark execution.

### 5.1 Required task contract

Every task must define:

- Unique task identity.
- Task family.
- Task version.
- Public input.
- Required capabilities.
- Allowed operations.
- Business world identity.
- Relevant constraints.
- Semantic expectations.
- Valid alternative solutions.
- Negative cases.
- Evaluation scope.
- Applicability.
- Source and licensing provenance.

### 5.2 Ground truth independence

Reference answers must be independently established.

Preferred sources:

- Executable deterministic reference programs.
- Independently specified business-state invariants.
- Formally defined predicates.
- Exhaustive enumeration for bounded tasks.
- Independently authored truth tables.
- Verified reference execution.
- Human expert review when required and genuinely available.

Do not treat output from the model being evaluated as ground truth.

Do not use the same generator function to produce both the test answer and the only verification logic without independent checks.

### 5.3 Dataset qualification tests

For each family verify:

- At least one executable correct witness.
- Critical incorrect witnesses.
- Alternative valid representations.
- Contradictory answers.
- Ambiguous tasks.
- Impossible tasks.
- Missing prerequisites.
- Invalid initial states.
- Unauthorized actions.
- Incorrect reference answers.
- Hidden-answer leakage.
- Train/dev/confirmation/holdout overlap.

Where a task intentionally requires clarification or abstention, qualify that behavior as an explicit valid outcome.

### 5.4 Dataset mutations

Inject:

- Flipped expected answers.
- Incorrect entity IDs.
- Wrong units.
- Missing constraints.
- Contradictory policies.
- Unreachable goals.
- Invalid tool prerequisites.
- Incorrect initial states.

The qualification engine must reject these when they violate the declared task contract.

Do not claim universal dataset correctness from successful checks of a few sample tasks.

Require per-family and per-task qualification evidence where applicable.

Gate:

`EA03_DATASET_QUALIFICATION_GO`

---

## 6. EA04 — Parser Semantic Integrity

Build a Parser Qualification Framework.

The central principle:

The Parser may translate representations into typed values, but must not silently repair an incorrect answer into a correct answer.

Mandatory coverage:

### Structured responses

- Valid JSON.
- Invalid JSON.
- Duplicate keys.
- Unknown fields.
- Missing fields.
- Unexpected nested fields.
- Wrong data types.
- Non-finite numeric values.
- Invalid units.
- Overflow and range violations.
- Unsupported schemas.
- Extra consequential arguments.

### Closed-vocabulary responses

- Exact identifiers.
- Declared aliases.
- Multiple candidate answers.
- Contradictory answers.
- Negation.
- Leading zeros.
- Case-sensitive identifiers.
- Unicode variations.
- Substring collisions.

### Tool calls

- Wrong tool name.
- Wrong parameter.
- Missing required argument.
- Extra argument.
- Multiple unexpected calls.
- Duplicate calls.
- Invalid call ordering.
- Incorrect tool-call identity.

### Multi-stage responses

- Invalid stage-one selection.
- Stage-two response inconsistent with stage-one selection.
- Missing stage.
- Unexpected stage.
- Hidden wrong actions.
- Wrong causal parent.
- Incomplete execution.

### Free-form responses

Use strictly defined extraction contracts.

Do not treat an arbitrary occurrence of an expected string as semantic correctness.

When a response cannot be interpreted reliably, distinguish between:

- A qualified invalid model output.
- An unsupported representation.
- A limitation of the Parser.

Maintain complete raw response provenance.

Record every normalization.

Never allow discarded fields to disappear from audit evidence.

Gate:

`EA04_PARSER_SEMANTIC_INTEGRITY_GO`

---

## 7. EA05 — Independent Dual-path Evaluation

Implement two independent evaluation paths for supported deterministic scopes.

### Path A — Production Evaluator

Use the actual evaluator intended for benchmark execution.

It may reuse:

- Qualified N05AR cognitive comparators.
- Qualified business Oracle components.
- Existing typed semantic contracts.

### Path B — Independent Reference Evaluator

Implement a separately derived reference checker from the public task contract and independently specified expected behavior.

Prefer:

- Direct executable assertions.
- Independent truth tables.
- Reference state transitions.
- Exhaustive search over bounded action spaces.
- Independent arithmetic and predicate logic.
- Constraint checking.
- Independent business postcondition verification.

### 7.1 Avoid common-mode failures

The reference evaluator must not merely call the production evaluator under another name.

Do not share:

- Core semantic comparator implementations.
- Decision branches that implement the same business rule.
- The same normalization helper when that helper is under test.
- Expected-answer generators without independent verification.
- The same Parser as the only interpretation path for raw-response qualification.

Shared data types may be acceptable.

Shared semantic implementations require explicit justification and a corresponding reduction in the claimed independence scope.

Document which components are truly independent and which remain shared.

### 7.2 Differential verification

Compare:

- Semantic verdict.
- Parsed action identity.
- Arguments.
- Entity binding.
- Numeric values and units.
- Preconditions.
- State transitions.
- Final business state.
- Safety invariants.
- Failure reasons.

An unexplained disagreement must produce:

`ORACLE_DISAGREEMENT`

The affected result becomes NOT_EVALUABLE pending investigation.

Do not automatically assume that the production evaluator or reference evaluator is correct.

A second evaluator is not necessarily a correct evaluator.

### 7.3 Human and AI review

Use human adjudication for cases where a deterministic independent reference cannot establish truth.

If human reviewers are unavailable, record that limitation.

AI-generated review may help discover defects but must not be described as independent human validation.

For LLM-judged subjective tasks, maintain a separate qualification scope including disagreement, calibration, rubric validity and uncertainty.

Do not claim deterministic business truth from an LLM judge alone.

Deliver:

- Production/reference evaluator interfaces.
- Independence analysis.
- Differential comparison engine.
- Disagreement ledger.
- Scope-specific qualification evidence.

Gate:

`EA05_INDEPENDENT_DIFFERENTIAL_EVALUATION_GO`

---

## 8. EA06 — Golden Witness Library

Create an immutable, versioned Golden Witness Library.

A Golden Witness is a controlled raw response or execution trace whose expected verdict is independently established before being evaluated.

Include:

- Correct model responses.
- Incorrect model responses.
- Correct alternative solutions.
- Invalid structural outputs.
- Semantically incorrect but structurally valid answers.
- Valid tool-call-only responses.
- Empty responses.
- Transport failures.
- Parser exceptions.
- Evaluator exceptions.
- Corrupted artifacts.
- Multi-stage inconsistencies.
- Business-state violations.

### Initial proposed minimum coverage

- At least 500 qualified controls for the core supported evaluation scopes.
- At least one correct and one incorrect witness for every supported scoring rule.
- At least one boundary witness for every relevant boundary condition.
- At least one control for every historical critical defect.
- Both Chinese and English where language affects interpretation.
- All relevant protocol response shapes.

The 500-control minimum is a proposed engineering budget. Preregister the exact coverage matrix and expand it when required.

Control counts do not replace rule coverage.

Do not inflate coverage through duplicate paraphrases.

### Independence requirements

Golden Witnesses must be:

- Frozen before qualification.
- Independently checked.
- Version-bound.
- Protected against accidental modification.
- Separated from formal benchmark holdouts.

Do not evaluate the tested model on Golden Witnesses as if they were normal benchmark trials.

They are controls of the measurement instrument.

Gate:

`EA06_GOLDEN_WITNESS_LIBRARY_QUALIFIED`

---

## 9. EA07 — Mutation and Metamorphic Verification

Build a permanent Mutation Testing framework.

### 9.1 Historical mutants

Reintroduce historical defects deliberately in isolated test implementations.

Mandatory mutants include:

- Dictionary unpacking instead of keyed artifact loading.
- Exception converted to model failure.
- Unknown result converted to PASS.
- Missing predicate ignored.
- Extra argument discarded.
- Wrong inequality operator.
- Identifier substring matching.
- Wrong unit accepted.
- Duplicate JSON key accepted.
- Contradictory answer accepted.
- Wrong stage-one selection hidden by stage two.
- Missing evidence accepted.
- Hash mismatch ignored.
- Duplicate trial counted twice.
- Missing telemetry converted to zero.
- Unmatched task populations compared.
- Revoked qualification ignored.

Do not merely remove final reason codes.

Mutate the actual logic that implements the scoring rule.

### 9.2 Additional mutants

Create new mutants representing plausible undiscovered failures:

- Off-by-one errors.
- Boundary-condition mistakes.
- Boolean coercion.
- Wrong entity association.
- Incorrect state version.
- Incorrect trial join.
- Wrong evaluator version.
- Incorrect cache reuse.
- Truncated artifact.
- Inconsistent endpoint identity.
- Reversed expected label.
- Wrong denominator.
- Missing safety check.
- Fail-open exception handling.

### 9.3 Metamorphic tests

Verify relations that must hold across transformed cases.

Examples:

- Reordering an unordered predicate set preserves the verdict.
- Changing a required argument changes the verdict when it violates the contract.
- Permitted equivalent units preserve meaning.
- Irrelevant metadata does not alter semantic correctness.
- Equivalent authorized execution paths preserve business correctness.
- Changing an entity to an unauthorized entity must not preserve PASS.
- Removing required evidence must revoke evaluation eligibility.
- Duplicating a result must not alter qualified unique coverage.
- Changing the evaluator version must invalidate the old certificate binding.

Only assert transformations whose semantics are independently justified.

### Acceptance

Require:

- 100% detection of critical non-equivalent historical mutants.
- 100% detection of critical non-equivalent new mutants.
- Explicit disposition of surviving and equivalent mutants.
- Zero unresolved critical false positives.
- Zero unresolved critical false negatives.

Report mutation coverage by scoring rule and failure class.

Do not claim that surviving no tested mutants proves the absence of all software defects.

Gate:

`EA07_MUTATION_AND_METAMORPHIC_ASSURANCE_GO`

---

# PART III — CONTINUOUS SELF-VERIFICATION

## 10. EA08 — End-to-End Evidence and Replay Integrity

Extend the qualified N02RR evidence recovery architecture.

Create one authoritative validation path for:

Raw API Response → Artifact Writer → Artifact Loader → Parser → Evaluator → Result Record → Analyzer → Report.

### Mandatory evidence identity

Bind:

- Experiment identity.
- Trial identity.
- Task identity.
- Model weights.
- Quantization.
- Runtime configuration.
- Engine binary and relevant libraries.
- Backend.
- Physical device identity where applicable.
- Request renderer.
- Actual request.
- Chat Template.
- Parser version.
- Evaluator version.
- Reference evaluator version.
- Dataset.
- Execution budgets.
- Decoding settings.
- Evidence schema.
- Analyzer version.

Separate execution identity from analysis/replay identity.

An evaluator correction must not create the false impression that a new physical inference attempt occurred.

### Mandatory artifact controls

- Complete sanitized raw response.
- Strict schema validation.
- SHA256 verification.
- Trial identity validation.
- Stage count and order.
- Endpoint consistency.
- Causal event parents.
- Finite resource values.
- Provenance binding.
- Atomic publication.
- Duplicate detection.
- Resume validation.

Missing or corrupted evidence must not enter ordinary semantic scoring.

### Replay verification

Require:

- Original and replayed typed payload agreement.
- Original and replayed semantic verdict agreement for unchanged implementations.
- Corrected verdict differences explicitly recorded after evaluator repair.
- Full multi-stage reconstruction.
- Independent reference verification of selected witnesses.

Use separate immutable replay identities.

Never silently replace historical results.

### Recovery tests

Simulate:

- Process crash during artifact writing.
- Process crash during scoring.
- Interrupted result publication.
- Partial JSONL record.
- Incorrect resume.
- Duplicate replay.
- Changed evaluator identity.
- Changed model identity.
- Missing artifact.
- Corrupted checkpoint.

Gate:

`EA08_END_TO_END_EVIDENCE_INTEGRITY_GO`

---

## 11. EA09 — Continuous Canary Self-verification

This is a central deliverable of the mission.

The evaluation system must verify itself before, during and after large-scale experiments.

### 11.1 Preflight canaries

Before an experiment starts:

- Validate all required qualification certificates.
- Verify implementation hashes.
- Execute protocol-specific positive witnesses.
- Execute critical negative witnesses.
- Execute evidence-integrity controls.
- Verify production/reference evaluator agreement.

If any mandatory control fails, do not start the affected experiment.

### 11.2 In-flight canaries

Inject evaluation controls through the same actual scoring and aggregation pipeline used by benchmark trials.

Use both:

A. Known-correct raw evidence that must PASS.

B. Known-incorrect raw evidence that must receive its designated verdict and reason.

Also include:

- Parser failure controls.
- Artifact failure controls.
- Oracle disagreement controls.
- NOT_EVALUABLE controls.
- Multi-stage controls where applicable.

The canaries must not use a special bypass path that avoids production evaluation logic.

### 11.3 Suggested initial cadence

Preregister a bounded cadence such as:

- Before every new experiment.
- Before every model/protocol/evaluator configuration change.
- After every resume.
- Every 25 benchmark trials or every 5 minutes, whichever occurs first.
- Before each batch is sealed.
- Before final publication.

Adjust cadence based on measured risk and overhead.

Do not weaken the maximum undetected contamination window merely to increase throughput.

The above cadence is an initial engineering proposal, not a pre-existing repository policy.

### 11.4 Blind control placement

Where practical:

- Randomize witness selection.
- Rotate controls.
- Prevent the production evaluator from selecting an alternate code path based on a visible Canary marker.
- Keep expected verdicts inaccessible to the tested model and production scoring path.

Control metadata remains available to the independent assurance layer.

### 11.5 Accounting

Canaries are not model benchmark trials.

Exclude them from:

- Model success rates.
- Formal benchmark denominators.
- Model performance rankings.
- Training examples unless separately authorized.

Report assurance overhead separately.

Gate:

`EA09_CONTINUOUS_SELF_VERIFICATION_GO`

---

## 12. EA10 — Automatic Circuit Breaker and Quarantine

Implement a deterministic evaluation circuit breaker.

Suggested states:

```text
UNQUALIFIED
    -> PREFLIGHT
    -> RUNNING
    -> PAUSED
    -> QUARANTINED
    -> ROOT_CAUSE_ANALYSIS
    -> REQUALIFYING
    -> RUNNING
    -> SEALED
```

Transitions must be explicit, auditable and version-bound.

### 12.1 Mandatory hard-stop triggers

Immediately stop authorizing new affected trials when:

- A Golden Witness receives an incorrect verdict.
- A critical mutant unexpectedly survives.
- Production and reference evaluators disagree.
- An unexpected evaluator exception occurs.
- Artifact schema validation fails.
- Evidence identity changes unexpectedly.
- Online/offline replay diverges.
- A revoked certificate is detected.
- An unauthorized state effect is discovered.
- A report attempts to consume invalid evidence.

Do not forcibly kill unrelated processes.

Allow safe bounded completion or cancellation of already dispatched work according to the host-wide resource protocol.

### 12.2 Contamination window

Maintain the last independently verified checkpoint.

When a defect is detected:

1. Stop or pause the affected execution scope.
2. Preserve all original evidence.
3. Mark results since the last trusted checkpoint as provisionally quarantined.
4. Investigate whether the actual contamination began earlier.
5. Trace all dependent summaries, reports and optimization decisions.
6. Revoke affected certificates.
7. Publish the exact suspected and confirmed contamination boundaries.

Do not assume the last successful Canary proves that all earlier trials are correct.

A defect may affect task families that previous canaries did not exercise.

### 12.3 Anomaly detection

Add diagnostic detectors for:

- All trials suddenly receiving the same verdict.
- Abnormal increases in PARSE_INVALID.
- Identical failure distributions across unrelated models.
- Sudden loss of telemetry.
- Unexpected constant field values.
- Sharp accuracy changes after an evaluator update.
- Abnormal protocol-specific failure patterns.
- Unexpected denominator changes.

An anomaly is a trigger for investigation, not proof of evaluator error.

Do not rewrite valid scientific results merely because they are unusual.

A genuinely weak model may correctly fail every trial.

Use distribution alerts alongside independent controls.

### 12.4 Recovery authorization

Resume only when:

- Root cause is identified or the remaining uncertainty is explicitly isolated.
- Affected scope is known.
- Repair is independently validated.
- Historical defect reproduction is preserved.
- Regression tests pass.
- Qualification is reissued.
- Affected evidence is re-scored or re-executed as necessary.
- The resume point is verified.

No manual status edit may bypass a mandatory gate.

Gate:

`EA10_FAIL_CLOSED_CIRCUIT_BREAKER_GO`

---

## 13. EA11 — Statistical and Publication Integrity

Implement a Qualified Result Analyzer.

No formal Analyzer may directly consume unqualified benchmark rows without validation.

### 13.1 Denominator reconciliation

Distinguish:

- Planned logical slots.
- Applicable slots.
- Physical attempts.
- Unique executed trials.
- Reused physical evidence.
- Qualified evaluable trials.
- Correct trials.
- Incorrect trials.
- NOT_EVALUABLE trials.
- Inapplicable trials.
- Quarantined trials.
- Blocked trials.
- NOT_RUN trials.
- Canary controls.

Never count reused trials as independent observations.

### 13.2 Required metrics

Report separately:

```text
Evaluation coverage =
    qualified evaluable trials / applicable planned trials

Conditional semantic accuracy =
    correct qualified trials / qualified evaluable trials

Verified success coverage =
    correct qualified trials / applicable planned trials
```

These metrics answer different questions.

Always publish the numerator and denominator.

Do not report conditional accuracy alone when evaluation coverage is incomplete.

Do not silently remove failed or unevaluable cases to inflate accuracy.

### 13.3 Uncertainty and incomplete evidence

Where appropriate, report lower and upper outcome bounds reflecting unevaluable trials.

Do not claim that missing evidence is random without justification.

If a qualification scope has unresolved critical evidence failures, the scope must remain unqualified.

### 13.4 Matched comparisons

Require:

- Identical applicable task populations.
- Correct pairing.
- Frozen comparison identities.
- Paired confidence intervals where appropriate.
- Task-family and business-world clustering where relevant.
- Multiple-comparison handling.
- Preserved failed and blocked comparisons.

Do not interpret overlapping confidence intervals as proof of equivalence.

Do not treat repeated seeds or paraphrases as independent task worlds.

### 13.5 Resource metrics

Never convert unavailable telemetry to zero.

For every mean or percentile report:

- Actual measurement count.
- Missing count.
- Applicable scope.
- Field semantics.

For multi-stage execution, report complete resource totals only when every required stage is measured.

Otherwise report partial totals with explicit coverage or UNAVAILABLE.

### 13.6 Publication gate

Formal reports must bind:

- Dataset qualification.
- Evaluator qualification.
- Parser qualification.
- Reference evaluator scope.
- Replay qualification.
- Canary history.
- Circuit-breaker state.
- Evidence integrity.
- Statistical analysis identity.

If any required certificate is missing, incompatible or revoked:

`PUBLICATION_BLOCKED`

Separate diagnostic reports from formal qualified conclusions.

Gate:

`EA11_QUALIFIED_STATISTICS_AND_PUBLICATION_GO`

---

# PART IV — HISTORICAL RECOVERY AND REAL PROJECT INTEGRATION

## 14. EA12 — Historical Defect Regression and Evidence Revalidation

Use previously published historical evidence as a mandatory regression corpus.

### Primary corpus

N02RR corrected evidence:

- Physical experiment: `ec5b95357e960f99`.
- Source experiment: `7a1b9d7d160202d8`.
- Diagnostic experiment: `36bfed1d55a9987b`.
- Corrected replay: `6701a6a6a08b34d9`.

Revalidate all 2,184 logical slots through the new EAE interfaces.

Expected historical reconciliation:

- 1,397 affected offline-scored rows.
- 588 corrected false negatives.
- 0 corrected false positives.
- 787 unaffected physical rows.
- 870 corrected semantic PASS.

These are historical reference results, not answers that the new evaluator is required to reproduce regardless of evidence.

If independently qualified evaluation finds a discrepancy, preserve it and investigate.

Do not tune the new evaluator merely to reproduce the previous headline.

### Additional historical corpora

Inspect available IJ-SLM, IJ-SDK and Atlas artifacts.

Prioritize evidence associated with previously identified scoring defects.

For each historical corpus determine:

- Complete replay possible.
- Partial replay possible.
- Diagnostic only.
- Evidence insufficient.
- Re-execution necessary.

Do not make historical results formally qualified merely by wrapping them in EAE.

### Cross-mission impact

Produce an impact report identifying:

- Which existing conclusions remain valid.
- Which require reevaluation.
- Which require stronger qualification.
- Which require physical re-execution.

Do not alter other active PRs without authorization.

Gate:

`EA12_HISTORICAL_EVALUATION_REGRESSION_GO`

---

## 15. EA13 — N03 C01–C32 Cognitive Evaluation Qualification

This is the first mandatory real integration target.

Read the original C01–C32 taxonomy from the existing IJ-NANO mission order.

Do not invent a replacement taxonomy.

Qualify all 32 cognitive primitives required by N03.

Preserve the original minimum dataset requirements:

- 640 development cases.
- 320 reserved confirmation cases.

Use per-family evaluation contracts rather than one generic score for every capability.

### For each primitive establish

- Exact cognitive operation.
- Task specification.
- Output contract.
- Expected semantic behavior.
- Independent reference implementation.
- Golden Witnesses.
- Critical negative controls.
- Mutation tests.
- Applicable protocols.
- Required raw evidence.
- Failure taxonomy.
- Qualification certificate.

For planning and recovery, use actual executable state and dependency verification wherever possible.

Do not treat a valid-looking plan as proof that the plan is executable.

### Holdout protection

The EAE qualification process may validate the protected dataset through a separate trusted process.

The Runtime designer, optimizer and model-facing components must not gain access to protected reference answers.

Access boundaries must be enforced, not merely described.

### Physical integration smoke

After software qualification:

- Acquire the existing host-wide GPU lease.
- Use the pinned qualified llama.cpp engine.
- Use approved model assets.
- Verify actual physical GPU identity.
- Run a small preregistered representative physical panel.
- Verify raw evidence capture and exact replay.
- Verify production/reference evaluator agreement.
- Inject assurance controls into the actual execution path.
- Demonstrate automatic pause after a synthetic evaluation fault.

Use MiniCPM5-2B, LFM3-1.7B and Qwen3.5-2B where available and applicable.

Model failure on a physical smoke task is an acceptable research observation.

Evaluator failure is a qualification failure.

Do not require every model response to be correct as a condition for evaluator qualification.

### N03 release decision

Allow formal N03 GPU execution only for cognitive scopes whose required EAE controls qualify.

Unqualified cognitive primitives remain BLOCKED.

Do not allow one qualified primitive to grant qualification to the other 31.

Gate:

`EA13_N03_COGNITIVE_EVALUATION_QUALIFIED`

---

## 16. EA14 — Fault Injection and Systemic Stress Testing

Demonstrate that the EAE prevents large-scale evaluation contamination under realistic failure conditions.

### 16.1 Fault-injection categories

Inject failures in:

- Task construction.
- Ground truth.
- Parser logic.
- Evaluator logic.
- Artifact serialization.
- Artifact loading.
- Replay.
- Identity binding.
- Checkpoint recovery.
- Canary execution.
- Statistics.
- Publication.
- Reward generation.
- Concurrency.

Inject failures:

- Before experiment execution.
- At a random trial within a batch.
- Immediately before a Canary.
- Immediately after a Canary.
- During resume.
- During result sealing.
- During report generation.

### 16.2 Mandatory campaign A — Reproduce the 1,397-row historical catastrophe

Create a CPU-only synthetic benchmark campaign reproducing the conditions that caused the N02R catastrophe.

Inject the original dictionary-unpacking defect.

Verify:

- The fault is detected.
- The pipeline cannot silently classify every result as a model failure.
- New trial dispatch stops at the applicable circuit-breaker boundary.
- Suspect evidence is quarantined.
- Formal publication is blocked.
- Original evidence is preserved.
- Recovery restores valid verdicts.

Repeat with:

- An exception-masking mutant.
- A semantic false-positive mutant.
- A ground-truth corruption mutant.
- An Analyzer that ignores qualification metadata.

### 16.3 Mandatory campaign B — Large synthetic execution

Run at least 10,000 logical synthetic benchmark trials as a proposed initial stress budget.

Use CPU-based fixtures wherever possible.

Inject at least 1,000 controlled fault instances across the supported failure classes.

Include multiple independent fault seeds and scheduling conditions.

Preregister coverage and avoid counting repeated equivalent mutations as distinct defect classes.

### 16.4 Required measurements

Measure:

- Fault detection rate.
- Critical fault escape rate.
- False alarm rate.
- Detection latency.
- Trials dispatched after fault activation.
- Contamination window.
- Number of quarantined trials.
- Recovery success.
- Incorrect verdicts entering qualified statistics.
- Incorrect verdicts entering formal publication.
- Assurance CPU overhead.
- Storage overhead.
- Execution overhead.

### Acceptance criteria

For critical injected faults within the qualified detection scope:

- Zero erroneous qualified publications.
- Zero known invalid rows entering qualified statistics.
- Zero silent conversion of evaluator failures into ordinary model failures.
- Every detected fault receives an auditable disposition.
- Contamination remains recoverable from preserved evidence.
- Detection occurs within the preregistered applicable bound.

A zero observed escape count applies only to the tested fault population.

Report uncertainty and residual untested risks.

Do not claim that all future bugs have been eliminated.

Gate:

`EA14_SYSTEMIC_FAULT_CONTAINMENT_GO`

---

## 17. EA15 — Cross-Mission Integration Contracts

Build lightweight integration adapters for:

### IJ-SLM

- Tool-call evaluation.
- Planning evaluation.
- Multi-tool execution.
- Cognitive capability measurement.
- Model Passport generation.

### IJ-SDK

- Cross-SDK experiment fairness.
- Native versus assisted execution.
- Gateway and business-state verification.
- Matched SDK comparisons.

### IJ-NANO

- Protocol comparisons.
- Cognitive primitives.
- Runtime mechanism ablations.
- Model × Harness transfer experiments.

### IJ-ADAPTER

- Training environment qualification.
- Trajectory verification.
- Reward correctness.
- Learnability evaluation.
- Adapter transfer comparisons.

### JobBot

- Business result correctness.
- Authorization.
- Transaction safety.
- Goal completion.
- Human approval requirements.
- End-to-end qualification.

Implement common contracts and compatibility tests.

Do not duplicate complete evaluators for every mission.

Do not assume that an existing evaluator can inherit a new qualification certificate automatically.

Publish an integration readiness matrix:

- SUPPORTED.
- ADAPTER_READY.
- QUALIFIED.
- PARTIAL.
- BLOCKED.
- NOT_RUN.

Avoid interfering with other missions currently running on different hardware or branches.

Prepare small reviewable integration patches or documented pinned dependency consumption instructions.

Do not merge those changes into other mission branches without authorization.

Gate:

`EA15_CROSS_MISSION_ASSURANCE_INTERFACES_READY`

---

# PART V — FUTURE TRAINING AND LONG-TERM RESEARCH VALUE

## 18. EA16 — Reinforcement Learning Reward Assurance

Prepare the foundation for future harness-native post-training inspired by the Hugging Face Harness Adapter research.

Do not start model training in this mission.

The objective is to ensure that a future reward function cannot silently inherit a benchmark evaluation defect.

### 18.1 Reward contract

Distinguish:

- Valid successful execution.
- Valid unsuccessful execution.
- Unsafe or unauthorized execution.
- Environment failure.
- Evaluator failure.
- Missing evidence.
- Unresolved Oracle disagreement.

A failed evaluator must not automatically generate reward zero or a negative reward as though the model performed incorrectly.

Return an explicit invalid-reward status.

The trainer must reject or quarantine the affected rollout.

For group-relative methods such as GRPO, define how invalid rollouts affect the eligibility of the whole rollout group.

Do not silently substitute rewards, change group composition or bias the training distribution.

### 18.2 Verified environment controls

Require:

- Correct reference execution obtains the expected maximum correctness reward.
- No-op execution cannot obtain success reward when action is required.
- Known incorrect execution cannot obtain success reward.
- Unauthorized execution cannot obtain success reward.
- Legitimate alternative solutions are accepted.
- Replay yields consistent rewards.
- Incorrect evaluator mutations are detected.

### 18.3 Reward hacking tests

Investigate:

- Model attempts to read hidden expected answers.
- Attempts to modify verification files.
- Forged tool results.
- Fabricated final-state evidence.
- Premature termination.
- Skipping required approvals.
- Excessive retries.
- Manipulating reported token counts.
- Reward obtained without actual business execution.

Efficiency rewards must be subordinate to correctness and safety.

Necessary clarification and authorization must not be penalized as undesirable behavior.

### 18.4 Training-grade qualification

Define compatibility requirements for:

- OpenEnv-style environment contracts.
- Harness-in-the-loop training.
- TRL/GRPO rollout integration.
- Training-grade trajectories.

Keep unavailable training-grade fields explicitly unavailable.

Do not label evaluation-grade traces as fully qualified RL trajectories.

Publish a reward qualification interface and synthetic tests.

Gate:

`EA16_RL_REWARD_ASSURANCE_CONTRACT_READY`

This gate does not imply a trained model or qualified physical RL platform.

---

## 19. EA17 — Assurance Dashboard and Operational CLI

Build a usable operational interface for engineers.

Suggested commands:

```text
python -m eval_assurance audit
python -m eval_assurance qualify-dataset
python -m eval_assurance qualify-parser
python -m eval_assurance qualify-evaluator
python -m eval_assurance run-canaries
python -m eval_assurance compare-oracles
python -m eval_assurance replay
python -m eval_assurance verify-batch
python -m eval_assurance inject-faults
python -m eval_assurance quarantine
python -m eval_assurance impact
python -m eval_assurance requalify
python -m eval_assurance status
python -m eval_assurance verify-publication
```

The exact CLI can be adjusted to existing repository conventions.

Every command must be real and tested.

### Dashboard requirements

Display:

- Current evaluation contract version.
- Qualified task families.
- Parser versions.
- Evaluator versions.
- Independent reference scopes.
- Golden Witness coverage.
- Mutation coverage.
- Canary status.
- Last trusted checkpoint.
- Quarantined evidence.
- Open disagreements.
- Historical false-positive/false-negative findings.
- Evidence-valid coverage.
- Publication eligibility.
- Outstanding blockers.
- Current assurance certificates.

Include exact evidence links.

Never use green indicators for NOT_RUN, UNKNOWN or BLOCKED.

### Qualification certificate

Implement a machine-readable certificate binding:

- Qualification scope.
- Dataset identity.
- Parser identity.
- Evaluator identity.
- Reference evaluator identity.
- Replay identity.
- Applicable protocols.
- Control suite identity.
- Mutation coverage.
- Known limitations.
- Qualification time.
- Revocation status.

Changed implementations must invalidate incompatible certificates.

Certificates are evidence-bound records, not guarantees against all future bugs.

Gate:

`EA17_ASSURANCE_OPERATIONS_READY`

---

# PART VI — INDEPENDENT ACCEPTANCE

## 20. EA18 — Independent Adversarial Review

Perform a clean-checkout acceptance campaign.

Do not review only the code written in the current development session.

### Review strategy

Where feasible:

- Use a separate reviewer context.
- Derive tests independently from the contracts.
- Inspect actual artifact and verdict schemas.
- Review historical defect reproductions.
- Challenge expected answers.
- Inject previously unseen faults.
- Audit Analyzer eligibility filters.
- Attempt to bypass qualification checks.
- Attempt to reuse revoked certificates.
- Verify actual fail-closed behavior.

Do not claim a human review occurred unless it actually occurred.

### Mandatory bypass challenges

Attempt to:

1. Convert NOT_EVALUABLE into INCORRECT.
2. Convert NOT_EVALUABLE into CORRECT.
3. Publish without a qualification certificate.
4. Publish using an incompatible certificate.
5. Publish using a revoked certificate.
6. Reintroduce a historical Parser defect.
7. Submit incomplete multi-stage evidence.
8. Corrupt expected answers.
9. Hide unauthorized arguments.
10. Resume from a contaminated checkpoint.
11. Include duplicate trials.
12. Count Canary trials as model evidence.
13. Expose protected reference answers.
14. Generate valid RL rewards from invalid evaluation evidence.
15. Hide evidence errors using exception guards.

Every discovered defect must follow:

Preserve → Reproduce → Source inspection → Root cause → Repair → Regression → Requalification → Publication.

Do not weaken acceptance tests after observing failures.

If a defect cannot be resolved, maintain a scoped BLOCKED verdict.

Gate:

`EA18_INDEPENDENT_ADVERSARIAL_ACCEPTANCE_GO`

---

## 21. EA19 — Final Qualification and Research Release Decision

Produce a final gate table covering EA00–EA19.

For each gate report:

- Status.
- Scope.
- Acceptance criteria.
- Actual executed tests.
- Test results.
- Evidence.
- Remaining limitations.
- Dependent work authorized.

Maintain independent final verdicts.

### Verdict A — Core infrastructure

`EAE_CORE_SOFTWARE_INTEGRITY_GO`

Requires the typed contract, evidence pipeline, qualification engine, assurance controls and publication protections to qualify.

### Verdict B — Continuous assurance

`EAE_CONTINUOUS_SELF_VERIFICATION_GO`

Requires proven Canary execution, automatic fault detection, quarantine and recovery.

### Verdict C — N03 scope

`EAE_N03_COGNITIVE_BENCHMARK_GO`

Requires qualification of the intended C01–C32 dataset, Parser, evaluator and independent reference scopes.

Do not grant all-32 qualification if only a subset passes.

Allow scoped qualification with explicit family identities.

### Verdict D — Cross-mission readiness

`EAE_CROSS_MISSION_INTEGRATION_READY`

Requires tested integration contracts.

This does not automatically qualify every historical mission result.

### Verdict E — Reward assurance

`EAE_RL_REWARD_CONTRACT_GO`

Requires verified reward semantics and synthetic environment qualification.

This does not establish physical training-platform readiness.

### Verdict F — Business production qualification

Maintain a separate business qualification verdict.

Do not close IJN-B-002 merely because the EAE infrastructure qualifies.

End-to-end business qualification still requires an independently qualified business Oracle and actual business-execution evidence.

### Overall mission decision

Use explicit PASS, CONDITIONAL_GO or BLOCKED with detailed scope.

Do not claim absolute evaluator reliability.

The defensible conclusion is:

The qualified system detects, contains and recovers from the defined tested failure classes within measured bounds, while unresolved and unsupported evaluation scopes remain fail-closed.

---

# PART VII — DELIVERY

## 22. Mandatory Deliverables

Publish at least the following:

### Architecture and standards

```text
docs/IJEVAL_MISSION_ORDER.md
docs/IJEVAL_ARCHITECTURE.md
docs/IJEVAL_RESULT_CONTRACT.md
docs/IJEVAL_QUALIFICATION_STANDARD.md
docs/IJEVAL_CANARY_AND_CIRCUIT_BREAKER.md
docs/IJEVAL_CROSS_MISSION_INTEGRATION.md
docs/IJEVAL_REWARD_ASSURANCE.md
```

### Implementation

```text
src/eval_assurance/
tests/ij_eval_assurance/
scripts/ij_eval_assurance/
```

### State and coordination

```text
MISSION_STATE_IJEVAL.json
TASK_LEDGER_IJEVAL.md
BLOCKERS_IJEVAL.md
HANDOFF_IJEVAL.md
```

### Evidence

```text
evidence/IJEVAL/EA00/
evidence/IJEVAL/EA01/
...
evidence/IJEVAL/EA19/
```

### Reports

```text
reports/IJEVAL_HISTORICAL_DEFECT_AUDIT.md
reports/IJEVAL_DATASET_QUALIFICATION.md
reports/IJEVAL_INDEPENDENT_ORACLE_VERIFICATION.md
reports/IJEVAL_MUTATION_TEST_REPORT.md
reports/IJEVAL_CONTINUOUS_CANARY_REPORT.md
reports/IJEVAL_FAULT_CONTAINMENT_REPORT.md
reports/IJEVAL_HISTORICAL_REVALIDATION.md
reports/IJEVAL_N03_QUALIFICATION_REPORT.md
reports/IJEVAL_INDEPENDENT_ACCEPTANCE_REPORT.md
reports/IJEVAL_FINAL_REPORT_CN.md
reports/IJEVAL_FINAL_REPORT_EN.md
```

Use equivalent repository-native paths if justified.

The CN/EN final reports must be content-equivalent.

---

## 23. Final Engineering Report Questions

The final report must explicitly answer:

1. Have the known historical evaluation defects been reproduced and prevented?
2. Can a software exception still enter model semantic failure statistics?
3. Can a missing or corrupted artifact become a qualified verdict?
4. Which evaluator components are genuinely independently verified?
5. Which components still have common-mode failure risks?
6. How quickly does the system detect a scoring fault?
7. How many potentially contaminated trials can execute before detection?
8. Can the system automatically stop affected work?
9. Can contaminated evidence be isolated without losing valid raw responses?
10. Can all historical affected results be recovered?
11. Does the corrected N02RR corpus pass independent verification?
12. Which C01–C32 task families are fully qualified?
13. Which cognitive families remain BLOCKED?
14. Can an unqualified result enter the formal Analyzer?
15. Can an unqualified result enter a formal research report?
16. Can an invalid evaluation generate a usable RL reward?
17. What assurance overhead is incurred?
18. What defects escaped the fault-injection campaign?
19. What is the measured residual risk within the tested scope?
20. What future risks remain untested?
21. Which existing missions can safely consume the EAE?
22. Is N03 authorized to start or resume?
23. What exact commands should an engineer execute to reproduce the qualification?

Every claim must include relevant source references, test identities, denominators, actual evidence and uncertainty.

Do not substitute assertions of confidence for evidence.

---

## 24. GitHub Delivery Requirements

Use a dedicated branch and Draft PR.

Create a dedicated tracking issue if authorized.

Link the existing PR #6, #8, #9 and #11 dependencies.

Keep commits small, logically separated and reviewable.

Preserve existing mission branches.

Do not force-push.

Do not merge without explicit authorization.

Do not commit:

- Credentials.
- Personal usernames or local paths.
- Model weights.
- Protected holdout answers.
- Unlicensed artifacts.
- Private business data.

Use the existing fail-closed sensitive-data publication check.

Verify the actual parsed finding count, not the process exit code alone.

Run relevant existing regression suites.

Any failure must be investigated rather than suppressed.

Publish milestone evidence after each qualified phase.

Verify final remote SHA against local HEAD.

Keep a clean worktree or explicitly document outstanding local changes.

---

## 25. Resource Management and Mission Dependencies

This mission is CPU-first.

Do not acquire the GPU for work that can be validated through synthetic artifacts, deterministic reference execution or offline replay.

If an existing physical experiment is active:

- Verify actual host and GPU identity.
- Do not forcibly terminate it.
- Do not modify its active implementation.
- Coordinate pause at a safe checkpoint if the affected evaluation scope is unqualified.
- Preserve all completed raw evidence.
- Quarantine results whose evaluation eligibility is unresolved.

Continue independent software qualification.

Reuse the existing host-wide GPU lease protocol.

Do not create a mission-specific mutex.

Do not interfere with other physical workstations.

For N03, prevent new formal execution in unqualified evaluation scopes.

A separately identified diagnostic smoke experiment may proceed when its local evaluation requirements qualify.

Do not require every future cross-mission or RL extension to finish before an independently qualified N03 scope can proceed.

---

## 26. Execution Order

Execute the work in dependency-driven waves.

### Wave A — Audit and contract

EA00 → EA01 → EA02.

Identify historical defects and enforce the unified typed verdict model.

### Wave B — Qualification foundation

EA03 → EA04 → EA05 → EA06 → EA07 → EA08.

Establish independently verified semantic and evidence integrity.

### Wave C — Continuous protection

EA09 → EA10 → EA11.

Implement self-verification, automatic containment and qualified publication.

### Wave D — Historical and real integration

EA12 → EA13 → EA14.

Revalidate historical evidence, qualify actual N03 task families and demonstrate systemic fault containment.

### Wave E — Independent acceptance

EA18.

Challenge the actual running infrastructure.

After the applicable core and N03 scopes satisfy all required acceptance gates, publish a scoped N03 execution authorization.

### Wave F — Long-term integration

EA15 → EA16 → EA17.

Complete cross-mission compatibility, reward assurance and operational tooling.

### Wave G — Final closure

Repeat any affected EA18 acceptance tests after later changes.

Complete EA19.

Independent software work may proceed in parallel where safe.

Do not advance through a failed dependency merely to report more completed gates.

---

## 27. Explicitly Forbidden Shortcuts

The following are unacceptable:

- Claiming evaluation correctness because unit tests pass.
- Treating SHA256 verification as proof of semantic correctness.
- Calling the same evaluator twice and claiming independent evaluation.
- Counting software exceptions as model failures.
- Counting missing telemetry as zero.
- Ignoring unevaluable trials in published coverage.
- Accepting results without independently verified ground truth.
- Hiding incorrect stage-one actions using final-stage answers.
- Weakening tests to make qualification pass.
- Masking exceptions to keep long-running experiments alive.
- Retrospectively excluding inconvenient results.
- Changing formal holdout answers after observing model outputs.
- Publishing results with revoked evaluator qualification.
- Claiming production readiness from synthetic software tests.
- Claiming human independent review when no human reviewer participated.
- Re-executing thousands of GPU trials when valid raw evidence allows offline recovery.
- Treating a negative scientific finding as a failed engineering mission.
- Claiming that finite fault-injection tests prove the absence of all future defects.

---

## 28. Final Execution Directive

Start immediately.

The most important deliverable is a trustworthy, independently verified and continuously self-checking scientific evaluation instrument.

When a new failure occurs:

1. Preserve the original evidence.
2. Reproduce the failure.
3. Inspect the exact source.
4. Identify the first incorrect observable stage.
5. Establish the root cause.
6. Implement a minimal justified repair.
7. Add permanent regression controls.
8. Independently validate the repaired behavior.
9. Determine the full historical impact.
10. Revoke contaminated qualifications.
11. Recover valid evidence.
12. Requalify the affected scope.
13. Publish the complete evidence chain.
14. Continue the mission.

Do not stop at architecture.

Do not stop at green unit tests.

Do not stop at a successful smoke test.

Demonstrate that the complete system prevents known evaluation defects from silently propagating into large-scale scientific results.

Demonstrate that critical injected failures are detected, quarantined and recovered within the measured qualification scope.

Deliver the working Evaluation Assurance Engine.

Publish its source code, qualification controls, historical recovery results, continuous self-verification evidence, fault-containment measurements and reproducible acceptance procedures to GitHub.

Only then authorize qualified large-scale GPU research.

**Scientific integrity first. GPU throughput second.**

**No qualified evidence, no qualified conclusion.**

Execute now.