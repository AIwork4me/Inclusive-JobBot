"""Paired single-variable Radeon diagnostics for the 131 original Q1 truncations."""
import argparse
from collections import Counter
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path
import time

from benchmarks.tool_calling_v2.oracle import decode_object
from .archive import digest, export
from .controller import DEFAULT, add, connect, gpu_lock, quarantine_unsealed, work
from .gold import iter_gold
from .history import lines
from .local_judge import check
from .meta_evaluation import snapshot
from .q2_closure import wall_summary
from .qualification import request_for, require_freeze
from .runtime import ROOT, fingerprint, write_json

COLLECTION = "gold-development-truncation-v1"
ARMS = ("baseline", "token_budget", "output_contract")
ROSTER = ROOT / "evidence/IJ073/aeve/q1_root_cause_ledger.jsonl.gz"
AUDIT = ROSTER.with_name("q1_source_audit.json")
FREEZE = Path(__file__).with_name("truncation_freeze.json")
ALIASES = {"v": "verdict", "e": "evidence_refs", "r": "reason_summary"}


@lru_cache(maxsize=1)
def roster():
    audit = json.loads(AUDIT.read_bytes())
    if digest(ROSTER) != audit["ledger_sha256"]:
        raise ValueError("unverified Q1 truncation inventory")
    cases = {case["case_id"]: case for case in iter_gold("qualification")}
    jobs = []
    protocol = require_freeze()
    for row in lines(ROSTER):
        if "judge_output_truncation" not in row["classification"]:
            continue
        candidate, case_id = row["judge"], row["case_id"]
        case = cases[case_id]
        role, original = request_for(case, candidate)
        identity = ["gold-qualification", case_id, candidate, case["dimension"], role,
                    {**original, "qualification_freeze": protocol}]
        if fingerprint(identity) != row["job"] or case["packet_sha256"] != row["packet_sha256"]:
            raise ValueError("truncation does not match its frozen source case")
        jobs.append({**row, "case": case, "role": role, "original": original})
    if len(jobs) != 131 or len({row["job"] for row in jobs}) != len(jobs):
        raise ValueError("truncation inventory differs from frozen Q1")
    return sorted(jobs, key=lambda row: (row["judge"], row["case_id"]))


def spec_for(item, arm):
    spec = deepcopy(item["original"])
    if arm == "token_budget":
        spec["body"]["max_tokens"] = 320
    elif arm == "output_contract":
        schema = spec["body"]["response_format"]["json_schema"]["schema"]
        props = schema["properties"]
        schema["properties"] = {key: props[original] for key, original in ALIASES.items()}
        schema["required"] = list(ALIASES)
    elif arm != "baseline":
        raise ValueError("unknown truncation arm")
    return {**spec, "arm": arm, "source_job": item["job"]}


def grade(spec, raw):
    if spec["arm"] == "output_contract":
        parsed = decode_object(raw)
        if set(parsed) != set(ALIASES):
            raise ValueError("invalid compact output contract")
        raw = json.dumps({target: parsed[key] for key, target in ALIASES.items()})
    return check(spec["packet"], raw)


def freeze():
    rows = roster()
    return {"version": COLLECTION, "scope": "diagnostic replay of original truncations",
            "required": len(rows) * len(ARMS), "source_ledger_sha256": digest(ROSTER),
            "source_sha256": digest(Path(__file__)), "arms": list(ARMS),
            "candidate_counts": dict(Counter(row["judge"] for row in rows)),
            "roster_sha256": fingerprint([spec_for(row, arm) for row in rows for arm in ARMS])}


def expected(plan):
    return {(row["judge"], f"{row['case_id']}/{arm}"):
            (row, {**spec_for(row, arm), "development_freeze": fingerprint(plan)})
            for row in roster() for arm in plan["arms"]}


