"""Verify and explicitly resume the interleaved SDK causal development queue."""

import argparse
import gzip
import json
from pathlib import Path
import subprocess
import sys
from tempfile import mkdtemp

from audit import write_evidence
from benchmarks.root_cause.gpu_lease import _named_lease
from evaluation.aeve.archive import digest
from evaluation.aeve.gpu_handoff import HANDOFF
from evaluation.aeve.runtime import ROOT, fingerprint

from .sdk_ablation_summary import check_report
from .tc_v3 import HERE

PROFILE = HERE.parent / "sdk-causal-experiment.json"
SEAL_VERSION = "IJ-SLM-SDK-CAUSAL-WAVE/1.0"
CONTROLLER_LOCK = "InclusiveJobBotSLMCausalController"
WAVE_SIZE = 3


def expected_wave(candidate, round_index):
    profile = json.loads(PROFILE.read_bytes())
    cases = [case for case in profile["development_case_ids"] if case not in profile["pilot_case_ids"]]
    start = WAVE_SIZE * round_index
    if candidate not in profile["models"] or not 0 <= start < len(cases):
        raise ValueError("unknown diagnostic wave")
    chosen = cases[start:start + WAVE_SIZE]
    profile_hash = digest(PROFILE)
    return {"version": SEAL_VERSION, "wave": f"{candidate}-{round_index:02d}", "candidate": candidate,
            "profile_sha256": profile_hash, "dataset_manifest_sha256": digest(HERE / "manifest.json"),
            "runner_sha256": digest(Path(__file__).with_name("sdk_causal_ablation.py")),
            "handoff_sha256": digest(ROOT / HANDOFF), "sdk": "0.1.24", "cases": chosen, "arms": profile["arms"],
            "trial_ids": [fingerprint([profile_hash, candidate, case, arm]) for case in chosen for arm in profile["arms"]]}


def verify_gpu_artifact(folder, name, launch):
    if launch["backend"] != "vulkan" or launch["owns_port"] is not True or not (
            0 < launch["layers_offloaded"] == launch["layers_total"]):
        raise ValueError("diagnostic launch lacks full Radeon offload")
    prefix = f"pid_{launch['pid']}_"
    rows = (json.loads(line) for line in gzip.decompress((folder / name).read_bytes()).splitlines())
    samples = [row for row in rows if row.get("instance", "").startswith(prefix)]
    if not (any(row["kind"] == "gpu_process_memory" and row["committed_bytes"] > 0 for row in samples)
            and any(row["kind"] == "gpu_engine" and row["engtype"] in ("3D", "Compute")
                    and 0 < row["utilization"] <= 100 for row in samples)):
        raise ValueError("diagnostic archive lacks process-linked Radeon telemetry")


def verified_run(folder, expected, cases):
    report = check_report(folder)
    if (report["candidate"] != expected["candidate"] or report["case_ids"] != cases
            or [row["case_id"] for row in report["results"]] != cases
            or report["version"] != json.loads(PROFILE.read_bytes())["version"]
            or report["dataset_manifest_sha256"] != expected["dataset_manifest_sha256"]
            or report["source_sha256"] != expected["runner_sha256"]
            or report["handoff_sha256"] != expected["handoff_sha256"] or report["sdk"] != expected["sdk"]):
        raise ValueError("diagnostic report differs from the scheduled wave identity")
    if report["gpu_execution"] != "PASS" or set(report["artifacts"]) != {"gpu.jsonl.gz", "native.jsonl.gz"}:
        raise ValueError("diagnostic report lacks the required GPU and native artifacts")
    lease = report["gpu"]["gpu_lease"]
    handoff = json.loads((ROOT / HANDOFF).read_bytes())["lease"]
    if (lease["runtime_session"] != report["run_id"] or lease["mission_id"] != "IJ-SLM-1.0"
            or any(lease[key] != handoff[key] for key in ("host_sha256", "gpu_physical_sha256"))):
        raise ValueError("diagnostic GPU lease differs from the scheduled Radeon identity")
    verify_gpu_artifact(folder, "gpu.jsonl.gz", report["gpu"])
    for row in report["results"]:
        if sorted(arm["arm"] for arm in row["arms"]) != sorted(expected["arms"]):
            raise ValueError("diagnostic case lacks the scheduled arm roster")
        for arm in row["arms"]:
            capture = arm.get("capture")
            trial_id = fingerprint([report["run_id"], row["case_id"], arm["arm"]])
            if capture is not None and capture["trial_id"] != trial_id:
                raise ValueError("diagnostic arm differs from the run trial identity")
            if capture is None and arm.get("status") not in ("NOT_RUN", "BLOCKED"):
                raise ValueError("diagnostic arm lacks capture or explicit disposition")
    return report["results"]


