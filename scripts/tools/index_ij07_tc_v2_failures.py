"""Index every unsuccessful scored TC-V2 trial against the preserved capture."""

import argparse
from collections import Counter
import gzip
import json
from pathlib import Path


def build(evidence):
    for backend in ("vulkan", "rocm"):
        archive = evidence / backend / "terminal.jsonl.gz"
        with gzip.open(archive, "rt", encoding="utf-8") as handle:
            for line, text in enumerate(handle, 1):
                checkpoint = json.loads(text)
                row = checkpoint["row"]
                if row["key"].startswith("fixture--") or row["status"] == "PASS":
                    continue
                requests = row.get("requests", [])
                source_ids = [
                    request["source_generation"]["completion_id"]
                    for request in requests if request.get("source_generation")
                ]
                yield {
                    "backend": backend,
                    "archive": f"{backend}/{archive.name}",
                    "archive_line": line,
                    "checkpoint_sha256": checkpoint["sha256"],
                    "case_id": row["case_id"],
                    "key": row["key"],
                    "run_id": row["run_id"],
                    "status": row["status"],
                    "findings": row.get("findings", []),
                    "business_state": row.get("business_state_status"),
                    "source_completion_ids": source_ids,
                    "fault_isolation": "NOT_RUN",
                }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rows = list(build(args.evidence))
    index = args.evidence / "failure_index.jsonl"
    data = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows).encode()
    if args.check:
        if index.read_bytes() != data:
            parser.exit(1, "FAIL: TC-V2 failure index differs\n")
    else:
        index.write_bytes(data)
    print("PASS:", dict(Counter((row["backend"], row["status"]) for row in rows)))


if __name__ == "__main__":
    main()
