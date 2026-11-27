"""Compare public-input L0 intent decisions against the frozen planning oracle."""

from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path

from benchmarks.agentic_planning_v1.freeze import FROZEN, verify
from benchmarks.agentic_planning_v1.oracle import score
from benchmarks.agentic_planning_v1.run import load_jsonl
from benchmarks.atlas_validity.planning_intent_witness import understand

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "evidence/IJ072/benchmark_validity/planning-intent-controls.json"


def execute():
    manifest = verify(FROZEN)
    public = load_jsonl(FROZEN / "datasets/holdout.jsonl")
    selected = [case for case in public if case["level"] == "L0"]
    witnesses = {case["case_id"]: understand(case["prompt"]) for case in selected}
    graphs = {row["case_id"]: row for row in load_jsonl(FROZEN / "task_graphs/holdout.jsonl")}
    trials = []
    for case in selected:
        case_id = case["case_id"]
        graph = graphs[case_id]
        final = witnesses[case_id]
        if case["tools"] or case["action_budget"]:
            raise ValueError(f"the software control requires zero permitted actions: {case_id}")
        empty_state = {"drafts": {}, "deliverables": {}}
        facts = final["facts"]
        wrong_disposition = "understood" if final["disposition"] == "clarify" else "clarify"
        mutated = {
            "wrong_subject": {**final, "facts": {**facts, "subject": "REF-0-99999"}},
            "wrong_disposition": {**final, "disposition": wrong_disposition},
        }
        target = "needs_tool" if "needs_tool" in facts else "reason"
        mutated["wrong_fact"] = {**final, "facts": {**facts, target: not facts[target] if target == "needs_tool"
                                                 else "delivery_scope_required"}}
        out = score(case, graph, [], empty_state, final, track="A")
        mutations = {name: score(case, graph, [], empty_state, payload, track="A")["status"]
                     for name, payload in mutated.items()}
        if set(mutations.values()) != {"FAIL"}:
            raise ValueError(f"L0 mutation accepted: {case_id}")
        trials.append({"case_id": case_id, "language": case["language"], "witness": final,
                       "oracle_status": out["status"], "mutations": mutations,
                       "differences": {name: value for name, value in graph["final"]["facts"].items()
                                       if facts.get(name) != value}})
    return {
        "evidence_class": "deterministic_software_control",
        "scope": "all L0 cases, Acting-first zero-action intent only",
        "dataset_sha256": manifest["artifact_sha256"]["datasets/holdout.jsonl"],
        "counts": dict(Counter(row["oracle_status"] for row in trials)),
        "trials": trials,
    }


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = execute()
    raw = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    if args.check:
        if EVIDENCE.read_bytes() != raw:
            parser.error("L0 public intent results differ")
    else:
        with EVIDENCE.open("xb") as handle:
            handle.write(raw)
    print(result["counts"])


if __name__ == "__main__":
    main()