def reconcile(folder, expected):
    """Read completed artifacts and identify the next provably undispatched case."""
    legacy_report = report_path(folder)
    reservation = folder / "reservation.json"
    if not folder.exists():
        return {}, expected["cases"]
    if legacy_report.is_file():
        if reservation.exists():
            raise ValueError("mixed legacy and reserved wave layouts")
        verified_run(legacy_report.parent, expected, expected["cases"])
        return {legacy_report.parent.relative_to(folder).as_posix(): digest(legacy_report)}, []
    if not reservation.is_file():
        raise ValueError("interrupted legacy wave requires reconciliation of existing physical captures")
    if json.loads(reservation.read_bytes()) != expected:
        raise ValueError("wave reservation differs from expected trial identity")
    recovered, pending = {}, []
    for case in expected["cases"]:
        case_folder = folder / "cases" / case
        path = report_path(case_folder)
        if path.is_file():
            verified_run(path.parent, expected, [case])
            recovered[path.parent.relative_to(folder).as_posix()] = digest(path)
        elif case_folder.exists():
            raise ValueError(f"interrupted reservation {case} requires reconciliation of existing physical captures")
        else:
            pending.append(case)
    return recovered, pending


def report_path(folder):
    path = folder / "portable/report.json"
    return path if path.is_file() else folder / "recovered-portable/report.json"


def recover_finalized(folder, expected, cases):
    """Rebuild a missing portable report without executing a reserved case."""
    if report_path(folder).is_file() or not folder.is_dir():
        return
    private = folder / "report.json"
    if not private.is_file():
        return
    report = json.loads(private.read_bytes())
    if report.get("gpu_execution") != "PASS" or [row["case_id"] for row in report["results"]] != cases:
        return
    from .admission import archive
    from .portable import portable

    launch = report["gpu"]
    trace = folder / launch["trace_file"]
    if digest(trace) != report["private_native_trace_sha256"]:
        raise ValueError("finalized private native trace differs from its recorded digest")
    stage = Path(mkdtemp(prefix=".recover-", dir=folder))
    report["artifacts"] = {
        "gpu.jsonl.gz": archive(folder / launch["counter_file"], stage / "gpu.jsonl.gz"),
        "native.jsonl.gz": archive(trace, stage / "native.jsonl.gz", redact=True),
    }
    write_evidence(stage / "report.json", portable(report) | {"private_report_sha256": digest(private)})
    verified_run(stage, expected, cases)
    stage.rename(folder / "recovered-portable")


def wave_manifest(expected, reports):
    return {"expected": expected, "verified_reports": reports}


def verify_seal(folder, expected):
    reports, pending = reconcile(folder, expected)
    path = folder / "wave-seal.json"
    if not path.is_file() or pending or json.loads(path.read_bytes()) != wave_manifest(expected, reports):
        raise ValueError("wave lacks an intact atomic seal")
    return [folder / name for name in reports]


def invoke(module, *args):
    subprocess.run([sys.executable, "-m", f"benchmarks.slm10.{module}", *map(str, args)], check=True, cwd=ROOT)


