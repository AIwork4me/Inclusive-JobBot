# IJ073 Oracle engineering checkpoint

**Qualification remains open.** The candidate accepts a version-2 bounded JSON AST, validates action references and cycles, evaluates three-valued guards, and replays finite, explicitly supplied control worlds. The control-world runner checks the terminal disposition, permitted steps, scoped external approval and actual call budget. It can express independent steps through partial-order constraints. The tested controls use synthetic business data. [Contract](../schemas/conditional_plan_v2.schema.json) · [Verifier](../benchmarks/agentic_planning_v2/oracle.py)

| Cohort | Result | Interpretation |
|---|---|---|
| A/D, 128 original failures among 800 plans | 47 of 128 match all executed calls under relaxed guards | Necessary observed-path check. Detailed breakdown in the [root-cause report](IJ073_CONDITIONAL_PLAN_ORACLE_ROOT_CAUSE.md). |
| B, 602 interventions | 562/562 disabled-node and 40/40 declined-approval interventions each make at least one additional required effect unreachable | The original experimental interventions are encoded as ASTs. Every other prose guard is relaxed. The reachability algorithm sees only the graph, guard and public requirements. 582 have a baseline with all necessary effects reachable. The remaining 20 interventions affect 10 original plans missing the verification tool on a nominal success path. [Results](../evidence/IJ073/oracle/mutation_replay.json) |
| C, 13 groups | Recomputed the old public grouping and distinct paths from the 200 source cases. Only 3/29 old graphs match the complete observed path. | All 13 groups now execute one repaired graph per group and take distinct paths as observations change. |
| D/E, 800 + 800 software traces | 1,600 matched final objects, observations and replayed synthetic business states | These calls were chosen by the separate software witness. [Replay](../evidence/IJ073/oracle/witness_replay.json) |
| F, 1,600 physical first attempts + 960 repeats | 530 contained calls, all with matching sandbox observations and recorded end state. 393 had a recorded final output, none matched both expected object and state. 2,167 had no final output. Of 1,280 Plan-first initial responses, 1,130 lacked a strict JSON object and 150 returned other object fields. None supplied the five originally requested plan fields. | Offline replay verified every compressed part and member. Commit authorization was unexercised throughout. [Replay](../evidence/IJ073/oracle/archive_replay.json) |

## Reproduction

From the checkout root, use Python 3.12 with the repository's pinned jsonschema dependency and pytest. Each command emits JSON to stdout.

```text
python -m scripts.tools.ij073_verify
python -m scripts.tools.ij073_baseline
python -m scripts.tools.ij073_plan_alignment
python -m scripts.tools.ij073_mutation_replay
python -m scripts.tools.ij073_witness_replay
python -m scripts.tools.ij073_archive_replay
python -m pytest -q tests/regression/test_ij073_conditional.py
```

## Executed conditional witness

A second experiment builds the typed graph solely from the public request, before opening the synthetic world. Action choice, argument binding, terminal disposition and final facts all come from the graph interpreter. Across 800 tasks, 62 distinct plan/contract pairs reproduced the correct observations, required actions, business state and answer. This includes the 128 cases with rejected historical plans. The archive contains the exact graphs, action-level observations, terminal answers and resource counts. Each of the 13 public-equivalent groups has one graph hash and multiple observed paths. [Plans and traces](../evidence/IJ073/oracle/executable_witness.json)

Against these repaired graphs, disabling the corresponding first action changes the observed outcome in 562/562 cases. Changing the commit guard to require a decline changes 30/40 actual outcomes. The remaining 10 worlds already decline approval, so their real terminal outcome correctly stays the same. The guard disables the legal approval branch in all 40 under the single-variable approval counterfactual. [Paired interventions](../evidence/IJ073/oracle/guard_controls.json)

The repaired graphs are software witnesses evaluated in frozen synthetic worlds. They establish feasibility on this suite. The new standalone model-facing boundary constructs the public wire request and evaluates raw replies in separate control worlds. Nine independently authored controls over 21 threshold/recovery worlds produced their expected verdicts, including a redundant guard that correctly leaves all outcomes unchanged. The reference model has now exercised the local wire boundary. Broader independent safety and evaluator qualification remain open. [Public controls](../evidence/IJ073/oracle/public_worlds.json) The offline terminal replay compares literal objects and state. Semantic judgments and human calibration belong to later gates.

## Radeon protocol regression

Qwen3-14B Q8_0 ran with 41/41 layers on the Radeon 8060S Vulkan backend. The development task asked for clarification of missing dates, exposed zero tools, and allowed zero tool calls. In each pair, the unconstrained reply failed the V2 schema. The constrained reply passed the schema and proposed an unavailable tool named `ask`. Both modes produced a nonempty action list.

The first request named the initial object `initial` while the interpreter reserved `public`. In the second pair only this field name changed on the model wire. The model used the corrected reference name but still proposed `ask`. All four requests received HTTP 200, generated untruncated replies and have source tokens, sampler settings and process GPU counters. Strict plan results were 0/4. This is one development case with repeated treatments. [Paired result](../evidence/IJ073/transport/paired_result.json)

The updated software witness archive includes trusted before/after snapshots for every synthetic call. A separate verifier reconstructs the expected draft and delivery changes and checks for partial effects on rejected operations. A negative control injects a state change after a denied write and the verifier rejects it. Crash recovery and production database durability have separate evidence requirements.
