"""Link every unsuccessful MULTITOOL and planning primary trial to its evidence."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path


def multitool(evidence):
    source = evidence / "multitool/primary-vulkan-full/terminal.jsonl.gz"
    with gzip.open(source, "rt", encoding="utf-8") as handle:
        for line, text in enumerate(handle, 1):
            checkpoint = json.loads(text)
            row = checkpoint["row"]
            if row["status"] == "PASS":
                continue
            findings = row["findings"]
            boundary = "evaluated trajectory or persisted state"
            if any(item.get("detail") == "invalid tool call batch" for item in findings):
                boundary = "non-streamed wire batch limit"
            yield {
                "suite": "MULTITOOL-V1", "case_id": row["case_id"], "trial_id": row["key"], "status": row["status"],
                "run_id": row["run_id"], "archive": source.relative_to(evidence).as_posix(),
                "archive_line": line, "checkpoint_sha256": checkpoint["sha256"],
                "observed_boundary": boundary, "finding_codes": sorted({item["code"] for item in findings}),
                "stage_control": ("root_causes/multitool_batch_limit_full_control.json"
                                  if boundary == "non-streamed wire batch limit" else None),
            }


def planning(evidence):
    source = evidence / "planning/primary-vulkan-full"
    manifest = json.loads((source / "archive_manifest.json").read_bytes())
    lexical = json.loads((evidence / "root_causes/planning_reference_boundary_control.json").read_bytes())
    corrected = {row["case_id"] for row in lexical["trials"] if row["after"]["status"] == "PASS"}
    for part in sorted(source.glob("planning-part-*.jsonl.gz")):
        with gzip.open(part, "rt", encoding="utf-8") as handle:
            for line, text in enumerate(handle, 1):
                member = json.loads(text)
                if not member["name"].startswith("cases/"):
                    continue
                raw = member["raw_text"].encode("utf-8")
                if hashlib.sha256(raw).hexdigest() != manifest["sha256"][member["name"]]:
                    raise ValueError("planning raw checkpoint differs")
                row = json.loads(raw)
                if row["status"] == "PASS":
                    continue
                flags = {item["code"] for item in row["findings"]}
                if row["final_raw"] is not None and not row["final_matches"]:
                    flags.add("FINAL_ANSWER_MISMATCH")
                if row["errors"]:
                    flags.add("ORACLE_TRACE_ERROR")
                source_control = None
                if "INITIAL_PLAN_REJECTED" in flags:
                    boundary = "initial plan acceptance"
                elif row["track"] == "A" and row["case_id"] in corrected:
                    boundary = "reference token boundary"
                    source_control = "root_causes/planning_reference_boundary_control.json"
                elif "PROPOSAL_REJECTED" in flags:
                    boundary = "proposal validation"
                else:
                    boundary = "final goal, trace or state comparison"
                yield {
                    "suite": "AGENTIC-PLAN-V1", "case_id": row["case_id"], "trial_id": row["trial"]["trial_id"],
                    "status": row["status"], "run_id": row["run_id"], "archive": part.relative_to(evidence).as_posix(),
                    "archive_line": line, "member": member["name"], "checkpoint_sha256": row["artifact_sha256"],
                    "journal": row["journal"], "journal_sha256": row["journal_sha256"],
                    "observed_boundary": boundary, "finding_codes": sorted(flags), "stage_control": source_control,
                }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rows = [*multitool(args.evidence), *planning(args.evidence)]
    identifiers = {(row["suite"], row["trial_id"]) for row in rows}
    if len(rows) != len(identifiers):
        raise ValueError("reused failure evidence identity")
    data = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows).encode()
    if args.check:
        if not args.output.is_file() or args.output.read_bytes() != data:
            parser.exit(1, "FAIL: physical primary failure index differs\n")
    else:
        args.output.write_bytes(data)
    print(f"PASS: {len(rows)} case-linked physical primary failure records")


if __name__ == "__main__":
    main()
