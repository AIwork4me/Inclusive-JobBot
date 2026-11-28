# MISSION IJ-NANO-1.0 — SLM-native Agentic Runtime Co-design & Capability-driven Harness Optimization

## 0. Mission Identity

- Repository: https://github.com/AIwork4me/Inclusive-JobBot
- GitHub account: AIwork4me
- Mission ID: IJ-NANO-1.0
- Proposed research branch: `mission/ij-nano-1.0-slm-native-agentic-runtime`
- Proposed SDK name: JobBot NanoAgent SDK
- Target platform: Native Windows + AMD Radeon RX 7900 XTX 24GB
- GPU architecture: gfx1100
- Primary inference engine: llama.cpp
- Primary backend: Vulkan
- Secondary backend: ROCm/HIP
- Primary model class: approximately 1–3B total parameters
- Deployment objective: fully local, commercially deployable, resource-efficient Purpose-built JobBots
- Future hardware target: low-power NPU and dedicated edge AI platforms
- Delivery: independent GitHub tracking Issue, Draft PR, source code, physical benchmark evidence, SDK package, Chinese and English research reports.

Act as a Principal AI Infrastructure Architect, Small Language Model Research Scientist, Agentic Runtime Engineer, Compiler Engineer, Benchmark Scientist, Security Engineer and independent software quality reviewer.

Your responsibility is to complete the research, implementation, physical experiments, causal investigation, engineering qualification and publication of this mission.

Do not stop after literature review, architectural design, SDK scaffolding, a successful demonstration or a preliminary benchmark.

Deliver a reproducible engineering research system capable of determining which Agentic Runtime design is most suitable for a specific small language model and professional job.

---

# 1. North Star — Minimum Sufficient Intelligence

The latest Inclusive-JobBot research suggests that general-purpose Agentic SDKs may impose cognitive requirements that are poorly matched to 2B-class language models.

This mission investigates the following hypothesis:

**Small language models require capability-matched Agentic Runtimes. Redesigning the runtime around the model's actual capabilities may substantially improve business reliability and resource efficiency without increasing model size.**

The final objective is to develop a scientifically validated methodology for building:

    Purpose-built JobBot
        = Purpose-built Model
        × Capability-matched Agentic Runtime
        × Professional Job Intelligence
        × Business Assurance
        × Appropriate Hardware

Investigate:

1. Which agentic capabilities are intrinsically difficult for 2B models?
2. Which failures originate from the model, inference engine, tool protocol or SDK?
3. Which cognitive burdens can be transferred from probabilistic inference to deterministic software?
4. Which Runtime optimization mechanisms genuinely improve small-model capability?
5. Do different 2B models require different Runtime profiles?
6. Can SLM-specific Runtime optimization generalize across jobs?
7. Can a capability-driven Harness Optimizer automatically discover effective Runtime configurations?
8. Can a 2B model with a specialized runtime outperform larger general-purpose agents on clearly defined professional workloads?
9. What is the minimum sufficient model capacity and runtime architecture required by each job?
10. Can the resulting architecture be deployed economically on future low-power NPU hardware?

Long-term product targets:

- Greater than 99% first-pass business correctness within a qualified job scope.
- Human-agent dialogue turns no greater than one tenth of a comparable general-purpose agent.
- Zero unauthorized business state changes.
- Fully local model inference.
- Bounded execution.
- Low model invocation count.
- Low token consumption.
- Small memory footprint.
- Maintainable software architecture.
- Commercial deployment eligibility.

These targets are hypotheses and product requirements, not pre-approved research conclusions.

A scientifically valid negative result is an acceptable mission outcome.

---

# 2. Research Hypotheses and Falsification Criteria

Preregister the following hypotheses before confirmatory experiments.

| ID | Hypothesis |
|---|---|
| H01 | Smaller models benefit more from appropriately designed Runtime assistance than from simply adding longer instructions. |
| H02 | State-aware context reduction improves semantic decision accuracy and inference efficiency. |
| H03 | Dependency-aware tool routing improves tool selection and multi-tool task success. |
| H04 | Constrained action decoding improves structural validity, with measurable but potentially different semantic gains. |
| H05 | Typed state and provenance-aware slot binding reduce entity hallucinations and argument errors. |
| H06 | Deterministic task control reduces long-horizon error accumulation. |
| H07 | Typed recovery policies outperform unrestricted model self-repair for identifiable failure classes. |
| H08 | The optimal Harness configuration differs across model families. |
| H09 | Some SLM-oriented Runtime mechanisms generalize across unseen professional jobs. |
| H10 | Failure-driven automatic Harness optimization can improve held-out task performance at acceptable engineering cost. |
| H11 | A compact, specialized runtime can outperform heavier general-purpose frameworks under equivalent task requirements. |
| H12 | A specialized 2B JobBot can approach or exceed larger general-purpose agents within a qualified professional scope. |

For every hypothesis define:

- Independent variable.
- Dependent variable.
- Matched baseline.
- Expected mechanism.
- Competing explanations.
- Experimental population.
- Statistical analysis.
- Minimum practically meaningful effect.
- Acceptance criteria.
- Falsification criteria.
- Known confounders.

Do not change confirmatory success criteria after inspecting formal results.

Distinguish:

- SUPPORTED
- NOT_SUPPORTED
- INCONCLUSIVE
- BLOCKED
- NOT_RUN

A hypothesis must not be marked SUPPORTED merely because one favorable example exists.

---

# 3. Non-negotiable Research Principles

## 3.1 Evidence integrity

Every physical result must bind to:

- Exact source commit.
- Model revision.
- Model SHA256.
- Quantization.
- Chat Template SHA256.
- Tokenizer identity.
- Inference engine binary SHA256.
- GPU identity.
- GPU backend.
- SDK or Harness identity.
- Runtime Profile SHA256.
- Job Package SHA256.
- Dataset SHA256.
- Oracle identity.
- Run ID.
- Trial ID.

Maintain separate statuses for:

- Execution completion.
- Evidence validity.
- Business success.
- Safety compliance.
- Capability qualification.
- Product readiness.

Use PASS, FAIL, BLOCKED and NOT_RUN consistently.

Never present:

- Software fixtures as real model execution.
- CPU inference as Radeon GPU execution.
- A successful demonstration as capability qualification.
- A structurally valid action as a semantically correct action.
- A correct final answer as proof of correct business execution.
- An SDK self-reported success as an independent business verdict.
- Synthetic business results as field reliability.
- Radeon resource measurements as physical NPU performance.

## 3.2 Fixed model weights

The primary research intervention is Runtime design.

Do not fine-tune or change model weights during primary Runtime comparison experiments.

If reproducing a paper requires a specially trained model, create a separate reproduction arm.

Do not attribute improvements caused by weight changes to the Harness.

## 3.3 Research independence

The tested Runtime must never:

- Read hidden Oracle expectations.
- Read formal benchmark solutions.
- Modify its own evaluation criteria.
- Choose favorable test cases after observing results.
- Exclude difficult tasks.
- Fabricate missing tool results.
- Inject a correct action obtained from benchmark answer metadata.

A production validator and an independent research evaluator must be distinct components.

## 3.4 Local-only execution

All primary runtime model inference must occur locally.

No cloud LLM fallback.

No external agent service.

No hidden external API.

A larger model may be used separately for offline research or Harness optimization only if its identity, role, data access and engineering cost are explicitly recorded.

The final runtime must not require the offline optimizer.

---

# 4. N00 — Repository Audit and Research Isolation

## 4.1 Inspect existing work

Clone and inspect:

https://github.com/AIwork4me/Inclusive-JobBot

Read all relevant repository instructions:

- `AGENTS.md`
- `HANDOFF.md`
- `MISSION_STATE.json`
- `MISSION_STATE_IJSDK.json`
- `TASK_LEDGER.md`
- `TASK_LEDGER_IJSDK.md`
- `BLOCKERS.md`
- `DECISIONS.md`
- Existing model passports.
- Existing runtime configurations.
- Existing benchmark implementations.
- Existing evaluation and Oracle implementations.
- Existing GitHub Issues and Pull Requests.

Previously observed remote state:

- PR #6 HEAD: `06f25ab50db9e8ef074d9fb804de3191d7eadb98`
- PR #8 HEAD: `71660fbb885d2ee9cdf73c37293ea6f616d86947`
- PR #8 frozen source: `fe56f324daf4ae106908e0d0a0f16967afc9c463`

Treat these as historical audit anchors.

Re-query the actual remote state before choosing the research base.

## 4.2 Dependency constraints

At the previously audited PR #8 HEAD:

- P3 SDK admission had been reopened as FAIL.
- P4 Harness integrity had been reopened as FAIL.
- P5 Oracle qualification had been reopened as FAIL.
- Formal GPU matrix execution was not authorized.
- IJ-SDK-1.1 P4A/P4B/P5R remained pending.

Do not inherit invalid qualification results.

Inspect whether these blockers have subsequently been resolved.

Reuse a component only when its required scope is independently qualified and its exact implementation identity is recorded.

If a dependency remains blocked:

- Continue literature research.
- Continue isolated software development.
- Continue physical model microbenchmarks that do not depend on the defective component.
- Prepare independent conformance and Oracle controls.
- Keep affected formal business evaluations BLOCKED.

Do not duplicate or interfere with ongoing IJ-SDK-1.1 repairs.

If a temporary independent evaluator is necessary, clearly identify its scope and independently qualify it.

## 4.3 Branch isolation

Create:

`mission/ij-nano-1.0-slm-native-agentic-runtime`

Use a dedicated worktree.

Select a reviewed source commit containing the required assets.

Document dependencies on PR #6 and PR #8.

Do not automatically rebase onto changing parent branches.

Do not:

- Modify PR #6 or PR #8 directly.
- Stop another active GPU research worker.
- Overwrite historical evidence.
- Force-push.
- Merge into the default branch.
- Publish upstream Issues or PRs without explicit authorization.

If the same Radeon GPU is already reserved by another mission, respect its exclusive lease.

Parallelize software work while waiting for an available GPU lease.

