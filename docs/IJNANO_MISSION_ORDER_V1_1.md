# MISSION IJ-NANO-1.1 — Cognitive Evidence-driven Runtime Design & Integrity Hardening

## 0. Mission Identity

- Parent Mission: IJ-NANO-1.0
- Repository: https://github.com/AIwork4me/Inclusive-JobBot
- Tracking Issue: #10
- Draft PR: #11
- Branch: `mission/ij-nano-1.0-slm-native-agentic-runtime`
- Audited HEAD: `f3d5817f8b2a1e7b78c9492578afc931247df11c`
- Frozen source: `56c6c74bf7216eb9cf65be4056c8db1964d23b05`
- Hardware: Windows + Radeon RX 7900 XTX 24GB, gfx1100
- Engine: llama.cpp b12359
- Primary backend: Vulkan
- Primary models: MiniCPM5-2B, LFM3-1.7B, Qwen3.5-2B.

Act as a Principal AI Infrastructure Architect, SLM Research Scientist, Runtime Engineer, Benchmark Scientist and independent software reviewer.

This is a continuation of IJ-NANO-1.0, not a replacement mission.

Preserve all original requirements, evidence, research hypotheses and remaining experimental obligations.

The immediate objective is to transform the current NanoAgent software prototype into an evidence-driven SLM-native Runtime foundation.

Do not finalize model-specific execution policies before measuring the cognitive capabilities that justify those policies.

---

## 1. N00RR — Resume and Reconcile

Inspect the latest local and remote state.

Read:

- `AGENTS.md`
- `MISSION_STATE_IJNANO.json`
- `TASK_LEDGER_IJNANO.md`
- `BLOCKERS_IJNANO.md`
- `HANDOFF_IJNANO.md`
- `docs/IJNANO_MISSION_ORDER.md`
- `docs/IJNANO_RESEARCH_PROTOCOL.md`
- N00R and N02 evidence.
- N01 research catalog.
- NanoAgent Layer A source and tests.

Reconcile the current HEAD against the audited anchor.

Do not restart completed work.

Preserve historical evidence.

Correct stale status records:

- PR #11 description still reports the old GPU blocker.
- N01 research_catalog.json is present but its ledger entry remains stale.
- N02 ledger headings and phase progress must reconcile.
- N06 software progress must be recorded separately from complete Runtime qualification.

Maintain machine-readable scoped gate statuses.

Respect the host-wide GPU lease.

Do not interfere with PR #6, #8 or #9.

---

## 2. N01 — Complete Research and Reuse Decision

Complete the outstanding N01 deliverables:

- `evidence/IJNANO/N01/research_catalog.json`
- `evidence/IJNANO/N01/license_matrix.json`
- `reports/IJNANO_01_RESEARCH_LANDSCAPE_CN.md`
- `reports/IJNANO_01_RESEARCH_LANDSCAPE_EN.md`
- `reports/IJNANO_OPEN_SOURCE_REUSE_DECISION.md`

Audit the four primary-source verification sweeps.

For every important claim include:

- Primary source.
- Exact paper identity.
- Repository revision.
- License.
- Model parameter count.
- Whether model weights changed.
- Evaluation method.
- Experimental metric.
- Reported result.
- Reproduction limitations.

Explicitly distinguish:

- 1–3B total parameters.
- Larger MoE models with small active parameter counts.
- Runtime-only optimization.
- Weight fine-tuning.
- Job-specific specialization.
- LLM-judged results.
- Deterministically verified results.

Do not treat the number of dependencies as a complete framework quality ranking.

PocketFlow's small dependency footprint is useful, but a framework requiring substantial custom orchestration may have higher total engineering cost.

For PocketFlow, Pydantic AI, smolagents and effGen, compare:

- Native functionality.
- Required custom code.
- Dependency footprint.
- Initialization cost.
- Observability.
- Security.
- Maintenance effort.
- Commercial licensing.
- Local Windows compatibility.
- Model-specific adaptation effort.

Make a component-level reuse decision rather than choosing an entire SDK prematurely.

Gate:

`N01_RESEARCH_LANDSCAPE_VERIFIED`

---

## 3. N02R — Model × Inference Protocol Causal Analysis

