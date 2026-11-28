"""Apply historical interventions to repaired executable witnesses at corresponding actions."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path

from benchmarks.agentic_planning_v1.contract import request
from benchmarks.agentic_planning_v1.sandbox import SyntheticSandbox
from benchmarks.agentic_planning_v2.execution import execute
from benchmarks.agentic_planning_v2.public_witness import build
from benchmarks.agentic_planning_v2.reachability import may_hold
from scripts.tools.ij073_baseline import VALIDITY, read, records


def audit():
    root = Path("benchmarks/agentic_planning_v1")
    cases, graphs = ({r["case_id"]: r for r in records(root / group / "holdout.jsonl")}
                     for group in ("datasets", "task_graphs"))
    rows = []
    for intervention in read(VALIDITY / "planning-precondition-controls.json")["trials"]:
        key = intervention["case_id"]
        case, graph = cases[key], graphs[key]
        plan, _, public = build(request(case, "P"))
        changed = deepcopy(plan)
        baseline_sandbox = SyntheticSandbox(graph["world"])
        baseline = execute(plan, public, case["action_budget"], baseline_sandbox.invoke)
        if baseline["final"] != graph["final"] or baseline_sandbox.snapshot() != graph["goal_state"]:
            raise ValueError(f"missing positive control for {key}")
        if intervention["mutation"] == "disable_first_action":
            node = changed["actions"][0]
            guard = False
        else:
            node, = (n for n in changed["actions"] if n["tool"] == "commit")
            guard = {"op": "eq", "left": {"from": "event", "field": "decision"}, "right": "declined"}
        if node["tool"] != intervention["tool"]:
            raise ValueError("non-equivalent intervention target")
        previous = node["when"]
        node["when"] = guard
        sandbox = SyntheticSandbox(graph["world"])
        result = execute(changed, public, case["action_budget"], sandbox.invoke)
        changed_terminal = result["final"] != baseline["final"] or sandbox.snapshot() != baseline_sandbox.snapshot()
        approved = {"event": {"decision": "approved"}}
        loses_approved_path = (node["tool"] == "commit" and may_hold(previous, approved) is True
                               and may_hold(guard, approved) is False)
        rows.append({"case_id": key, "intervention": intervention["mutation"], "node": node["id"],
                     "original_v1_negative_control": intervention["status"], "baseline_v2": "PASS",
                     "terminal_or_state_changed": changed_terminal, "approved_path_disabled": loses_approved_path,
                     "outcome": "PASS" if changed_terminal or loses_approved_path else "FAIL"})
    return {"scope": "paired executable software control with one guard changed",
            "outcomes": dict(Counter(r["outcome"] for r in rows)), "rows": rows}


if __name__ == "__main__":
    print(json.dumps(audit(), sort_keys=True, indent=2))