def report(archive, plan):
    planned = expected(plan)
    results = {}
    with snapshot(archive) as (view, hashes):
        manifests = {}
        for stamp in sorted((view / "sessions").glob("*/manifest.json")):
            outcomes = json.loads(stamp.with_name("outcomes.json").read_bytes())
            if not any(row["collection"] == COLLECTION for row in outcomes):
                continue
            manifests[stamp.parent.name] = hashes[stamp.parent.name]
            for row in lines(stamp.with_name("captures.jsonl.gz")):
                if row["collection"] != COLLECTION:
                    continue
                key = row["candidate"], row["item"]
                original, spec = planned[key]
                if key in results or spec != row["spec"]:
                    raise ValueError("sealed truncation assessment differs from the frozen request")
                capture = row["capture"]
                try:
                    response = json.loads(capture["raw_response"] or "{}")
                except ValueError:
                    response = {}
                choice = (response.get("choices") or [{}])[0]
                finish_reason = choice.get("finish_reason")
                answer = None
                if row["transport"] == "PASS":
                    try:
                        answer = grade(spec, choice["message"]["content"])
                    except (ValueError, TypeError, KeyError):
                        pass
                if (answer != row["evaluation"]
                        and (answer is not None or "verdict" in row["evaluation"])):
                    raise ValueError("archived truncation score does not replay")
                predicted = answer["verdict"] if answer else "INVALID"
                expected_label = original["case"]["expected"]
                results[key] = {"candidate": key[0], "case_id": original["case_id"], "source_job": original["job"],
                                "run": row["run"], "job": row["job"], "arm": spec["arm"], "expected": expected_label,
                                "prediction": predicted, "valid_decision": predicted in {"PASS", "FAIL"},
                                "correct": predicted == expected_label, "truncated": finish_reason == "length",
                                "transport": row["transport"], "http_status": capture["http_status"],
                                "finish_reason": finish_reason, "wall_ms": capture["wall_ms"],
                                "usage": response.get("usage"), "timings": response.get("timings"),
                                "citations": answer["evidence_refs"] if answer else None}
    rows = [results[key] for key in sorted(results)]
    arms = {}
    for arm in plan["arms"]:
        group = [row for row in rows if row["arm"] == arm]
        arms[arm] = {"required": len(roster()), "recorded": len(group),
                     **{metric: sum(row[metric] for row in group) for metric in ("valid_decision", "correct", "truncated")},
                     "wall": wall_summary([row["wall_ms"] for row in group])}
    base = {row["source_job"]: row for row in rows if row["arm"] == "baseline"}
    for arm in plan["arms"][1:]:
        pairs = [(base[row["source_job"]], row) for row in rows
                 if row["arm"] == arm and row["source_job"] in base]
        arms[arm]["paired"] = {
            "count": len(pairs),
            "newly_valid": sum(not left["valid_decision"] and right["valid_decision"] for left, right in pairs),
            "lost_validity": sum(left["valid_decision"] and not right["valid_decision"] for left, right in pairs),
            "newly_correct": sum(not left["correct"] and right["correct"] for left, right in pairs),
            "lost_correctness": sum(left["correct"] and not right["correct"] for left, right in pairs),
            "truncations_prevented": sum(left["truncated"] and not right["truncated"] for left, right in pairs),
            "truncations_introduced": sum(not left["truncated"] and right["truncated"] for left, right in pairs),
        }
    return {"freeze": plan, "status": "PASS" if len(rows) == plan["required"] else "NOT_RUN",
            "formal_qualification": "NOT_RUN", "recorded": len(rows), "arms": arms,
            "manifests": manifests, "cases": rows}


def execute(state, assets, archive, port, plan):
    db = connect(state)
    try:
        while True:
            try:
                with gpu_lock(state, "controller.lock"):
                    with gpu_lock(state):
                        quarantine_unsealed(db, state)
                    export(db, state, archive)
                    with db:
                        for (candidate, item), (original, spec) in expected(plan).items():
                            add(db, COLLECTION, item, candidate, spec["packet"]["dimension"], original["role"], spec)
                    for candidate in sorted(plan["candidate_counts"]):
                        while work(db, state, assets, port, candidate, [COLLECTION], 72, grader=grade):
                            export(db, state, archive)
                    return
            except BlockingIOError:
                time.sleep(20)
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "report"))
    parser.add_argument("--state", type=Path, default=DEFAULT)
    parser.add_argument("--assets", type=Path, default=ROOT.parent.parent)
    parser.add_argument("--archive", type=Path, default=ROOT / "evaluation/aeve/results")
    parser.add_argument("--port", type=int, default=18744)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    plan = freeze()
    if args.action == "freeze":
        if args.output is None:
            parser.error("freeze requires --output")
        write_json(args.output, plan)
        print(plan["required"], "frozen physical assessment identities")
        return
    if json.loads(FREEZE.read_bytes()) != plan:
        raise ValueError("truncation protocol differs from registered bytes")
    if args.output is None:
        parser.error("run and report require --output")
    if args.action == "run":
        execute(args.state.resolve(), args.assets.resolve(), args.archive.resolve(), args.port, plan)
    result = report(args.archive, plan)
    write_json(args.output, result)
    print(result["recorded"], "sealed truncation diagnostics")


if __name__ == "__main__":
    main()
