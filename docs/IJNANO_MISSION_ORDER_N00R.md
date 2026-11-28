# MISSION IJ-NANO-1.0 — N00R Dependency Reconciliation & Parallel Research Execution

## 0. Mission Identity

- Repository: https://github.com/AIwork4me/Inclusive-JobBot
- Tracking Issue: #10
- Draft PR: #11
- Branch: `mission/ij-nano-1.0-slm-native-agentic-runtime`
- Audited HEAD: `d45be1378c04223de58e8f18e38b0180c1417a8b`
- Frozen source: `56c6c74bf7216eb9cf65be4056c8db1964d23b05`
- Physical workstation: Native Windows + Radeon RX 7900 XTX 24GB, gfx1100.

All original IJ-NANO-1.0 requirements remain valid.

This supplemental mission resolves dependency interpretation, establishes safe parallel execution and advances the research beyond N00.

Do not restart the mission.

Do not modify PR #6, PR #8 or PR #9 directly.

## 1. N00R — Correct GPU Lease Scope

The previous audit classified all IJ-NANO physical execution as BLOCKED because IJ-SLM-1.0 holds a Radeon GPU lease.

New independent GitHub evidence indicates that this lease belongs to a different physical GPU.

PR #9 audited HEAD:

`364c7cafb21376038e1278c67d0b3da2d068ff3d`

Inspect:

- `atlas/slm/v1.0/environment.json`
- `evidence/IJ073/aeve/gpu_handoff.json`
- `evidence/IJSLM/tc-v3/ijslm-tcv3-0040656689af4b04ae738887fd999e2d/manifest.json`

The published physical run identifies:

- GPU: AMD Radeon 8060S Graphics.
- Architecture: gfx1151.
- Backend: Vulkan.
- Physical offloading: 25/25 layers.
- GPU execution: PASS.
- Lease mission: IJ-SLM-1.0.

Your workstation targets RX 7900 XTX, gfx1100.

### 1.1 Physical resource identity verification

Re-query the latest PR #9 state.

Inspect its latest sealed physical run identities.

Independently identify the local physical GPU using:

- Privacy-preserving host identity.
- Physical GPU identity.
- PCI device identity.
- Adapter LUID where available.
- Vulkan or HIP device identity.
- GPU architecture.
- Local process ownership.
- Existing host-wide GPU mutex and lease records.

A GitHub repository, GPU vendor, model name or mission ID is not a physical resource identity.

Determine whether IJ-SLM and IJ-NANO actually contend for the same physical GPU.

If identities establish distinct physical devices, classify the cross-host conflict as resolved.

Do not release or override IJ-SLM's existing lease.

If identity remains ambiguous, retain the blocker until verified.

### 1.2 Local gfx1100 coordination

Inspect whether IJ-SDK-1.1 currently owns or reserves the local gfx1100 GPU.

Use the existing host-wide lease protocol wherever compatible.

Do not create a mission-specific mutex that fails to coordinate with other worktrees.

Require:

- Exclusive physical GPU ownership for primary comparative experiments.
- Process ownership verification.
- Atomic lease acquisition.
- Correct release.
- Abandoned-owner recovery.
- Persistent trial checkpoints.
- No forced termination of another mission.

If the local GPU is available under the owner-authorized lease policy, proceed with N02.

If the local GPU is occupied, continue independent software tasks.

### 1.3 Correct dependency scope

IJ-SDK's formal GPU matrix authorization applies to its own unqualified benchmark and evaluator scopes.

It is not a repository-wide ban on all physical model inference.

Separate:

- Physical runtime admission.
- Cognitive microbenchmarks.
- Protocol diagnostics.
- Runtime mechanism development.
- Formal business performance evaluation.
- Product qualification.

An unqualified business Oracle must block formal business claims, but it does not automatically block independently valid physical runtime diagnostics or cognitive microbenchmarks.

Update the dependency matrix accordingly.

