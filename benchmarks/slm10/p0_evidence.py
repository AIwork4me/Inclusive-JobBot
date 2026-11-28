"""Publish and independently recheck the portable IJ-SLM P0 physical controls."""

import argparse
from collections import Counter
import gzip
from hashlib import sha256
import json
from pathlib import Path
import shutil

from benchmarks.ij06_sdk.wire_boundary import assemble_reply
from evaluation.aeve.archive import check_text, digest
from evaluation.aeve.runtime import ROOT, canonical
from model_gateway import GatewayError

from .portable import portable
from .tc_v3 import HERE

OUTPUT = ROOT / "evidence/IJSLM/p0"
MANIFEST = OUTPUT / "manifest.json"
SOURCES = {
    **{f"native-{model}-{mode}": f"p0-v2-{model}-native-{mode}"
       for model in ("A", "B", "D") for mode in ("on", "off")},
    **{f"tc-v3-development-{model}": f"p0-tcv3-development-{model}" for model in ("A", "B", "D")},
    **{f"ag02-{profile}": f"p0-9913e64-D-ag02-{profile}" for profile in ("original", "repaired")},
}


def read_report(directory):
    raw = (directory / "report.json").read_bytes()
    check_text(raw)
    report = json.loads(raw)
    if report["gpu_execution"] != "PASS" or report["formal_core_recorded"] != 0:
        raise ValueError("P0 evidence must carry its own development GPU proof")
    for name, expected in report["artifacts"].items():
        path = directory / name
        if digest(path) != expected:
            raise ValueError("compressed P0 artifact digest mismatch")
        check_text(gzip.decompress(path.read_bytes()))
    return report


def inventory():
    manifest = {"evidence_class": "local Radeon development only", "formal_recorded": 0, "runs": {}}
    for label in SOURCES:
        directory = OUTPUT / label
        report = read_report(directory)
        manifest["runs"][label] = {
            "run_id": report["run_id"], "git_sha": report["git_sha"], "candidate": report["candidate"],
            "report_sha256": digest(directory / "report.json"), "artifacts": report["artifacts"],
        }
        if label.startswith("tc-v3-development"):
            trials = report["results"]
            manifest["runs"][label]["trajectories"] = len(trials)
            manifest["runs"][label]["native_requests"] = dict(Counter(
                event["native_evidence"]["status"] for trial in trials for event in trial["wire"]))
    fixture = OUTPUT / "ag02-same-bytes.sse.gz"
    source_info = OUTPUT / "ag02-same-bytes.json"
    raw = gzip.decompress(fixture.read_bytes())
    check_text(raw)
    raw_info = source_info.read_bytes()
    check_text(raw_info)
    info = json.loads(raw_info)
    if info["response_sha256"] != sha256(raw).hexdigest() or info["response_bytes"] != len(raw):
        raise ValueError("AG-02 raw bytes do not match their original capture")
    replay = {}
    for size in (524288, 1048576):
        try:
            result = assemble_reply("text/event-stream", raw, max_stream_bytes=size)
        except GatewayError as error:
            replay[str(size)] = {"status": "FAIL", "message": str(error)}
        else:
            replay[str(size)] = {"status": "PASS", "finish_reason": result.finish_reason}
    if replay != {"524288": {"status": "FAIL", "message": "stream byte limit exceeded"},
                  "1048576": {"status": "PASS", "finish_reason": "stop"}}:
        raise ValueError("AG-02 same-byte rejection and recovery no longer reproduce")
    manifest["ag02_same_bytes"] = {"archive_sha256": digest(fixture), "capture_sha256": digest(source_info),
                                   "bytes": len(raw), "replay": replay}
    return manifest


def require_development():
    manifest = json.loads(MANIFEST.read_bytes())
    for model in ("A", "B", "D"):
        label = f"tc-v3-development-{model}"
        folder = OUTPUT / label
        report = read_report(folder)
        if (manifest["runs"][label]["report_sha256"] != digest(folder / "report.json")
                or report["dataset_manifest_sha256"] != digest(HERE / "manifest.json")
                or len(report["results"]) != 9):
            raise ValueError("TC-V3 development preflight differs from its freeze")
        for trial in report["results"]:
            if not trial["wire"] or any(row["native_evidence"]["status"] != "PASS" for row in trial["wire"]):
                raise ValueError("TC-V3 development preflight lacks native evidence")
        for track in ("sdk_first", "sdk_streaming"):
            if not any(trial["track"] == track and trial["calls"] for trial in report["results"]):
                raise ValueError("TC-V3 development preflight lacks SDK callbacks")
    return digest(MANIFEST)


def verify_planning_development():
    folder = OUTPUT.parent / "planning-development"
    manifest = json.loads((folder / "manifest.json").read_bytes())
    if manifest["formal_trials"] != 0:
        raise ValueError("planning development cannot enter the formal core denominator")
    for name, expected in manifest["files"].items():
        if Path(name).name != name or digest(folder / name) != expected:
            raise ValueError("planning development artifact differs from its seal")
        raw = (folder / name).read_bytes()
        check_text(gzip.decompress(raw) if name.endswith(".gz") else raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-runtime", type=Path)
    parser.add_argument("--ag02-failure", type=Path)
    args = parser.parse_args()
    if args.from_runtime:
        if not args.ag02_failure:
            parser.error("raw AG-02 failure capture is required")
        for label, folder in SOURCES.items():
            source = args.from_runtime / folder / "portable"
            report = read_report(source)
            path = OUTPUT / label
            path.mkdir(parents=True, exist_ok=True)
            for name in ("report.json", *report["artifacts"]):
                shutil.copyfile(source / name, path / name)
        capture = json.loads(args.ag02_failure.read_bytes())["wire"][0]
        raw = capture["response"].encode("utf-8")
        check_text(raw)
        (OUTPUT / "ag02-same-bytes.sse.gz").write_bytes(gzip.compress(raw, mtime=0))
        metadata = {key: value for key, value in capture.items() if key != "response"}
        metadata["evidence_class"] = "physical pilot capture with working-tree diagnostics"
        (OUTPUT / "ag02-same-bytes.json").write_bytes(canonical(portable(metadata)) + b"\n")
        MANIFEST.write_bytes(canonical(inventory()) + b"\n")
    if MANIFEST.read_bytes() != canonical(inventory()) + b"\n":
        raise ValueError("P0 portable evidence manifest mismatch")
    require_development()
    verify_planning_development()
    print("Eleven physical development runs and the AG-02 same-byte control verified.")


if __name__ == "__main__":
    main()