### 3.1 Preserve original observations

The audited N02 evidence shows:

- S2 chat-path JSON Schema failure.
- 4,030 reasoning_content characters.
- 1,024-token generation budget.
- finish_reason = length.
- Empty final content.
- GBNF completion path PASS.
- JSON Schema completion path PASS.
- Native tool-call probe PASS.

The raw S2 protocol artifact has `overall: FAIL`.

Do not rewrite it as PASS.

Distinguish:

- Physical model loading qualification.
- Engine API availability.
- Request protocol conformance.
- Structural generation capability.
- Semantic action correctness.
- Model-specific protocol suitability.

### 3.2 Audit protocol probes

Inspect `benchmarks/ij_nano/n02_protocol_probe.py`.

Investigate potential false positives:

- Basic generation PASS with empty content.
- Tool-call structure PASS without complete semantic verification.
- Client cancellation PASS inferred from client abort and subsequent health.
- SSE usage fields present without exact token-accounting verification.

Strengthen the relevant probe scopes.

Cancellation qualification must distinguish:

- Client connection closed.
- Server generation actually terminated.
- Inference slot released.
- Subsequent task executes correctly.

Record unsupported observability explicitly.

### 3.3 Controlled protocol comparison

Execute the following experiment arms across S1/S2/S3:

| Arm | Protocol | Constraint |
|---|---|---|
| A0 | Chat Completions, default thinking | None |
| A1 | Chat Completions, default thinking | JSON Schema |
| A2 | Chat Completions, thinking disabled where supported | JSON Schema |
| A3 | Completion | JSON Schema |
| A4 | Completion | GBNF |
| A5 | Native Function Calling | Native tool protocol |
| A6 | Completion | Compact Action DSL |
| A7 | Completion | Enumerated Action |

Use identical model weights and quantization within comparisons.

Use equivalent task information, semantic goals and tool capabilities.

Capture actual rendered prompt/template where observable.

Do not assume that `enable_thinking=false` is honored by every model.

Verify the actual behavior.

If thinking control is unsupported, mark the corresponding arm appropriately.

For completion-path comparisons, preserve the correct model-specific prompt formatting.

Do not create a weaker chat baseline through incorrect template usage.

### 3.4 Budget sensitivity

Use generation budget profiles of:

- 64.
- 128.
- 256.
- 512.
- 1,024 tokens.

Use the same budget within matched comparisons.

Preregister applicability and the primary comparison budget.

Conduct a staged initial screen using at least 60 independent development tasks covering:

- Enumerated action selection.
- Tool selection.
- Slot extraction.
- Structured action generation.
- Conditional decisions.
- Stop versus continue.

Expand the best-supported comparisons through the original N03/N07 protocols.

Record:

- Prompt tokens.
- Generated tokens.
- Reasoning-channel tokens when measurable.
- Final-action tokens.
- Finish reason.
- Empty-output rate.
- Structural validity.
- Semantic correctness.
- First-pass success.
- Latency.
- Timeout.
- Actual inference backend.

Do not convert reasoning_content character length into a claimed exact token count.

### 3.5 Root cause analysis

Investigate:

- Model Chat Template.
- Template thinking control.
- llama.cpp reasoning parser.
- Grammar activation point.
- JSON Schema conversion.
- Token budget accounting.
- Completion versus chat formatting.
- GBNF escaped-quote behavior.

Inspect exact upstream source corresponding to the pinned binary identity where available.

Use controlled counterfactuals.

Do not conclude that the model itself is responsible until competing template, parser and engine explanations have been investigated.

Preserve the pinned engine baseline.

Any upgraded or patched engine must have a separate experimental identity.

Deliver:

- `reports/IJNANO_02R_PROTOCOL_CAUSAL_ANALYSIS.md`
- `evidence/IJNANO/N02R/protocol_matrix.json`
- Raw physical traces.
- Minimal reproductions.
- Model-specific protocol capability matrix.

Gate:

`N02R_MODEL_PROTOCOL_BEHAVIOR_CHARACTERIZED`

---

## 4. N06A-R — Execution Integrity Hardening

Execute in parallel with N02R where safe.

