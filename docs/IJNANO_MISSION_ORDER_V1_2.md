# MISSION IJ-NANO-1.2 — Physical Cognitive Discovery & Model-specific Protocol Qualification

## 0. Mission Identity

- Parent Missions: IJ-NANO-1.0 and IJ-NANO-1.1
- Repository: https://github.com/AIwork4me/Inclusive-JobBot
- Tracking Issue: #10
- Draft PR: #11
- Branch: `mission/ij-nano-1.0-slm-native-agentic-runtime`
- Audited HEAD: `dfce2952accb48c177bd4798cc23bd425c88a9ca`
- Hardware: Native Windows + AMD Radeon RX 7900 XTX 24GB, gfx1100
- Primary engine: llama.cpp b12359
- Primary backend: Vulkan
- Mandatory models: MiniCPM5-2B, LFM3-1.7B, Qwen3.5-2B
- Reference models: previously pinned Qwen3-8B and Qwen3-14B.

Act as a Principal AI Infrastructure Engineer, Small Language Model Research Scientist, Agentic Runtime Architect and independent benchmark reviewer.

This mission continues IJ-NANO-1.0 and IJ-NANO-1.1.

Do not restart completed phases.

The main objective of this session is physical cognitive discovery: collect trustworthy evidence that determines how NanoAgent should be designed for each small model.

Do not stop after software implementation or preliminary smoke tests.

---

## 1. Resume and Baseline Verification

Read:

- AGENTS.md
- HANDOFF_IJNANO.md
- MISSION_STATE_IJNANO.json
- TASK_LEDGER_IJNANO.md
- BLOCKERS_IJNANO.md
- docs/IJNANO_MISSION_ORDER.md
- docs/IJNANO_MISSION_ORDER_V1_1.md
- docs/IJNANO_RESEARCH_PROTOCOL.md

Verify the live local and remote Git identities.

The previously delivered checkpoint is `dfce2952`.

Preserve:

- N00, N00R and N00RR evidence.
- N01 research closure.
- N02 physical admission evidence.
- N06A-R red/green evidence.
- N05A original qualification evidence.
- Original S2 protocol artifact with `overall: FAIL`.

Do not modify other mission branches or their ledgers.

Reuse the existing host-wide GPU lease.

Reverify physical GPU ownership, model hashes and engine identity before physical execution.

---

## 2. N05A-R — Targeted Cognitive Evaluator Requalification

A source-level review of the current evaluator identified seven additional concerns.

Reproduce each concern before modifying the implementation.

### EV01 — Incomplete state predicates

Inspect `evaluate_family()` in `src/nanoagent/eval/comparators.py`.

The current state_interpretation branch uses zip(got, want) and checks excess predicates but does not sufficiently reject missing required predicates.

Create controls for:

- All required predicates correct.
- Only the first predicate correct.
- Missing middle predicate.
- Missing final predicate.
- Duplicate predicate.
- Valid predicates in a different order.
- Extra incorrect predicate.

Require complete semantic coverage.

Use entity/property/operator identity or another explicit matching contract instead of positional matching alone where appropriate.

### EV02 — Undeclared action arguments

The action_representation evaluator checks expected slots but may ignore unexpected keys in response.args.

Test:

- Correct required arguments.
- Correct required arguments plus an unknown field.
- Correct required arguments plus a consequential unauthorized option.
- Explicitly permitted optional arguments.
- Missing required argument.
- Duplicate keys in raw structured output.

The evaluator must distinguish permitted optional arguments from unauthorized or unsupported arguments.

Do not rely solely on extra_assertions populated by an upstream parser.

### EV03 — Predicate semantics

Inspect `predicate_holds()`.

Separate:

1. Predicate expression equivalence.
2. Predicate truth against an independently supplied world state.

Do not compare one predicate's threshold against another threshold as though the first threshold were an observed business value.

Test eq, ne, gt, ge, lt and le.

