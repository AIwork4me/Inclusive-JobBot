"""Run public read-only Planning L1-L3 witnesses in the frozen sandbox."""

from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path

from benchmarks.agentic_planning_v1.contract import request
from benchmarks.agentic_planning_v1.freeze import FROZEN, verify
from benchmarks.agentic_planning_v1.oracle import score
from benchmarks.agentic_planning_v1.run import load_jsonl
from benchmarks.agentic_planning_v1.sandbox import SyntheticSandbox
from benchmarks.atlas_validity.planning_intent_witness import solve_read_only

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "evidence/IJ072/benchmark_validity/planning-read-controls.json"


def execute():
    manifest = verify(FROZEN)
    public = load_jsonl(FROZEN / "datasets/holdout.jsonl")
    graphs = {row["case_id"]: row for row in load_jsonl(FROZEN / "task_graphs/holdout.jsonl")}
    results = []
    for case in public:
        if case["level"] not in {"L1", "L2", "L3"}:
            continue
        case_id = case["case_id"]
        graph = graphs[case_id]
        sandbox = SyntheticSandbox(graph["world"])
        start = sandbox.snapshot()
        records = []

        def call(tool, arguments):
            observed = sandbox.invoke(tool, arguments)
            records.append({"turn": len(records), "tool": tool, "args": arguments, "observation": observed})
            return observed

        wire = request(case, "A")
        final = solve_read_only(wire["messages"][-1]["content"], wire["tools"], call)
        end = sandbox.snapshot()
        # The old scorer expects a proposed action in the model role. The saved
        # witness calls keep software attribution and the suite is software-only.
        scoring_rows = [{**row, "origin": "model", "trigger": "tool_feedback" if index else "user_request"}
                        for index, row in enumerate(records)]
        result = score(case, graph, scoring_rows, end, final, track="A")
        missing = score(case, graph, scoring_rows[1:], end, final, track="A")["status"]
        if missing != "FAIL" or start != end:
            raise ValueError(f"read-only state or omitted-action control differs for {case_id}")
        results.append({"case_id": case_id, "level": case["level"], "language": case["language"],
                        "status": result["status"], "missing_first_action": missing, "read_only_state": "PASS",
                        "calls": [{**row, "origin": "software_witness"} for row in records], "final": final,
                        "errors": result["errors"]})
    return {"scope": "L1-L3 Acting-first public-input read-only tasks", "evidence_class": "deterministic_software_control",
            "dataset_sha256": manifest["artifact_sha256"]["datasets/holdout.jsonl"],
            "counts": dict(Counter(row["status"] for row in results)), "trials": results}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = execute()
    raw = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    if args.check:
        if EVIDENCE.read_bytes() != raw:
            parser.error("Planning read witness evidence differs")
    else:
        with EVIDENCE.open("xb") as output:
            output.write(raw)
    print(result["counts"])


if __name__ == "__main__":
    main()