## 4.4 Mission-specific state

Create:

- `MISSION_STATE_IJNANO.json`
- `TASK_LEDGER_IJNANO.md`
- `BLOCKERS_IJNANO.md`
- `HANDOFF_IJNANO.md`
- `docs/IJNANO_RESEARCH_PROTOCOL.md`

Avoid conflicting changes to other missions' state files.

Create a new tracking Issue and Draft PR.

Record exact initial source commit and dependency graph.

Deliver:

- `reports/IJNANO_00_BASELINE_AND_DEPENDENCY_AUDIT.md`
- `evidence/IJNANO/N00/baseline_manifest.json`
- `evidence/IJNANO/N00/dependency_qualification.json`

Gate:

`N00_RESEARCH_BASELINE_FROZEN`

---

# 5. N01 — Comprehensive Literature and Open-source Technology Investigation

Conduct a current, primary-source-based research survey.

Do not rely only on summaries from previous conversations.

Retrieve official papers, code, documentation, release artifacts and licenses.

## 5.1 Mandatory research subjects

### R01 — effGen

Repository:

https://github.com/ctrl-gaurav/effGen

Paper candidate:

EffGen: Enabling Small Language Models as Capable Autonomous Agents.

Investigate:

- Small-model-specific prompting.
- Tool description compression.
- Complexity-aware routing.
- Task decomposition.
- Memory mechanisms.
- Native local model integration.
- Loop detection.
- Tool-call recovery.
- Experimental findings for approximately 1.5B models.
- Framework overhead.
- Ablation methodology.

### R02 — PTC-Decoder

Repository candidate:

https://github.com/yuminghui/llm-tool-constrained-decoder

Paper candidate:

PTC-Decoder: Towards Intelligent SLMs on Offline Resource-Constrained Edge Devices.

Investigate:

- Plan-to-Act.
- Tool-constrained decoding.
- DFA-based tool selection.
- Dynamic token constraints.
- Parameter generation.
- Qwen3.5-2B experiments.
- Original evaluation methodology.
- Compatibility with llama.cpp Grammar interfaces.

### R03 — TinyAgent

Repository:

https://github.com/SqueezeAILab/TinyAgent

Investigate:

- LLMCompiler.
- ToolRAG.
- Function calling.
- Task dependency planning.
- Small-model-specific tool training.
- Local deployment.
- Quantization.
- Separation of model training effects from Runtime effects.

### R04 — Automated SLM Harness Adaptation

Repository candidate:

https://github.com/malusamayo/slm-harness-adaptation

Paper candidate:

Better Harnesses, Smaller Models: Building 90% Cheaper Agents via Automated Harness Adaptation.

Investigate:

- Failure-driven Harness modification.
- Tool redesign.
- Workflow skeletons.
- Hooks.
- Prompt adaptation.
- Automated search.
- Development/holdout separation.
- Model size and active parameter distinctions.
- Optimization and deployment cost.

### R05 — Growing Harness

Paper candidate:

Grow the Harness, Not the Context.

Investigate:

- Converting repeated model decisions into executable programs.
- Function-level Harness improvements.
- Control-flow optimization.
- Independent validation.
- Regression prevention.
- Model call reduction.

### R06 — Meta-Harness

Repository candidate:

https://github.com/stanford-iris-lab/meta-harness

Investigate:

- Automated task-specific Harness design.
- Search-space representation.
- Evaluation feedback.
- Optimization cost.
- Generalization.
- Reproducibility.

### R07 — MagenticLite

Repository candidate:

https://github.com/microsoft/magentic-ui

Investigate:

- Small-model and Harness co-design.
- Context management.
- Delegation.
- Task decomposition.
- Recovery.
- Lightweight execution patterns.

### R08 — Constrained generation

Investigate:

- llama.cpp GBNF.
- llama.cpp JSON Schema conversion.
- LLGuidance.
- XGrammar.
- Other currently relevant constrained decoding implementations.

Primary repositories:

- https://github.com/ggml-org/llama.cpp
- https://github.com/guidance-ai/llguidance
- https://github.com/mlc-ai/xgrammar

### R09 — Existing general-purpose frameworks

Investigate reusable mechanisms from:

- Pydantic AI.
- LangGraph.
- OpenAI Agents SDK.
- Google ADK.
- smolagents.
- PocketFlow.
- DSPy.

Prioritize component reuse over unnecessary reimplementation.

## 5.2 Verify every research claim

For every paper record:

- Verified title.
- Authors.
- Publication date.
- Venue or preprint status.
- Official URL.
- Exact model identities.
- Total and active parameter counts.
- Evaluation dataset.
- Baselines.
- Metrics.
- Reported gains.
- Statistical support.
- Limitations.
- Available reproduction code.

For every repository record:

- Exact upstream commit.
- Latest stable release.
- SPDX license.
- Full license text.
- Commercial use eligibility.
- Dependency licensing.
- Local execution support.
- Native Windows support.
- Community activity.
- Security advisories.
- Reproduction requirements.

Verify that the cited project and paper actually exist and correspond to the same research.

Do not invent paper results, repository capabilities, commercial rights or model compatibility.

If a previously proposed research reference cannot be verified, mark it UNVERIFIED and continue.

## 5.3 Reuse versus rebuild decision

Classify every relevant component:

- REUSE_DIRECTLY
- REUSE_WITH_ADAPTER
- EXTEND_EXISTING_FRAMEWORK
- REIMPLEMENT_CLEAN_ROOM
- RESEARCH_ONLY
- LICENSE_BLOCKED
- TECHNICALLY_UNSUITABLE
- UNVERIFIED

Explain why.

Deliver:

- `reports/IJNANO_01_RESEARCH_LANDSCAPE_CN.md`
- `reports/IJNANO_01_RESEARCH_LANDSCAPE_EN.md`
- `reports/IJNANO_OPEN_SOURCE_REUSE_DECISION.md`
- `evidence/IJNANO/N01/research_catalog.json`
- `evidence/IJNANO/N01/license_matrix.json`

Gate:

`N01_RESEARCH_LANDSCAPE_VERIFIED`

---

# 6. N02 — Physical Runtime and Model Identity Qualification

## 6.1 Mandatory model arms

| ID | Model | Role |
|---|---|---|
| S1 | MiniCPM5-2B | Existing project model |
| S2 | LFM3-1.7B | Alternative small-model architecture |
| S3 | Qwen3.5-2B | Competitive small-model baseline |
| R1 | Qualified approximately 8B model | Larger reference |
| R2 | Qualified approximately 14B model | Larger reference |

Verify the exact identities from IJ-SDK research assets.

Reuse downloaded weights only after SHA256 verification.

If a model cannot be loaded or its required protocol is unsupported, preserve the blocker and continue other models.

## 6.2 Inference configuration

Use llama.cpp as the primary runtime.

Attempt to reproduce the pinned IJ-SDK runtime configuration.

Verify:

- Exact engine binary.
- GPU offloading.
- Physical GPU identity.
- Native tool-call protocol.
- Chat Template.
- Structured generation.
- Grammar support.
- Tokenizer.
- Context length.
- Streaming.
- Cancellation.
- Token accounting.

Keep Vulkan as the primary candidate unless a new preregistered qualification protocol justifies changing it.

ROCm/HIP is a separate backend comparison.

Do not mix backend results.

## 6.3 Quantization strategy

Use the previously qualified Q8_0 profiles as initial research anchors where available.

Also investigate supported Q4-class profiles.

Separate:

- Primary model/Harness comparison.
- Quantization sensitivity.
- Deployment footprint comparison.

Do not silently change quantization between arms.

Preregister the primary quantization selection rule before confirmatory evaluation.

## 6.4 Commercial model eligibility

Independently verify official model weight licenses.

In particular, investigate any revenue-conditioned licensing terms applicable to LFM3.

A model may remain a valuable research candidate even if its commercial deployment requires additional permission.

Do not confuse an open SDK license with unrestricted model weight commercial rights.

Deliver:

- `reports/IJNANO_02_PHYSICAL_RUNTIME_AND_MODEL_PASSPORTS.md`
- `models/ij_nano/model_manifest.json`
- `evidence/IJNANO/N02/`

Gate:

`N02_PHYSICAL_MODEL_RUNTIME_QUALIFIED`

---

# 7. N03 — Fine-grained SLM Cognitive Capability Profiling

The objective is to measure the cognitive primitives that a Runtime needs from a model.

Do not use a single generic benchmark score to configure the Harness.

## 7.1 Capability taxonomy

Create measurable primitives covering:

| ID | Cognitive capability |
|---|---|
| C01 | Intent classification |
| C02 | Goal extraction |
| C03 | Single instruction understanding |
| C04 | Multiple constraint understanding |
| C05 | Boolean decision |
| C06 | Enumerated choice |
| C07 | Natural-language action selection |
| C08 | Tool-name selection |
| C09 | JSON structural generation |
| C10 | Nested schema generation |
| C11 | Compact DSL generation |
| C12 | Slot extraction |
| C13 | Entity reference resolution |
| C14 | Numerical extraction |
| C15 | Unit and currency understanding |
| C16 | Tool result comprehension |
| C17 | State interpretation |
| C18 | Action dependency recognition |
| C19 | Short-horizon planning |
| C20 | Conditional branching |
| C21 | Dynamic replanning |
| C22 | Error recognition |
| C23 | Argument correction |
| C24 | Alternative action recovery |
| C25 | Stop versus continue decision |
| C26 | Clarification decision |
| C27 | Escalation decision |
| C28 | Context interference resistance |
| C29 | Instruction ambiguity robustness |
| C30 | Multilingual semantic consistency |
| C31 | Grounded answer generation |
| C32 | Uncertainty and abstention behavior |

## 7.2 Capability isolation

Each primitive should measure a narrowly defined cognitive requirement.

Examples:

- Tool selection with all arguments supplied.
- Argument generation with the correct tool supplied.
- State interpretation without tool execution.
- Planning with deterministic tool outcomes.
- Recovery with a standardized error.
- Termination with explicit task-state information.

