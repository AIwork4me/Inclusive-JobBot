# IJ-NANO-1.2 Addendum — N02R Protocol Matrix Integrity & Causal Evidence Closure

## 0. Identity

- Repository: https://github.com/AIwork4me/Inclusive-JobBot
- Issue: #10
- Draft PR: #11
- Branch: `mission/ij-nano-1.0-slm-native-agentic-runtime`
- Audited HEAD: `9b137f6927351f3abf45b6b9328a5cb268b6f63d`
- Existing experiment: `36bfed1d55a9987b`
- Hardware: Windows + RX 7900 XTX, gfx1100
- Engine: llama.cpp b12359
- Backend: Vulkan

Continue the existing IJ-NANO-1.2 mission.

Preserve all completed qualifications and original evidence.

Do not restart the entire mission or introduce unnecessary new architecture.

The immediate objective is to establish the scientific validity of the N02R protocol comparison before using its results to design NanoAgent Runtime Profiles.

## 1. Protect the running experiment

Inspect the actual local controller, GPU lease, process ownership and persistent queue.

Do not forcibly terminate a healthy physical experiment.

Do not modify source files used by an active experiment.

At the next safe checkpoint:

- Preserve completed trials.
- Record exact execution progress.
- Seal original evidence.
- Preserve the original experiment identity.
- Record the audited implementation hashes.
- Pause before additional affected comparisons where necessary.

Classify the existing experiment as development/diagnostic evidence pending integrity review.

Do not grant N02R formal comparison closure until the following concerns are reproduced or refuted.

## 2. Reproduce PR-D01 — Information equivalence

Inspect `tasks.py` and `arms.py`.

Verify whether each experimental arm receives equivalent task information, particularly:

- Tool names.
- Tool descriptions.
- Required parameters.
- Candidate actions.
- Relevant business context.
- Output requirements.

The current free-text P0 path may lack information supplied to other arms through schemas, grammars or native tool definitions.

Create a request-level comparison manifest for every task family.

Separate:

- Native protocol usability comparison.
- Information-matched causal comparison.

For the matched comparison, provide the same legitimate tool and action information to all applicable arms.

Do not reveal hidden expected answers.

Separate the benefit of candidate exposure from the benefit of constrained decoding.

## 3. Reproduce PR-D02 — P5 contract mismatch

Inspect the Structured Action native-function-calling request.

The audited implementation defines `record_answer(args_json)` but the parser appears to require an actual business tool name.

Create an executable control where the model returns a perfectly valid response according to the supplied tool definition.

Determine whether the current parser incorrectly rejects it.

Repair the contract using one of two explicitly separated experimental arms:

A. Native business tool selection with actual typed business tool schemas.

B. Structured answer recording using a declared record_answer tool.

Do not label B as native business tool execution.

Verify single versus multiple tool calls, expected names, argument schemas and complete response semantics.

## 4. Reproduce PR-D03 — P7 applicability

Inspect enumeration support for:

- Tool selection.
- Enumerated action.
- Conditional branch.
- Stop/continue.
- Slot extraction.
- Structured action.

P7 appears to lack meaningful candidate sets for some task families.

Do not count an impossible protocol/task combination as a model capability failure.

Preregister applicability based on the task contract.

If an enumerated protocol requires a second slot-filling stage, implement that as a separately identified protocol.

Do not expose a list containing the hidden correct argument merely to make enumeration possible.

## 5. Reproduce PR-D04/D05 — Parser and evaluator integration

Inspect:

- `_closed_set_find`
- `_coerce_slot_value`
- `_kv_scan`
- `_payload_from_json`
- `parse_response`
- `scorer.score`

Add end-to-end controls from raw API response to final evaluator verdict.

Mandatory negatives:

- Multiple competing candidate answers.
- Negated candidate answer.
- Contradictory final answer.
- Unexpected tool argument.
- Duplicate JSON key.
- Duplicate DSL key.
- Duplicate DSL slot name.
- Incorrect DSL slot name.
- Invalid DSL header.
- Trailing contradictory DSL content.
- Malformed quantity.
- Wrong entity.
- Multiple unexpected tool calls.
- Wrong record_answer function name.
- Truncated output.
- Missing required answer.

A parser must not silently transform a semantically invalid output into a correct answer.

Preserve:

- Raw response.
- Parser output.
- Parsing warnings.
- Structural verdict.
- Semantic verdict.
- Any declared normalization.

Do not discard unknown fields before the evaluator can inspect them.

Retain the N05AR comparator qualification and add a separate integration gate:

`N02R_PARSER_EVALUATOR_INTEGRATION_GO`

## 6. Reproduce PR-D06 — Experiment identity integrity

Inspect the controller experiment identity and resume implementation.

Verify complete binding to:

- Model SHA256.
- Quantization.
- Chat Template SHA256.
- Engine binary and relevant DLL SHA256.
- Backend.
- GPU physical identity.
- Evaluator implementation.
- Parser implementation.
- Task suite.
- Request renderer.
- Budgets.
- Decoding settings.
- Cache policy.
- Controller implementation.

Changing any relevant experimental factor must create a new experiment identity.

Do not allow resume to combine results from different backends, weights, engines or evaluators.

Validate every restored trial against its frozen experiment manifest.

Do not overwrite historical manifests when executing subsequent phases.

## 7. Reproduce PR-D07 — Physical GPU evidence

