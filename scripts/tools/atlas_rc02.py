"""Reconcile archived TC-V2 quote failures with checked source trajectories."""

from argparse import ArgumentParser
from collections import Counter
from decimal import Decimal
import gzip
import json
from pathlib import Path

from benchmarks.atlas_validity.evaluation import FENCE, parsed
from benchmarks.competitive_slm.tc_v2_batch import legacy, read_checkpoint
from benchmarks.tool_calling_v2.holdout.dataset import load
from benchmarks.tool_calling_v2.oracle import equal
from business_tools import encode_state

ROOT = Path(__file__).resolve().parents[2]
CATEGORY = "tool_result_round_trip"


def quote_diagnostics(case_id, row, expected):
    calls = row["calls"]
    captures = row["requests"]
    reads = [call for call in calls if call["name"] == "read_item"
             and equal(expected, {"rate": call["result"].get("quoted_rate"),
                                  "currency": call["result"].get("rate_currency")})]
    observed = False
    rendered = False
    for call in reads:
        content = encode_state(call["result"])
        for capture in captures[call["turn"] + 1:]:
            messages = capture["request"]["messages"]
            if any(message["role"] == "tool" and message["tool_call_id"] == call["call_id"]
                   and message["content"] == content for message in messages):
                observed = True
                prompt = json.loads(capture["render_response"], parse_float=Decimal)["prompt"]
                actual = call["result"]
                rendered |= all(str(actual[key]) in prompt and key in prompt
                                for key in ("quoted_rate", "rate_currency"))
    raw = row["final"]
    fence = FENCE.fullmatch(raw)
    answer = parsed(fence["body"] if fence else raw)
    facts_correct = answer is not None and all(equal(value, answer.get(key)) for key, value in expected.items())
    exact_fields = answer is not None and answer.keys() == expected.keys()
    codes = [finding["code"] for finding in row["findings"]]
    raw_text = bytes.fromhex(captures[-1]["source_generation"]["pre_parser_bytes_hex"]).decode("utf-8", "replace")
    return {
        "case_id": case_id,
        "correct_tool_result": bool(reads),
        "correct_tool_result_in_later_request": observed,
        "correct_tool_result_values_in_rendered_prompt": rendered,
        "completed": row["completed"],
        "native_parser_rejected": row["native_parser_rejected"],
        "source_context_truncated": any(q["source_generation"]["truncated"] for q in captures),
        "correct_requested_facts_in_final_object": facts_correct,
        "correct_requested_facts_with_extra_fields": facts_correct and not exact_fields,
        "correct_requested_facts_in_fenced_object": facts_correct and bool(fence),
        "fenced_answer_present_in_pre_parser_output": bool(fence) and raw.strip() in raw_text,
        "strict_tool_workflow": row["strict_sop_status"] == "PASS",
        "business_state": row["business_state_status"],
        "fence_only_counterfactual": facts_correct and exact_fields and bool(fence)
                                     and codes == ["F12_FINAL_ANSWER_ERROR"],
        "finding_codes": codes,
        "terminal_completion_id": captures[-1]["source_generation"]["completion_id"],
    }


def reconcile(raw_root):
    cases, _ = load("holdout")
    cases = [case for case in cases if case["category"] == CATEGORY]
    report = {"scope": "retrospective diagnostic of first TC-V2 price_roundtrip trials", "candidates": {}}
    for candidate in "BDFG":
        source = raw_root / f"ij07-competitive-full-{candidate}"
        archive = ROOT / "evidence/IJ071/legacy_competitive" / candidate
        identity = json.loads((archive / "archive.json").read_bytes())
        run_file = source / "run.json"
        if legacy.sha256_of(run_file) != identity["source_run_sha256"]:
            raise ValueError(f"source run differs from archived identity for candidate {candidate}")
        source_commit = json.loads(run_file.read_bytes())["configuration"]["git"]["commit"]
        trials_file = archive / "trials.jsonl.gz"
        if legacy.sha256_of(trials_file) != identity["files"][trials_file.name]["gzip_sha256"]:
            raise ValueError(f"archive changed for candidate {candidate}")
        archived = {row["key"]: row for row in map(json.loads, gzip.decompress(trials_file.read_bytes()).splitlines())}
        rows = []
        for case in cases:
            key = f"first--{case['id']}"
            trial = archived[key]
            trajectory = source / "trajectories" / f"{key}.json"
            if legacy.sha256_of(trajectory) != trial["proof"]["trajectory_sha256"]:
                raise ValueError(f"trajectory differs from the archived proof: {candidate} {key}")
            row = read_checkpoint(trajectory)
            if (row["run_id"] != identity["run_id"] or row["key"] != key or row["trajectory_status"] != trial["status"]
                    or row["session"] != trial["proof"]["session"]
                    or row["database_sha256"] != trial["proof"]["sqlite_sha256"]
                    or row["source_capture_status"] != "PASS"):
                raise ValueError(f"unverified trajectory: {candidate} {key}")
            result = quote_diagnostics(case["id"], row, case["oracle"]["final"])
            if set(result["finding_codes"]) != set(trial["finding_codes"]):
                raise ValueError(f"historical verdict details changed: {candidate} {key}")
            rows.append({**result, "strict": trial["status"], "language": case["language"],
                         "trajectory_sha256": trial["proof"]["trajectory_sha256"], "key": key})
        counts = Counter()
        for row in rows:
            counts.update({key: value for key, value in row.items() if type(value) is bool})
            counts[row["strict"]] += 1
        report["candidates"][candidate] = {"run_id": identity["run_id"], "source_commit": source_commit, "count": len(rows),
                                            "counts": dict(counts), "trials": rows}
    return report


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("raw_root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = (json.dumps(reconcile(args.raw_root), indent=2, sort_keys=True) + "\n").encode()
    if args.check:
        if args.output.read_bytes() != data:
            parser.error("RC-02 diagnostic output differs")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("xb") as output:
            output.write(data)
    print("320 previously sealed first attempts checked")


if __name__ == "__main__":
    main()
