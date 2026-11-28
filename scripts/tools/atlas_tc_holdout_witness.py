"""Verify TC-V2 holdout traces built from public requests and actual tool observations."""

from argparse import ArgumentParser
from collections import Counter
from contextlib import closing
from dataclasses import replace
import gzip
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from benchmarks.atlas_validity.tc_holdout_witness import solve
from benchmarks.tool_calling_v2.evaluator import Call
from benchmarks.tool_calling_v2.holdout.dataset import load
from benchmarks.tool_calling_v2.holdout.host import Session, TOOLS, wire_tools
from benchmarks.tool_calling_v2.holdout.oracle import score
from benchmarks.tool_calling_v2.oracle import decode_object, equal
from business_tools import encode_state
from business_tools.store import BUSINESS_TABLES

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "evidence/IJ072/benchmark_validity/tc-holdout-witness.json"
EXTENDED = ROOT / "evidence/IJ072/benchmark_validity/tc-holdout-extended-controls.json.gz"


def extended_controls(case, database, session, calls, final):
    first, *later = calls
    arguments = decode_object(first.arguments_raw)
    resource = TOOLS[first.name].resource_key
    unknown = encode_state({**arguments, resource: "UNSEEN-SYNTHETIC-RECORD"})
    variants = {
        "unavailable_tool": ([replace(first, name="unknown_synthetic_tool"), *later], final),
        "unseen_business_id": ([replace(first, arguments_raw=unknown), *later], final),
    }
    commit = next((call for call in calls if call.result.get("status") == "committed"), None)
    if commit is None:
        answer = {**decode_object(final), "change_applied": True}
        variants["false_success_claim"] = (calls, encode_state(answer))
    else:
        variants["duplicated_commit_receipt"] = ([*calls, commit], final)
    outcomes = {name: score(case, trace, answer, session)["status"]
                for name, (trace, answer) in variants.items()}
    if set(outcomes.values()) != {"FAIL"}:
        raise ValueError("TC-V2 accepted an unauthorized or false trace mutation")
    state = session.store.snapshot()
    invalid = session.execute("extended-unknown-reference", first.name, unknown)
    protected = (*BUSINESS_TABLES, "approval_records")
    if "error" not in invalid or any(session.store.snapshot()[table] != state[table] for table in protected):
        raise ValueError("an unseen identifier was accepted")
    guards = {"unseen_id_denied": "PASS"}
    if commit is not None:
        unsigned = Session({**case, "approval": None}, database.with_name(database.stem + "-unsigned.sqlite"))
        denied = unsigned.execute("extended-unsigned-write", commit.name, commit.arguments_raw)
        if "error" not in denied or any(unsigned.store.snapshot()[table] != unsigned.before[table] for table in protected):
            raise ValueError("an unsigned write changed state")
        session.execute("extended-duplicate-write", commit.name, commit.arguments_raw)
        if any(session.store.snapshot()[table] != state[table] for table in protected):
            raise ValueError("a repeated approved write changed state")
        guards.update(unsigned_write_denied="PASS", duplicate_effect_prevented="PASS")
    return {"scorer": outcomes, "sandbox": guards}


def execute_case(case, database, *, extended=False):
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
    row = {
        "case_id": case["id"], "language": case["language"], "category": case["category"],
        "status": strict["status"],
        "persisted_state": "PASS" if equal(expected, observed) else "FAIL",
        "calls": [{"tool": call.name, "arguments": call.arguments_raw, "observation": encode_state(call.result)}
                  for call in calls],
        "final": final,
        "mutations": mutations,
        "finding_codes": [finding["code"] for finding in strict["findings"]],
    }
    if extended:
        row["extended_controls"] = extended_controls(case, database, session, calls, final)
    return row


def execute(*, extended=False):
    cases, manifest = load("holdout")
    with TemporaryDirectory() as folder:
        rows = []
        for case in cases:
            try:
                rows.append(execute_case(case, Path(folder).resolve() / (case["id"] + ".sqlite"), extended=extended))
            except ValueError as error:
                raise ValueError(f"{case['id']}: {error}") from error
    if extended:
        controls = [{"case_id": row["case_id"], **row["extended_controls"]} for row in rows]
        return {"scope": "TC-V2 holdout authorization, identifier and duplicate write controls",
                "evidence_class": "deterministic_software_mutation",
                "dataset_sha256": manifest["split"]["holdout"]["sha256"],
                "rejected_scorer_mutations": dict(Counter(key for row in controls for key in row["scorer"])),
                "sandbox_guard_passes": dict(Counter(key for row in controls for key in row["sandbox"])),
                "trials": controls}
    return {"evidence_class": "deterministic_software_control",
            "scope": "complete TC-V2 holdout, public-input witnesses with the real synthetic gateway",
            "dataset_sha256": manifest["split"]["holdout"]["sha256"],
            "counts": dict(Counter(row["status"] for row in rows)),
            "persisted_counts": dict(Counter(row["persisted_state"] for row in rows)),
            "trials": rows}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--extended", action="store_true")
    args = parser.parse_args()
    result = execute(extended=args.extended)
    raw = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    output = EXTENDED if args.extended else OUTPUT
    if args.check:
        actual = output.read_bytes()
        if (gzip.decompress(actual) if args.extended else actual) != raw:
            parser.error("TC-V2 witness evidence differs")
    else:
        with output.open("xb") as stream:
            stream.write(gzip.compress(raw, mtime=0) if args.extended else raw)
    if args.extended:
        print(result["rejected_scorer_mutations"], result["sandbox_guard_passes"])
    else:
        print(result["counts"], result["persisted_counts"])


if __name__ == "__main__":
    main()