Correct IJN-B-003 references where the model license blocker was incorrectly identified as IJN-B-005.

Deliver:

- `reports/IJNANO_00R_RESOURCE_AND_DEPENDENCY_RECONCILIATION.md`
- `evidence/IJNANO/N00R/gpu_identity_comparison.json`
- `evidence/IJNANO/N00R/lease_scope_decision.json`
- Updated mission state and blockers.

Possible verdicts:

- `CROSS_HOST_GPU_LEASE_CONFLICT_RESOLVED`
- `LOCAL_GPU_LEASE_AVAILABLE`
- `LOCAL_GPU_LEASE_OCCUPIED`
- `GPU_IDENTITY_UNVERIFIED`

Do not conflate these verdicts.

## 2. Shared Evaluation Architecture Decision

Adopt the following engineering principle:

**One common business evaluation contract, multiple independently qualified specialized evaluators.**

Do not build another redundant full business Oracle if IJ-SDK P5R can supply the required qualified functionality.

Do not inherit the defective original IJ-SDK P5 Oracle.

### 2.1 Shared evaluation components

Coordinate reuse of the following once qualified:

- Event evidence contracts.
- Business state reconstruction.
- Transaction invariants.
- Authorization verification.
- Idempotency.
- Rollback.
- Common metric definitions.
- Resource accounting.
- Evidence sealing.

Treat these as shared benchmark assurance infrastructure.

### 2.2 IJ-NANO-specific evaluator

Implement independent evaluation for:

- Cognitive primitives C01–C32.
- Context sufficiency.
- Context information loss.
- Tool retrieval recall.
- Dependency closure correctness.
- Dynamic action constraints.
- Compact DSL correctness.
- Slot binding provenance.
- Typed state consistency.
- Runtime profile effectiveness.
- Recovery mechanism attribution.
- Model × Harness transfer.
- Cross-job transfer.

These scopes need not wait for the full IJ-SDK P5R business Oracle.

Each must receive its own deterministic controls, independent expected results and mutation tests.

### 2.3 Formal business claim gate

Formal end-to-end business evaluations require either:

A. A qualified and re-audited IJ-SDK P5R evaluator.

B. An independently implemented and qualified evaluator satisfying the same business contract.

If A is unavailable, continue Nano-specific work.

Build only the minimum independent evaluator functionality necessary to avoid a genuine critical-path blocker, and document why the functionality cannot be reused.

Do not duplicate the active IJ-SDK repair work unnecessarily.

## 3. Complete N01 — Primary-source Research Verification

Execute the full R01–R09 investigation.

Prioritize:

1. effGen.
2. PTC-Decoder.
3. TinyAgent.
4. Automated SLM Harness Adaptation.
5. Growing Harness.
6. Meta-Harness.
7. MagenticLite.
8. llama.cpp GBNF, LLGuidance and XGrammar.
9. Reusable components from established Agentic SDKs.

Verify all paper identities, code repositories, authors, experimental results and licenses.

In particular, determine:

- Which approaches have directly evaluated models with approximately 1–3B total parameters?
- Which approaches use larger models with small active parameter counts?
- Which gains come from changed weights?
- Which gains come from Runtime mechanisms alone?
- Which results rely on LLM judges?
- Which mechanisms have independently verified business correctness?
- Which components run locally on native Windows?
- Which implementations can be legally reused in a commercial SDK?

Produce a source-backed reuse-versus-rebuild decision.

Do not invent or inherit unverified literature claims.

Complete the N01 gate before claiming the research landscape has been verified.

## 4. N02 — Physical Runtime Admission

Once a valid local lease is acquired, qualify:

- MiniCPM5-2B.
- LFM3-1.7B.
- Qwen3.5-2B.
- The pinned larger reference models.

Verify exact model and engine hashes.

Retain llama.cpp b12359 and Vulkan as the initial baseline.