Diagnostic interventions may provide information that an autonomous agent would normally infer.

Label such trials as diagnostic capability isolation, not autonomous task completion.

## 7.3 Stress dimensions

Independently vary:

- Number of instructions.
- Tool inventory size: 2, 4, 8, 16, 32, 64.
- Number of candidate actions.
- Number of arguments.
- Schema nesting depth.
- Number of entity references.
- Action dependency depth.
- Context length.
- Number of irrelevant observations.
- Error complexity.
- Language.
- Prompt representation.
- Quantization.

Investigate interaction effects rather than assuming monotonic degradation.

## 7.4 Minimum experimental coverage

Create:

- At least 20 independent development cases per cognitive primitive.
- At least 640 primitive-level development cases in total.
- At least 320 additional reserved capability confirmation cases.

Execute all three small models.

Include representative larger-model reference trials.

Use task-family splits rather than paraphrase-only splits.

Report confidence intervals and subgroup coverage.

The minimum number of cases is a research floor, not proof of deployment reliability.

## 7.5 Model Capability Passport

Create a machine-readable profile containing:

- Exact model identity.
- Qualified primitive capabilities.
- Observed failure classes.
- Context sensitivity.
- Tool inventory sensitivity.
- Supported action representations.
- Error recovery performance.
- Planning depth.
- Resource profile.
- Uncertainty.
- Recommended Runtime interventions.

Example structure:

```yaml
model_id: exact-pinned-model
quantization: Q8_0

capabilities:
  tool_selection:
    evidence_status: QUALIFIED
    measurement_ref: capability-result-id
  invalid_argument_recovery:
    evidence_status: LIMITED
    measurement_ref: capability-result-id
  conditional_planning:
    evidence_status: NOT_QUALIFIED

runtime_recommendations:
  action_representation: candidate-to-be-validated
  context_strategy: candidate-to-be-validated
  recovery_strategy: candidate-to-be-validated
```

Do not populate recommended numeric limits from intuition.

Derive them from measured capability curves and subsequent Runtime confirmation experiments.

Deliver:

- `reports/IJNANO_03_SLM_COGNITIVE_CAPABILITY_ATLAS.md`
- `atlas/ij_nano/model_capabilities/`
- `profiles/ij_nano/model_passports/`

Gate:

`N03_COGNITIVE_CAPABILITY_PROFILES_AVAILABLE`

---

# 8. N04 — Reproduce Existing SLM-native Agentic Approaches

Before inventing a new SDK, determine what existing research and software can already achieve.

## 8.1 Reproduction tiers

For every research technique distinguish:

### Tier A — Exact reproduction

Use the original paper's:

- Model.
- Dataset.
- Code.
- Configuration.
- Evaluation.
- Hardware where feasible.

### Tier B — Platform adaptation

Retain the original mechanism while changing:

- Inference backend.
- Windows integration.
- Hardware.
- Supported model interface.

### Tier C — Mechanism reproduction

Implement the central algorithm or design principle using our fixed model weights and qualified JobBot benchmark.

Do not present Tier B or C as exact paper reproduction.

## 8.2 Mandatory investigations

### E01 — effGen native

Install the verified SDK in an isolated environment.

Evaluate its original SLM-oriented mechanisms without task-specific tuning.

Verify actual local model integration.

Inspect native execution loops and framework-added prompts.

### E02 — effGen model-specific adaptation

Tune only using development data.

Compare:

- Original effGen configuration.
- SLM-class optimized configuration.
- Model-specific configuration.

### E03 — PTC-inspired constrained execution

Reproduce separately:

- Plan-to-Act only.
- Tool-constrained decoding only.
- Combined mechanism.

Measure plan validity, semantic tool accuracy and token overhead.

### E04 — TinyAgent-inspired ToolRAG

Use the same model weights across arms.

Compare:

- All tools exposed.
- Semantic Top-K retrieval.
- Dependency-aware retrieval.
- State-aware legal tool filtering.

### E05 — Failure-driven Harness adaptation

Reproduce the core optimization methodology:

- Collect failure trajectories.
- Identify failure mechanisms.
- Propose Harness changes.
- Evaluate on development data.
- Accept or reject changes using a frozen selection rule.

### E06 — Growing Harness principle

Identify repeated control operations and compile them into reusable deterministic software.

Measure how many model calls are eliminated without changing task semantics.

## 8.3 Reproduction acceptance

For each technique provide:

- Original claim.
- Actual reproduced scope.
- Exact implementation.
- Matched baseline.
- Physical measurements.
- Known discrepancies.
- Engineering applicability.
- Licensing status.
- Reuse recommendation.

If the original implementation is unavailable or incompatible with Windows, investigate a minimal mechanism reproduction.

Do not conceal an unsuccessful reproduction.

Deliver:

- `reports/IJNANO_04_RESEARCH_REPRODUCTION_REPORT.md`
- `evidence/IJNANO/N04/`
- Reproduction scripts and locked configurations.

Gate:

`N04_EXISTING_SLM_APPROACHES_CHARACTERIZED`

---

# 9. N05 — Independent Benchmark and Oracle Qualification

This phase is a mandatory prerequisite for formal business performance claims.

## 9.1 Reuse policy

Inspect IJ-SDK-1.1 P4A/P4B/P5R progress.

If its qualified Harness, Gateway and Oracle are available, reuse their exact audited commits.

If not, keep dependent formal experiments BLOCKED.

Never rely on the original 14-control Oracle qualification.

## 9.2 Required evaluator architecture

Separate:

- E0: transport and evidence integrity.
- E1: semantic action correctness.
- E2: planning and dependency correctness.
- E3: execution correctness.
- E4: final business correctness.
- E5: security and authorization.
- E6: performance and resource accounting.

Require an independently implemented business state verifier.

Verify:

- Initial world.
- Actual executed actions.
- Authorization.
- State transitions.
- Final state.
- Transaction effects.
- Idempotency.
- Rollback.
- Business invariants.
- Correct refusal and clarification.
- False completion.
- Missing evidence.

Use independently authored positive witnesses and critical negative mutations.

Do not rely on substring matching for semantic business facts.

Do not rely on a single golden action sequence.

Accept valid alternative execution trajectories.

## 9.3 Prevent evaluation leakage

NanoAgent must never access:

- Ground-truth actions.
- Hidden expected arguments.
- Expected final state.
- Oracle internals used for formal scoring.
- Formal task solutions.
- Hidden fault schedules.
- Holdout answers.

Production validation may use legitimate business rules available in a real deployment.

The formal evaluation system may use additional independent verification information.

Keep these boundaries explicit.

## 9.4 Oracle challenge testing

Include at least 500 qualification controls unless a broader previously qualified control suite is reused.

Cover:

- Incorrect state hashes.
- Missing audit events.
- Unauthorized state changes.
- Duplicate effects.
- Incorrect polarity.
- Wrong numerical values.
- Wrong units.
- Missing approval.
- Contradictory planning preconditions.
- Incorrect entity binding.
- Unexpected tool outputs.
- Semantically wrong answers containing correct keywords.
- Correct alternative trajectories.

Run mutation tests against intentionally weakened evaluators.

Every critical negative must be rejected for the intended reason.

No critical unresolved disagreement may remain in a formally qualified scope.

Deliver:

- `reports/IJNANO_05_BENCHMARK_VALIDITY.md`
- `evidence/IJNANO/N05/oracle_scope_matrix.json`
- Exact evaluator manifest.

Gate:

`N05_INDEPENDENT_EVALUATION_QUALIFIED`

---

# 10. N06 — NanoAgent SDK Architecture

Design a modular, lightweight, capability-aware runtime.

Working product name:

**JobBot NanoAgent SDK**

Do not create a large generic framework merely to demonstrate feature completeness.

Every substantial component must address a measured or testable research problem.

## 10.1 Target architecture

Implement the following conceptual layers:

    User / Business Request
              |
    Job Intelligence Compiler
              |
    Capability-aware Runtime Profile
              |
    SLM-native Agent Controller
       |          |          |
    Context    Action      Typed
    Compiler   Decoder     State
       |          |          |
    Local Model Runtime    Recovery Engine
              |
    Business Tool Gateway
              |
    Production Business Validator
              |
    Verified Business Result

A separate research evaluator observes the resulting evidence.

It does not participate in runtime decision-making.

## 10.2 Core abstractions

Provide stable interfaces equivalent to:

```python
class ModelRuntime:
    def capabilities(self): ...
    def generate(self, request, budget): ...
    def cancel(self, request_id): ...


class ModelCapabilityProfile:
    def load(self, manifest): ...


class ContextCompiler:
    def compile(self, task, state, profile, legal_actions): ...


class ActionDecoder:
    def decode(self, model_output, action_schema): ...


class ToolRouter:
    def candidates(self, goal, state, tool_manifest): ...


class SlotBinder:
    def bind(self, action, trusted_state): ...


class StateStore:
    def read(self, session_id): ...
    def apply(self, verified_event): ...


class RecoveryPolicy:
    def decide(self, failure, state, budget): ...


class GoalController:
    def evaluate(self, task, state): ...


class JobBot:
    def execute(self, request): ...
    def cancel(self): ...
    def resume(self, checkpoint): ...
```

These are conceptual interfaces.

Adapt the concrete implementation to the repository's existing conventions and research findings.

## 10.3 Proposed directory structure

```text
src/nanoagent/
    core/
    runtime/
    profiles/
    context/
    actions/
    decoders/
    routing/
    state/
    binding/
    planning/
    recovery/
    gateway/
    validation/
    observability/
    optimization/

benchmarks/ij_nano/
    contracts/
    cognitive/
    datasets/
    experiments/
    runners/
    ablations/
    statistics/

configs/ij_nano/
profiles/ij_nano/
jobs/ij_nano/
evaluation/ij_nano/
evidence/IJNANO/
atlas/ij_nano/
tests/ij_nano/
```

Avoid unnecessary dependencies.

Measure:

- Installed dependency footprint.
- Startup cost.
- Runtime memory overhead.
- Transitive dependencies.
- Code size.
- Public API complexity.
- Maintenance burden.