Test exact boundary values, units, invalid types, contradictory predicates and logically equivalent expressions within the supported contract.

Use exact or explicitly defined semantic equivalence rules.

### EV04 — Identifier collisions

Inspect `canonical_label()`.

Case folding, whitespace normalization and underscore replacement can merge distinct identifiers.

Separate:

- Natural-language closed-vocabulary labels.
- Tool identifiers.
- Entity identifiers.
- Action identifiers.

Use exact identity unless a declared alias contract explicitly permits normalization.

Test case-sensitive IDs, underscore/space collisions, leading zeros and Unicode variants.

### EV05 — Missing unit handling

A quantity supplied as a scalar must not silently inherit the hidden expected unit unless the public task or schema explicitly defines that unit.

Test:

- Explicit unit.
- Implicit unit declared in the public schema.
- Missing mandatory unit.
- Incorrect unit.
- Incompatible dimensions.
- Currency mismatch.
- Non-finite values.
- Numeric type coercion.

Do not derive runtime-visible assumptions from evaluator expectations.

### EV06 — Strengthen mutation testing

The current mutation suite primarily removes reason codes after evaluation.

Retain these tests but add actual comparator-level mutants, including:

- Skip missing-predicate detection.
- Ignore extra arguments.
- Compare entities by substring.
- Normalize identifiers incorrectly.
- Accept incorrect units.
- Flip inequality operators.
- Ignore numeric thresholds.
- Treat invalid types as valid.
- Accept malformed raw output.

Run the same qualification gate against each intentionally weakened implementation.

The gate must reject the mutant.

### EV07 — Coverage reconciliation

The current contract declares 16 reason codes, while the published negative controls exercise 14 distinct codes.

Reconcile declared, reachable and tested reason codes.

Add controls for missing coverage, including PARSE_INVALID.

If a reason code is obsolete or unreachable, document its disposition and update the versioned contract.

Do not claim complete rule coverage from the number of declared codes.

### Dataset-level qualification

Add strict validation of Expectation and Response contracts.

Reject malformed evaluator inputs rather than silently accepting missing semantic expectations.

The current 41-case battery establishes preliminary comparator behavior but does not qualify every future N03 case.

For each new N03 task family require:

- Executable or independently verified positive witness.
- Relevant critical negative controls.
- Semantic mutations.
- Valid alternative responses where applicable.
- Evaluator scope identity.

Publish the updated coverage matrix.

Deliver:

- `reports/IJNANO_05AR_COGNITIVE_EVALUATOR_REQUALIFICATION.md`
- `evidence/IJNANO/N05AR/defect_ledger.json`
- Red/green regression evidence.
- Comparator mutation results.
- Dataset-specific qualification rules.

Gate:

`N05AR_COGNITIVE_EVALUATOR_INTEGRITY_GO`

This gate remains separate from the end-to-end business Oracle.

---

## 3. N02R — Model × Protocol Causal Analysis

Execute physical experiments on the RX 7900 XTX.

### 3.1 Investigate the existing LFM3 observation

Preserve the following original evidence:

- Chat Completions + JSON Schema: FAIL.
- Generation budget: 1,024 tokens.
- reasoning_content: 4,030 characters.
- Final content empty.
- finish_reason: length.
- Completion + GBNF: PASS.
- Completion + JSON Schema: PASS.

Treat this as a protocol-associated observation requiring causal analysis.

Do not assume the root cause is intrinsic to model weights.

### 3.2 Audit and repair the protocol probes

Verify:

- Empty final content is not classified as successful text generation.
- Tool calls receive structural and semantic scoring.
- Client-side cancellation is distinguished from server-side inference termination.
- Inference slots are released after cancellation.
- SSE usage is reconciled with actual generated content and observable token accounting.
- Response structure and raw evidence are correctly captured.

Preserve previous results under their original identities.

### 3.3 Experimental arms

