"""Publish verified, already-redacted SLM admission diagnostics."""

import argparse
import csv
import gzip
import json
from pathlib import Path
import shutil

from evaluation.aeve.archive import check_text, digest
from evaluation.aeve.gpu_handoff import HANDOFF, require_handoff
from evaluation.aeve.runtime import ROOT


def verify(source, candidate, handoff_path, gate):
    report = source / "report.json"
    check_text(report.read_bytes())
    data = json.loads(report.read_bytes())
    lease = data["gpu"]["gpu_lease"]
    bound = all(lease[field] == gate["lease"][field] for field in ("host_sha256", "gpu_physical_sha256"))
    if (data["candidate"] != candidate or data["handoff_sha256"] != digest(handoff_path)
            or data["formal_admission"] != "NOT_RUN" or data["formal_core_recorded"] != 0
            or data["diagnostic_coverage"] != "PASS" or data["gates"]["gpu_execution"] != "PASS"
            or not bound or lease["mission_id"] != "IJ-SLM-1.0"
            or lease["runtime_session"] != data["run_id"]):
        raise ValueError("diagnostic does not match the mission's GPU handoff and run identity")
    expected = {data["gpu"][key] + ".gz" for key in ("counter_file", "trace_file")}
    if set(data["sha256"]) != expected or any(Path(name).name != name for name in expected):
        raise ValueError("diagnostic evidence seal is incomplete")
    for name, sha in data["sha256"].items():
        path = source / name
        if digest(path) != sha:
            raise ValueError("diagnostic evidence SHA256 differs")
        with gzip.open(path, "rb") as stream:
            for line in stream:
                check_text(line)
    return data


def publish(assets, handoff_root, repo):
    target = repo / "evidence/IJSLM/admission"
    target.mkdir(parents=True, exist_ok=True)
    gate = require_handoff(handoff_root)
    rows = []
    for candidate in "ABDFG":
        source = assets / ".runtime/ij-slm-1.0" / ("admission-" + candidate) / "portable"
        if not (source / "report.json").is_file():
            rows.append((candidate, "runtime", "diagnostic_coverage", "NOT_RUN", ""))
            continue
        record = verify(source, candidate, handoff_root / HANDOFF, gate)
        dest = target / candidate
        dest.mkdir(exist_ok=True)
        for name in ["report.json", *record["sha256"]]:
            obj = dest / name
            if obj.exists():
                if digest(obj) != digest(source / name):
                    raise ValueError("existing diagnostic must be preserved")
            else:
                shutil.copyfile(source / name, obj)
        for probe, status in record["gates"].items():
            rows.append((candidate, "runtime", probe, status, record["run_id"]))
        for probe, result in record["sdk"].items():
            rows.append((candidate, "real_sdk", probe, result["status"], record["run_id"]))
        rows.append((candidate, "real_sdk", "AG-11", record["offline_egress"], record["run_id"]))
    matrix = repo / "atlas/slm/v1.0/sdk_admission_diagnostics.csv"
    with matrix.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["candidate", "track", "diagnostic", "status", "runtime_session"])
        writer.writerows(rows)
    return matrix


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--assets", type=Path, required=True)
    cli.add_argument("--handoff-root", type=Path, required=True)
    args = cli.parse_args()
    print(publish(args.assets.resolve(), args.handoff_root.resolve(), ROOT).relative_to(ROOT))


if __name__ == "__main__":
    main()