Reproduce each reported concern against the audited source before repairing it.

### NA-D01 — Transaction isolation

Current gateway uses:

    self._draft = dict(self._store)

Investigate nested-state aliasing.

Create regression tests for:

- Nested dictionaries.
- Nested lists.
- Multiple entities.
- Handler exception.
- Cancellation during execution.
- Invalid commit.
- Concurrent writes where supported.

Require rollback to preserve the original business state exactly.

A deep copy may be sufficient for the initial synthetic in-memory store, but it does not establish durable transactional behavior.

For persistent job worlds, implement or reuse appropriate transactional storage.

Prevent handlers from bypassing the transaction boundary.

### NA-D02 — Evidence integrity

Inspect EventLog.

The current hash computation does not include parent_id or timestamp.

Require the canonical integrity envelope to cover all security- and causality-relevant fields.

Verify:

- Trial identity.
- Event identity.
- Parent identity.
- Sequence.
- Timestamp.
- Stage.
- Kind.
- Payload.
- Previous hash.

Detect:

- Parent reassignment.
- Cross-trial event injection.
- Duplicate event ID.
- Missing parent.
- Invalid stage.
- Reordered events.
- Truncated evidence.
- Modified payload.
- Mutation through nested references.

A hash chain is not proof of authenticity against an adversary who can rewrite the entire chain.

Bind sealed evidence to a separately trusted manifest or equivalent external anchor.

### NA-D03 — Checkpoint integrity

Inspect Checkpoint.capture, restore and validate.

Require integrity binding across:

- Trial identity.
- Experiment identity.
- Budget specification.
- Budget counters.
- State snapshot.
- Epoch.
- Event sequence.
- Evidence seal.
- Idempotency state.
- Pending transactions.

Reject invalid checkpoints during restore rather than relying on callers to remember a separate validation step.

Demonstrate actual recovery of executable state and budget.

Restoring a data record alone is not equivalent to resuming a task.

Define how absolute deadlines and remaining budgets survive process restart without silently granting a new budget.

Test atomic persistence and interruption during checkpoint publication.

### NA-D04 — Budget integrity

Implement an authoritative and, where concurrent execution is supported, atomic reservation and settlement protocol.

Distinguish:

- Attempt count.
- Reserved capacity.
- Actual usage.
- Released reservation.
- Unknown usage after transport failure.
- Overrun.

Ensure:

- No budget bypass through zero-unit reservations.
- No invalid negative budgets.
- No accounting loss when a request fails.
- No corrective retry when retry budget is exhausted.
- No uncontrolled token overrun.
- No concurrent reservation race.
- No sliding deadline.

Bind request max_tokens to available budget.

Check deadline and cancellation before dispatch and before consequential commit.

Do not silently undercount actual usage.

### NA-D05 — Provenance integrity

A nonempty source_event_id does not prove that a Fact is trustworthy.

Require a verified source event belonging to:

- The correct trial.
- The correct session.
- The correct business world.
- An authorized source.
- A valid state version.

Validate:

- Entity identity.
- Property.
- Data type.
- Unit.
- Value.
- Source.
- Validity scope.

Prevent arbitrary model-generated data from entering the trusted state as verified facts.

Test fake source IDs, stale events, cross-session facts and nested-value mutation.

### NA-D06 — Epoch and cancellation protection

The gateway exposes state_epoch_getter but does not currently enforce it.

Implement epoch verification at the relevant execution boundaries.

Prevent late model responses or tool operations from committing state after:

- Session reset.
- Cancellation.
- Deadline expiration.
- Task replacement.
- Checkpoint invalidation.

Test a delayed handler completing after the session is aborted.

Verify zero unauthorized late effects.

For non-reversible external actions, document the appropriate pre-dispatch and compensation policy.

### NA-D07 — Approval and idempotency

Bind approval to the actual authorized operation:

- Session.
- Business entity.
- Tool.
- Canonical arguments.
- Operation identity.
- Permission scope.
- Expiration where applicable.

Do not rely only on a reusable call_key.

Require effect-key binding to the canonical business operation.

Detect:

- Same key with different arguments.
- Same key across different tools.
- Duplicate request.
- Duplicate operation after restart.
- Approval reused for another operation.
- Approval after expiration.
- Missing mandatory idempotency key.

