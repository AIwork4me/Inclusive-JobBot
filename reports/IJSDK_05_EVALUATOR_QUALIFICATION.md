# IJSDK_05_EVALUATOR_QUALIFICATION — P5 Independent Evaluator Qualification

Mission: **IJ-SDK-1.0** · Generated: 2026-11-27 · Branch: `mission/ij-sdk-1.0-cross-sdk-agentic-benchmark`
Evidence: `evidence/IJSDK/P5/differential_results.json` (14 controls, full rules fired), `evaluation/ij_sdk/business_oracle.py`, `evaluation/ij_sdk/qualify_oracle.py`

---

## 1. Verdict

| Gate item | Status |
|---|---|
| Oracle independence from model/SDK/loop/answer/self-reported status | PASS (oracle consumes only frozen evidence structures) |
| Independently authored control battery (positives + alternative trajectories + every critical negative class + metamorphic) | PASS — 14 controls |
| Differential testing run | PASS — 14/14 accepted; 0 critical failures |
| Oracle defects found by the battery fixed with rule-level attribution | PASS — 4 defects fixed (below) |
| AEVE inheritance | **NOT INHERITED** (per P0 audit: all Atlas/AEVE verdicts BLOCKED/NOT_RUN at source commit) |
| Gate `P5_EVALUATOR_SCOPE_QUALIFIED` | **PASS for the qualified scopes below; other scopes remain NOT_QUALIFIED** |

## 2. Qualified scopes (mission 8.1 layers)

| Layer | Scope | Basis |
|---|---|---|
| E1 semantic tool correctness | tool selection, argument values, entity grounding (fabricated IDs rejected) | controls P01/P02/P05, N01/N02/N03 |
| E3 execution correctness | gateway-recorded failures detected | N04 |
| E4 final business correctness | answer-vs-evidence, evidence grounding (asserted facts must be in the call-args+result chain), false completion, incomplete, refusal, clarification | P01/P03/P04/P05, N04/N06/N08/N09 |
| E5 safety | unauthorized attempt contained vs unauthorized state change, verdict precedence over business classification | N05, P03 |
| E6 efficiency | token/model-call/tool-call counters from server usage + harness accounting | deterministic counters (no judgment) |
| Distinguishing classes | all 9 mission-8.2 classes have at least one control | battery |

**NOT qualified (stays BLOCKED for formal claims):** qualitative language quality (E4-subjective), plan elegance, LLM-judged dimensions (AEVE remains unqualified by its own gates — separate worker mid-qualification), human accessibility dimensions (no real reviewer; score-blind review packet pending → human review marked NOT_RUN).

## 3. Oracle defects found by differential testing (fixed, rule-attributed)

1. **E1 expected-call indexing** — `expected_tool`/`expected_args` were applied to every call, flagging legitimate multistep trajectories (P05 fired `E1.tool_selection_mismatch` on a valid 3-step chain). Fixed: apply at `expected_call_index` (default 0) + new `E1.required_call_missing`.
2. **E5 verdict precedence** — an unauthorized state change with a completion-claiming answer classified as `INCORRECT_FINAL_RESPONSE`. Fixed: safety verdicts dominate the classification chain (N05 now `UNAUTHORIZED_STATE_CHANGE`).
3. **E4 evidence grounding missing** — a factual claim ("SUP-007 合格") passed as CORRECT with no supporting tool call. Fixed: `answer_requires_tool_result` rule `E4.ungrounded_assertion` (N09).
4. **Grounding chain definition** — first implementation checked only the result payload; a lookup key asserted from the call's own arguments is legitimate evidence. Fixed: chain = call args ∪ result (P02/P05).

Each fix was driven by a control that produced a DISCREPANCY; no control was edited to fit the oracle's old behavior (controls were authored against the mission contract, then N09's expectation was *extended* with the new grounding spec that the contract requires).

## 4. Independence statement

The oracle consumes `TrialEvidence` (tool calls, gateway results, rejected calls, state changes, final answer) populated by the harness from wire-captured events. It never reads SDK identity, model identity, prompts' origin, or any framework-reported status. Verdicts are pure functions of that evidence plus the frozen world/expectations. Rejection is the default on ambiguity (fail-closed).

## 5. Carry-forward

1. The same battery pattern extends to the P10 job worlds (J01–J06) — each world freeze ships its own control file; a world without a passing control battery cannot contribute formal scores.
2. LLM-judged dimensions remain BLOCKED until an AI evaluator passes gold-case qualification with false-positive/false-negative rates (AEVE's own gates are a separate worker's active work; no inheritance).
3. Score-blind human review packet: generated at P19; independent human review marked NOT_RUN until a real reviewer completes it.
