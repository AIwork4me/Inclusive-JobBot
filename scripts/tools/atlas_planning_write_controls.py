"""Challenge the frozen scorer and sandbox with synthetic Planning mutations."""

from argparse import ArgumentParser
from collections import Counter
import gzip
import json
from pathlib import Path

from benchmarks.agentic_planning_v1.freeze import FROZEN, verify
from benchmarks.agentic_planning_v1.oracle import score
from benchmarks.agentic_planning_v1.run import load_jsonl
from benchmarks.agentic_planning_v1.sandbox import SyntheticSandbox


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "evidence/IJ072/benchmark_validity"
WITNESSES = EVIDENCE / "planning-advanced-controls.json"
OUTPUT = EVIDENCE / "planning-advanced-mutations.json.gz"


def trace_mutations(records, final, state):
    changed_facts = {**final["facts"], "subject": "unknown-synthetic-reference"}
    variants = {
        "wrong_business_subject": {"final": {**final, "facts": changed_facts}},
        "correct_facts_with_fence": {"final": "```json\n" + json.dumps(final) + "\n```"},
    }
    for disposition, name in (("clarify", "unnecessary_clarification"), ("escalate", "unnecessary_escalation"),
                              ("completed", "false_success_claim")):
        if final["disposition"] != disposition:
            variants[name] = {"final": {**final, "disposition": disposition}}
    if any(state.values()):
        variants["missing_persisted_state"] = {"state": {"drafts": {}, "deliverables": {}}}
    if records:
        first, *remaining = records
        variants["missing_required_action"] = {"records": remaining}
        variants["wrong_tool"] = {"records": [{**first, "tool": "unknown_synthetic_tool"}, *remaining]}
        if "reference" in first["args"]:
            args = {**first["args"], "reference": "unknown-synthetic-reference"}
            variants["wrong_arguments"] = {"records": [{**first, "args": args}, *remaining]}
    if len(records) >= 2:
        variants["wrong_dependency"] = {"records": [records[1], records[0], *records[2:]]}
    for index, row in enumerate(records):
        before, after = records[:index], records[index + 1:]
        observed = row["observation"]
        code = observed["code"]
        if code != "ok" and "ignored_tool_exception" not in variants:
            variants["ignored_tool_exception"] = {"records": before + after}
        if observed.get("external_event", {}).get("revised_reference") is not None:
            variants["ignored_revised_reference"] = {"records": before + [row]}
        if row["tool"] == "stage" and code == "ok":
            variants["premature_stage_trace"] = {"records": [row, *before, *after]}
        if row["tool"] == "commit" and code == "ok":
            args = {**row["args"], "approval": "forged-synthetic-approval"}
            variants["untrusted_approval"] = {"records": [*before, {**row, "args": args}, *after]}
            variants["duplicate_commit_trace"] = {"records": [*before, row, row, *after]}
    return variants


def sandbox_safety(world, records):
    fresh = SyntheticSandbox(world)
    results = {}

    def rejected(name, sandbox, tool, args, expected):
        before = sandbox.snapshot()
        outcome = sandbox.invoke(tool, args)["code"]
        if outcome != expected or sandbox.snapshot() != before:
            raise ValueError(f"synthetic mutation was not safely rejected: {name}")
        results[name] = outcome

    sandbox = SyntheticSandbox(world)
    for row in records:
        tool, args, expected = row["tool"], row["args"], row["observation"]
        if tool == "stage" and expected["code"] == "ok":
            rejected("stage_before_audit", fresh, tool, args, "permission_denied")
        if tool == "commit" and expected["code"] == "ok":
            rejected("commit_before_approval", fresh, tool, args, "permission_denied")
            forged = {**args, "approval": "forged-synthetic-approval"}
            rejected("forged_approval", sandbox, tool, forged, "permission_denied")
        if sandbox.invoke(tool, args) != expected:
            raise ValueError("independent witness observation did not reproduce")
        if tool == "commit" and expected["code"] == "ok":
            rejected("duplicate_commit", sandbox, tool, args, "duplicate_mutation")
    return results


def run():
    manifest = verify(FROZEN)
    witnesses = json.loads(WITNESSES.read_bytes())
    dataset_sha = manifest["artifact_sha256"]["datasets/holdout.jsonl"]
    if witnesses["dataset_sha256"] != dataset_sha:
        raise ValueError("advanced witness dataset differs from the frozen manifest")
    cases = {row["case_id"]: row for row in load_jsonl(FROZEN / "datasets/holdout.jsonl")
             if row["level"] in {"L4", "L5", "L6", "L7"}}
    graphs = {row["case_id"]: row for row in load_jsonl(FROZEN / "task_graphs/holdout.jsonl")}
    ids = [row["case_id"] for row in witnesses["trials"]]
    if len(ids) != len(cases) or set(ids) != set(cases):
        raise ValueError("advanced witness roster differs from the frozen cohort")
    output, aggregate, denied = [], Counter(), Counter()
    for witness in witnesses["trials"]:
        key = witness["case_id"]
        graph, case = graphs[key], cases[key]
        sandbox = SyntheticSandbox(graph["world"])
        records = [{**row, "origin": "model", "trigger": "tool_feedback" if index else "user_request"}
                   for index, row in enumerate(witness["calls"])]
        for row in records:
            if sandbox.invoke(row["tool"], row["args"]) != row["observation"]:
                raise ValueError(f"tool observation differs from advanced witness: {key}")
        state, final = sandbox.snapshot(), witness["final"]
        observed = {"records": records, "state": state, "final": final}
        original = score(case, graph, track="A", **observed)
        if original["status"] != "PASS":
            raise ValueError(f"unmutated witness did not pass: {key}")
        variants = trace_mutations(records, final, state)
        statuses = {}
        for name, changed in variants.items():
            verdict = score(case, graph, track="A", **(observed | changed))
            statuses[name] = verdict["status"]
            aggregate[name, verdict["status"]] += 1
        guards = sandbox_safety(graph["world"], records)
        denied.update(guards.keys())
        output.append({"case_id": key, "level": case["level"], "language": case["language"],
                       "original": original["status"], "negative_trace_results": statuses, "sandbox_guards": guards})
    return {"scope": "400 frozen Planning L4-L7 Acting-first public-input witnesses",
            "evidence_class": "deterministic_software_mutation", "dataset_sha256": dataset_sha,
            "mutations": {name: {"rejected": aggregate[name, "FAIL"], "accepted": aggregate[name, "PASS"]}
                          for name in sorted({name for name, _ in aggregate})},
            "unchanged_state_guard_rejections": dict(denied), "trials": output}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = run()
    raw = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    if args.check:
        if gzip.decompress(OUTPUT.read_bytes()) != raw:
            parser.error("advanced mutation evidence differs")
    else:
        with OUTPUT.open("xb") as handle:
            handle.write(gzip.compress(raw, mtime=0))
    print(result["mutations"])
    print(result["unchanged_state_guard_rejections"])


if __name__ == "__main__":
    main()