| Arm | Protocol and representation |
|---|---|
| P0 | Native Chat Completions, default behavior |
| P1 | Chat Completions + JSON Schema |
| P2 | Chat Completions + verified thinking-disabled mode + JSON Schema |
| P3 | Completion + JSON Schema |
| P4 | Completion + GBNF |
| P5 | Native Function Calling |
| P6 | Completion + Compact Action DSL |
| P7 | Completion + enumerated action |

Evaluate S1, S2 and S3.

Use matched:

- Model weights.
- Quantization.
- Task semantics.
- Available information.
- Business entity identities.
- Generation budget.
- Decoding settings where supported.

Verify the actual rendered prompt.

Do not deliberately weaken one protocol by supplying an incorrect Chat Template.

### 3.4 Isolate causal factors

Where supported, construct matched comparisons for:

- Chat versus completion transport with equivalent rendered prompts.
- Thinking enabled versus disabled.
- Grammar enabled versus disabled.
- JSON Schema versus native tool calls.
- Action representation.
- Parser behavior.
- Output budget.

The eight primary arms change multiple factors in some comparisons.

Use additional controlled counterfactuals before attributing an observed gain to one factor.

### 3.5 Physical trial design

Use at least 60 independent development tasks covering six families:

- Enumerated action selection.
- Tool selection.
- Slot extraction.
- Structured action generation.
- Conditional decisions.
- Stop/continue decisions.

Initial common-budget screen:

    3 models × 8 arms × 60 cases = 1,440 nominal trial slots.

Then investigate generation-budget sensitivity:

- 64 tokens.
- 128 tokens.
- 256 tokens.
- 512 tokens.
- 1,024 tokens.

Preregister the primary budget and sensitivity-panel selection rule.

Do not silently remove unfavorable comparisons.

Record all structurally inapplicable arms.

### 3.6 Measurements

Capture:

- Semantic correctness.
- Structural validity.
- Tool selection correctness.
- Argument correctness.
- Empty-output rate.
- Truncation rate.
- Finish reason.
- Prompt tokens.
- Total generated tokens.
- Reasoning tokens where directly observable.
- Final-action tokens where directly observable.
- Latency.
- Timeout.
- GPU execution evidence.

Do not estimate exact reasoning token counts from character counts.

Report uncertainty when token-channel attribution is unavailable.

### 3.7 Source-level investigation

Inspect the pinned llama.cpp implementation corresponding to b12359.

Investigate:

- Model-specific Chat Template.
- Thinking configuration.
- Reasoning parser.
- Grammar activation point.
- JSON Schema conversion.
- Token budget accounting.
- Server request handling.
- GBNF parser behavior.

Reproduce the escaped-quote observation using known-valid upstream grammar examples.

Distinguish incorrect grammar construction from a genuine engine defect.

If source instrumentation or a newer engine is required, use a separately identified experimental arm.

Do not replace the pinned baseline.

Deliver:

- `reports/IJNANO_02R_PROTOCOL_CAUSAL_ANALYSIS.md`
- `evidence/IJNANO/N02R/protocol_matrix.json`
- Source-level findings.
- Matched physical traces.
- Model-specific protocol recommendation candidates.

Gate:

`N02R_MODEL_PROTOCOL_BEHAVIOR_CHARACTERIZED`

---

## 4. N03 — Full Physical SLM Cognitive Capability Atlas

Complete the original C01–C32 taxonomy.

Prioritize the twelve families specified in IJ-NANO-1.1, then complete every remaining primitive.

### 4.1 Dataset

Create and freeze:

- 640 independent primitive-level development cases.
- 320 reserved capability confirmation cases.

Use at least 20 development cases per cognitive primitive.

Where the same case measures multiple dimensions, distinguish case count from measurement count.

Use Chinese and English.

Split by task families, entity structures and underlying business worlds.

Do not produce apparent independence through paraphrasing alone.

