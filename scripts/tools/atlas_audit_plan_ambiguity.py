"""Locate identical public Planning contracts with different observed action paths."""

from argparse import ArgumentParser
from collections import Counter, defaultdict
from copy import deepcopy
import gzip
from hashlib import sha256
import json
from pathlib import Path

from benchmarks.agentic_planning_v1.contract import request
from benchmarks.agentic_planning_v1.freeze import FROZEN
from benchmarks.agentic_planning_v1.oracle import initial_plan
from benchmarks.agentic_planning_v1.run import load_jsonl
from benchmarks.atlas_validity.planning_intent_witness import REFERENCE


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "evidence/IJ072/benchmark_validity"
WITNESSES = EVIDENCE / "planning-plan-controls.json.gz"
OUTPUT = EVIDENCE / "planning-public-ambiguity.json"
PRECONDITIONS = EVIDENCE / "planning-precondition-controls.json"


def signature(value):
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return sha256(REFERENCE.sub("<subject>", raw).encode("utf-8")).hexdigest()


def build():
    witness = json.loads(gzip.decompress(WITNESSES.read_bytes()))
    cases = {row["case_id"]: row for row in load_jsonl(FROZEN / "datasets/holdout.jsonl")}
    groups = defaultdict(list)
    for trial in witness["trials"]:
        case = cases[trial["case_id"]]
        if case["level"] not in {"L4", "L7"}:
            continue
        wire = request(case, "P")
        key = (case["level"], case["language"], signature(wire), signature(trial["initial_plan"]))
        groups[key].append({"case_id": trial["case_id"], "strict": trial["status"],
                            "plan_errors": trial["plan_errors"], "action_budget": case["action_budget"],
                            "observed_tool_path": [row["tool"] for row in trial["calls"]]})
    examples = []
    for (level, language, contract, plan), rows in sorted(groups.items()):
        counts = Counter(row["strict"] for row in rows)
        paths = {tuple(row["observed_tool_path"]) for row in rows}
        if len(paths) <= 1 or not counts["FAIL"]:
            continue
        examples.append({"level": level, "language": language, "public_contract_sha256": contract,
                         "initial_plan_shape_sha256": plan, "observed_distinct_paths": len(paths),
                         "strict_results": dict(counts), "cases": rows})

    return {"scope": "frozen Plan-first L4 and L7 independent software witness audit",
            "dataset_sha256": witness["dataset_sha256"],
            "normalization": "Only the opaque subject identifier is substituted for public-contract and plan grouping.",
            "interpretation": "Public-equivalent tasks can require different actions after observations. Mixed strict "
                              "outcomes identify cases for review of the frozen plan gate and conditional syntax.",
            "candidate_cases": sum(len(rows) for rows in groups.values()),
            "groups_with_divergent_paths_and_failures": len(examples),
            "groups_with_both_strict_outcomes": sum(bool(group["strict_results"].get("PASS")) for group in examples),
            "cases_in_reported_groups": sum(len(group["cases"]) for group in examples), "groups": examples}


def audit_preconditions():
    witness_bytes = WITNESSES.read_bytes()
    witness = json.loads(gzip.decompress(witness_bytes))
    cases = {row["case_id"]: row for row in load_jsonl(FROZEN / "datasets/holdout.jsonl")}
    graphs = {row["case_id"]: row for row in load_jsonl(FROZEN / "task_graphs/holdout.jsonl")}
    trials = []
    for row in witness["trials"]:
        key = row["case_id"]
        plan = row["initial_plan"]
        if row["status"] != "PASS" or not plan["actions"]:
            continue
        baseline = initial_plan(cases[key], graphs[key], plan)
        if not (baseline["goal_understood"] and baseline["executable"]):
            raise ValueError(f"archived positive plan changed before mutation: {key}")
        changes = [("disable_first_action", 0, "Never execute this action.")]
        changes.extend(("require_denied_approval", index,
                        "Commit only after the external user explicitly declines approval for this draft.")
                       for index, action in enumerate(plan["actions"]) if action["tool"] == "commit")
        for mutation, index, condition in changes:
            revised = deepcopy(plan)
            action = revised["actions"][index]
            action["preconditions"] = [condition]
            verdict = initial_plan(cases[key], graphs[key], revised)
            trials.append({"case_id": key, "level": row["level"], "mutation": mutation,
                           "action_id": action["id"], "tool": action["tool"], "precondition": condition,
                           "status": "FAIL" if verdict["executable"] else "PASS",
                           "oracle_errors": verdict["errors"]})
    counts = defaultdict(Counter)
    for row in trials:
        counts[row["mutation"]][row["status"]] += 1
    return {"scope": "frozen initial plan evaluator, strict positive independent witnesses containing actions",
            "evidence_class": "deterministic_software_mutation", "dataset_sha256": witness["dataset_sha256"],
            "independent_witness_archive_sha256": sha256(witness_bytes).hexdigest(),
            "status_rule": "FAIL identifies a contradictory plan condition accepted by the frozen initial plan evaluator.",
            "counts": counts, "trials": trials}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--preconditions", action="store_true")
    args = parser.parse_args()
    result = audit_preconditions() if args.preconditions else build()
    output = PRECONDITIONS if args.preconditions else OUTPUT
    raw = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    if args.check:
        if output.read_bytes() != raw:
            parser.error("conditional Planning source audit differs")
    else:
        with output.open("xb") as stream:
            stream.write(raw)
    if args.preconditions:
        print(dict(result["counts"]))
    else:
        print(result["groups_with_divergent_paths_and_failures"], result["groups_with_both_strict_outcomes"],
              result["cases_in_reported_groups"])


if __name__ == "__main__":
    main()