def resume_wave(assets, diagnostics, candidate, round_index):
    expected = expected_wave(candidate, round_index)
    folder = diagnostics / expected["wave"]
    if (folder / "wave-seal.json").exists():
        verify_seal(folder, expected)
        return
    if not folder.exists():
        stage = Path(mkdtemp(prefix=f".{folder.name}-", dir=diagnostics))
        write_evidence(stage / "reservation.json", expected)
        stage.rename(folder)
    reservation = folder / "reservation.json"
    if reservation.is_file() and json.loads(reservation.read_bytes()) == expected:
        for case in expected["cases"]:
            recover_finalized(folder / "cases" / case, expected, [case])
    elif not reservation.exists():
        recover_finalized(folder, expected, expected["cases"])
    reports, pending = reconcile(folder, expected)
    for case in pending:
        invoke("sdk_causal_ablation", candidate, "--assets", assets, "--output", folder / "cases" / case,
               "--case", case)
    if pending:
        reports, pending = reconcile(folder, expected)
    if pending:
        raise ValueError("cannot seal a diagnostic wave with undispatched cases")
    write_evidence(folder / "wave-seal.json", wave_manifest(expected, reports))
    verify_seal(folder, expected)


def verify_transport(folder):
    report = check_report(folder)
    expected = {"on-gpu.jsonl.gz", "off-gpu.jsonl.gz"}
    if (report["version"] not in ("IJ-SLM-SDK-TRANSPORT/1.0", "IJ-SLM-SDK-TRANSPORT/1.1")
            or report["candidate"] != "D" or report["sdk"] != "0.1.24" or set(report["artifacts"]) != expected
            or set(report["variants"]) != {"on", "off"}):
        raise ValueError("transport control differs from the scheduled identity")
    for name, row in report["variants"].items():
        if row["gpu_execution"] != "PASS":
            raise ValueError("transport control lacks a physical variant")
        verify_gpu_artifact(folder, name + "-gpu.jsonl.gz", row["launch"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--resume", action="store_true")
    mode.add_argument("--audit", action="store_true")
    mode.add_argument("--seal-complete", action="store_true", help="adopt verified reports without dispatch")
    args = parser.parse_args()
    assets = args.assets.resolve(strict=True)
    runtime = assets / ".runtime/ij-slm-1.0"
    diagnostics = runtime / "sdk-causal-waves"
    profile = json.loads(PROFILE.read_bytes())
    waves = (len(profile["development_case_ids"]) - len(profile["pilot_case_ids"]) + WAVE_SIZE - 1) // WAVE_SIZE
    if args.audit or args.seal_complete:
        for round_index in range(waves):
            for candidate in profile["models"]:
                expected = expected_wave(candidate, round_index)
                folder = diagnostics / expected["wave"]
                try:
                    if args.seal_complete:
                        with _named_lease(CONTROLLER_LOCK):
                            reports, pending = reconcile(folder, expected)
                            if reports and not pending:
                                if not (folder / "wave-seal.json").is_file():
                                    write_evidence(folder / "wave-seal.json", wave_manifest(expected, reports))
                                verify_seal(folder, expected)
                    else:
                        reports, pending = reconcile(folder, expected)
                except ValueError as error:
                    print(expected["wave"], "BLOCKED", str(error))
                else:
                    print(expected["wave"], "PASS" if reports and not pending else "NOT_RUN")
        return
    with _named_lease(CONTROLLER_LOCK):
        diagnostics.mkdir(parents=True, exist_ok=True)
        for round_index in range(46):
            for candidate in profile["models"]:
                invoke("tc_queue", "--assets", assets, "--candidate", candidate, "--batch-size", 36, "--limit", 36)
                if round_index < waves:
                    resume_wave(assets, diagnostics, candidate, round_index)
                if round_index == 0 and candidate == "D":
                    folder = runtime / "sdk-transport-controls-v1"
                    if not folder.exists():
                        invoke("sdk_transport_controls", "--assets", assets, "--output", folder)
                    verify_transport(folder)
        invoke("tc_five_model_queue", "--assets", assets)


if __name__ == "__main__":
    main()
