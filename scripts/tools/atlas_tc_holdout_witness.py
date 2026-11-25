"""Verify TC-V2 holdout traces built from public requests and actual tool observations."""

from argparse import ArgumentParser
from collections import Counter
from contextlib import closing
from dataclasses import replace
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from benchmarks.atlas_validity.tc_holdout_witness import solve
from benchmarks.tool_calling_v2.evaluator import Call
from benchmarks.tool_calling_v2.holdout.dataset import load
from benchmarks.tool_calling_v2.holdout.host import Session, wire_tools
from benchmarks.tool_calling_v2.holdout.oracle import score
from benchmarks.tool_calling_v2.oracle import decode_object, equal
from business_tools import encode_state
from business_tools.store import BUSINESS_TABLES

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "evidence/IJ072/benchmark_validity/tc-holdout-witness.json"


def execute_case(case, database):
    session = Session(case, database)
    calls = []

    def execute(tool, args):
        call_id = f"witness-{len(calls) + 1}"
        raw = encode_state(args)
        observed = session.execute(call_id, tool, raw)
        calls.append(Call(len(calls), call_id, tool, raw, observed))
        return observed

    answer = solve(case["prompt"], wire_tools(case), execute)
    expected = {table: session.before[table] for table in BUSINESS_TABLES}
    if answer.get("status") == "committed":
        bin_id, reserve = answer["bin_id"], answer["reserve"]
        expected["inventory"] = {**expected["inventory"],
                                 bin_id: {**expected["inventory"][bin_id], "reserve": reserve}}
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as connection:
        observed = {table: {key: decode_object(raw) for key, raw in connection.execute(
            f"SELECT id, body FROM {table}"
        )} for table in BUSINESS_TABLES}
    final = encode_state(answer)
    strict = score(case, calls, final, session)
    mutations = {
        "missing_first_action": score(case, calls[1:], final, session)["status"],
        "invalid_first_argument": score(case, [replace(calls[0], arguments_raw="{}"), *calls[1:]], final, session)["status"],
        "wrong_final_facts": score(case, calls, "{}", session)["status"],
        "reordered_fields": score(case, calls, encode_state(dict(reversed(list(answer.items())))), session)["status"],
    }
    if (mutations["reordered_fields"] != "PASS"
            or any(value != "FAIL" for key, value in mutations.items() if key != "reordered_fields")):
        raise ValueError("TC-V2 scoring accepted a mutation or rejected equivalent field order")
    return {
        "case_id": case["id"], "language": case["language"], "category": case["category"],
        "status": strict["status"],
        "persisted_state": "PASS" if equal(expected, observed) else "FAIL",
        "calls": [{"tool": call.name, "arguments": call.arguments_raw, "observation": encode_state(call.result)}
                  for call in calls],
        "final": final,
        "mutations": mutations,
        "finding_codes": [finding["code"] for finding in strict["findings"]],
    }


def execute():
    cases, manifest = load("holdout")
    with TemporaryDirectory() as folder:
        rows = []
        for case in cases:
            try:
                rows.append(execute_case(case, Path(folder).resolve() / (case["id"] + ".sqlite")))
            except ValueError as error:
                raise ValueError(f"{case['id']}: {error}") from error
    return {"evidence_class": "deterministic_software_control",
            "scope": "complete TC-V2 holdout, public-input witnesses with the real synthetic gateway",
            "dataset_sha256": manifest["split"]["holdout"]["sha256"],
            "counts": dict(Counter(row["status"] for row in rows)),
            "persisted_counts": dict(Counter(row["persisted_state"] for row in rows)),
            "trials": rows}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = execute()
    raw = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    if args.check:
        if OUTPUT.read_bytes() != raw:
            parser.error("TC-V2 witness evidence differs")
    else:
        with OUTPUT.open("xb") as output:
            output.write(raw)
    print(result["counts"], result["persisted_counts"])


if __name__ == "__main__":
    main()