Inspect `ServerSession.wait_ready()` and the physical execution proof.

The audited implementation appears to assign the launched PID as the socket owner without independently verifying the actual listening process.

Require:

- Real socket-to-PID ownership.
- Server process identity.
- Exact model identity.
- Full required GPU offload.
- Physical GPU identity.
- PID-bound GPU counters where required by repository rules.
- Host-wide lease.
- Per-session evidence binding.

Fail closed if physical execution cannot be established.

A successful HTTP request alone is not proof of GPU execution.

## 8. Reproduce PR-D08/D09 — Response and resource evidence

Implement endpoint-specific telemetry extraction for both Chat Completions and Completion.

Capture, where actually exposed:

- Prompt tokens.
- Generated tokens.
- Cached tokens.
- Finish reason or equivalent stop reason.
- Truncation.
- Latency.
- Inference timing.
- Thinking-channel text.
- Final-action text.
- Complete tool calls.

Use explicit NOT_CAPTURED or UNAVAILABLE when telemetry is absent.

Never treat unavailable usage as zero.

Preserve complete sanitized API responses or content-addressed response artifacts with verified hashes.

Do not truncate the only available evidence to 4,000 characters.

Do not claim exact SSE token reconciliation from the presence of usage fields and nonempty text alone.

For cancellation, distinguish:

- Client connection closed.
- Server cancellation observed.
- Original generation stopped.
- Inference slot released.
- Subsequent generation completed.

## 9. Reconcile PR-D10 — Trial denominators

Current nominal plan:

- Main: 3 × 8 × 60 = 1,440 slots.
- Budget panel: 3 × 4 × 12 × 5 = 720 slots.
- Main/panel overlap at 1,024 tokens: 144 slots.
- Unique logical slots: 2,016.

Verify the actual frozen task roster and Trial ID implementation.

Report:

- Planned logical slots.
- Unique experiment slots.
- Reused trials.
- Actual physical attempts.
- Evidence-valid trials.
- Semantic PASS.
- Semantic FAIL.
- BLOCKED.
- NOT_RUN.
- INAPPLICABLE.

Do not count reused trials as independent observations.

Do not claim 2,160 unique physical trials from the current plan.

## 10. Causal analysis of thinking and grammar

Preserve the current source-level findings.

Refine the causal claim:

The lazy-grammar mechanism and shared generation budget permit reasoning to exhaust the available completion budget. Model-specific reasoning behavior may still influence whether and how frequently the failure occurs.

Do not claim that model weights have been completely excluded as a contributing factor.

Compare:

T0: Default thinking.

T1: Verified thinking disabled.

T2: Explicitly bounded reasoning budget, using the actual supported engine controls.

T3: Eager constrained generation through Completion.

Where technically possible, hold the rendered prompt and semantic information constant to isolate transport and sampler effects.

Investigate the pinned engine's reasoning-budget mechanism instead of assuming larger generation budgets are the best solution.

Report both:

- Empty-final-content and structural success.
- Semantic decision correctness.

Disabling thinking may improve structural completion while reducing complex reasoning accuracy. Measure this trade-off.

Preserve the original engine identity.

## 11. Evidence disposition and selective re-execution

For every original trial classify:

- VALID_AS_IS
- OFFLINE_RESCORE_POSSIBLE
- DIAGNOSTIC_ONLY
- PHYSICAL_REEXECUTION_REQUIRED
- EVIDENCE_INSUFFICIENT

Reuse valid physical evidence where the complete experimental identity and raw response permit it.

For parser-only defects, prefer offline re-scoring.

For request, information exposure, engine identity or physical attribution defects, re-execute the affected comparisons under a new frozen experimental identity.

Do not overwrite original results.

Publish an exact reuse and re-execution manifest.

## 12. N02R final closure

Complete:

- Original experiment evidence audit.
- Parser × Evaluator integration tests.
- Information-equivalence matrix.
- Corrected protocol applicability matrix.
- Physical execution identity audit.
- Endpoint-specific resource metrics.
- Matched protocol comparison.
- Budget sensitivity analysis.
- Source-level causal analysis.

Publish:

- `reports/IJNANO_02R_PROTOCOL_CAUSAL_ANALYSIS.md`
- `reports/IJNANO_02R_EXPERIMENT_INTEGRITY_AUDIT.md`
- `evidence/IJNANO/N02R/protocol_matrix.json`
- `evidence/IJNANO/N02R/evidence_disposition.json`
- `evidence/IJNANO/N02R/parser_evaluator_qualification.json`
- Corrected physical experiment manifests.

Grant:

`N02R_MODEL_PROTOCOL_BEHAVIOR_CHARACTERIZED`

only when its applicable comparison scopes are supported by trustworthy evidence.

## 13. Continue N03

After the required N02R scopes qualify, execute the original N03 plan:

- All C01–C32 cognitive primitives.
- 640 development cases.
- 320 reserved confirmation cases.
- Three mandatory small models.
- Matched larger-model reference panels.
- Capability scaling curves.
- Model-specific Runtime Profile candidates.

Use N02R findings to determine protocol candidates.

Do not tune on reserved confirmation answers.

Continue N06B/C and the 3,600-slot causal pilot according to the existing mission order.

Publish milestone evidence to Issue #10 and Draft PR #11.

Run regression tests and the fail-closed sensitive-data publication check.

Do not merge or force-push.

Execute now.