Prefer proven existing libraries for generic infrastructure.

The original contribution should concentrate on capability-driven orchestration.

Gate:

`N06_NANOAGENT_MODULAR_RUNTIME_IMPLEMENTED`

---

# 11. N07 — Develop and Validate Individual Runtime Mechanisms

Each mechanism must be independently switchable.

Every mechanism requires:

- Explicit configuration.
- Unit tests.
- Integration tests.
- Negative controls.
- Physical model evaluation.
- Failure attribution.
- Resource measurement.

## M01 — Minimum Sufficient Context Compiler

Investigate whether smaller, decision-specific context improves model behavior.

Compare:

- Full conversation history.
- Sliding window.
- Static compact prompt.
- Deterministically compiled task state.
- Retrieved relevant observations.
- Model-generated summary.

The compiler must preserve all necessary:

- User intent.
- Business constraints.
- Verified facts.
- Unresolved requirements.
- Relevant prior decisions.
- Current legal actions.

Do not use hidden benchmark solutions to determine what information is relevant.

Measure:

- Prompt tokens.
- Prefill latency.
- Semantic correctness.
- Information omission.
- Context interference.
- Long-horizon consistency.

## M02 — Dependency-aware Tool Router

Implement:

- Semantic tool retrieval.
- Job-specific tool groups.
- Dependency graph.
- Required prerequisite tools.
- State-aware action availability.
- Candidate expansion when confidence is insufficient.

Compare:

- Full tool inventory.
- Top-K retrieval.
- Dependency closure.
- State legality filtering.
- Combined approach.

Measure:

- Required tool recall.
- Candidate inventory reduction.
- Tool selection accuracy.
- Multi-tool execution success.
- Failure caused by over-filtering.

A missing necessary tool must be explicitly classified as a routing failure.

Do not report only candidate precision.

## M03 — Action Representation Layer

Support:

1. Native Function Calling.
2. Free JSON.
3. Grammar-constrained JSON.
4. Enumerated natural-language actions.
5. Numeric Action IDs.
6. Compact Action DSL.
7. Tool Selection followed by Slot Filling.

Use equivalent action semantics.

Measure:

- Structural validity.
- Semantic action accuracy.
- Argument accuracy.
- Output tokens.
- Model calls.
- Decode latency.
- Error recovery.

A shorter action representation is not automatically better.

Investigate compatibility with each model's training distribution and tokenizer.

## M04 — Dynamic Constrained Decoder

Implement state-dependent action schemas and Grammar generation.

Use llama.cpp native capabilities where possible.

Investigate LLGuidance and XGrammar only where compatible and justified.

Evaluate:

- No constraint.
- Tool-name constraints.
- Argument schema constraints.
- State-dependent constraints.
- Full compact DSL constraints.

Handle:

- Empty legal action sets.
- EOS and stop conditions.
- Unicode.
- Tokenizer boundaries.
- Unsupported grammar constructs.
- Grammar compilation cost.
- Dynamic schema changes.

Constraints must not be treated as an authorization boundary.

A valid output can still be semantically incorrect.

All consequential actions require independent Gateway validation.

## M05 — Provenance-aware Slot Binder

Represent trusted business facts as:

```text
Fact:
    entity_id
    property
    value
    data_type
    unit
    source_event_id
    timestamp
    validity_scope
    state_version
```

Support references to existing verified facts.

Allow deterministic binding of already known values.

Never fabricate missing values.

Never read hidden expected arguments.

Distinguish:

- Model-extracted slots.
- User-provided slots.
- Tool-observed slots.
- Deterministically derived slots.
- Unresolved slots.

Require clarification when essential data is unavailable.

Measure:

- Argument accuracy.
- Entity hallucinations.
- Slot completeness.
- Provenance correctness.
- Incorrect binding.
- Token reduction.

## M06 — Typed State and Memory

Maintain structured state outside the model context.

Include:

- Current business goal.
- Verified facts.
- Completed actions.
- Pending actions.
- Outstanding prerequisites.
- Active permissions.
- Unresolved questions.
- Relevant errors.
- Recovery history.

Separate persistent session state from current model input.

Verify:

- State consistency.
- Cross-session isolation.
- Stale fact invalidation.
- State versioning.
- Checkpoint recovery.
- Concurrent access.
- Privacy.

Do not allow generated text to overwrite trusted state directly.

## M07 — Conditional Action Graph Engine

Implement:

- Nodes.
- Edges.
- Preconditions.
- Postconditions.
- Conditional branches.
- Alternative valid paths.
- Dependency relationships.
- Compensation actions.
- Approval boundaries.
- Goal predicates.

Support model-driven decisions only at appropriate graph nodes.

The graph must derive from independently defined business rules and SOPs, not from individual test answers.

Compare:

- Autonomous Plan-first.
- Autonomous Acting-first.
- Guided planning.
- Conditional Action Graph.
- Deterministic workflow.
- Hybrid workflow.

Measure:

- Planning validity.
- Executability.
- Long-horizon completion.
- Model invocation count.
- Business correctness.
- Workflow authoring cost.

## M08 — Typed Recovery Engine

Classify failures into:

- Structural generation error.
- Invalid argument.
- Unknown entity.
- Unknown tool.
- Missing prerequisite.
- Temporary tool failure.
- Conflicting observation.
- Permission denial.
- Context exhaustion.
- Model timeout.
- Stale state.
- Invalid action.
- Unrecoverable business exception.

Define policy-specific recovery actions:

- Retry same action.
- Request missing slot.
- Regenerate only invalid field.
- Select an alternative allowed action.
- Refresh trusted state.
- Replan a bounded subtask.
- Execute deterministic recovery.
- Request human intervention.
- Stop safely.

Compare unrestricted model recovery against typed recovery.

Measure:

- First-pass performance.
- Recovered success.
- Extra model calls.
- Additional latency.
- Retry loops.
- Incorrect recovery.
- User interaction cost.

Do not count recovered success as first-pass success.

## M09 — Goal and Budget Controller

Implement:

- Explicit business goal predicates.
- Completion verification.
- Stop conditions.
- Absolute deadlines.
- Model call budgets.
- Tool call budgets.
- Token budgets.
- Retry budgets.
- Loop detection.
- Cancellation.
- Escalation.

The model may propose termination.

The controller verifies whether termination is valid.

Do not let the Runtime silently complete unmet business goals.

Measure:

- False completion.
- Premature termination.
- Infinite loop rate.
- Budget compliance.
- Successful task cost.

## M10 — Model Capability-aware Runtime Profile

Use the evidence from N03 to configure:

- Context strategy.
- Maximum visible tools.
- Action representation.
- Grammar strategy.
- Slot binding.
- Planning strategy.
- Recovery policy.
- Maximum autonomous horizon.
- Escalation conditions.

Profile selection must be driven by measurable capability requirements.

Do not hardcode special cases based on benchmark task IDs.

Provide an auditable explanation for every Runtime decision.

Publish individual mechanism reports and profiles.

Gate:

`N07_RUNTIME_MECHANISMS_CHARACTERIZED`

---

# 12. N08 — Controlled Experiment Design

This phase establishes the causal contribution of each Runtime mechanism.

## 12.1 Mandatory benchmark arms

| Arm | Architecture |
|---|---|
| B0 | Raw llama.cpp minimal agent loop |
| B1 | Antigravity, if independently qualified |
| B2 | Pydantic AI native baseline |
| B3 | LangGraph native baseline |
| B4 | Best qualified additional general-purpose SDK from IJ-SDK |
| B5 | effGen native |
| B6 | effGen model-specific configuration |
| B7 | PTC-inspired runtime |
| B8 | TinyAgent-inspired runtime |
| B9 | NanoAgent unoptimized reference core |
| B10 | NanoAgent SLM-class optimized |
| B11 | NanoAgent model-specific optimized |
| B12 | NanoAgent automatically optimized |
| B13 | NanoAgent + Job-specific specialization |
| D0 | Deterministic-only workflow |

Any unqualified candidate remains BLOCKED.

Do not substitute a generic custom loop and label it as a native SDK implementation.

## 12.2 Separate experimental lanes

### Lane L0 — Native execution

User goal and common tool information only.

No task-specific workflow or hidden planning assistance.

### Lane L1 — Runtime specialization

Allow model-matched Runtime mechanisms.

Keep domain knowledge and task information equivalent.

### Lane L2 — Job specialization

Add legitimate professional knowledge, SOPs, Action Graphs and business policies.

Compare equivalent domain assets across frameworks.

### Lane L3 — Joint specialization

Combine model-specific Runtime Profiles and professional Job Packages.

### Lane L4 — Deterministic reference

Use deterministic software without model inference for applicable workloads.

Do not compare L3 directly with L0 and attribute the entire difference to Runtime engineering.

## 12.3 Dataset design

Reuse qualified legacy suites where available:

- TC-V2.
- MULTITOOL-V1.
- Autonomous Planning.
- JOB-V1.

Verify exact hashes.

Legacy cases are not unseen holdout cases.

Create a new mission-specific dataset with at least:

- Development set: 600 cases.
- Reserved causal confirmation set: 600 cases.
- Formal held-out test: 1,200 execution cases.
- Cross-job transfer cohort: 600 cases.
- Separate final reliability cohorts.

These cohorts must be disjoint by underlying task/world families where required by the experimental protocol.

Suggested fresh holdout distribution:

| Suite | Cases |
|---|---:|
| Cognitive and zero-tool tasks | 120 |
| Structured actions and slot binding | 180 |
| Multi-tool execution | 240 |
| Autonomous and conditional planning | 240 |
| Recovery and replanning | 180 |
| End-to-end professional tasks | 240 |
| Total | 1,200 |

Independently track unique worlds and repeated trajectories.

Include Chinese, English and mixed business terminology.

## 12.4 Holdout protection

Separate:

- Harness development.
- Optimization.
- Model selection.
- Evaluator repair.
- Confirmatory scoring.
- Final independent testing.

Do not permit the optimizer to inspect formal holdout results during search.

