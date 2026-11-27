"""Replay the recorded Acting-first and Plan-first software witnesses independently of their plan score."""
from collections import Counter
import json
from pathlib import Path

from benchmarks.agentic_planning_v1.sandbox import SyntheticSandbox
from benchmarks.tool_calling_v2.oracle import equal
from scripts.tools.ij073_baseline import VALIDITY, read, records


def audit():
    directory = Path("benchmarks/agentic_planning_v1")
    cases, graphs = ({r["case_id"]: r for r in records(directory / group / "holdout.jsonl")}
                     for group in ("datasets", "task_graphs"))
    rows = []
    for track, file in (("A", "planning-intent-controls.json"), ("A", "planning-read-controls.json"),
                        ("A", "planning-advanced-controls.json"), ("P", "planning-plan-controls.json.gz")):
        for recorded in read(VALIDITY / file)["trials"]:
            key = recorded["case_id"]
            calls = recorded.get("calls", [])
            final = recorded.get("final", recorded.get("witness"))
            sandbox = SyntheticSandbox(graphs[key]["world"])
            errors = []
            if len(calls) > cases[key]["action_budget"]:
                errors.append("budget")
            for index, call in enumerate(calls):
                if (call["tool"] not in cases[key]["tools"] or
                        not equal(sandbox.invoke(call["tool"], call["args"]), call["observation"])):
                    errors.append(f"call {index}")
            if not equal(sandbox.snapshot(), graphs[key]["goal_state"]):
                errors.append("state")
            if not equal(final, graphs[key]["final"]):
                errors.append("answer")
            rows.append({"track": track, "case_id": key, "calls": len(calls), "errors": errors,
                         "status": "FAIL" if errors else "PASS"})
    if {(r["track"], r["case_id"]) for r in rows} != {(t, k) for t in ("A", "P") for k in cases} or len(rows) != 2*len(cases):
        raise ValueError("witness coverage mismatch")
    return {"scope": "software replay of recorded calls and terminal outcomes; excludes initial plan qualification",
            "counts": dict(Counter(r["track"]+"/"+r["status"] for r in rows)), "rows": rows}


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2, sort_keys=True))