Protect the reserved confirmation set from the Runtime designer and optimizer until candidate configurations are frozen.

Do not expose expected answers through evaluator APIs, case metadata or prompt construction.

### 4.2 Capability isolation

Use diagnostic controls to independently measure:

- Tool selection with arguments supplied.
- Argument generation with the tool supplied.
- Intent understanding without execution.
- State interpretation.
- Conditional branching.
- Recovery action selection.
- Stop/continue decisions.

Label diagnostic tasks as cognitive isolation.

Do not report supplied prerequisites or known tool identities as autonomous planning success.

### 4.3 Baseline physical coverage

Run every mandatory small model against the complete development and confirmation rosters.

Nominal initial coverage:

    3 models × (640 + 320 cases) = 2,880 trial slots.

The confirmation roster may execute only after its corresponding candidate or measurement protocol has been frozen.

Additional scaling curves, protocol comparisons, larger-model references and repeatability trials are separate.

Preserve the original denominator and all blocked slots.

### 4.4 Capability scaling curves

Construct matched development panels for:

A. Tool inventory size:

- 2, 4, 8, 16, 32, 64 tools.

B. Context:

- Relevant context length.
- Irrelevant context volume.
- Distractor similarity.
- Historical observations.

C. Action complexity:

- Single slot.
- Multiple slots.
- Nested structures.
- Entity references.
- Mixed data types.

D. Planning horizon:

- Single action.
- Two dependent actions.
- Three to six dependent actions.
- Conditional branches.
- Replanning after a state change.

E. Recovery:

- Invalid argument.
- Missing prerequisite.
- Unknown entity.
- Stale observation.
- Temporary tool failure.
- Conflicting observation.

F. Action representation:

- Native Function Calling.
- JSON.
- Grammar-constrained JSON.
- Natural-language actions.
- Numeric identifiers.
- Compact DSL.
- Two-stage selection and slot filling.

Use staged, preregistered sampling.

Do not run an uncontrolled Cartesian product.

Measure each curve with sample sizes and uncertainty.

Do not assume degradation is monotonic.

### 4.5 Reference models

Include matched stratified panels for the pinned 8B and 14B reference models.

This is necessary to distinguish a genuinely small-model-specific Runtime benefit from an optimization that also benefits larger models.

Do not mix larger-model results into the primary 2B ranking.

### 4.6 Repeatability

Repeat a preregistered representative panel under multiple seeds.

Distinguish:

- Independent task worlds.
- Repeated trials.
- Backend nondeterminism.
- Sampling nondeterminism.

Never treat repeated seeds as independent users or independent task worlds.

---

## 5. N03T — Capability-to-Runtime Translation

Transform measured capabilities into candidate Runtime Profiles.

For each model produce a traceable mapping:

    Measured cognitive limitation
        -> First incorrect observable stage
        -> Confirmed or unverified causal mechanism
        -> Candidate Runtime intervention
        -> Expected benefit
        -> Potential regression
        -> Required confirmation experiment

Investigate:

| Observed weakness | Candidate intervention |
|---|---|
| Tool confusion | State-aware tool filtering |
| Missing prerequisite tools | Dependency-aware ToolRAG |
| Malformed actions | Constrained decoding |
| Incorrect business identifiers | Provenance-aware slot binding |
| Reasoning budget starvation | Protocol and thinking policy |
| Context interference | Minimum sufficient context |
| Premature termination | Goal predicate |
| Invalid recovery | Typed recovery policy |
| Planning dependency errors | Conditional Action Graph |

These are candidate mappings, not predetermined solutions.

Do not hardcode a model name as the basis for Runtime selection.

Derive the configuration from capability measurements and resource constraints.

### Runtime Profile contract

Provide machine-readable profiles containing:

- Exact model identity.
- Quantization.
- Qualified protocols.
- Candidate action representations.
- Effective context envelope.
- Tool inventory sensitivity.
- Planning horizon.
- Slot binding requirements.
- Recovery capabilities.
- Thinking policy.
- Resource constraints.
- Evidence references.
- Confidence intervals.
- Known limitations.
- Qualification status.

Do not assign numeric thresholds without measured evidence.

Deliver:

- `reports/IJNANO_03_SLM_COGNITIVE_CAPABILITY_ATLAS.md`
- `reports/IJNANO_CAPABILITY_TO_RUNTIME_MAPPING.md`
- `atlas/ij_nano/cognitive_capability_matrix.json`
- `atlas/ij_nano/capability_curves.json`
- `profiles/ij_nano/model_passports/`

Gate:

`N03_COGNITIVE_CAPABILITY_PROFILES_AVAILABLE`

---

## 6. N06B/C — Build Evidence-driven Runtime Mechanisms

Once initial N03 development evidence exists, implement the justified Runtime interventions.

### Layer B

- Context Compiler.
- Dependency-aware Tool Router.
- Dynamic Action Schema.
- Grammar Compiler.
- Action Decoder.
- Compact DSL.
- Provenance-aware Slot Binder.

### Layer C

- Typed State integration.
- Conditional Action Graph.
- Typed Recovery Engine.
- Goal Predicate.
- Bounded replanning.
- Model Capability Profile.
- Protocol Selection Policy.

Every module must be:

- Independently switchable.
- Independently testable.
- Independently measurable.
- Explicitly versioned.
- Free from hidden benchmark answers.

Reuse the qualified Layer A.

Do not unnecessarily rebuild generic infrastructure.

Use the N01 component-level reuse decision as a starting point, not an irrevocable architectural commitment.

When a physical result contradicts the architecture hypothesis, revise the candidate design and preserve the original evidence.

Complete the N06 software gate only when the modular Runtime has been implemented and its specified conformance tests pass.

Keep physical mechanism qualification separate.

---

## 7. N04/N07 — Existing Mechanism Reproduction

Run mandatory development comparisons:

### effGen

Use the verified official implementation and native local model interface.

Capture actual framework-added prompts, model requests, retries and tool execution behavior.

Separate native effGen from model-specific adaptations.

### PTC-inspired Runtime

Compare:

- Plan-to-Act only.
- Tool-name constraints only.
- Combined mechanism.

Measure semantic correctness and additional token cost.

### TinyAgent-inspired ToolRAG

Use identical model weights.

Compare:

- All tools exposed.
- Semantic retrieval.
- Dependency closure.
- State-aware legal action filtering.

Do not attribute gains from original TinyAgent fine-tuned weights to Runtime engineering.

### Action representations

Compare JSON, GBNF, native function calling, enumerated actions and compact DSL under equivalent task requirements.

For every mechanism publish failures as well as improvements.

---

## 8. Balanced 3,600-slot SLM Harness Causal Pilot

Retain the original preregistered development pilot:

| Arm | Intervention |
|---|---|
| A0 | Minimal native reference loop |
| A1 | Compact context only |
| A2 | State-aware tool filtering only |
| A3 | Grammar-constrained action only |
| A4 | Provenance-aware slot binding only |
| A5 | Typed state only |
| A6 | Typed recovery only |
| A7 | Compact Action DSL only |
| A8 | Combined NanoAgent development profile |
| A9 | Verified effGen native |

Run at least 120 matched development cases per model and applicable arm.

Nominal maximum:

    3 models × 10 arms × 120 cases = 3,600 trial slots.

Before execution freeze:

- Model identity.
- Engine identity.
- Backend.
- Quantization.
- Dataset.
- Runtime configuration.
- Evaluator version.
- Execution budgets.
- Applicability.
- Statistical comparison protocol.

Do not count N02R or N03 trials as independent pilot evidence unless their full experimental identities match and the reuse is explicitly documented.

Report:

- Semantic action accuracy.
- Argument correctness.
- Entity hallucinations.
- Structural validity.
- Recovery success.
- Termination correctness.
- Model calls.
- Prompt tokens.
- Generated tokens.
- P50/P95 latency.
- Memory.
- Evidence completeness.

Use matched comparisons, paired confidence intervals and appropriate multiple-comparison handling.

The pilot is development evidence.

Do not declare a final SDK winner from this pilot.

Do not publish formal business correctness claims without the independently qualified business Oracle.

---

## 9. Persistent Physical Experiment Controller

Before substantial GPU execution, implement or reuse:

- Host-wide GPU lease.
- Persistent trial queue.
- Atomic result persistence.
- Immutable trial identity.
- Checkpoint recovery.
- Duplicate prevention.
- Watchdog.
- Bounded timeouts.
- Process ownership verification.
- Disk-space monitoring.
- Resource accounting.
- Evidence sealing.

Balance execution across all three small models.

Do not exhaust the entire GPU budget on a single preferred model.

Estimate GPU hours from observed pilot throughput.

Maintain exact remaining coverage.

Do not silently reduce the required matrix to achieve mission completion.

A changed configuration must create a new experiment identity.

---

## 10. Research Integrity and GitHub Delivery

Continue publishing to:

- Issue #10.
- Draft PR #11.
- Existing IJ-NANO research branch.

Preserve historical evidence.

Do not merge or force-push.

Run all relevant regression tests.

The sensitive-data scanner returns exit code 0 even when findings exist.

Implement a fail-closed publication check that verifies the actual finding count, not the exit code alone.

Add a synthetic scanner control without introducing real personal information.

Never commit:

- Credentials.
- Personal file paths.
- Model weights.
- Protected holdout answers.
- Unlicensed artifacts.

For every milestone publish:

- Exact remote SHA.
- Completed gates.
- Software versus physical qualification.
- Planned and executed trial counts.
- PASS/FAIL/BLOCKED/NOT_RUN.
- Evidence-valid coverage.
- Current blockers.
- Next recovery command.

---

## 11. Final Interim Report

Produce:

`reports/IJNANO_1_2_INTERIM_RESEARCH_REPORT_CN.md`

Answer:

1. Which inference protocols are suitable for each small model?
2. What is the confirmed cause of LFM3's chat-path structured-output failure?
3. Which cognitive primitives differ most across the three models?
4. Which action representations are most effective?
5. How does tool inventory affect semantic accuracy?
6. How does context interference affect each model?
7. Where do planning and recovery capabilities degrade?
8. Which Runtime mechanisms deliver meaningful improvements?
9. Which mechanisms introduce regressions?
10. Which model-specific profiles should enter formal transfer experiments?
11. Which existing frameworks and components should NanoAgent reuse?
12. What are the remaining evaluator and business qualification gaps?

Every important conclusion requires:

- Exact comparison.
- Sample size.
- Effect size.
- Confidence interval where applicable.
- Physical evidence reference.
- Known limitations.

---

## 12. Execution Directive

Execute in this order:

1. Resume and verify baseline.
2. Complete N05A-R targeted evaluator corrections.
3. Execute N02R physical protocol causal analysis.
4. Execute N03 full cognitive profiling.
5. Produce capability-to-Runtime mappings.
6. Implement N06B/C based on measured needs.
7. Reproduce relevant existing mechanisms.
8. Execute the balanced 3,600-slot causal pilot.

Parallelize independent software work safely.

Do not wait for the full business Oracle to conduct independently valid cognitive experiments.

Do not bypass the business Oracle for formal end-to-end business claims.

When failures occur:

Preserve → Reproduce → Inspect source → Establish mechanism → Repair where justified → Regression test → Revalidate → Publish → Continue.

The mission succeeds by discovering the measurable capability requirements of SLM-native Agentic Runtime design.

Do not simply build more SDK features.

Use physical evidence to determine which SDK features are necessary.

Execute now.