Freeze:

- Dataset.
- Task contract.
- World generator.
- Tool definitions.
- Oracle.
- Fault schedules.
- Resource budgets.
- Analysis protocol.

Use access separation between optimizer and evaluation artifacts where practical.

If the same engineering agent authored multiple components, disclose the resulting independence limitations.

Do not claim independent human blindness without actual independent human participation.

## 12.5 Initial physical matrix

Use a staged strategy.

### Stage A — Conformance pilot

30 development cases per applicable model/runtime configuration.

Establish:

- Runtime stability.
- Correct evidence.
- Task applicability.
- Budget compliance.
- Physical throughput.
- Expected storage.

### Stage B — Development mechanism screening

Use at least 120 stratified development cases per primary mechanism comparison.

Execute all three small models.

Use matched trials.

Prioritize screening important factors before large combinatorial experiments.

### Stage C — Factorial interactions

Investigate at minimum:

- Context compiler × tool routing.
- Grammar × action representation.
- Slot binding × typed state.
- Action Graph × recovery.
- Model profile × action representation.
- Model profile × context strategy.

Preregister factorial or fractional-factorial design and its aliasing limitations.

### Stage D — Frozen causal confirmation

Use the reserved 600-case confirmation cohort for selected comparisons.

Do not tune based on this cohort.

### Stage E — Full independent comparison

Run the frozen candidate configurations on the complete 1,200-case formal holdout.

With three models and fifteen applicable arms, the nominal maximum is 54,000 trial slots for one configuration per model/arm.

Additional lanes, repeatability, factorial experiments, transfer experiments, fault injection and reliability tests are separate.

Declare applicability before formal results.

Do not silently remove blocked or poor-performing arms.

### Stage F — Repeatability

Repeat a stratified panel of at least 100 cases using three declared seeds for finalist configurations.

Report correlation and execution nondeterminism.

## 12.6 Execution budgets

Preregister:

- Model calls.
- Tool calls.
- Generated tokens.
- Prompt tokens where applicable.
- Retry count.
- Absolute task deadline.
- Tool timeout.
- Context limits.
- Cache policy.

Evaluate at least:

- Native/default configuration.
- Matched common-budget configuration.
- Resource-constrained deployment configuration.

Use a shared authoritative budget controller.

Measure actual outgoing requests rather than trusting configuration declarations.

Gate:

`N08_EXPERIMENTAL_PROTOCOL_FROZEN`

---

# 13. N09 — Model × Harness Transfer Matrix

This is a central scientific contribution of IJ-NANO-1.0.

Determine whether a specialized Harness is:

- Universal across small models.
- Specific to a model architecture.
- Specific to a model's training distribution.
- Specific to a model and job combination.

## 13.1 Harness candidates

Create:

- H0: generic baseline.
- H1: SLM-class shared optimized Harness.
- H2: MiniCPM5-2B-specific Harness.
- H3: LFM3-1.7B-specific Harness.
- H4: Qwen3.5-2B-specific Harness.
- H5: capability-driven automatically selected Harness.

Optimize H2, H3 and H4 using only the respective model's development results.

Use equivalent optimization budgets.

Freeze each Harness before transfer evaluation.

## 13.2 Full cross-transfer matrix

Execute:

| Harness | MiniCPM5-2B | LFM3-1.7B | Qwen3.5-2B |
|---|---|---|---|
| H0 generic | Required | Required | Required |
| H1 shared SLM | Required | Required | Required |
| H2 MiniCPM-specific | Matched | Transfer | Transfer |
| H3 LFM-specific | Transfer | Matched | Transfer |
| H4 Qwen-specific | Transfer | Transfer | Matched |
| H5 automatic | Required | Required | Required |

Run at least 600 common reserved cases per cell.

Nominal initial transfer matrix: 10,800 trial slots.

Reuse trials only when the complete experimental identities are identical.

Do not double-count reused evidence as independent samples.

## 13.3 Transferability analysis

Calculate:

- Matched Harness gain.
- Cross-model transfer gain.
- Transfer degradation.
- Performance regret relative to best known Harness.
- Resource cost.
- Negative transfer.
- Robustness across capability families.

Define:

    Matched Gain =
        Success(model, matched_harness)
        - Success(model, generic_harness)

    Transfer Gain =
        Success(model, foreign_harness)
        - Success(model, generic_harness)

    Harness Regret =
        Best qualified success for model
        - Selected Harness success

Use paired confidence intervals.

Test model × Harness interaction effects.

Control for:

- Quantization.
- Prompt differences.
- Tool protocol.
- Context length.
- Execution budget.
- Optimization effort.
- Inference backend.

Do not declare model-specific specialization necessary if a shared SLM Harness performs equivalently within the preregistered practical margin.

## 13.4 Capability-based prediction

Investigate whether cognitive capability profiles can predict which Runtime mechanism will help a new model.

Perform leave-one-model-out experiments:

- Build the initial profile-selection rule using two models.
- Predict Runtime configuration for the third model.
- Evaluate the prediction on reserved tasks.

With only three models, report this as limited cross-family evidence.

Do not claim broad generalization to all SLMs.

Deliver:

- `reports/IJNANO_09_MODEL_HARNESS_TRANSFER.md`
- `atlas/ij_nano/model_harness_matrix.json`
- Transfer visualizations.
- Runtime recommendation evidence.

Gate:

`N09_MODEL_HARNESS_INTERACTION_CHARACTERIZED`

---

# 14. N10 — Capability-driven Automatic Harness Optimization

Build a reproducible research prototype:

**NanoAgent Harness Optimizer**

Its objective is to discover a suitable Harness using observed model capability and failure evidence.

## 14.1 Optimization loop

Implement:

    Profile model
        -> Select initial Harness
        -> Execute development cases
        -> Capture failure trajectories
        -> Identify failure classes
        -> Propose bounded Runtime changes
        -> Verify software correctness
        -> Run matched development experiments
        -> Evaluate improvement and cost
        -> Reject regressions
        -> Freeze selected Harness
        -> Independent confirmation

## 14.2 Search space

Use a typed, versioned search space.

Include:

- Context compiler strategy.
- Tool candidate count.
- Dependency-aware retrieval.
- Action format.
- Grammar mode.
- Slot binding strategy.
- State representation.
- Planning policy.
- Maximum autonomous horizon.
- Retry policy.
- Recovery strategy.
- Goal controller behavior.

Separate parameter optimization from code modification.

Start with declarative configuration search.

Allow function-level code changes only in a separate reviewed research arm.

## 14.3 Optimizer comparators

Evaluate:

- O0: fixed default configuration.
- O1: human-engineered configuration.
- O2: simple random search.
- O3: capability-rule-driven selection.
- O4: failure-class-driven iterative adaptation.
- O5: more advanced search or optimization methods where justified.

Use equivalent search budgets.

Record:

- Number of configurations evaluated.
- Number of development trials.
- GPU time.
- Tokens.
- Human engineering effort.
- Optimizer model costs.
- Failed candidate count.

Initial suggested cap:

- 40 candidate configurations per small model for each comparable search method.
- Up to 120 development cases per candidate.

Preregister a feasible final search budget after pilot measurements.

Do not expand the budget selectively until the preferred method wins.

## 14.4 Optimization objective

Apply hard gates first:

- Evidence integrity.
- Security.
- Authorization.
- Business correctness requirements.
- Resource limits.
- Local deployment requirements.

Then optimize the Pareto trade-off among:

- First-pass correctness.
- Autonomous completion.
- Token consumption.
- Model calls.
- P95 latency.
- Memory.
- Runtime complexity.
- Maintenance cost.

Do not optimize a weighted score that allows unsafe behavior to compensate for performance gains.

## 14.5 Prevent overfitting

The optimizer may access:

- Development task inputs.
- Development execution traces.
- Development evaluation outcomes.
- Model capability measurements.

The optimizer may not access:

- Reserved confirmation answers.
- Formal holdout answers.
- Final reliability cohorts.
- Hidden Oracle expectations outside its permitted development scope.

Prevent per-case action caches or memorized solutions from masquerading as general Runtime improvements.

Test on unseen task templates and worlds.

If a proposed adaptation encodes job-specific knowledge, classify it as Job specialization rather than pure model Runtime specialization.

## 14.6 Safe modification

All proposed changes must:

- Be versioned.
- Be reviewable.
- Pass regression tests.
- Preserve mandatory business security controls.
- Preserve evidence integrity.
- Be reversible.

Do not allow the optimizer to change:

- Oracle correctness rules.
- Holdout content.
- Security policies.
- Permission requirements.
- Experimental success criteria.

Generated code must remain isolated until reviewed and tested.

No uncontrolled runtime self-modification in the deployment candidate.

Deliver:

- `src/nanoagent/optimization/`
- `reports/IJNANO_10_HARNESS_OPTIMIZATION.md`
- Optimization trajectories.
- Candidate lineage.
- Accepted and rejected configurations.
- Search cost analysis.

Gate:

`N10_CAPABILITY_DRIVEN_OPTIMIZER_VALIDATED`

---

# 15. N11 — Cross-job Generalization and Professionalization

The SDK should support multiple jobs without rewriting its core runtime.

## 15.1 Job Package abstraction

Define a portable Job Package containing:

```text
job.yaml
tools.json
domain_knowledge/
action_graph.json
business_rules/
permission_policy.json
recovery_policy.json
output_contract.json
validation/
benchmark/
```

The package must clearly separate:

- Domain knowledge.
- Workflow.
- Tool interfaces.
- Security.
- Model profile.
- Runtime behavior.

Business rules must be explicit, auditable and versioned.

## 15.2 Mandatory job classes

Implement production-shaped synthetic workloads for:

- J01: Customer Service.
- J02: Procurement.
- J03: Order Processing.
- J04: Manufacturing/AOI Inspection.
- J05: IT Helpdesk.
- J06: Employment Service.

Use synthetic business worlds unless authorized real data is available.

For employment assistance, do not infer protected attributes or automate hiring/rejection decisions.

For IT Helpdesk, use safe simulated operations and authorization boundaries.

