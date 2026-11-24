"""Verify and archive the matched three-case JOB-V1 GPU diagnostics."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
from shutil import copyfile

from benchmarks.job_productivity_v1.holdout.dataset import digest
from benchmarks.tool_calling_v2.holdout.qualify import pid_counter_proof, read_checkpoint
from scripts.tools.scan_sensitive import scan


CASES = {"JOB-DOC-001", "JOB-CUS-001", "JOB-PRD-001"}


def archive(source, output):
    reports, observed_pairing = {}, {}
    for arm in "ABCDE":
        folder = source / f"ij07-job-diagnostic-{arm}"
        run = json.loads((folder / "run.json").read_bytes())
        configuration = run["configuration"]
        roster = configuration["roster"]
        summary = json.loads((folder / "summary.json").read_bytes())
        if (configuration["arm"] != arm or configuration["scope"] != "diagnostic"
                or run["fingerprint"] != digest(configuration) or summary["run_id"] != run["run_id"]
                or summary["physical_evidence_status"] != "PASS"
                or {row["case_id"] for row in roster.values()} != CASES or len(roster) != 3):
            raise ValueError(f"diagnostic identity differs for arm {arm}")
        records = sorted((folder / "cases").glob("*.json"))
        if {record.stem for record in records} != roster.keys():
            raise ValueError(f"missing diagnostic terminal cases for arm {arm}")
        counters = [session["counter_file"] for session in run["sessions"].values()]
        for session in run["sessions"].values():
            proof = pid_counter_proof(folder, session)
            if proof != session["proof"] or proof["status"] != "PASS":
                raise ValueError(f"diagnostic GPU capture differs for arm {arm}")
        paths = ["run.json", "summary.json", *counters, *(record.relative_to(folder).as_posix() for record in records)]
        if scan(folder, paths):
            raise ValueError(f"diagnostic failed privacy checks for arm {arm}")
        rows = [read_checkpoint(path, run, path.stem, folder / "sqlite") for path in records]
        arm_pairing = {row["case_id"]: row["pairing_sha256"] for row in rows}
        if observed_pairing and arm_pairing != observed_pairing:
            raise ValueError(f"case pairing differs for arm {arm}")
        observed_pairing = arm_pairing
        raw = b"".join(record.read_bytes().strip() + b"\n" for record in records)
        dest = output / arm
        dest.mkdir(parents=True, exist_ok=False)
        for name in ("run.json", "summary.json"):
            copyfile(folder / name, dest / name)
        for name in counters:
            (dest / (name + ".gz")).write_bytes(gzip.compress((folder / name).read_bytes(), mtime=0))
        (dest / "terminal.jsonl.gz").write_bytes(gzip.compress(raw, mtime=0))
        reports[arm] = {"summary": summary, "terminal_uncompressed_sha256": hashlib.sha256(raw).hexdigest(),
                        "cases": {row["case_id"]: {key: row[key] for key in ("status", "completed", "model_calls", "findings")}
                                  for row in rows}}
    result = {"scope": "three-case Radeon diagnostic; frozen primary and repeat panels separate",
              "pairing_sha256": observed_pairing, "arms": reports}
    (output / "coverage.json").write_bytes((json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode())
    print("PASS: 15 matched JOB-V1 diagnostics, checkpoint/SQLite digests, GPU proof")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    archive(args.source, args.output)


if __name__ == "__main__":
    main()
