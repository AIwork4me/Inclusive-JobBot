"""Execute public-input MULTITOOL-V1 witnesses and independently read SQLite state."""

from argparse import ArgumentParser
from collections import Counter
from contextlib import closing
from dataclasses import replace
import gzip
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from benchmarks.atlas_validity.multitool_witness import solve
from benchmarks.multitool_v1.dataset import load_freeze
from benchmarks.multitool_v1.runtime import Scenario, score
from benchmarks.tool_calling_v2.evaluator import Call
from benchmarks.tool_calling_v2.oracle import decode_object, equal
from business_tools import encode_state

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "evidence/IJ072/benchmark_validity/multitool-witness.json.gz"


def execute_case(case, database):
    scenario = Scenario(case, database)
    before = scenario.snapshot()
    calls, events = [], []

    def execute(tool, args):
        turn = len(calls)
        call_id = f"witness-{turn + 1}"
        raw = encode_state(args)
        observed = scenario.call(call_id, tool, raw)
        calls.append(Call(turn, call_id, tool, raw, observed))
        return observed

    def take_messages():
        observed = scenario.take_events()
        events.extend((len(calls) - 1, key) for key, _ in observed)
        return [message for _, message in observed]

    final = solve(case.model_input(), execute, take_messages)
    after = scenario.snapshot()
    storage = "NOT_APPLICABLE"
    if before is not None:
        expected = {}
        if final.get("status") == "drafted":
            ref = final["draft_ref"]
            expected[ref] = {"review_ref": ref, "submitted": False, "reason": "route_review"}
            final = {"status": "drafted", "review_ref": ref}
        with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as db:
            drafts = {key: decode_object(value) for key, value in db.execute("SELECT id, body FROM review_drafts")}
        storage = "PASS" if equal(drafts, expected) else "FAIL"
    facts = encode_state(final)
    observations = {"before": before, "after": after, "delivered_events": events}
    result = score(case, calls, facts, **observations)
    mutations = {
        "missing_first_action": score(case, calls[1:], facts, **observations)["status"],
        "invalid_first_argument": score(case, [replace(calls[0], arguments_raw="{}"), *calls[1:]],
                                        facts, **observations)["status"],
        "wrong_final_facts": score(case, calls, "{}", **observations)["status"],
    }
    if events:
        mutations["missing_user_update"] = score(case, calls, facts, before=before, after=after)["status"]
    if set(mutations.values()) != {"FAIL"}:
        raise ValueError("MULTITOOL scoring accepted a critical mutation")
    return {"case_id": case.case_id, "status": result["status"], "sqlite_review_drafts": storage,
            "final": final, "events": events, "mutations": mutations,
            "calls": [{"tool": call.name, "arguments": call.arguments_raw, "observation": encode_state(call.result)}
                      for call in calls],
            "finding_codes": [finding["code"] for finding in result["findings"]]}


def execute():
    frozen = load_freeze()
    with TemporaryDirectory() as folder:
        rows = []
        for case in frozen.active.values():
            try:
                rows.append(execute_case(case, Path(folder).resolve() / (case.case_id + ".sqlite")))
            except (KeyError, ValueError) as error:
                raise ValueError(f"{case.case_id}: {error}") from error
    return {"scope": "MULTITOOL-V1 active frozen roster", "evidence_class": "deterministic_software_control",
            "freeze_sha256": frozen.manifest["freeze_sha256"], "counts": dict(Counter(row["status"] for row in rows)),
            "persisted_counts": dict(Counter(row["sqlite_review_drafts"] for row in rows)), "trials": rows}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = execute()
    raw = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    if args.check:
        if gzip.decompress(OUTPUT.read_bytes()) != raw:
            parser.error("MULTITOOL witness evidence differs")
    else:
        with OUTPUT.open("xb") as output:
            output.write(gzip.compress(raw, mtime=0))
    print(result["counts"], result["persisted_counts"])


if __name__ == "__main__":
    main()