Do not imply physical manufacturing validation from synthetic AOI data.

## 15.3 Cross-job transfer matrix

Investigate:

- Shared SLM Runtime.
- Model-specific Runtime.
- Job-specific Harness.
- Model × Job jointly optimized Harness.

Optimize model-oriented mechanisms using selected development job families.

Evaluate on unseen job families.

Conduct leave-one-job-family-out experiments where practical.

Use at least 100 independent cases per job in the reserved cross-job cohort.

Preserve a separate final reliability cohort.

## 15.4 New JobBot engineering cost

Measure:

- Time required to define a new Job Package.
- Number of tools.
- Number of workflow nodes.
- Number of business rules.
- Required examples.
- Runtime configuration changes.
- New code size.
- New dependency count.
- Number of required regression tests.
- Human review effort.

Distinguish development elapsed time, active engineering effort and automated optimization effort.

The objective is to determine whether NanoAgent enables scalable JobBot development.

## 15.5 Accessible interaction

Evaluate:

- Number of clarification questions.
- Number of repeated questions.
- Number of approval interactions.
- Instruction complexity.
- Clear recovery explanations.
- Correct escalation.
- User correction requirements.

Do not claim human accessibility qualification without real independent review and appropriately conducted participant studies.

Deliver:

- Six Job Packages.
- `reports/IJNANO_11_CROSS_JOB_GENERALIZATION.md`
- `reports/IJNANO_JOB_PACKAGE_DEVELOPMENT_GUIDE.md`
- Job-specific capability requirements.

Gate:

`N11_JOB_PACKAGE_TRANSFER_CHARACTERIZED`

---

# 16. N12 — Business Reliability, Security and Resource Qualification

## 16.1 Fault injection

Cover at least:

- Invalid arguments.
- Unknown tools.
- Missing observations.
- Stale state.
- Malformed tool responses.
- Timeouts.
- Temporary failures.
- Context exhaustion.
- Model server crash.
- Runtime crash.
- Invalid checkpoint.
- Unauthorized action.
- Missing approval.
- Duplicate execution.
- Interrupted transaction.
- Prompt injection in tool output.
- Conflicting business rules.

Use deterministic fault schedules.

Include at least 400 stratified fault injection cases per finalist architecture.

## 16.2 Security boundary

Require:

- Authorization before execution.
- Strict schema validation.
- Transaction safety.
- Idempotency.
- Rollback.
- Trusted approval handling.
- Session isolation.
- Safe handling of untrusted tool output.
- No unauthorized business writes.
- No external data leakage.

The shared deterministic business Gateway must be used by every comparable runtime.

Record both unauthorized action attempts and actual unauthorized state changes.

Do not hide unsafe model behavior simply because the Gateway blocked it.

## 16.3 Physical resource measurements

Measure:

- Prompt tokens per task.
- Completion tokens per task.
- Model calls per task.
- Tool calls per task.
- Cold start.
- Warm start.
- Time to first token.
- P50/P95/P99 latency where supported.
- Prompt processing throughput.
- Decode throughput.
- Peak process RAM.
- Peak VRAM.
- CPU utilization.
- GPU utilization.
- Framework dependency footprint.
- Tasks completed per hour.
- Energy per attempted task where measurable.
- Energy per successful task where measurable.

Do not estimate physical energy from TDP.

Separate GPU board energy from total system energy.

If energy cannot be reliably measured, report NOT_MEASURED.

## 16.4 Reliability target qualification

For each job scope and finalist configuration:

- Preregister task distribution.
- Define first-pass business correctness.
- Define legitimate clarification and approval.
- Define autonomous completion separately.
- Select an independent qualification sample.
- Establish the statistical analysis in advance.

For a greater-than-99% claim, require a one-sided 95% confidence lower bound above 99% under the tested distribution.

An illustrative minimum is 300 genuinely independent cases with zero failures for one narrowly defined scope.

Larger or adjusted samples may be required for failures, correlated worlds, multiple finalist claims or multiple job scopes.

Do not repeatedly expand samples until a favorable threshold is crossed without a valid sequential testing protocol.

Do not confuse synthetic reliability with customer deployment reliability.

## 16.5 Human dialogue efficiency

Compare equivalent task scope against a qualified general-purpose agent.

Measure actual human-facing dialogue turns separately from internal model calls.

Report:

- Human clarification turns.
- Approval turns.
- User correction turns.
- Internal model calls.
- Autonomous completion rate.

Handle zero-denominator cases explicitly.

Do not reduce dialogue by skipping necessary approvals or failing to ask essential clarification questions.

## 16.6 Larger-model reference

Compare finalists with R1 and R2.

Use equivalent task information, safety controls and business evaluation.

Report general-purpose and similarly specialized larger-model references separately.

A 2B specialized system outperforming a larger general-purpose system does not prove that the 2B model itself is more capable.

## 16.7 Stability testing

For final candidates execute:

- Functional smoke.
- One-hour continuous run.
- Eight-hour soak.
- Twenty-four-hour extended qualification.

Measure:

- Failure accumulation.
- Memory growth.
- Latency drift.
- Recovery.
- State consistency.
- Duplicate effects.
- Process crashes.

Publish actual coverage.

Do not claim a completed soak without the corresponding physical execution evidence.

Deliver:

- `reports/IJNANO_12_RELIABILITY_AND_SECURITY.md`
- `reports/IJNANO_12_PERFORMANCE_AND_RESOURCE_PROFILE.md`
- `reports/IJNANO_12_LARGER_MODEL_COMPARISON.md`

Gate:

`N12_DEPLOYMENT_CHARACTERISTICS_QUALIFIED`

---

# 17. N13 — NPU Portability and Minimum Hardware Requirements

The Radeon workstation is the research platform.

The intended future deployment platform may use low-power NPU hardware such as DEEPX DX-M2.

Do not assume the NPU supports a particular model, quantization method, operator or decoding interface.

## 17.1 Runtime portability

Separate:

- Model execution.
- Tokenization.
- Action parsing.
- Constrained decoding.
- Tool routing.
- Typed memory.
- Workflow.
- Business validation.
- Recovery.

Investigate which functions can be executed deterministically on the host CPU.

## 17.2 Runtime capability negotiation

A portable model backend must expose whether it supports:

- Text generation.
- Streaming.
- Native tool calling.
- Logits access.
- Token masking.
- Grammar constraints.
- Structured output.
- Cancellation.
- Usage accounting.
- Context management.
- KV Cache control.

Do not require every backend to support every feature.

When token-level constrained decoding is unavailable, investigate explicitly identified host-side alternatives.

Examples:

- Enumerated action selection.
- Bounded structured generation.
- Host-side parsing and validation.
- Limited field regeneration.

Host-side validation is not equivalent to token-level constrained decoding.

Measure the difference on available physical hardware.

## 17.3 Minimum hardware profile

For each qualified JobBot configuration provide:

- Model weight memory.
- Minimum qualified context.
- Peak runtime memory.
- Tokens per successful task.
- Model calls per successful task.
- Required prompt throughput.
- Required decode throughput.
- Host CPU workload.
- Required storage.
- Required runtime capabilities.
- Estimated deployment requirements.

Clearly distinguish:

- MEASURED
- DERIVED_REQUIREMENT
- PROJECTED
- UNVERIFIED

Do not publish fabricated NPU latency, throughput or energy values.

Create a future physical validation plan.

Deliver:

- `reports/IJNANO_13_NPU_PORTABILITY.md`
- `docs/nanoagent/model_runtime_contract.md`
- `configs/ij_nano/hardware_requirements.json`

Gate:

`N13_RUNTIME_PORTABILITY_CONTRACT_READY`

Physical NPU qualification remains a separate gate.

---

# 18. N14 — Source-level Root Cause Analysis

Index every failed trial.

Group failures only when evidence demonstrates a shared mechanism.

Use a detailed taxonomy covering:

- Model comprehension.
- Model choice.
- Model planning.
- Prompt ambiguity.
- Context overload.
- Tokenizer.
- Chat Template.
- Native model tool protocol.
- Parser.
- Grammar.
- SDK adapter.
- Tool routing.
- Action decoding.
- Slot binding.
- State compiler.
- Action Graph.
- Recovery policy.
- Goal controller.
- Authorization.
- Gateway.
- Business tool implementation.
- Oracle.
- Dataset.
- Budget.
- Runtime.
- GPU.
- Driver.
- External dependency.
- Unknown.

For each distinct mechanism:

1. Preserve original evidence.
2. Reproduce the smallest failing case.
3. Identify the first incorrect observable stage.
4. Inspect the corresponding source implementation.
5. Record exact source commit, file, function and relevant lines.
6. Construct competing explanations.
7. Run controlled counterfactuals.
8. Establish confirmed or unverified root cause.
9. Implement the minimal justified repair.
10. Add regression tests.
11. Demonstrate red-to-green behavior.
12. Execute matched revalidation.
13. Preserve original results.
14. Publish repaired results under a new experiment identity.

Do not claim access to hidden model reasoning.

Investigate observable outputs, state transitions and execution traces.

Use:

- CONFIRMED
- PROBABLE
- UNVERIFIED
- EXTERNAL_BLOCKER

An unexplained failure must remain unexplained.

If an upstream defect is found, prepare a minimal reproduction and patch proposal locally.

Do not submit upstream Issues or PRs without authorization.

Deliver:

- `reports/IJNANO_14_ROOT_CAUSE_ATLAS.md`
- `evidence/IJNANO/N14/failure_ledger.jsonl`
- Minimal reproductions.
- Regression tests.
- Causal repair evidence.

Gate:

`N14_FAILURE_MECHANISMS_CHARACTERIZED`

---

# 19. N15 — Statistical Analysis and Capability-driven Selection

## 19.1 Primary outcome metrics

Report:

- Semantic action accuracy.
- Argument correctness.
- Structured output validity.
- Planning executability.
- Multi-tool execution success.
- First-pass business correctness.
- Recovered business correctness.
- Autonomous completion.
- Correct refusal.
- Correct clarification.
- Unauthorized attempts.
- Unauthorized state changes.
- False completion.
- Tool calls.
- Model calls.
- Tokens.
- Latency.
- Memory.
- Energy where measured.

