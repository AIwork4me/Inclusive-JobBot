"""Run JOB-V1 public-input witnesses and check the actual SQLite handoff."""

from argparse import ArgumentParser
from collections import Counter
from contextlib import closing
import gzip
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from benchmarks.atlas_validity.job_witness import solve
from benchmarks.job_productivity_v1.holdout.dataset import load
from benchmarks.job_productivity_v1.holdout.model_arms import Session
from benchmarks.job_productivity_v1.holdout.oracle import evaluate
from benchmarks.tool_calling_v2.oracle import decode_object, equal
from business_tools import BusinessStore, encode_state
from business_tools.store import BUSINESS_TABLES
from model_gateway import Proposal

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "evidence/IJ072/benchmark_validity/job-witness.json.gz"


def execute_case(case, database):
    store = BusinessStore(database, initial=case.world["state"])
    session = Session(case, store, "B")
    before = store.snapshot()
    calls = []

    def execute(tool, args):
        proposal = Proposal(f"witness-{len(calls) + 1}", tool, encode_state(args))
        observation = session.execute(proposal)
        calls.append({"tool": tool, "arguments": proposal.arguments_raw, "observation": encode_state(observation)})
        return observation

    updates = case.task["followups"]
    try:
        answer = solve(case.input_initial(), [event["text"] for event in updates], session.tools(), execute)
    except (TypeError, KeyError, ValueError) as error:
        return {"case_id": case.plan["case_id"], "status": "FAIL", "witness_error": str(error), "calls": calls}
    final_state = store.snapshot()
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as connection:
        direct = {table: {key: decode_object(raw) for key, raw in connection.execute(f"SELECT id, body FROM {table}")}
                  for table in BUSINESS_TABLES}
    draft_calls = [call for call in calls if call["tool"] == "stage_delivery_review"
                   and "error" not in decode_object(call["observation"])]
    expected = {table: before[table] for table in BUSINESS_TABLES}
    if draft_calls:
        expected["review_drafts"] = {case.plan["case_id"]: decode_object(draft_calls[0]["observation"])}
    state_ok = equal(expected, direct) and len(draft_calls) <= 1
    reads = [(table, key, value) for (table, key), value in session.observed.items()]
    followup_ids = [event["id"] for event in updates]
    current = {"answer": answer, "reads": reads, "before": before, "after": final_state,
               "delivered_followups": followup_ids}
    result = evaluate(case, **current)
    changes = {"wrong_business_answer": {"answer": {}}}
    if followup_ids:
        changes["omitted_trusted_update"] = {"delivered_followups": []}
    if draft_calls:
        changes["missing_persisted_draft"] = {"after": {**final_state, "review_drafts": {}}}
    mutations = {name: evaluate(case, **(current | change))["status"] for name, change in changes.items()}
    if set(mutations.values()) != {"FAIL"}:
        raise ValueError("JOB-V1 scoring accepted an incorrect witness variant")
    return {"case_id": case.plan["case_id"], "status": result["status"] if state_ok else "FAIL",
            "state_check": "PASS" if state_ok else "FAIL", "calls": calls, "answer": answer, "mutations": mutations,
            "completed": result["completed"] and state_ok, "findings": result["findings"]}


def execute():
    frozen = load()
    with TemporaryDirectory() as folder:
        directory = Path(folder).resolve()
        rows = [execute_case(case, directory / (name + ".sqlite")) for name, case in frozen.cases.items()]
    return {"scope": "JOB-V1 600 frozen primary cases using Arm B's public tool contract",
            "evidence_class": "deterministic_software_control", "freeze_sha256": frozen.manifest["freeze_sha256"],
            "counts": dict(Counter(row["status"] for row in rows)), "trials": rows}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = execute()
    raw = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    if args.check:
        if gzip.decompress(OUTPUT.read_bytes()) != raw:
            parser.error("JOB-V1 witness evidence differs")
    else:
        with OUTPUT.open("xb") as output:
            output.write(gzip.compress(raw, mtime=0))
    print(result["counts"])


if __name__ == "__main__":
    main()
