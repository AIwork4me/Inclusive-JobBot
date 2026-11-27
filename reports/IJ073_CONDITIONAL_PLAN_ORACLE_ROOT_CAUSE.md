# IJ073 conditional planning root causes

At baseline `0ba158cf95cd802ca9f9091d6abc893dce543644`, the public software witness constructs a plan before opening the sandbox. It then delegates execution to a separate solver. Agreement between the final answer and business state therefore leaves an open question about whether the proposed plan could have produced the calls. See `scripts/tools/atlas_planning_plan_controls.py:32` and `benchmarks/atlas_validity/planning_public_plan.py:9`.

| Frozen source | Mechanism | Reproduction |
|---|---|---|
| `oracle.py:45`, `initial_plan` | Goal equality uses the private graph. | Compare the public goal vocabulary in `contract.py:56` with the graph argument to the scorer. |
| `oracle.py:49`, `initial_plan` | Rejects graphs larger than twice the action budget before inspecting a branch. | AP1-L4-002 has 19 nodes, a 7-call budget and a representable 5-call observed path. |
| `oracle.py:54`, `initial_plan` | Excludes the authored disruption and descendants using the hidden witness. | Compare normalized public-equivalent contracts with different path lengths in the 29-case cohort. |
| `oracle.py:69`, `initial_plan` | Dependencies must precede the node in the list. Preconditions only need to be lists of nonempty strings. | Replay the 602 interventions using `python -m scripts.tools.atlas_audit_plan_ambiguity --check --preconditions`. |
| `oracle.py:78`, `initial_plan` | Rejects literal private IDs, then resolves prior references against assumed private observations. Policy assessment can use the private threshold. | Follow a lookup ID into a primary read. A legitimate conditional path can reference an output that never occurs in this world. |
| `oracle.py:97`, `initial_plan` | Matches each node to private arguments and observations. Uses these matches to count initial coverage. | AP1-L4-005 first fails actual path alignment at the seventh call. Relaxing coverage alone would conceal this missing branch. |
| `contract.py:67`, `request` | Sends prompt, policy and tool schemas. The initial request omits numeric action and context budgets. | Compare the public wire and `datasets/holdout.jsonl` for AP1-L4-002. |
| `runner.py:99`, `Boundary.validate`, and `runner.py:126`, `Boundary.observe` | Checks available IDs and consumes actual feedback. The dynamic solver can repeat reads after a revised reference. | Inspect a scope revision in L5/L6 and compare the original plan to the independent solver in `planning_advanced_witness.py:26`. |
| `sandbox.py:37`, `_delivery_tool`, and `oracle.py:123`, `score` | A synthetic external decision releases a draft-specific grant. Terminal scoring checks the private goal state, required observations and answer. | Replaying both sets of 800 calls reproduces observations, answers and business state. The original physical archive includes zero commit calls. |

Source paths without a package prefix above are inside `benchmarks/agentic_planning_v1/`. The bounded diagnostic examines all node bindings compatible with the observed prefix, consumes each node at most once and binds arguments only to earlier observations. It permits any old prose precondition. A complete match establishes representability of **one observed path**. Replanning could legitimately depart from an initial graph where the contract allows it.

| Original result | Full observed path representable | First unmatched call exists |
|---|---:|---:|
| Rejected by plan size | 47 | 6 |
| Rejected by initial subgoal coverage | 0 | 75 |
| Accepted by old plan gate | 437 | 235 |

Of the 29 public-equivalent cases, 3 match completely and 26 fail alignment. The per-case file records plan size, actual budget, matched prefix and first unmatched tool. [Alignment evidence](../evidence/IJ073/oracle/legacy_alignment.json)
