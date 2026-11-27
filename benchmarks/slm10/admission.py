"""Run the priority SLMs through local CPU, Radeon and real SDK admission probes."""

import argparse
import asyncio
from functools import partial
import gzip
from importlib.metadata import version
import json
from pathlib import Path
import subprocess
from uuid import uuid4

from google.antigravity import bin as harness_package

from benchmarks.competitive_slm.admission import GATES, chat_ok, cpu_server, request, test_gpu
from benchmarks.competitive_slm.tc_v2_candidate import server_environment, verify_launch, verify_runtime
from benchmarks.ij06_sdk.qualify import CASE_SPECS, execute_case
from benchmarks.root_cause.historical_replay import gpu_server
from evaluation.aeve.archive import check_text, digest
from evaluation.aeve.runtime import ROOT, canonical, write_json
from scripts.tools.verify_ij06_evidence import verify_gpu


def git_head():
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def archive(source, destination):
    raw = source.read_bytes()
    check_text(raw)
    destination.write_bytes(gzip.compress(raw, mtime=0))
    return digest(destination)


async def sdk_probes(client, alias, target, harness):
    results = {}
    for gate in CASE_SPECS:
        results[gate] = await execute_case(client.base_url, alias, target / gate, harness, gate)
        write_json(target / "sdk-observations.json", results)
    return results


def execute(candidate, assets, handoff_root, port):
    from evaluation.aeve.gpu_handoff import HANDOFF, require_handoff

    gate = require_handoff(handoff_root)
    registry_path = ROOT / "atlas/slm/v1.0/model_registry.json"
    record = json.loads(registry_path.read_bytes())["models"][candidate]
    model = (assets / record["local_asset"]).resolve(strict=True)
    engines = assets / ".tools/ij07-toolchoice-p4b-vulkan"
    cpu_binary = assets / "runtime/llama-cpp/cpu/llama-server.exe"
    harness = Path(harness_package.__file__).with_name("localharness.exe")
    sdk_version = version("google-antigravity")
    if sdk_version != "0.1.24":
        raise ValueError("unexpected installed Antigravity SDK version")
    identity = verify_runtime(candidate, model, engines)
    if identity["model"]["model_sha256"] != record["asset"]["expected_sha256"]:
        raise ValueError("SLM model file differs from the registered identity")
    pin = ROOT / record["reference_model_identity"]
    if digest(pin) != record["reference_model_identity_sha256"]:
        raise ValueError("historical model identity differs from its recorded digest")
    state = assets / ".runtime/ij-slm-1.0"
    state.mkdir(parents=True, exist_ok=True)
    run_id = "ijslm-admission-" + uuid4().hex
    target = state / ("admission-" + candidate)
    # The shared, fixed host asset root keeps another worktree from rescheduling
    # this diagnostic. Preserve interrupted artifacts for explicit reconciliation.
    target.mkdir(exist_ok=False)
    alias = "ijslm-candidate-" + candidate.lower()
    report = {
        "version": "IJ-SLM-ADMISSION-DIAGNOSTIC-1", "git_sha": git_head(),
        "run_id": run_id, "candidate": candidate, "runtime": identity,
        "handoff_sha256": digest(handoff_root / HANDOFF), "sdk_version": sdk_version,
        "sdk_harness_sha256": digest(harness), "model_registry_sha256": digest(registry_path),
        "evidence_class": "runtime admission diagnostic",
        "formal_admission": "NOT_RUN", "formal_core_recorded": 0,
        "offline_egress": "BLOCKED", "gates": dict.fromkeys(GATES, "NOT_RUN"),
        "wire": [], "sdk": {},
    }
    report_path = target / "report.json"
    write_json(report_path, report)

    def send_for(client):
        return partial(request, client, alias, wire=report["wire"], disable_thinking=True)

    try:
        report["gates"]["artifact_identity"] = "PASS"
        with cpu_server(cpu_binary, model, port, target / "cpu.log", alias) as (client, build):
            report["cpu"] = {"engine_sha256": digest(cpu_binary), "build": build}
            report["gates"]["load"] = "PASS"
            report["gates"]["cpu_reference"] = "PASS" if chat_ok(send_for(client)) else "FAIL"
        write_json(report_path, report)
        with gpu_server(engines / "llama-server.exe", model, "vulkan", server_environment(),
                        target, port, "vulkan", True, alias=alias, mission_id="IJ-SLM-1.0",
                        lease_owner="slm-admission", runtime_session=run_id) as (client, launch):
            verify_launch(launch, identity)
            for field in ("host_sha256", "gpu_physical_sha256"):
                if launch["gpu_lease"][field] != gate["lease"][field]:
                    raise ValueError("Radeon lease does not match the handoff identity")
            report["gpu"] = launch
            write_json(report_path, report)
            test_gpu(send_for(client), report)
            write_json(report_path, report)
            sdk_dir = target / "sdk"
            sdk_dir.mkdir()
            report["sdk"] = asyncio.run(sdk_probes(client, alias, sdk_dir, harness))
        launch_record = target / "launch.json"
        write_json(launch_record, {**report["gpu"], "status": "PASS"})
        passed = verify_gpu({"gpu_launch": launch_record,
                             "gpu_counters": target / report["gpu"]["counter_file"]}, "vulkan")
        report["gates"]["gpu_execution"] = "PASS" if passed else "FAIL"
        portable = target / "portable"
        portable.mkdir()
        report["sha256"] = {
            name + ".gz": archive(target / name, portable / (name + ".gz"))
            for name in (report["gpu"]["counter_file"], report["gpu"]["trace_file"])
        }
        report["diagnostic_coverage"] = "PASS"
        check_text(canonical(report))
        write_json(portable / "report.json", report)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        report["diagnostic_coverage"] = "BLOCKED"
        report["interruption_type"] = type(error).__name__
        raise
    finally:
        write_json(report_path, report)
    return report


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("candidate", choices=tuple("ABDFG"))
    cli.add_argument("--assets", type=Path, required=True)
    cli.add_argument("--handoff-root", type=Path, required=True)
    cli.add_argument("--port", type=int, default=18754)
    args = cli.parse_args()
    report = execute(args.candidate, args.assets.resolve(), args.handoff_root.resolve(), args.port)
    print(report["candidate"], report["diagnostic_coverage"], report["gates"],
          {gate: row["status"] for gate, row in report["sdk"].items()})


if __name__ == "__main__":
    main()
