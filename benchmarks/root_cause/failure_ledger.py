"""Index archived and fresh historical failures by case, run and observable boundary."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from benchmarks.tool_calling_v2 import rescore


HEADER = {
    "model_id": "OpenBMB/MiniCPM5-2B-GGUF",
    "modelscope_revision": "8cc1178b0a5cee98872ca3f2f88d49b3d3fa6f59",
}


def ledger_entry(original, verdict, identity, source_row_hash, capture):
    status = dict(v1=original["status"], v2=verdict["status"], state=verdict["business_state_status"])
    if status["v1"] == status["v2"] == "PASS":
        return None
    observations = verdict["findings"]
    reasons = verdict["v1_false_failure_reasons"]
    boundary = "POST_PARSER_WIRE_OR_STATE"
    confidence = "UNVERIFIED"
    hypothesis = "Follow the preserved proposals from generation through scoring; isolate one variable at a time."
    risk = "First divergence and reproduction stability still need verification."
    if reasons:
        boundary = "V1_EVALUATOR"
        confidence = "SUPPORTED_BUT_INCOMPLETE"
        hypothesis = "V1 rejected a valid ordering, grouping, or fact representation retained in the archived trace."
        risk = "The historical rescore does not verify persisted effects or replicate generation."
    if not capture and status["state"] == "BLOCKED" and verdict["trace_status"] == "PASS":
        boundary = "PERSISTED_STATE_EVIDENCE"
        hypothesis = "V1 recorded a synthetic receipt without an independent persisted transaction."
        risk = "State verdict requires a new run with before/after snapshots and authorization evidence."
    exact = [
        item["source_generation"] for item in capture
        if "pre_parser_bytes_hex" in item["source_generation"]
    ]
    empty_tags = [
        source for source in exact
        if b'<function name="create_ticket">' in bytes.fromhex(source["pre_parser_bytes_hex"])
        and b'<param name="tags">[]</param>' in bytes.fromhex(source["pre_parser_bytes_hex"])
    ]
    wrong_tags = any("tags" in finding.get("fields", []) for finding in observations)
    if empty_tags and wrong_tags:
        boundary = "BEFORE_NATIVE_PARSER"
        confidence = "SUPPORTED_BUT_INCOMPLETE"
        hypothesis = "This generation already contained empty tags. The original archived generation and the influence of schema, template or precision remain unverified."
        risk = "This reproduction does not establish the origin of every historical empty-tags case."
    source_digest = (hashlib.sha256(b"\x00".join(bytes.fromhex(source["pre_parser_bytes_hex"])
                                                for source in exact)).hexdigest() if exact else None)
    return {
        **HEADER, **identity, "case_id": original["id"], "category": original["category"],
        "original_row_sha256": source_row_hash, "statuses": status, "raw_output_digest": source_digest,
        "failure_layer": boundary, "confidence": confidence, "root_cause_hypothesis": hypothesis,
        "expected_behavior": "Satisfy the frozen case and the V2 dependency, argument, outcome and state checks.",
        "observed_behavior": {"v1": original["failures"], "v2": observations, "v1_rescore_findings": reasons},
        "minimal_reproducer": None, "source_file": None, "source_function": None,
        "counterfactual_result": None, "fix_commit": None, "red_test": None, "green_test": None,
        "regression_status": "NOT_RUN", "remaining_risk": risk,
    }


def archived():
    for backend in rescore.BACKENDS:
        original = rescore.BASELINE / f"tool_calling_test_{backend}"
        run = rescore.read_json(original / "run.json")
        checks = rescore.json_lines(rescore.DEFAULT_OUTPUT / f"{backend}.jsonl")
        for raw, verdict in zip((original / "results.jsonl").read_bytes().splitlines(), checks, strict=True):
            row = json.loads(raw)
            if row["id"] != verdict["id"] or row["run_id"] != verdict["original_run_id"]:
                raise ValueError(f"archived row mismatch for {backend}")
            yield ledger_entry(row, verdict, {
                "track": "ARCHIVED_IJ0", "backend": backend, "run_id": run["run_id"],
                "runtime_sha": run["engine"]["exe_sha256"], "dataset_sha256": run["dataset_sha256"],
            }, hashlib.sha256(raw).hexdigest(), [])


def fresh(path):
    run = rescore.read_json(path / "run.json")
    conf = run["configuration"]
    from .historical_replay import stable_digest

    if stable_digest(conf) != run["fingerprint"]:
        raise ValueError("fresh run fingerprint differs")
    for raw in (path / "results.jsonl").read_bytes().splitlines():
        row = json.loads(raw)
        if row["run_id"] != run["run_id"] or row["id"] not in conf["case_ids"]:
            raise ValueError("fresh row identity differs")
        yield ledger_entry(row, row["rescored_v2"], {
            "track": "FRESH_HISTORICAL", "arm": conf["arm"], "backend": conf["backend"],
            "run_id": run["run_id"], "runtime_sha": conf["engine"]["exe_sha256"],
            "dataset_sha256": conf["dataset_sha256"],
        }, hashlib.sha256(raw).hexdigest(), row["capture"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fresh", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    entries = [entry for entry in archived() if entry is not None]
    for path in args.fresh:
        entries.extend(entry for entry in fresh(path) if entry is not None)
    identities = {(entry["run_id"], entry["case_id"]) for entry in entries}
    if len(identities) != len(entries):
        parser.error("a failure identity appears more than once")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as handle:
        for entry in entries:
            handle.write((json.dumps(entry, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"))
    print(f"{len(entries)} investigations: {dict(Counter(row['confidence'] for row in entries))}")


if __name__ == "__main__":
    main()
