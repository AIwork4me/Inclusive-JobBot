"""Verify and publish independent F/G TC-V3 Radeon admission evidence."""

import argparse
import json
from pathlib import Path
import shutil

from audit import write_evidence
from evaluation.aeve.archive import digest
from evaluation.aeve.gpu_handoff import HANDOFF
from evaluation.aeve.runtime import ROOT, fingerprint

from .p0_evidence import read_report
from .sdk_wave_queue import verify_gpu_artifact
from .tc_dashboard import objects
from .tc_v3 import FIRST_SEED, HERE

MODELS = ("F", "G")
TRACKS = ("direct_first", "sdk_first", "sdk_streaming")
OUTPUT = ROOT / "evidence/IJSLM/tc-v3-admissions"


def verify_admission(folder, candidate):
    if candidate not in MODELS:
        raise ValueError("additional admission is limited to the frozen F/G roster")
    report = read_report(folder)
    record = json.loads((HERE.parent / "model_registry.json").read_bytes())["models"][candidate]
    handoff = json.loads((ROOT / HANDOFF).read_bytes())["lease"]
    gpu = report["gpu"]
    lease = gpu["gpu_lease"]
    if (report["candidate"] != candidate or report["dataset_manifest_sha256"] != digest(HERE / "manifest.json")
            or report["handoff_sha256"] != digest(ROOT / HANDOFF) or report["sdk_version"] != "0.1.24"
            or report["model"]["model_sha256"] != record["asset"]["expected_sha256"]
            or report["model"]["runtime_revision"] != record["asset"]["revision"]
            or lease["runtime_session"] != report["run_id"] or lease["mission_id"] != "IJ-SLM-1.0"
            or any(lease[key] != handoff[key] for key in ("host_sha256", "gpu_physical_sha256"))
            or set(report["artifacts"]) != {"gpu.jsonl.gz", "native.jsonl.gz"}):
        raise ValueError("additional candidate admission identity differs from the freeze")
    verify_gpu_artifact(folder, "gpu.jsonl.gz", gpu)
    expected_cases = [case["case_id"] for case in objects(HERE / "development-public.jsonl")
                      if case["case_id"].endswith("-000") and case["family"] in ("dependency", "authorization", "parallel")]
    expected = [(case, track) for case in expected_cases for track in TRACKS]
    if [(row["case_id"], row["track"]) for row in report["results"]] != expected:
        raise ValueError("additional candidate development roster differs")
    for track in ("sdk_first", "sdk_streaming"):
        if not any(result["track"] == track and result["calls"] for result in report["results"]):
            raise ValueError(f"{candidate} lacks a linked SDK callback for {track}")
    for trial in report["results"]:
        if (trial["trial_id"] != fingerprint([report["run_id"], trial["track"], trial["case_id"]])
                or trial["seed"] != FIRST_SEED or not trial["wire"]
                or any(event["trial_id"] != trial["trial_id"]
                       or event["native_evidence"]["status"] != "PASS" for event in trial["wire"])):
            raise ValueError(f"{candidate} lacks native evidence for a scheduled development request")
    return report


def inventory(output):
    states = {}
    for candidate in MODELS:
        folder = output / candidate
        if not folder.exists():
            states[candidate] = {"status": "NOT_RUN"}
            continue
        report = verify_admission(folder, candidate)
        states[candidate] = {"status": "PASS", "run_id": report["run_id"], "git_sha": report["git_sha"],
                             "report_sha256": digest(folder / "report.json"), "artifacts": report["artifacts"]}
    return {"version": "IJ-SLM-TC-V3-ADMISSIONS/1.0", "formal_trials": 0, "candidates": states}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish-from", type=Path)
    args = parser.parse_args()
    if args.publish_from:
        for candidate in MODELS:
            source = args.publish_from / candidate / "development/portable"
            if not (source / "report.json").is_file():
                continue
            report = verify_admission(source, candidate)
            target = OUTPUT / candidate
            target.mkdir(parents=True, exist_ok=True)
            for name in (*report["artifacts"], "report.json"):
                artifact = target / name
                if not artifact.exists():
                    shutil.copyfile(source / name, artifact)
                elif digest(artifact) != digest(source / name):
                    raise ValueError("published admission differs from source archive")
    manifest = OUTPUT / "manifest.json"
    result = inventory(OUTPUT)
    if args.publish_from:
        OUTPUT.mkdir(parents=True, exist_ok=True)
        write_evidence(manifest, result)
    if not manifest.is_file() or json.loads(manifest.read_bytes()) != result:
        raise ValueError("published additional admission manifest differs from replay")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
