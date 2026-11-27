# IJ-NANO-1.0 Research Protocol

Operative protocol extracted from the mission order
(`docs/IJNANO_MISSION_ORDER.md`, the verbatim preregistration). Where any
document disagrees with the mission order, the mission order governs.

## 1. Mission hypothesis (North Star)

Small language models require capability-matched Agentic Runtimes.
Redesigning the runtime around the model's actual capabilities may
substantially improve business reliability and resource efficiency without
increasing model size.

A scientifically valid negative result is an acceptable mission outcome.

## 2. Preregistered hypotheses (frozen)

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

Before each confirmatory experiment, record per hypothesis: independent
variable, dependent variable, matched baseline, expected mechanism, competing
explanations, experimental population, statistical analysis, minimum
practically meaningful effect, acceptance criteria, falsification criteria,
known confounders. Confirmatory success criteria never change after formal
results are inspected. Verdicts: SUPPORTED / NOT_SUPPORTED / INCONCLUSIVE /
BLOCKED / NOT_RUN. One favorable example never yields SUPPORTED.

## 3. Evidence integrity (binding fields)

Every physical result binds to: exact source commit, model revision, model
SHA256, quantization, chat-template SHA256, tokenizer identity, engine binary
SHA256, GPU identity, GPU backend, SDK/harness identity, runtime profile
SHA256, job package SHA256, dataset SHA256, oracle identity, run ID, trial ID.

Statuses are kept separate for: execution completion, evidence validity,
business success, safety compliance, capability qualification, product
readiness. Test statuses: PASS / FAIL / BLOCKED / NOT_RUN (repo D-008).

Never presented as what they are not: fixtures as model runs, CPU as GPU,
demos as qualification, structural validity as semantic correctness, correct
answers as correct business execution, SDK self-reports as verdicts, synthetic
results as field reliability, Radeon measurements as NPU performance.

## 4. Fixed weights, independence, locality

- Primary intervention is Runtime design; model weights never change during
  primary comparisons. Weight-change effects are never attributed to the
  harness.
- The tested runtime never reads hidden expectations, formal solutions or
  oracle internals; never modifies its own evaluation criteria; never chooses
  favorable cases post hoc. Production validators and research evaluators are
  distinct components.
- All primary runtime inference is local. No cloud LLM fallback, no external
  agent service. A larger offline optimizer model, if used, has its identity,
  role, data access and cost recorded, and the final runtime never requires it.

## 5. Phase gates

N00 RESEARCH_BASELINE_FROZEN · N01 RESEARCH_LANDSCAPE_VERIFIED ·
N02 PHYSICAL_MODEL_RUNTIME_QUALIFIED · N03 COGNITIVE_CAPABILITY_PROFILES_AVAILABLE ·
N04 EXISTING_SLM_APPROACHES_CHARACTERIZED · N05 INDEPENDENT_EVALUATION_QUALIFIED ·
N06 NANOAGENT_MODULAR_RUNTIME_IMPLEMENTED · N07 RUNTIME_MECHANISMS_CHARACTERIZED ·
N08 EXPERIMENTAL_PROTOCOL_FROZEN · N09 MODEL_HARNESS_INTERACTION_CHARACTERIZED ·
N10 CAPABILITY_DRIVEN_OPTIMIZER_VALIDATED · N11 JOB_PACKAGE_TRANSFER_CHARACTERIZED ·
N12 DEPLOYMENT_CHARACTERISTICS_QUALIFIED · N13 RUNTIME_PORTABILITY_CONTRACT_READY ·
N14 FAILURE_MECHANISMS_CHARACTERIZED · N15 EVIDENCE_BACKED_SELECTION_AVAILABLE ·
N16 NANOAGENT_SDK_RC_READY · N17 INDEPENDENT_AUDIT_COMPLETE ·
N18 RESEARCH_ATLAS_PUBLISHED · N19 GITHUB_DELIVERY_AND_MISSION_CLOSURE

Gate completion requires machine-readable acceptance conditions plus evidence
references. A report's existence never implies gate completion.

## 6. Experimental lanes (comparability rule)

L0 native execution · L1 runtime specialization · L2 job specialization ·
L3 joint specialization · L4 deterministic reference. L3 is never compared
directly against L0 with the difference attributed to runtime engineering.
Benchmark arms B0-B13, D0 (mission order §12.1); unqualified arms stay
BLOCKED and are never silently dropped after seeing results.

## 7. Holdout protection

Separate harness development, optimization, model selection, evaluator
repair, confirmatory scoring and final independent testing. The optimizer
never sees formal holdout results during search. Frozen before confirmatory
runs: dataset, task contract, world generator, tool definitions, oracle,
fault schedules, resource budgets, analysis protocol. Repeated worlds,
paraphrases and seeds are not automatically independent observations.
Disclosure: where one engineering agent authored multiple components, the
independence limitation is stated; independent human blindness is never
claimed without actual independent humans.

## 8. Forbidden shortcuts (verbatim scope)

Never: tune on formal holdout answers; use hidden task solutions as Action
Graphs; read expected arguments from evaluator metadata; present deterministic
lookup as autonomous capability; hide custom orchestration inside a "native
SDK" arm; treat grammar validity as semantic correctness; treat a rejected
unsafe action as autonomous safety success without reporting the attempt;
treat recovered success as first-pass success; treat repeated seeds as
independent users/worlds; attribute weight improvements to runtime changes;
attribute job-knowledge gains entirely to SDK changes; change quantization
silently; mix GPU and CPU results; claim unmeasured NPU performance; hide
failed or blocked experiments; declare the SDK optimal because it is ours.

## 9. N00 additions specific to this execution

- GPU lease (IJN-B-001): physical phases BLOCKED while IJ-SLM-1.0 holds the
  Radeon; software-only work proceeds.
- Dependency scoping: see `evidence/IJNANO/N00/dependency_qualification.json`
  (nothing from reopened-FAIL IJ-SDK scopes is inherited as qualified).
- GPU-run evidence follows repo D-010 in addition to the mission order's
  binding fields.
