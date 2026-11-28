"""Execute a public-input TC-V2 quote witness and explicit mutations."""

from argparse import ArgumentParser
from collections import Counter
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from benchmarks.atlas_validity.quote_witness import read_current_quote
from benchmarks.tool_calling_v2.evaluator import Call
from benchmarks.tool_calling_v2.holdout.dataset import load
from benchmarks.tool_calling_v2.holdout.host import Session, wire_tools
from benchmarks.tool_calling_v2.holdout.oracle import score
from benchmarks.tool_calling_v2.oracle import decode_object, equal
from business_tools import encode_state
from business_tools.store import BUSINESS_TABLES


def witness(case, database):
    session = Session(case, database)
    calls = []

    def execute(tool, args):
        call_id = f"quote-read-{len(calls) + 1}"
        encoded = encode_state(args)
        observation = session.execute(call_id, tool, encoded)
        calls.append(Call(len(calls), call_id, tool, encoded, observation))
        return observation

    facts = read_current_quote(case["prompt"], wire_tools(case), execute)
    product = decode_object(calls[0].arguments_raw)["item_id"]
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as connection:
        raw, = connection.execute("SELECT body FROM products WHERE id = ?", (product,)).fetchone()
    row = decode_object(raw)
    observed_state = session.store.snapshot()
    business_tables = (*BUSINESS_TABLES, "approval_records")
    unchanged = all(equal(observed_state[table], session.before[table]) for table in business_tables)
    independent_pass = unchanged and equal(facts, {"rate": row["quoted_rate"], "currency": row["rate_currency"]})
    strict = {
        "valid": score(case, calls, encode_state(facts), session)["status"],
        "reordered_fields": score(case, calls, encode_state(dict(reversed(list(facts.items())))), session)["status"],
        "fenced_json": score(case, calls, "```json\n" + encode_state(facts) + "\n```", session)["status"],
        "wrong_rate": score(case, calls, encode_state({**facts, "rate": facts["rate"] + 1}), session)["status"],
        "extra_field": score(case, calls, encode_state({**facts, "item_id": product}), session)["status"],
        "missing_action": score(case, [], encode_state(facts), session)["status"],
        "wrong_tool": score(case, [Call(0, calls[0].call_id, "read_bin", calls[0].arguments_raw, calls[0].result)],
                            encode_state(facts), session)["status"],
        "wrong_argument": score(case, [Call(0, calls[0].call_id, "read_item",
                                            encode_state({"item_id": "CAT-OTHER"}), calls[0].result)],
                                encode_state(facts), session)["status"],
    }
    execute("read_item", {"item_id": product})
    strict["duplicate_action"] = score(case, calls, encode_state(facts), session)["status"]
    expected = dict.fromkeys(strict, "FAIL")
    expected.update(valid="PASS", reordered_fields="PASS")
    if not independent_pass or strict != expected:
        raise ValueError(f"quote witness or mutations disagree for {case['id']}")
    return {"case_id": case["id"], "language": case["language"], "witness": "PASS",
            "independent_business_facts_and_unmodified_state": "PASS", "strict": strict}


def execute():
    cases, manifest = load("holdout")
    selected = [case for case in cases if case["category"] == "tool_result_round_trip"]
    with TemporaryDirectory() as directory:
        records = [witness(case, Path(directory).resolve() / (case["id"] + ".sqlite")) for case in selected]
    return {"evidence_class": "deterministic_software_control", "scope": "TC-V2 holdout price_roundtrip only",
            "dataset_sha256": manifest["split"]["holdout"]["sha256"], "count_by_language": dict(
                Counter(row["language"] for row in records)), "cases": records}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = execute()
    data = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    if args.check:
        if args.output.read_bytes() != data:
            parser.error("quote control evidence differs")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("xb") as output:
            output.write(data)
    print(f"{len(result['cases'])} public-input quote witnesses and mutations passed")


if __name__ == "__main__":
    main()