Ensure atomic recording of transaction effects and idempotency state.

### NA-D08 — Schema validation

Inspect `src/nanoagent/gateway/schema.py`.

Verify the actual supported schema subset.

Test:

- minimum/maximum.
- exclusiveMinimum/exclusiveMaximum.
- String length.
- Pattern constraints.
- Nested objects.
- Arrays.
- Unknown properties.
- Invalid schema definitions.
- Unsupported keywords.
- Non-finite numeric values.

Do not silently ignore unsupported semantic constraints.

Prefer a trusted standard validator when its dependency and licensing costs are acceptable.

If maintaining a limited validator, explicitly reject unsupported schemas at registration time.

### Layer A gate

Create adversarial and mutation tests for all eight defect classes.

Require:

- Original red reproduction.
- Confirmed or refuted root cause.
- Minimal justified repair.
- Green regression.
- Negative controls.
- No regression in existing NanoAgent tests.
- No changes to other missions.
- Exact evidence manifest.

Publish:

- `reports/IJNANO_06A_RUNTIME_INTEGRITY_HARDENING.md`
- `evidence/IJNANO/N06A-R/defect_ledger.json`
- `evidence/IJNANO/N06A-R/regression_results.json`

Gate:

`NANOAGENT_LAYER_A_SOFTWARE_INTEGRITY_GO`

Do not claim production transaction safety from this software qualification alone.

---

## 5. N05A — Independent Cognitive Evaluator Qualification

Create the minimum independent evaluator infrastructure required for N03 and mechanism-level experiments.

Do not wait for the full business Oracle if the specific cognitive scope can be independently evaluated.

Define typed evaluation contracts for:

- Intent.
- Goal.
- Tool selection.
- Action representation.
- Entity reference.
- Slot value.
- Numeric value and unit.
- State interpretation.
- Conditional branch.
- Recovery action.
- Stop/continue decision.
- Correct clarification.

Use deterministic semantic comparisons wherever possible.

Do not use substring matching as the primary correctness method.

Do not expose expected results to the tested runtime.

Create controls including:

- Correct alternative representation.
- Wrong entity.
- Wrong polarity.
- Wrong numeric value.
- Invalid units.
- Missing required slots.
- Extra incorrect assertions.
- Structurally valid but semantically incorrect actions.
- Incorrect branch.
- Invalid recovery.
- Premature stop.
- Unnecessary continuation.

Map every scoring rule to positive and negative controls.

Run mutation tests against weakened evaluators.

Every critical negative must fail for the intended reason.

Publish evaluator coverage per cognitive family.

Do not grant end-to-end business Oracle qualification based on cognitive evaluator qualification.

Gate:

`N05A_COGNITIVE_EVALUATOR_QUALIFIED`

---

## 6. N03 — Full SLM Cognitive Capability Profiling

The cognitive results must determine Runtime design.

Execute the twelve priority families first:

1. Enumerated action selection.
2. Native tool-name selection.
3. Grammar-constrained action selection.
4. Compact DSL generation.
5. Slot extraction.
6. Entity reference resolution.
7. Context interference resistance.
8. Tool inventory sensitivity.
9. Error recognition.
10. Invalid argument recovery.
11. Stop versus continue.
12. Conditional branching.

Then complete the remaining original C01–C32 taxonomy.

### 6.1 Independent dataset

Preserve the original minimum coverage requirements:

- 640 primitive-level development cases.
- 320 reserved capability confirmation cases.

Use genuinely distinct task families and business worlds.

Do not count paraphrases alone as independent tasks.

Cover Chinese and English.

Preserve the distinction between diagnostic capability isolation and autonomous execution.

### 6.2 Capability curves

Measure performance as a function of:

- Available tools: 2, 4, 8, 16, 32, 64.
- Instruction complexity.
- Required slots.
- Schema depth.
- Entity count.
- Context length.
- Irrelevant context volume.
- Planning depth.
- Error complexity.
- Action representation.
- Inference protocol.

Use a staged design instead of an uncontrolled Cartesian product.

Retain exact applicability and coverage.

### 6.3 Required cognitive profile

