"""Replay the reference gate on unchanged first-turn Vulkan planning proposals."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from benchmarks.agentic_planning_v1.freeze import FROZEN, verify
from benchmarks.agentic_planning_v1.runner import Boundary
from model_gateway.openai_protocol import decode_completion


ORIGINAL = re.compile(r"\bREF-\d+-\d+\b")
REJECTION = "reference was unavailable when proposed"


def decision(boundary, calls, budget):
    try:
        boundary.validate(calls, budget)
    except ValueError as error:
        return {"status": "FAIL", "detail": str(error)}
    return {"status": "PASS"}


def compare(source, levels):
    verify(FROZEN)
    run_file = (source / "run.json").read_bytes()
    run = json.loads(run_file)
    public = {case["case_id"]: case for line in (FROZEN / "datasets/holdout.jsonl").read_bytes().splitlines()
              for case in [json.loads(line)]}
    trials = []
    for path in sorted((source / "cases").glob("*-A-01.json")):
        terminal = json.loads(path.read_bytes())
        case = public[terminal["case_id"]]
        if case["level"] not in levels or not any(
            row.get("turn") == 0 and row.get("code") == "PROPOSAL_REJECTED" and row.get("detail") == REJECTION
            for row in terminal["findings"]
        ):
            continue
        journal = (source / terminal["journal"]).read_bytes()
        if hashlib.sha256(journal).hexdigest() != terminal["journal_sha256"]:
            raise ValueError("planning journal digest differs from terminal record")
        readings = [json.loads(line) for line in journal.splitlines()]
        wire = next(row["wire"] for row in readings if row["kind"] == "capture" and row["turn"] == 0)
        reply = wire["raw_response"].encode()
        calls = decode_completion(reply).calls
        old = Boundary(case)
        old.references = set(ORIGINAL.findall(case["prompt"]))
        before = decision(old, calls, case["action_budget"])
        if before != {"status": "FAIL", "detail": REJECTION}:
            raise ValueError("original planning reference gate failure did not reproduce")
        after = decision(Boundary(case), calls, case["action_budget"])
        generation = wire["source_generation"]
        trials.append({
            "case_id": case["case_id"], "level": case["level"], "language": case["language"],
            "original_trial_status": terminal["status"], "case_checkpoint_sha256": terminal["artifact_sha256"],
            "journal_sha256": terminal["journal_sha256"], "wire_response_sha256": hashlib.sha256(reply).hexdigest(),
            "prompt": case["prompt"], "exposed_tools": case["tools"],
            "calls": [{"id": call.call_id, "name": call.name, "arguments": call.arguments_raw} for call in calls],
            "source_generation": {key: generation[key] for key in ("completion_id", "pre_parser_bytes_hex", "sampled_token_ids")},
            "before": before, "after": after,
        })
    return {
        "run_id": run["run_id"], "run_configuration_sha256": run["fingerprint"], "levels": levels,
        "scope": "closed reference-gate replays of first-turn Acting-first failures with unchanged wire proposals",
        "terminal_result_changes": 0, "tools_executed": 0, "compared": len(trials),
        "after_counts": dict(Counter(row["after"]["status"] for row in trials)), "trials": trials,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--level", action="append", required=True)
    args = parser.parse_args()
    report = compare(args.source, args.level)
    args.output.write_bytes((json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode())
    print(report["compared"], report["after_counts"])


if __name__ == "__main__":
    main()
