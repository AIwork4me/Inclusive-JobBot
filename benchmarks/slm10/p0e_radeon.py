"""Run the independent P0-E development panel under the shared Radeon lease."""

import argparse
import asyncio
from importlib.metadata import version
import json
from pathlib import Path
from uuid import uuid4

from evaluation.aeve.archive import check_text, digest
from evaluation.aeve.runtime import ROOT, canonical, fingerprint

from . import p0e_development_preflight as panel
from .planning_matched_executor import execute_trial

CANDIDATES = ("A", "B", "D")
PROFILES = ("DIRECT_NATIVE", "SDK_NATIVE")
SEED = 7117


def planned():
    return [{"control": control, "profile": profile, "seed": SEED, **panel.control_identity(control)}
            for control in panel.public_cases() for profile in PROFILES]


def run(candidate, assets, output, port):
    from google.antigravity import bin as sdk_bin

    from audit import write_evidence
    from benchmarks.competitive_slm.tc_v2_candidate import server_environment, verify_launch, verify_runtime
    from benchmarks.root_cause.gpu_lease import _named_lease
    from benchmarks.root_cause.historical_replay import gpu_server
    from evaluation.aeve.gpu_handoff import HANDOFF, require_handoff
    from scripts.tools.verify_ij06_evidence import verify_gpu

    from .admission import archive, git_head
    from .native_diagnostics import BASE_ENGINE, OBSERVER_ENGINE, OBSERVER_HASHES
    from .portable import portable
    from .sdk_adapter_development import CONTROLLER_LOCK, require_idle_controller

    with _named_lease(CONTROLLER_LOCK):
        require_idle_controller()
        handoff = require_handoff(ROOT)
        model_spec = json.loads((ROOT / "atlas/slm/v1.0/model_registry.json").read_bytes())["models"][candidate]
        model = (assets / model_spec["local_asset"]).resolve(strict=True)
        runtime = verify_runtime(candidate, model, assets / BASE_ENGINE, require_prior_admission=False)
        sdk_version = version("google-antigravity")
        if sdk_version != "0.1.24" or runtime["model"]["model_sha256"] != model_spec["asset"]["expected_sha256"]:
            raise ValueError("preflight model or SDK differs from the registered identity")
        harness = Path(sdk_bin.__file__).with_name("localharness.exe").resolve(strict=True)
        engine = assets / OBSERVER_ENGINE
        hashes = {f.name: digest(f) for f in engine.iterdir() if f.suffix in {".dll", ".exe"}}
        if hashes != runtime["engine"]["dll_sha256"] | OBSERVER_HASHES:
            raise ValueError("preflight engine differs from the registered native observer")
        run_id = "ijslm-p0e-" + uuid4().hex
        alias = "ijslm-candidate-" + candidate.lower()
        roster = planned()
        cases = panel.public_cases()
        output.mkdir(parents=True, exist_ok=False)
        private = output / "report.json"
        report = {"version": panel.VERSION, "run_id": run_id, "candidate": candidate, "git_sha": git_head(),
                  "model": runtime["model"], "engine_build": runtime["engine"]["build"], "engine_sha256": hashes,
                  "backend": "vulkan", "sdk_version": sdk_version, "sdk_harness_sha256": digest(harness),
                  "handoff_sha256": digest(ROOT / HANDOFF), "roster_sha256": fingerprint(roster),
                  "sources": {name: digest(Path(__file__).with_name(name)) for name in
                              ("p0e_radeon.py", "p0e_development_preflight.py", "planning_matched_executor.py",
                               "planning_matched_assessment.py", "multitool_stateful_transport.py",
                               "multitool_stateful.py")},
                  "gpu_execution": "NOT_RUN", "formal_trial_attribution": 0,
                  "scope": "independent synthetic Radeon development", "results": []}
        write_evidence(private, report)
        with gpu_server(engine / "llama-server.exe", model, "vulkan", server_environment(), output, port,
                        "vulkan", True, alias=alias, mission_id="IJ-SLM-1.0", lease_owner="p0e-development",
                        runtime_session=run_id) as (client, launch):
            verify_launch(launch, runtime)
            if client.trace_path is None or any(
                    launch["gpu_lease"][key] != handoff["lease"][key]
                    for key in ("host_sha256", "gpu_physical_sha256")):
                raise ValueError("preflight lacks the verified Radeon lease or native observer")
            report["gpu"] = launch
            write_evidence(output / "launch.json", launch | {"status": "PASS"})
            for item in roster:
                control, profile = item["control"], item["profile"]
                trial_id = fingerprint([run_id, item])
                service = panel.build_service(control, output / "state" / trial_id)
                trace = asyncio.run(execute_trial(
                    client, alias, cases[control], service, trial_id, panel.PROFILES[profile],
                    target=output / "sessions" / trial_id, harness=harness, seed=SEED,
                    runtime_profile=profile, parallel_reads=control == "parallel"))
                assessment = panel.assess(control, trace)
                request_rows = [row for row in trace["wire"] if "provider_request_id" in row]
                native = bool(request_rows) and all(row.get("native_evidence", {}).get("status") == "PASS"
                                                    for row in request_rows)
                report["results"].append(item | {"trace": trace, "assessment": assessment,
                                                "native_capture": "PASS" if native else "BLOCKED",
                                                "state_readback": panel.verify_state_readback(service, trace)})
                write_evidence(private, report)
                print(candidate, control, profile, assessment["status"], flush=True)

        counter = output / launch["counter_file"]
        trace_path = output / launch["trace_file"]
        report["gpu_execution"] = "PASS" if verify_gpu(
            {"gpu_launch": output / "launch.json", "gpu_counters": counter}, "vulkan") else "FAIL"
        evidence = [report["gpu_execution"]]
        for row in report["results"]:
            evidence.append(row["native_capture"])
            if row["state_readback"]["applicable"]:
                evidence.append(row["state_readback"]["status"])
        report["development_execution"] = ("FAIL" if "FAIL" in evidence else
                                           "PASS" if set(evidence) == {"PASS"} else "BLOCKED")
        report["native_private_sha256"] = digest(trace_path)
        write_evidence(private, report)
        destination = output / "portable"
        destination.mkdir()
        report["artifacts"] = {
            "gpu.jsonl.gz": archive(counter, destination / "gpu.jsonl.gz"),
            "native.jsonl.gz": archive(trace_path, destination / "native.jsonl.gz", redact=True),
        }
        safe = portable(report) | {"private_report_sha256": digest(private)}
        check_text(canonical(safe))
        write_evidence(destination / "report.json", safe)
        return 0 if report["development_execution"] == "PASS" else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", choices=CANDIDATES)
    parser.add_argument("--assets", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--port", type=int, default=18754)
    parser.add_argument("--dispatch", action="store_true")
    args = parser.parse_args()
    if not args.dispatch:
        print(json.dumps({"formal_trial_attribution": 0, "planned_per_model": len(planned()), "physical": "NOT_RUN"}))
        return 0
    if not (args.candidate and args.assets and args.output):
        parser.error("physical preflight requires candidate, assets and a fresh output directory")
    return run(args.candidate, args.assets.resolve(), args.output.resolve(), args.port)


if __name__ == "__main__":
    raise SystemExit(main())