For every model generate:

- Capability scores.
- Confidence intervals.
- Failure classes.
- Context sensitivity.
- Tool inventory sensitivity.
- Action representation suitability.
- Protocol suitability.
- Planning limitations.
- Recovery behavior.
- Token and latency cost.

Separate observations from architectural recommendations.

For each proposed Runtime intervention identify:

- The measured weakness.
- Evidence.
- Candidate mechanism.
- Expected benefit.
- Potential regression.
- Confirmatory experiment.

Do not derive configuration limits from intuition.

Deliver:

- `reports/IJNANO_03_SLM_COGNITIVE_CAPABILITY_ATLAS.md`
- `profiles/ij_nano/model_passports/`
- `atlas/ij_nano/cognitive_capability_matrix.json`
- `atlas/ij_nano/capability_curves.json`
- `reports/IJNANO_CAPABILITY_TO_RUNTIME_MAPPING.md`

Gate:

`N03_COGNITIVE_CAPABILITY_PROFILES_AVAILABLE`

---

## 7. N06B/C — Evidence-driven NanoAgent Runtime Design

After the initial N03 results, convert measured capability weaknesses into modular Runtime strategies.

Do not hardcode a model name as a substitute for capability-based selection.

### Layer B

Implement independently switchable:

- Minimum Sufficient Context Compiler.
- Dependency-aware Tool Router.
- Dynamic Action Schema and Grammar.
- Native Function Calling adapter.
- Compact Action DSL.
- Enumerated Action representation.
- Provenance-aware Slot Binder.

### Layer C

Implement independently switchable:

- Typed State integration.
- Conditional Action Graph.
- Typed Recovery Engine.
- Goal Predicate.
- Bounded replanning.
- Model Capability Profile.
- Protocol Selection Policy.

Every module must have:

- Explicit contract.
- Evidence-based motivation.
- Unit tests.
- Negative tests.
- Ablation switch.
- Resource accounting.
- Observability.

The combined Runtime must not receive hidden task answers.

### Model-specific protocol policy

Investigate a profile structure equivalent to:

    ModelProfile
        capability_passport
        inference_protocol
        thinking_policy
        action_representation
        grammar_policy
        context_strategy
        tool_routing_policy
        slot_binding_policy
        recovery_policy
        execution_budget

Allow capability negotiation between the Runtime and actual backend.

Record unsupported capabilities.

Do not silently fall back to another protocol during formal experiments.

Fallback behavior must be a separately declared experimental factor.

### Reuse decision

Use N01 findings and measured N03 requirements to decide whether to reuse or implement:

- Graph orchestration.
- Schema validation.
- Model transport.
- Grammar construction.
- Event persistence.
- State management.

Do not create a heavier framework merely to maximize feature count.

Publish:

- `reports/IJNANO_06_CAPABILITY_DRIVEN_RUNTIME_ARCHITECTURE.md`
- Model Profile specification.
- Modular source code.
- Conformance tests.

Gate:

`N06_NANOAGENT_MODULAR_RUNTIME_IMPLEMENTED`

---

## 8. N04/N07 — Research Mechanism Reproduction

Prioritize existing techniques:

### effGen

Use the verified official implementation.

Run its native local model interface with pinned models.

Capture framework-added prompts and actual model calls.

Compare native effGen with the minimal reference loop.

### PTC-inspired Runtime

Separate:

- Plan-to-Act only.
- Tool-constrained decoding only.
- Combined mechanism.

Measure semantic correctness, planning correctness and token overhead.

Do not treat constrained tool-name validity as proof of correct tool selection.

### TinyAgent-inspired ToolRAG

Use fixed model weights.

Compare:

- All tools exposed.
- Semantic retrieval.
- Dependency-aware retrieval.
- State-aware legal tool filtering.

Measure required tool recall as well as action accuracy.

Do not attribute gains from original TinyAgent fine-tuned weights to Runtime mechanisms.

### Action Representation

Compare:

- Native Function Calling.
- JSON.
- Grammar-constrained JSON.
- Natural-language action names.
- Numeric IDs.
- Compact DSL.
- Two-stage selection and slot filling.

Investigate model-specific tokenizer and training-distribution effects.

