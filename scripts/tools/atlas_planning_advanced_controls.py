"""Run public-input Planning L4-L7 witnesses in the frozen sandbox."""

from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path

from benchmarks.agentic_planning_v1.contract import request
from benchmarks.agentic_planning_v1.freeze import FROZEN, verify
from benchmarks.agentic_planning_v1.oracle import score
from benchmarks.agentic_planning_v1.run import load_jsonl
from benchmarks.agentic_planning_v1.sandbox import SyntheticSandbox
from benchmarks.atlas_validity.planning_advanced_witness import solve, state_agrees

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "evidence/IJ072/benchmark_validity/planning-advanced-controls.json"


def execute():
    manifest = verify(FROZEN)
    public = load_jsonl(FROZEN / "datasets/holdout.jsonl")
    graphs = {row["case_id"]: row for row in load_jsonl(FROZEN / "task_graphs/holdout.jsonl")}
    results = []
    for case in public:
        if case["level"] not in {"L4", "L5", "L6", "L7"}:
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
        try:
            final = solve(wire, call)
        except (KeyError, TypeError, ValueError) as error:
            results.append({"case_id": case_id, "level": case["level"], "language": case["language"],
                            "status": "FAIL", "witness_error": str(error), "calls": records})
            continue
        end = sandbox.snapshot()
        # The old scorer expects a proposed action in the model role. The saved
        # witness calls keep software attribution and the suite is software-only.
        scoring_rows = [{**row, "origin": "model", "trigger": "tool_feedback" if index else "user_request"}
                        for index, row in enumerate(records)]
        result = score(case, graph, scoring_rows, end, final, track="A")
        missing = score(case, graph, scoring_rows[1:], end, final, track="A")["status"]
        state_ok = state_agrees(start, end, records, final)
        status = result["status"] if state_ok and (not records or missing == "FAIL") else "FAIL"
        results.append({"case_id": case_id, "level": case["level"], "language": case["language"],
                        "status": status, "missing_first_action": missing if records else "NOT_APPLICABLE",
                        "state_check": "PASS" if state_ok else "FAIL",
                        "calls": [{**row, "origin": "software_witness"} for row in records], "final": final,
                        "errors": result["errors"]})
    return {"scope": "L4-L7 Acting-first public-input tasks and in-memory end state", "evidence_class": "deterministic_software_control",
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
            parser.error("Advanced Planning witness evidence differs")
    else:
        with EVIDENCE.open("xb") as output:
            output.write(raw)
    print(result["counts"])


if __name__ == "__main__":
    main()
