"""Align every historical public plan to its independent software execution."""
import json
from collections import Counter
from pathlib import Path

from benchmarks.agentic_planning_v2.alignment import match_prefix
from scripts.tools.ij073_baseline import VALIDITY, digest, read, records


def audit():
    public = Path("benchmarks/agentic_planning_v1/datasets/holdout.jsonl")
    witness = VALIDITY / "planning-plan-controls.json.gz"
    cases = {r["case_id"]: r for r in records(public)}
    rows = []
    for r in read(witness)["trials"]:
        actions = r["initial_plan"]["actions"]
        calls = r["calls"]
        case = cases[r["case_id"]]
        matched = match_prefix(actions, calls, case.get("policy", ""))
        rows.append({"case_id": r["case_id"], "original": r["status"], "original_errors": r["plan_errors"],
                     "plan_nodes": len(actions), "action_budget": case["action_budget"], "actual_calls": len(calls),
                     "matched_prefix": matched, "first_unmatched_tool": None if matched == len(calls) else calls[matched]["tool"],
                     "trace_representability": "PASS" if matched == len(calls) else "FAIL"})
    if set(cases) != {r["case_id"] for r in rows} or len(rows) != len(cases):
        raise ValueError("case identity mismatch")
    return {"scope": "offline software witness alignment, ignoring prose conditions and terminal semantics",
            "sources": {p.as_posix(): digest(p) for p in (public, witness)},
            "cross_tab": dict(Counter(r["original"]+"/"+r["trace_representability"] for r in rows)), "rows": rows}


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2, sort_keys=True))