Do not silently change engine, quantization or template.

Execute:

- GPU identity verification.
- Model load.
- GPU offload.
- Basic text generation.
- Native tool-call protocol.
- Structured generation.
- Grammar support.
- Streaming.
- Cancellation.
- Token accounting.

These are physical runtime and protocol tests, not formal business correctness claims.

Publish fresh N02 evidence.

Preserve ROCm/HIP as an independently identified comparator.

## 5. N03 — Prioritize Cognitive Microbenchmarks

Do not wait for completion of the 36,550-trial IJ-SLM core plan.

Consume only sealed, identity-bound published IJ-SLM evidence as prior research.

Never treat gfx1151 evidence as gfx1100 physical performance evidence.

Do not use another mission's protected formal holdout results for optimization.

Avoid unnecessary duplication by identifying which cognitive dimensions IJ-SLM has already characterized and which are unique to NanoAgent design.

Prioritize the following twelve capability families:

- Enumerated action selection.
- Native tool-name selection.
- Grammar-constrained action selection.
- Compact Action DSL.
- Slot extraction.
- Entity reference resolution.
- Context interference.
- Tool inventory sensitivity.
- Error recognition.
- Invalid argument recovery.
- Stop versus continue decisions.
- Conditional branching.

These measurements directly inform the first NanoAgent Runtime Profile.

For each family:

- Create independent development cases.
- Define deterministic evaluation where possible.
- Execute software controls.
- Run physical model trials.
- Record exact resource usage.
- Preserve failures.
- Investigate source-level causes.
- Produce capability-specific confidence intervals.

Continue with all remaining C01–C32 requirements from the parent mission.

## 6. N04 — Existing SLM-native Framework Reproduction

After N01 source and license verification, prioritize:

### E01: effGen native

Use the verified official implementation and local llama.cpp backend.

Compare against the minimal reference loop.

Capture its actual prompts, tool schemas, model calls and execution traces.

### E02: PTC-inspired Runtime

Implement separately:

- Plan-to-Act only.
- Tool-name constraints only.
- Combined mechanism.

Use the same model weights.

### E03: TinyAgent-inspired ToolRAG

Compare:

- All tools exposed.
- Semantic Top-K.
- Dependency closure.
- State-aware legal action filtering.

### E04: Action representation

Compare:

- Native function calling.
- Grammar-constrained JSON.
- Enumerated action names.
- Numeric action identifiers.
- Compact DSL.
- Two-stage selection and slot filling.

Do not assume the shortest representation is the best.

All preliminary comparisons remain development or mechanism-level experiments until their applicable formal evaluation scopes qualify.

## 7. N06/N07 — Build the Minimum Viable NanoAgent Runtime

Do not begin with a large SDK implementation.

Build a small, testable execution core.

Implement in this order:

### Layer A — Execution integrity

- Authoritative budget controller.
- Monotonic task deadline.
- Complete session reset.
- Evidence event correlation.
- Typed task state.
- Safe tool gateway.
- Checkpoint and cancellation.

Explicitly test every relevant D01–D07 defect class from IJ-SDK.

### Layer B — Small-model assistance

- Context compiler.
- State-aware tool filtering.
- Dependency closure.
- Action representation.
- Dynamic Grammar.
- Provenance-aware slot binding.

### Layer C — Agent control

- Conditional Action Graph.
- Typed recovery.
- Goal predicates.
- Bounded replanning.
- Model Capability Profile.

Every mechanism must be independently configurable and ablatable.

Do not let the production Runtime read hidden evaluator expectations.

Do not encode per-benchmark-case solutions.

Prefer direct component reuse when it is qualified, secure and commercially eligible.

## 8. First High-value Physical Experiment — SLM Harness Causal Pilot

After applicable runtime, evidence and microbenchmark evaluator qualification, execute a balanced development pilot.

Mandatory models:

- S1 MiniCPM5-2B.
- S2 LFM3-1.7B.
- S3 Qwen3.5-2B.

Candidate configurations:

| Arm | Mechanism |
|---|---|
| A0 | Minimal native reference loop |
| A1 | Compact context only |
| A2 | State-aware tool filtering only |
| A3 | Grammar-constrained actions only |
| A4 | Provenance-aware slot binding only |
| A5 | Typed state only |
| A6 | Typed recovery only |
| A7 | Compact Action DSL only |
| A8 | Combined NanoAgent development profile |
| A9 | Verified effGen native |

Use a minimum initial panel of 120 matched development cases per model and applicable arm.

Nominal maximum: 3,600 physical trial slots.

Pre-register applicability, comparison budgets and scoring rules.

Separate:

- Single-mechanism causal effects.
- Combined mechanism performance.
- Existing SDK comparison.
- Structural correctness.
- Semantic correctness.
- Business correctness.

The combined NanoAgent arm must not be interpreted as the sum of individual mechanism effects.

Investigate interactions in the later factorial experiments.

Report:

- Semantic tool selection.
- Argument correctness.
- Entity hallucinations.
- Structural validity.
- Recovery success.
- Model calls.
- Prompt tokens.
- Completion tokens.
- P50/P95 latency.
- Memory usage.
- Evidence completeness.

Do not grant end-to-end business qualification without a qualified business Oracle.

Do not claim a winner from development results.

## 9. Commercial License Decision

Keep LFM3-1.7B as a mandatory scientific research arm.

Verify its actual model weight license from the official source.

Record any revenue-conditioned or other commercial restrictions.

Separate:

- Research eligibility.
- SDK redistribution eligibility.
- Model redistribution eligibility.
- Commercial deployment eligibility.

Do not exclude an otherwise informative model solely because its commercial license differs from Apache-2.0.

Do not declare unrestricted commercial use without evidence.

## 10. Persistent Research Execution

Maintain:

- Exclusive local GPU lease.
- Persistent queues.
- Atomic evidence sealing.
- Immutable trial identities.
- Exact model and engine hashes.
- Runtime configuration hashes.
- Dataset identities.
- Evaluator scope identities.
- Recovery commands.

Continue software work whenever physical resources are unavailable.

Schedule physical work whenever a valid local lease is available and the specific experimental scope is qualified.

Do not use the incomplete IJ-SDK business matrix authorization as a blanket blocker for all independently qualified NanoAgent experiments.

## 11. GitHub Delivery

Continue using:

- Issue #10.
- Draft PR #11.
- Branch `mission/ij-nano-1.0-slm-native-agentic-runtime`.

Publish:

1. Resource identity and dependency reconciliation.
2. Research landscape report.
3. License and component reuse matrix.
4. Physical runtime qualification.
5. Cognitive capability profiles.
6. Existing SLM-native mechanism reproduction.
7. Minimum NanoAgent Runtime.
8. SLM Harness Causal Pilot protocol and results.
9. Updated root cause ledger.
10. Updated mission dashboard.

Preserve original N00 evidence.

Do not rewrite historical qualification results.

Do not force-push or merge.

Run sensitive-data scanning and regression tests before publication.

## 12. Execution Directive

Start with N00R resource reconciliation.

Then proceed in dependency-aware parallel lanes:

- Lane A: N01 literature and source verification.
- Lane B: N05 specialized cognitive and mechanism evaluator development.
- Lane C: N06/N07 software implementation.
- Lane D: N02/N03 physical runtime and cognitive experiments, when the local lease is valid.
- Lane E: N04 research mechanism reproduction.
- Lane F: balanced SLM Harness Causal Pilot.

Continue the original IJ-NANO-1.0 requirements after these foundations are established.

Preserve every failed experiment and investigate its causal mechanism.

The objective is to identify the minimum sufficient Agentic Runtime for 2B-class models using trustworthy physical experiments.

Execute now.