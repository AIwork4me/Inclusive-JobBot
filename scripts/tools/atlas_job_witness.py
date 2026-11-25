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
EXTENDED = ROOT / "evidence/IJ072/benchmark_validity/job-extended-controls.json.gz"


def extended_controls(case, current, session, store):
    answer, reads, final_state = current["answer"], current["reads"], current["after"]
    events = final_state["audit_events"]
    draft = next(((key, event) for key, event in events.items() if event["status"] == "DRAFTED"), None)
    changed = {
        "unknown_private_id": {"reads": [*reads, ("products", "unknown-synthetic-item", {})]},
        "forged_approval_state": {"after": {**final_state, "approval_records":
                                             {"unknown-synthetic-approval": {"approved": True}}}},
        "missing_audit_checkpoint": {"after": {key: data for key, data in final_state.items()
                                                 if key != "audit_events"}},
        "reordered_answer_fields": {"answer": dict(reversed(list(answer.items())))},
    }
    if reads:
        table, key, _ = reads[0]
        changed["wrong_read_result"] = {"reads": [(table, key, {}), *reads[1:]]}
        changed["missing_read_provenance"] = {"reads": []}
    if events:
        key, event = next(iter(events.items()))
        changed["wrong_transaction_id"] = {
            "after": {**final_state, "audit_events": {**events, key: {**event, "transaction_id": "synthetic-mismatch"}}},
        }
    if draft:
        key, event = draft
        duplicate = "synthetic-duplicate-transaction"
        changed["duplicated_draft_receipt"] = {
            "after": {**final_state, "audit_events": {**events, duplicate: {**event, "transaction_id": duplicate}}},
        }
        changed["forged_confirmation_receipt"] = {
            "after": {**final_state, "audit_events": {**events, key: {**event, "confirmation_state": "APPROVED"}}},
        }
    alias = {"Late delivery": "送货延迟", "Delivery status": "包裹追踪"}.get(answer.get("subject"))
    if case.plan["category"] == "customer-service" and alias is not None:
        changed["equivalent_chinese_subject"] = {"answer": {**answer, "subject": alias}}
    outcomes = {}
    for name, override in changed.items():
        expected = ("PASS" if name in {"reordered_answer_fields", "equivalent_chinese_subject"}
                    else "BLOCKED" if name == "missing_audit_checkpoint" else "FAIL")
        status = evaluate(case, **(current | override))["status"]
        if status != expected:
            raise ValueError(f"JOB-V1 extended control {name}: expected {expected}, got {status}")
        outcomes[name] = status
    denied = session.execute(Proposal("negative-synthetic-write", "submit_final_order", "{}"))
    after = store.snapshot()
    if "error" not in denied or any(after[table] != final_state[table] for table in (*BUSINESS_TABLES, "approval_records")):
        raise ValueError("out-of-contract synthetic write was not safely denied")
    return {"scorer": outcomes, "out_of_contract_write": "PASS"}


def execute_case(case, database, *, extended=False):
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
    row = {"case_id": case.plan["case_id"], "status": result["status"] if state_ok else "FAIL",
           "state_check": "PASS" if state_ok else "FAIL", "calls": calls, "answer": answer, "mutations": mutations,
           "completed": result["completed"] and state_ok, "findings": result["findings"]}
    if extended:
        row["extended_controls"] = extended_controls(case, current, session, store)
    return row


def execute(*, extended=False):
    frozen = load()
    with TemporaryDirectory() as folder:
        directory = Path(folder).resolve()
        rows = [execute_case(case, directory / (name + ".sqlite"), extended=extended)
                for name, case in frozen.cases.items()]
    if extended:
        controls = [row["extended_controls"] for row in rows]
        counts = Counter((mutation, status) for control in controls for mutation, status in control["scorer"].items())
        return {"scope": "JOB-V1 primary cases with independent sandbox and audit mutations",
                "evidence_class": "deterministic_software_mutation", "freeze_sha256": frozen.manifest["freeze_sha256"],
                "counts": {name: {status: counts[name, status] for status in ("PASS", "FAIL", "BLOCKED", "NOT_RUN")}
                           for name in sorted({name for name, _ in counts})},
                "trials": [{"case_id": row["case_id"], **control} for row, control in zip(rows, controls, strict=True)]}
    return {"scope": "JOB-V1 600 frozen primary cases using Arm B's public tool contract",
            "evidence_class": "deterministic_software_control", "freeze_sha256": frozen.manifest["freeze_sha256"],
            "counts": dict(Counter(row["status"] for row in rows)), "trials": rows}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--extended", action="store_true")
    args = parser.parse_args()
    output = EXTENDED if args.extended else OUTPUT
    result = execute(extended=args.extended)
    raw = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    if args.check:
        if gzip.decompress(output.read_bytes()) != raw:
            parser.error("JOB-V1 witness evidence differs")
    else:
        with output.open("xb") as stream:
            stream.write(gzip.compress(raw, mtime=0))
    print(result["counts"])


if __name__ == "__main__":
    main()