Publish exact metric definitions, numerators and denominators.

Report all attempted trials.

Do not exclude failures from efficiency measurements without also reporting unconditional statistics.

## 19.2 Statistical methodology

Use:

- Appropriate confidence intervals.
- Paired binary comparisons.
- McNemar tests where appropriate.
- Paired bootstrap.
- Cluster-aware analysis.
- Factorial interaction analysis.
- Multiple comparison correction.
- Effect sizes.
- Practical significance.

Repeated worlds, paraphrases and seeds are not automatically independent observations.

Do not claim a meaningful improvement solely from a statistically significant but negligible effect.

## 19.3 Gain attribution

Separately quantify:

- Prompt improvement.
- Tool routing improvement.
- Constrained generation improvement.
- Typed state improvement.
- Slot binding improvement.
- Workflow improvement.
- Recovery improvement.
- Job knowledge improvement.
- Model-specific adaptation improvement.
- Automatic optimization improvement.

Investigate interactions.

Do not assume individual gains can simply be added.

## 19.4 Minimum Sufficient Intelligence selection engine

Build an evidence-driven selector that accepts:

```yaml
job_requirements:
  required_business_correctness: target
  required_planning_depth: target
  available_tools: count
  business_risk: level
  maximum_latency: limit
  maximum_memory: limit
  maximum_human_interactions: limit
  offline_required: true
  commercial_license_required: true

hardware_capabilities:
  model_memory_budget: limit
  runtime_features: supported-features
```

Return:

- Eligible models.
- Eligible Harness profiles.
- Required Job Package mechanisms.
- Qualified runtime configuration.
- Expected measured resource envelope.
- Evidence references.
- Confidence intervals.
- Unqualified requirements.
- Alternative Pareto candidates.

The selector must fail closed if evidence is missing.

Do not return a recommended production configuration merely because it has the highest relative benchmark score.

Deliver:

- `reports/IJNANO_15_STATISTICAL_AND_CAUSAL_ANALYSIS.md`
- `atlas/ij_nano/selection_matrix.json`
- `tools/nanoagent_selector/`

Gate:

`N15_EVIDENCE_BACKED_SELECTION_AVAILABLE`

---

# 20. N16 — NanoAgent SDK Engineering Release Candidate

The objective is to deliver a reusable engineering SDK, not just benchmark scripts.

## 20.1 Public API

Implement a practical API equivalent to:

```python
from nanoagent import JobBot, ModelProfile
from nanoagent.runtime import LlamaCppRuntime
from nanoagent.jobs import JobPackage

profile = ModelProfile.load(
    "profiles/ij_nano/qualified-profile.yaml"
)

runtime = LlamaCppRuntime(
    base_url="http://127.0.0.1:8080/v1"
)

job = JobPackage.load(
    "jobs/ij_nano/procurement/"
)

bot = JobBot(
    model_profile=profile,
    runtime=runtime,
    job=job
)

result = bot.execute(
    "检查库存并按照采购政策准备采购申请"
)
```

The actual API must reflect validated architecture and existing repository conventions.

## 20.2 Result contract

Return structured results containing:

- Execution status.
- Business verification status.
- Final answer.
- Verified facts.
- Executed actions.
- Pending approvals.
- Clarification requirements.
- Recovery information.
- Error information.
- Usage.
- Evidence reference.

Do not expose a misleading boolean success without defining its meaning.

## 20.3 Required SDK capabilities

Provide:

- Installable Python package.
- Versioned public API.
- Typed configuration.
- Model Runtime abstraction.
- Pluggable Context Compiler.
- Pluggable Action Decoder.
- Pluggable Tool Router.
- Typed State Store.
- Recovery policy.
- Job Package loader.
- Tool Gateway integration.
- Trace export.
- Persistent checkpoints.
- Cancellation.
- Offline execution.
- Reproducible benchmark interface.

## 20.4 Quality requirements

Require:

- Unit tests.
- Integration tests.
- Adapter conformance tests.
- Negative tests.
- Property-based tests where useful.
- Mutation tests for critical gates.
- Type checking.
- Linting.
- Dependency audit.
- Security audit.
- Packaging smoke test.
- Clean-checkout reproduction.

Do not optimize for test coverage percentage alone.

Require explicit coverage of critical business and security invariants.

## 20.5 SDK implementation decision

Based on evidence, choose one of:

- Directly reuse an existing SLM-native SDK.
- Build a thin capability-aware layer over an existing SDK.
- Extend a selected existing framework.
- Maintain a minimal independent NanoAgent Runtime.

Do not force an independent implementation if a simpler existing framework achieves equivalent performance and lower maintenance cost.

Document the evidence-backed build-versus-buy-versus-reuse decision.

If the best solution is an extension layer, preserve NanoAgent's model profiles, Job Package specification and evaluation contracts as reusable deliverables.

## 20.6 License and release

Verify all licenses.

Original project code should follow the repository's Apache-2.0 policy unless the owner explicitly decides otherwise.

Maintain attribution and third-party notices.

Do not publish restricted model weights or unlicensed research code.

Prepare an SDK release candidate in the research branch.

Do not publish a public package release, create a GitHub Release or merge the PR without explicit authorization.

Deliver:

- Installable SDK candidate.
- `docs/nanoagent/`
- Getting Started guide.
- API reference.
- Architecture guide.
- Model Profile specification.
- Job Package specification.
- Migration guide.
- Example JobBots.
- Release notes.

Gate:

`N16_NANOAGENT_SDK_RC_READY`

---

# 21. N17 — Independent Research and Engineering Audit

Before declaring mission closure, perform an adversarial review independent of the optimization process.

Attempt to falsify every major claim:

- Runtime specialization improves 2B models.
- Model-specific Harnesses are necessary.
- Context reduction preserves essential information.
- Tool filtering improves semantic success.
- Grammar improves business correctness.
- Slot binding reduces hallucinations.
- Action Graph improves reliable execution.
- Automatic optimization generalizes.
- NanoAgent outperforms existing SDKs.
- A 2B system approaches larger-model performance.
- The system meets the greater-than-99% target.
- The system meets the one-tenth dialogue target.
- The system is suitable for future NPU deployment.

Audit:

- Dataset leakage.
- Oracle correctness.
- Evidence completeness.
- Model identity.
- Runtime identity.
- GPU execution.
- Statistical methodology.
- Resource measurements.
- Safety.
- License.
- Optimization fairness.
- Negative transfer.
- Reproducibility.
- Hidden engineering assistance.
- Unreported failures.

Rebuild all summaries from sealed evidence.

Run a clean-checkout reproduction of representative physical experiments.

Generate score-blind review packets.

An internal AI-assisted review is not an independent external human review.

Keep external human review NOT_RUN until actually performed.

Publish:

- `reports/IJNANO_17_INDEPENDENT_AUDIT.md`
- `reports/IJNANO_REPRODUCIBILITY_GUIDE.md`
- `evidence/IJNANO/N17/audit_manifest.json`

Gate:

`N17_INDEPENDENT_AUDIT_COMPLETE`

---

# 22. N18 — Research Atlas and Final Deliverables

## 22.1 SLM Cognitive Capability Atlas

Answer:

- What can each model do reliably?
- Where does capability degrade?
- What cognitive burden should be delegated to deterministic software?

## 22.2 Runtime Mechanism Effectiveness Atlas

For every mechanism report:

- Affected capability.
- Supported models.
- Success improvement.
- Negative effects.
- Token cost.
- Latency cost.
- Resource impact.
- Evidence status.

## 22.3 Model × Harness Transfer Atlas

Report:

- Matched profiles.
- Cross-model profiles.
- Shared profiles.
- Automatic profiles.
- Transfer degradation.
- Pareto frontiers.
- Confidence intervals.

## 22.4 Job × Harness Transfer Atlas

Report:

- Shared Runtime mechanisms.
- Job-specific mechanisms.
- Cross-job generalization.
- Job Package engineering cost.
- Model × Job interactions.

## 22.5 Failure Causal Atlas

Map:

    Observable failure
        -> Root cause
        -> Runtime intervention
        -> Regression test
        -> Verified improvement
        -> Remaining limitation

## 22.6 Required design guidelines

Publish:

1. SLM-native Agentic Runtime Design Principles.
2. Model Capability Profiling Methodology.
3. Model-specific Harness Selection Guide.
4. Context Compiler Design Guide.
5. Tool Routing Design Guide.
6. Action Representation Selection Guide.
7. Constrained Decoding Guide.
8. Typed State and Slot Binding Guide.
9. Conditional Workflow Design Guide.
10. Recovery Policy Design Guide.
11. Job Package Development Guide.
12. Automatic Harness Optimization Guide.
13. Business Safety Design Guide.
14. NPU Migration Guide.

## 22.7 Dashboard

Build a locally viewable research dashboard showing:

- Model × Harness heatmaps.
- Cognitive capability profiles.
- Mechanism-level causal improvements.
- Tool inventory scaling.
- Context length sensitivity.
- Planning depth scaling.
- Recovery performance.
- First-pass versus recovered success.
- Latency and token trade-offs.
- Framework overhead.
- Transfer performance.
- Pareto frontiers.
- Failed, blocked and unexecuted coverage.

Missing data must not be visualized as zero success.

Every result must link to its evidence.

Deliver:

- `atlas/ij_nano/`
- `reports/IJNANO_CAPABILITY_ATLAS_CN.md`
- `reports/IJNANO_CAPABILITY_ATLAS_EN.md`
- `reports/IJNANO_INTERACTIVE_DASHBOARD.html`

Gate:

`N18_RESEARCH_ATLAS_PUBLISHED`

---

# 23. Persistent Execution and Recovery

Implement a durable research controller.

Suggested commands:

