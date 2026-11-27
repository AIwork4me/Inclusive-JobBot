"""Validate complete historical replay arms and export inspected, compressed evidence."""

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

from benchmarks.job_productivity_v1.statistics import exact_mcnemar, wilson_interval
from benchmarks.tool_calling_v2 import rescore
from scripts.tools.scan_sensitive import scan
from scripts.tools.verify_ij06_evidence import verify_gpu


ARMS = ("R0-V", "R0-R", "R1-V", "R1-R")


def digest(value):
    return hashlib.sha256(value).hexdigest()


def document(path, value):
    path.write_bytes((json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode())


def collect(source, target, arm, old_empty_tags):
    run = rescore.read_json(source / "run.json")
    conf = run["configuration"]
    summary = rescore.read_json(source / "summary.json")
    raw = (source / "results.jsonl").read_bytes()
    rows = [json.loads(line) for line in raw.splitlines()]
    if (
        conf["arm"] != arm or conf["git"]["dirty"] is not False or not conf["observe"]
        or len(rows) != 500 or len(set(conf["case_ids"])) != 500
        or [row["id"] for row in rows] != conf["case_ids"]
        or summary["run_id"] != run["run_id"] or summary["cases"] != 500
        or digest(raw) != summary["result_sha256"]
    ):
        raise ValueError(f"{arm} evidence is incomplete or identity differs")
    for row in rows:
        content = {key: value for key, value in row.items() if key != "artifact_sha256"}
        if row["run_id"] != run["run_id"] or (
            digest(json.dumps(content, sort_keys=True).encode()) != row["artifact_sha256"]
        ):
            raise ValueError(f"{arm} {row['id']} integrity mismatch")
    target.mkdir()
    names = ["run.json", "summary.json", "results.jsonl", *(
        item[key] for item in run["sessions"] for key in ("counter_file", "trace_file")
    )]
    findings = scan(source, names)
    if findings:
        raise ValueError(f"{arm} raw evidence failed privacy checks: {findings}")
    files = {}
    sessions = []
    for index, session in enumerate(run["sessions"], 1):
        launch = target / f"launch-{index}.json"
        document(launch, {**session, "status": "PASS"})
        offload = verify_gpu({
            "gpu_launch": launch, "gpu_counters": source / session["counter_file"],
        }, conf["backend"])
        sessions.append({"pid": session["pid"], "physical_gpu": "PASS" if offload else "FAIL"})
    for name in names:
        data = (source / name).read_bytes()
        out_name = name + ".gz" if name.endswith(".jsonl") else name
        path = target / out_name
        if out_name.endswith(".gz"):
            data = gzip.compress(data, compresslevel=6, mtime=0)
        path.write_bytes(data)
        files[out_name] = digest(data)
    raw_empty = []
    for row in rows:
        if row["id"] not in old_empty_tags:
            continue
        for request in row["capture"]:
            hex_text = request["source_generation"].get("pre_parser_bytes_hex")
            if not hex_text:
                continue
            text = bytes.fromhex(hex_text)
            if b'<function name="create_ticket">' in text and b'<param name="tags">[]</param>' in text:
                raw_empty.append(row["id"])
                break
    v2 = [r["rescored_v2"] for r in rows]
    by_category = {}
    for category in sorted({r["category"] for r in v2}):
        by_category[category] = rescore.summarize([r for r in v2 if r["category"] == category])
    intervals = {key: wilson_interval(counts.get("PASS", 0), 500) for key, counts in (
        ("v1", summary["v1"]), ("v2_complete", summary["v2"]["status"]),
        ("v2_semantic", summary["v2"]["trace_status"]),
    )}
    return rows, {
        "run_id": run["run_id"], "git": conf["git"], "dataset_sha256": conf["dataset_sha256"],
        "model_sha256": conf["model_sha256"], "backend": conf["backend"],
        "physical_gpu_sessions": sessions, "source_capture": summary["source_capture"],
        "v1": summary["v1"], "v2": summary["v2"], "by_category": by_category,
        "historical_empty_tags_cases_with_empty_pre_parser_array": raw_empty,
        "wilson_95": intervals, "archive_sha256": files,
    }


def paired(before, after, field):
    def status(row):
        return row["status"] if field == "v1" else row["rescored_v2"][field]

    counts = Counter((status(left), status(right)) for left, right in zip(before, after, strict=True))
    old_only = sum(count for (old, new), count in counts.items() if old == "PASS" and new != "PASS")
    new_only = sum(count for (old, new), count in counts.items() if old != "PASS" and new == "PASS")
    return {"outcomes": {f"{a}->{b}": count for (a, b), count in counts.items()},
            "mcnemar_exact_two_sided": exact_mcnemar(old_only, new_only)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    audit = rescore.read_json(rescore.ROOT / "evidence/IJ07/baseline_manifest.json")
    args.output.mkdir(exist_ok=False)
    rows, arms = {}, {}
    for arm in ARMS:
        backend = "vulkan" if arm.endswith("-V") else "rocm"
        rows[arm], arms[arm] = collect(
            args.source / arm, args.output / arm, arm,
            set(audit["recalculated"][backend]["v1_pass_with_empty_ticket_tags"]),
        )
    if any([r["id"] for r in rows[arm]] != [r["id"] for r in rows["R0-V"]] for arm in ARMS):
        raise ValueError("arms differ in case order")
    document(args.output / "summary.json", {
        "scope": "historical V1 simulator and V2 diagnostic; no persistent-state or SDK qualification",
        "cases_planned": 2000, "cases_executed": sum(len(group) for group in rows.values()),
        "arms": arms,
        "paired": {backend: {metric: paired(rows[f"R0-{suffix}"], rows[f"R1-{suffix}"], metric)
                            for metric in ("v1", "trace_status", "status")}
                   for backend, suffix in (("vulkan", "V"), ("rocm", "R"))},
    })
    print("PASS: four digest-verified archives of 500 real cases each")


if __name__ == "__main__":
    main()
