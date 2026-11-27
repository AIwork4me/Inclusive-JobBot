"""Export a score-blind human review sample from frozen public inputs and observations."""

from argparse import ArgumentParser
import gzip
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from benchmarks.agentic_planning_v1.contract import request
from benchmarks.agentic_planning_v1.freeze import FROZEN
from benchmarks.agentic_planning_v1.run import load_jsonl
from benchmarks.job_productivity_v1.holdout.dataset import load as load_job
from benchmarks.job_productivity_v1.holdout.model_arms import Session
from benchmarks.multitool_v1.dataset import load_freeze as load_multitool
from benchmarks.tool_calling_v2.holdout.dataset import load as load_tc
from benchmarks.tool_calling_v2.holdout.host import wire_tools
from business_tools import BusinessStore


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "evidence/IJ072/benchmark_validity"
PACKET = EVIDENCE / "a1-blind-review-packet.json"
INDEX = EVIDENCE / "a1-blind-review-provenance.json"


def witnesses(filename):
    data = (EVIDENCE / filename).read_bytes()
    if filename.endswith(".gz"):
        data = gzip.decompress(data)
    return {row["case_id"]: row for row in json.loads(data)["trials"]}


def build():
    items, index = [], {}

    def add(suite, key, language, public, calls, response, **context):
        identifier = sha256(f"IJ072-blind-review/{suite}/{key}".encode()).hexdigest()[:12]
        trace = [{k: v for k, v in call.items() if k != "origin"} for call in calls]
        items.append({"review_id": identifier, "suite": suite, "language": language,
                      "public_input": public, "observed_calls": trace, "answer": response, **context})
        index[identifier] = {"suite": suite, "case_id": key}

    tc, _ = load_tc("holdout")
    tc_rows = witnesses("tc-holdout-witness.json")
    for category in ("error_recovery", "unauthorized_injection"):
        for language in ("en", "zh"):
            case = next(row for row in tc if row["category"] == category and row["language"] == language)
            row = tc_rows[case["id"]]
            add("TC-V2", case["id"], language, {"prompt": case["prompt"], "tools": wire_tools(case)},
                row["calls"], row["final"])

    multi = load_multitool().active
    multi_rows = witnesses("multitool-witness.json.gz")
    for language in ("en", "zh"):
        candidates = [case for case in multi.values() if case.oracle["language"] == language]
        updated = next(case for case in candidates if multi_rows[case.case_id]["events"])
        guarded = next(case for case in candidates if "create_hold_draft" in case.prompt["tools"]
                       and case.case_id != updated.case_id)
        for case in (updated, guarded):
            row = multi_rows[case.case_id]
            event = case.world["event"]
            updates = [{"after_call_index": turn, "text": event["text"]} for turn, _ in row["events"]]
            add("MULTITOOL-V1", case.case_id, language, case.model_input(), row["calls"], row["final"],
                trusted_user_updates=updates)

    planning = load_jsonl(FROZEN / "datasets/holdout.jsonl")
    plan_rows = witnesses("planning-plan-controls.json.gz")
    for level in ("L4", "L7"):
        for language in ("en", "zh"):
            for outcome in ("PASS", "FAIL"):
                case = next(row for row in planning if row["level"] == level and row["language"] == language
                            and plan_rows[row["case_id"]]["status"] == outcome)
                row = plan_rows[case["case_id"]]
                add("AGENTIC-PLAN-V1", case["case_id"], language, request(case, "P"),
                    row["calls"], row["final"], initial_plan=row["initial_plan"])

    jobs = load_job().cases
    job_rows = witnesses("job-witness.json.gz")
    with TemporaryDirectory() as folder:
        for language in ("en", "zh", "mixed"):
            candidates = [case for case in jobs.values() if case.task["language"] == language]
            updated = next(case for case in candidates if case.task["followups"])
            draft = next(case for case in candidates if case is not updated and any(
                call["tool"] == "stage_delivery_review" for call in job_rows[case.plan["case_id"]]["calls"]))
            for case in (updated, draft):
                key = case.plan["case_id"]
                row = job_rows[key]
                store = BusinessStore(Path(folder) / f"{key}.sqlite", initial=case.world["state"])
                public = {"request": case.input_initial(), "tools": Session(case, store, "B").tools()}
                add("JOB-V1", key, language, public, row["calls"], row["answer"],
                    trusted_user_updates=[update["text"] for update in case.task["followups"]])
    if len(items) != len(index):
        raise ValueError("review sample contains duplicate cases")
    return {"schema_version": 1, "human_review": "NOT_RUN",
            "items": sorted(items, key=lambda item: item["review_id"])}, index


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    packet, index = build()
    for path, result in ((PACKET, packet), (INDEX, index)):
        raw = (json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
        if args.check:
            if path.read_bytes() != raw:
                parser.error(f"{path.name} differs")
        else:
            with path.open("xb") as stream:
                stream.write(raw)
    print(f"Prepared {len(index)} blinded human review items")


if __name__ == "__main__":
    main()
