# IJ073 Oracle engineering checkpoint

**Qualification remains open.** The candidate accepts a version-2 bounded JSON AST, validates action references and cycles, evaluates three-valued guards, and replays finite, explicitly supplied control worlds. The control-world runner checks the terminal disposition, permitted steps, scoped external approval and actual call budget. It can express independent steps through partial-order constraints. The tested controls use synthetic business data. [Contract](../schemas/conditional_plan_v2.schema.json) · [Verifier](../benchmarks/agentic_planning_v2/oracle.py)

| Cohort | Result | Interpretation |
|---|---|---|
| A/D, 128 original failures among 800 plans | 47 of 128 match all executed calls under relaxed guards | Necessary observed-path check. Detailed breakdown in the [root-cause report](IJ073_CONDITIONAL_PLAN_ORACLE_ROOT_CAUSE.md). |
| B, 602 interventions | 562/562 disabled-node and 40/40 declined-approval interventions each make at least one additional required effect unreachable | The original experimental interventions are encoded as ASTs. Every other prose guard is relaxed. The reachability algorithm sees only the graph, guard and public requirements. 582 have a baseline with all necessary effects reachable. The remaining 20 interventions affect 10 original plans missing the verification tool on a nominal success path. [Results](../evidence/IJ073/oracle/mutation_replay.json) |
| C, 13 groups | Recomputed the old public grouping and distinct paths from the 200 source cases. Only 3/29 old graphs match the complete observed path. | A repaired common plan still needs independent public counterfactual testing. |
| D/E, 800 + 800 software traces | 1,600 matched final objects, observations and replayed synthetic business states | These calls were chosen by the separate software witness. [Replay](../evidence/IJ073/oracle/witness_replay.json) |
| F, 1,600 physical first attempts + 960 repeats | 530 contained calls, all with matching sandbox observations and recorded end state. 393 had a recorded final output, none matched both expected object and state. 2,167 had no final output. | Offline replay verified every compressed part and member. Commit authorization was unexercised throughout. [Replay](../evidence/IJ073/oracle/archive_replay.json) |

## Reproduction

From the checkout root, use Python 3.12 with the repository's pinned jsonschema dependency and pytest. Each command emits JSON to stdout.

```text
python -m scripts.tools.ij073_baseline
python -m scripts.tools.ij073_plan_alignment
python -m scripts.tools.ij073_mutation_replay
python -m scripts.tools.ij073_witness_replay
python -m scripts.tools.ij073_archive_replay
python -m pytest -q tests/regression/test_ij073_conditional.py
```

The candidate still needs independently authored full public transition domains for L0–L7, a repaired conditional witness for the incomplete graphs, policies for all request/retry/context budgets, runner integration, and independent qualification. Passing a fixed set of worlds is scoped to those worlds. The archive replay checks literal terminal objects and state. Semantic judgments and reviewer calibration belong to later gates.