### Growing Harness / Automated Adaptation

Identify repeated control decisions that can be compiled into deterministic code.

Keep task-specific business logic separate from model-oriented Runtime logic.

Run matched comparisons with identical information availability.

Deliver mechanism-level physical evidence and reproducible implementation.

---

## 9. Execute Balanced SLM Harness Causal Pilot

Retain the original N00R pilot.

Mandatory models: S1, S2, S3.

| Arm | Mechanism |
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

Use at least 120 matched development cases per applicable model/arm.

Nominal maximum: 3,600 primary development trial slots.

Protocol sensitivity experiments from N02R remain separately identified.

For each arm preregister:

- Exactly which intervention changes.
- Applicable tasks.
- Information available.
- Tool inventory.
- Model budget.
- Retry budget.
- Evaluator scope.
- Comparison baseline.

Measure:

- Semantic tool accuracy.
- Argument correctness.
- Structural validity.
- Entity hallucinations.
- Dependency correctness.
- Recovery success.
- Termination.
- Model calls.
- Prompt tokens.
- Generated tokens.
- P50/P95 latency.
- Memory.
- Evidence completeness.

Do not publish formal business scores without a qualified business Oracle.

Use paired comparisons and appropriate confidence intervals.

Investigate negative transfer and mechanism interactions.

Do not optimize the formal holdout.

Deliver:

- `reports/IJNANO_SLM_HARNESS_CAUSAL_PILOT.md`
- `atlas/ij_nano/mechanism_effectiveness_matrix.json`
- `evidence/IJNANO/pilot/`
- Updated model profiles.
- Source-level failure ledger.

Gate:

`IJNANO_CAUSAL_PILOT_COMPLETE`

---

## 10. Required Interim Research Conclusions

The interim report must answer:

1. Does inference protocol selection materially affect small-model semantic accuracy?
2. Which LFM3 limitations originate from the model, template, parser or request protocol?
3. Which cognitive primitives differ most across the three small models?
4. Which action representations are best supported by each model?
5. What context and tool inventory sizes are appropriate?
6. Which deterministic Runtime mechanisms provide genuine gains?
7. Which mechanisms introduce regressions?
8. Can one common SLM profile serve all three models?
9. Which existing components should NanoAgent reuse?
10. Is the Layer A integrity foundation qualified?
11. Which formal research scopes remain blocked?
12. What is required to begin the Model × Harness transfer matrix?

For every conclusion provide:

- Exact tested comparison.
- Sample size.
- Effect size.
- Confidence interval where applicable.
- Evidence reference.
- Applicable scope.
- Remaining uncertainty.

Do not report untested architecture recommendations as verified findings.

---

## 11. GitHub Delivery and Recovery

Continue publishing to Issue #10 and Draft PR #11.

Do not create another competing research branch.

Preserve historical evidence and previous results.

Use small logical commits.

Maintain:

- Mission state.
- Task ledger.
- Blocker ledger.
- Hypothesis status.
- Defect ledger.
- Experiment manifests.
- Physical coverage.
- Persistent queue.
- Recovery command.

Update the PR description to reflect current scoped qualification.

Run sensitive-data scans and regression tests before publication.

Push normally.

Verify the remote SHA.

Do not force-push or merge.

---

## 12. Execution Directive

Start immediately.

Parallel execution lanes:

- Lane A: N01 research closure.
- Lane B: N06A-R execution-integrity hardening.
- Lane C: N05A cognitive evaluator qualification.
- Lane D: N02R physical protocol causal analysis.
- Lane E: N03 cognitive capability measurements.
- Lane F: evidence-driven N06B/C and N04/N07 implementation.
- Lane G: 3,600-slot causal pilot.

Schedule physical work under the existing host-wide GPU lease.

Do not block independently qualified physical diagnostics on the unavailable full business Oracle.

Do not run formal business evaluations before their required evaluator scope qualifies.

Continue through the original IJ-NANO-1.0 requirements after these foundations are established.

The primary research objective is to discover which Runtime mechanisms are necessary for each small model, and why.

Do not design NanoAgent around assumptions that have not been tested.

Design NanoAgent around measured model capabilities.

Execute now.
