"""Verify L0-L7 public Plan-first witnesses using the frozen sandbox."""

from argparse import ArgumentParser
from collections import Counter
import gzip
import json
from pathlib import Path

from benchmarks.agentic_planning_v1.contract import request
from benchmarks.agentic_planning_v1.freeze import FROZEN, verify
from benchmarks.agentic_planning_v1.oracle import score
from benchmarks.agentic_planning_v1.run import load_jsonl
from benchmarks.agentic_planning_v1.sandbox import SyntheticSandbox
from benchmarks.atlas_validity.planning_intent_witness import solve_read_only, understand
from benchmarks.atlas_validity.planning_advanced_witness import solve as solve_advanced, state_agrees
from benchmarks.atlas_validity.planning_public_plan import initial_plan

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "evidence/IJ072/benchmark_validity/planning-plan-controls.json.gz"


def execute():
    manifest = verify(FROZEN)
    public = load_jsonl(FROZEN / "datasets/holdout.jsonl")
    graphs = {row["case_id"]: row for row in load_jsonl(FROZEN / "task_graphs/holdout.jsonl")}
    results = []
    for case in public:
        case_id = case["case_id"]
        wire = request(case, "P")
        prompt = wire["messages"][-1]["content"]
        plan = initial_plan(wire)
        graph = graphs[case_id]
        sandbox = SyntheticSandbox(graph["world"])
        start = sandbox.snapshot()
        records = []

        def call(tool, arguments):
            observed = sandbox.invoke(tool, arguments)
            records.append({"turn": len(records), "tool": tool, "args": arguments, "observation": observed})
            return observed

        if case["level"] in {"L4", "L5", "L6", "L7"}:
            final = solve_advanced(wire, call)
        else:
            final = solve_read_only(prompt, wire["tools"], call) if wire["tools"] else understand(prompt)
        end = sandbox.snapshot()
        # The old scorer expects a proposed action in the model role. The saved
        # witness calls keep software attribution and the suite is software-only.
        scoring_rows = [{**row, "origin": "model", "trigger": "tool_feedback" if index else "user_request"}
                        for index, row in enumerate(records)]
        result = score(case, graph, scoring_rows, end, final, track="P", plan=plan, plan_before_tools=True)
        missing = score(case, graph, scoring_rows, end, final, track="P", plan=None)["status"]
        state_ok = state_agrees(start, end, records, final)
        status = result["status"] if state_ok and missing == "FAIL" else "FAIL"
        results.append({"case_id": case_id, "level": case["level"], "language": case["language"],
                        "status": status, "missing_initial_plan": missing, "initial_plan": plan,
                        "state_check": "PASS" if state_ok else "FAIL",
                        "calls": [{**row, "origin": "software_witness"} for row in records], "final": final,
                        "errors": result["errors"], "plan_errors": result["plan"]["errors"]})
    return {"scope": "L0-L7 Plan-first public-input initial plans and witnessed actions", "evidence_class": "deterministic_software_control",
            "dataset_sha256": manifest["artifact_sha256"]["datasets/holdout.jsonl"],
            "counts": dict(Counter(row["status"] for row in results)), "trials": results}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = execute()
    raw = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    if args.check:
        if gzip.decompress(EVIDENCE.read_bytes()) != raw:
            parser.error("Plan-first witness evidence differs")
    else:
        with EVIDENCE.open("xb") as output:
            output.write(gzip.compress(raw, mtime=0))
    print(result["counts"])


if __name__ == "__main__":
    main()