```powershell
python -m benchmarks.ij_nano preflight
python -m benchmarks.ij_nano profile
python -m benchmarks.ij_nano reproduce
python -m benchmarks.ij_nano freeze
python -m benchmarks.ij_nano pilot
python -m benchmarks.ij_nano run
python -m benchmarks.ij_nano optimize
python -m benchmarks.ij_nano resume
python -m benchmarks.ij_nano progress
python -m benchmarks.ij_nano verify
python -m benchmarks.ij_nano analyze
```

Adapt the commands to existing conventions.

Implement:

- Immutable experiment identity.
- Immutable trial identity.
- Persistent queue.
- Atomic result writes.
- Exact input and output hashes.
- Evidence sealing.
- GPU lease.
- Process supervision.
- Watchdog.
- Bounded retries.
- Checkpoint.
- Crash recovery.
- Duplicate prevention.
- Disk monitoring.
- Resource accounting.

Do not overwrite first attempts.

A changed configuration must create a new experiment identity.

After the physical pilot, estimate:

- Total GPU hours.
- Expected wall-clock execution.
- Storage.
- Search cost.
- Remaining formal coverage.

Balance execution across all models and frameworks.

Do not devote the entire GPU budget to the first model or preferred architecture.

If a session ends before completion, preserve the exact queue and provide the recovery command.

Do not claim future execution has occurred.

---

# 24. GitHub Delivery Requirements

Deliver all authorized research results to:

https://github.com/AIwork4me/Inclusive-JobBot

Use:

`mission/ij-nano-1.0-slm-native-agentic-runtime`

## 24.1 Git workflow

- Create an independent tracking Issue.
- Create an independent Draft PR.
- Document parent dependencies.
- Commit small logical changes.
- Use ordinary non-force pushes.
- Publish milestone checkpoints.
- Verify remote commit identity.
- Keep PR #6 and PR #8 isolated.

Where the PR is stacked, provide exact mission-only review commands.

Do not merge without authorization.

## 24.2 Evidence publication

Publish:

- Source code.
- Configuration.
- Research protocols.
- Model passports.
- Harness profiles.
- Dataset manifests.
- Reproduction scripts.
- Evaluation code.
- Statistical analysis.
- Compact physical traces.
- Failure reproductions.
- SDK documentation.
- Research reports.
- Evidence hashes.

Do not publish:

- Credentials.
- Private business data.
- Personal identifiers.
- Sensitive workstation information.
- Model weights.
- Large runtime binaries.
- Unlicensed redistribution artifacts.
- Protected formal holdout answers before experimental sealing.

Use repository-approved artifact storage for large evidence.

Verify artifact retrieval and checksums.

Run sensitive-data scanning before every commit.

## 24.3 Progress updates

Every meaningful milestone must report:

- Current phase.
- Gate status.
- Planned trials.
- Executed trials.
- Valid physical trials.
- PASS.
- FAIL.
- BLOCKED.
- NOT_RUN.
- Current source commit.
- Evidence location.
- Current blocker.
- Next recovery command.

Keep mission-specific ledgers synchronized.

---

# 25. N19 — Final Acceptance and Closure

Maintain twenty explicit phase gates.

| Gate | Required outcome |
|---|---|
| N00 | Research baseline and isolation |
| N01 | Verified literature and open-source landscape |
| N02 | Physical model and runtime qualification |
| N03 | Cognitive capability profiling |
| N04 | Existing SLM approach characterization |
| N05 | Independent evaluator qualification |
| N06 | Modular Runtime implementation |
| N07 | Runtime mechanism characterization |
| N08 | Frozen experimental protocol |
| N09 | Model × Harness transfer experiments |
| N10 | Automatic Harness optimization |
| N11 | Cross-job generalization |
| N12 | Reliability, safety and performance |
| N13 | Portable Runtime and hardware contract |
| N14 | Source-level causal analysis |
| N15 | Statistical and selection methodology |
| N16 | SDK release candidate |
| N17 | Independent audit |
| N18 | Research Atlas publication |
| N19 | GitHub delivery and mission closure |

Every gate must have machine-readable acceptance conditions and evidence references.

Do not infer completion of a gate from the existence of a report.

Do not count a phase as qualified merely because some work was performed.

## 25.1 Scientific verdict

Choose independently:

- `IJNANO_MODEL_MATCHED_RUNTIME_HYPOTHESIS_SUPPORTED`
- `IJNANO_MODEL_MATCHED_RUNTIME_HYPOTHESIS_NOT_SUPPORTED`
- `IJNANO_MODEL_MATCHED_RUNTIME_HYPOTHESIS_INCONCLUSIVE`

Also publish an individual verdict for H01–H12.

## 25.2 Research completion verdict

- `IJ_NANO_1_0_RESEARCH_COMPLETE`
- `IJ_NANO_1_0_RESEARCH_INCOMPLETE`
- `IJ_NANO_1_0_RESEARCH_BLOCKED`

## 25.3 Architecture verdict

- `NANOAGENT_INDEPENDENT_RUNTIME_GO`
- `NANOAGENT_EXISTING_SDK_EXTENSION_GO`
- `NANOAGENT_EXISTING_SDK_REUSE_GO`
- `NANOAGENT_ARCHITECTURE_CONDITIONAL_GO`
- `NANOAGENT_ARCHITECTURE_NO_GO`

## 25.4 Product qualification verdict

- `NANOAGENT_SYNTHETIC_JOBBOT_QUALIFICATION_GO`
- `NANOAGENT_PRODUCT_READINESS_BLOCKED`
- `NANOAGENT_PRODUCT_READINESS_NOT_RUN`

Maintain separate explicit statuses for:

- Real customer deployment.
- Independent human accessibility validation.
- Physical NPU validation.

Do not grant these based on synthetic Radeon experiments.

---

# 26. Mandatory Final Research Reports

Publish at minimum:

- `reports/IJNANO_FINAL_REPORT_CN.md`
- `reports/IJNANO_FINAL_REPORT_EN.md`
- `reports/IJNANO_EXECUTIVE_SUMMARY.md`
- `reports/IJNANO_SLM_NATIVE_RUNTIME_DESIGN_PRINCIPLES.md`
- `reports/IJNANO_REFERENCE_ARCHITECTURE.md`
- `reports/IJNANO_MODEL_HARNESS_SELECTION_GUIDE.md`
- `reports/IJNANO_BUILD_VS_REUSE_DECISION.md`
- `reports/IJNANO_HARNESS_OPTIMIZATION_GUIDE.md`
- `reports/IJNANO_JOBBOT_PRODUCT_DESIGN_GUIDE.md`
- `reports/IJNANO_NPU_MIGRATION_GUIDE.md`
- `reports/IJNANO_17_INDEPENDENT_AUDIT.md`

The final Chinese report must answer:

1. Does a 2B model genuinely benefit from a specialized Agentic Runtime?
2. Which mechanisms provide the largest reliable gains?
3. Which mechanisms introduce regressions?
4. Does each model require its own Harness?
5. Which mechanisms generalize across models?
6. Which mechanisms generalize across jobs?
7. Which existing frameworks should we reuse?
8. Is an independent NanoAgent SDK justified?
9. Can the optimizer select a good Runtime for a previously unseen model?
10. What is the improvement in first-pass business correctness?
11. What is the improvement in autonomous planning and multi-tool execution?
12. How many model calls and tokens are eliminated?
13. What is the actual physical performance and memory footprint?
14. How does a specialized 2B JobBot compare with larger general-purpose agents?
15. Has any specific job scope achieved the greater-than-99% target?
16. Has any configuration demonstrated the one-tenth human dialogue target?
17. What are the remaining safety and reliability limitations?
18. What is the minimum required hardware capability?
19. What is the effort required to develop a new JobBot?
20. What should the next JobBot product-development mission implement?

Every important conclusion must include:

- Exact comparison.
- Sample size.
- Confidence interval.
- Effect size.
- Evidence reference.
- Applicable scope.
- Known limitations.

---

# 27. Research Integrity — Forbidden Shortcuts

Under no circumstances:

- Tune on formal holdout answers.
- Use a hidden task solution as an Action Graph.
- Read expected arguments from evaluator metadata.
- Present deterministic answer lookup as autonomous model capability.
- Hide custom orchestration inside a supposedly native SDK arm.
- Treat Grammar validity as semantic correctness.
- Treat a rejected unsafe action as an autonomous safety success without reporting the attempt.
- Treat recovered success as first-pass success.
- Treat repeated seeds as independent users or independent business worlds.
- Attribute model weight improvements to Runtime changes.
- Attribute job-specific knowledge improvements entirely to SDK changes.
- Change model quantization silently.
- Mix GPU and CPU results.
- Claim an unmeasured NPU performance result.
- Hide failed or blocked experiments.
- Declare the SDK optimal solely because it is our own implementation.

Prefer simpler implementations when they provide equivalent qualified outcomes.

---

# 28. Execution Directive

Start immediately with N00.

Proceed through the research and engineering phases using evidence-driven dependency gates.

Prioritize:

1. Research isolation.
2. Verification of existing benchmark qualification.
3. SLM cognitive capability measurement.
4. Reproduction of established small-model Runtime mechanisms.
5. Modular NanoAgent implementation.
6. Controlled ablation.
7. Model × Harness transfer.
8. Automatic optimization.
9. Cross-job qualification.
10. Product engineering and publication.

Parallelize independent software work when safe.

Respect existing GPU leases.

When encountering a failure:

    Preserve
        -> Reproduce
        -> Inspect source
        -> Identify causal mechanism
        -> Repair where justified
        -> Add regression tests
        -> Revalidate
        -> Publish evidence
        -> Continue

When an external dependency blocks formal evaluation, continue independent workstreams without fabricating qualification.

Do not stop merely because an initial approach fails.

Do not stop at an implementation-only checkpoint.

Deliver the most complete, trustworthy, reproducible and commercially relevant research package possible.

The mission succeeds by establishing what is actually required to build a reliable 2B-class professional JobBot.

The final objective is not to prove that NanoAgent is superior.

The final objective is to discover, verify and engineer the Minimum Sufficient Agentic Runtime for Small Language Models.

Execute MISSION IJ-NANO-1.0 now.