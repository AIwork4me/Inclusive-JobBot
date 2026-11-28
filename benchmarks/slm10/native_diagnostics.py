"""Run synthetic SDK and Direct controls on the pinned Radeon workstation."""

import argparse
import asyncio
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from uuid import uuid4

from google.antigravity import bin as harness_package

from audit import write_evidence
from benchmarks.competitive_slm.tc_v2_candidate import server_environment, verify_launch, verify_runtime
from benchmarks.ij06_sdk.qualify import execute_case
from benchmarks.ij06_sdk.wire_boundary import assemble_reply
from benchmarks.root_cause.generation_capture import correlate, protocol_reply
from benchmarks.root_cause.historical_replay import gpu_server
from evaluation.aeve.archive import digest
from evaluation.aeve.gpu_handoff import HANDOFF, require_handoff
from evaluation.aeve.runtime import ROOT
from model_gateway import GatewayError
from model_gateway.openai_protocol import MAX_WIRE_BYTES
from scripts.tools.verify_ij06_evidence import verify_gpu

from .admission import archive, git_head
from .portable import portable

BASE_ENGINE = ".tools/ij07-toolchoice-p4b-vulkan"
OBSERVER_ENGINE = ".tools/ijslm-native-observer-vulkan-v2"
OBSERVER_PATCH = "patches/ij07/llama-b12359-sdk-native-observer.patch"
REPAIRED_STREAM_LIMIT = 2 * MAX_WIRE_BYTES
OBSERVER_HASHES = {
    "llama-server.exe": "cf5a25e9237eca6e442be87aaa19d1ceffc3bf1520c54b113d0ffdda7362d256",
    "llama-server-impl.dll": "4696947cdbdae100ba54c7a5aec2ab379a26cc50ab844c65fa1f1b693352cf51",
}


def observe_wire(client, event):
    request = json.loads(event["provider_request"])
    try:
        raw = event["response"].encode("utf-8")
        decoded = protocol_reply(raw, request.get("stream", False) and event["http_status"] == 200)
        completion = decoded["id"]
        choices = decoded["choices"]
        event.update(completion_id=completion, parsed_response=choices,
                     provider_stop_reason=choices[0]["finish_reason"], usage=decoded.get("usage"))
        if client.trace_path is not None:
            source = correlate(client.read_trace(), decoded, request.get("stream", False))
            if not source.get("rendered_prompt"):
                raise ValueError("rendered prompt missing from native capture")
            event["source_generation"] = source
    except (KeyError, TypeError, ValueError) as failure:
        event["native_evidence"] = {"status": "BLOCKED", "reason": str(failure)}
    else:
        event["native_evidence"] = {"status": "PASS" if client.trace_path is not None else "NOT_RUN"}


def direct(client, body, trial_id):
    raw_request = json.dumps(body, ensure_ascii=False).encode("utf-8")
    status, media, raw = client.post("/v1/chat/completions", body)
    event = {"trial_id": trial_id, "provider_request_id": uuid4().hex, "provider_request": raw_request.decode(),
             "provider_request_sha256": sha256(raw_request).hexdigest(), "http_status": status, "content_type": media,
             "response": raw.decode(), "response_sha256": sha256(raw).hexdigest()}
    observe_wire(client, event)
    return event


def replay_budget(event):
    raw = event["response"].encode("utf-8")
    if sha256(raw).hexdigest() != event["response_sha256"] or not event["response_capture_complete"]:
        raise ValueError("same-byte replay requires a complete matching capture")
    results = {}
    for limit in (MAX_WIRE_BYTES, REPAIRED_STREAM_LIMIT):
        try:
            reply = assemble_reply(event["content_type"], raw, max_stream_bytes=limit)
        except (ValueError, GatewayError) as failure:
            results[str(limit)] = {"status": "FAIL", "type": type(failure).__name__, "message": str(failure)}
        else:
            results[str(limit)] = {"status": "PASS", "finish_reason": reply.finish_reason}
    return results


def run(candidate, assets, output, port, profile):
    gate = require_handoff(ROOT)
    record = json.loads((ROOT / "atlas/slm/v1.0/model_registry.json").read_bytes())["models"][candidate]
    model = (assets / record["local_asset"]).resolve(strict=True)
    baseline = assets / BASE_ENGINE
    identity = verify_runtime(candidate, model, baseline, require_prior_admission=False)
    if identity["model"]["model_sha256"] != record["asset"]["expected_sha256"]:
        raise ValueError("model does not match the SLM registry")
    sdk_version = version("google-antigravity")
    if sdk_version != "0.1.24":
        raise ValueError("unexpected Antigravity SDK version")
    harness = Path(harness_package.__file__).with_name("localharness.exe")
    engine = baseline if profile.startswith("ag02-") else assets / OBSERVER_ENGINE
    engine_hashes = {file.name: digest(file) for file in engine.iterdir() if file.suffix in {".dll", ".exe"}}
    baseline_hashes = identity["engine"]["dll_sha256"] | {"llama-server.exe": identity["engine"]["exe_sha256"]}
    runtime_changes = {key for key in engine_hashes.keys() | baseline_hashes.keys()
                       if engine_hashes.get(key) != baseline_hashes.get(key)}
    expected_changes = {} if engine == baseline else OBSERVER_HASHES
    if runtime_changes != expected_changes.keys() or any(engine_hashes[key] != value
                                                         for key, value in expected_changes.items()):
        raise ValueError("observer engine differs from the pinned package")
    run_id = "ijslm-native-" + uuid4().hex
    output.mkdir(parents=True, exist_ok=False)
    report = {
        "run_id": run_id, "git_sha": git_head(), "candidate": candidate, "profile": profile,
        "engine_sha256": engine_hashes, "baseline_runtime": identity,
        "observer_patch_sha256": digest(ROOT / OBSERVER_PATCH) if expected_changes else None,
        "handoff_sha256": digest(ROOT / HANDOFF), "sdk_version": sdk_version, "sdk_harness_sha256": digest(harness),
        "evidence_class": "synthetic physical development diagnostic", "formal_core_recorded": 0,
        "gpu_execution": "NOT_RUN", "cases": {},
    }
    private = output / "report.json"
    write_evidence(private, report)
    alias = "ijslm-candidate-" + candidate.lower()
    observe = profile == "native-on"
    limit = MAX_WIRE_BYTES if profile == "ag02-original" else REPAIRED_STREAM_LIMIT
    with gpu_server(engine / "llama-server.exe", model, "vulkan", server_environment(), output, port,
                    "vulkan", observe, alias=alias, mission_id="IJ-SLM-1.0",
                    lease_owner="slm-native-development", runtime_session=run_id) as (client, launch):
        verify_launch(launch, identity, require_trace=observe)
        for field in ("host_sha256", "gpu_physical_sha256"):
            if launch["gpu_lease"][field] != gate["lease"][field]:
                raise ValueError("Radeon lease differs from the SLM handoff")
        report.update(gpu=launch, max_stream_bytes=limit)
        write_evidence(output / "launch.json", {**launch, "status": "PASS"})
        for case in (("AG-02",) if profile.startswith("ag02-") else ("AG-04", "AG-12")):
            result = asyncio.run(execute_case(
                client.base_url, alias, output / case, harness, case, trial_id=run_id + "-" + case,
                observe=lambda event: observe_wire(client, event), max_stream_bytes=limit,
            ))
            report["cases"][case] = result
            write_evidence(private, report)
            print(candidate, profile, case, result["status"], flush=True)
        if profile.startswith("ag02-"):
            event, = report["cases"]["AG-02"]["wire"]
            if event.get("response_capture_complete"):
                report["same_byte_replay"] = replay_budget(event)
        else:
            positive = report["cases"]["AG-04"]["wire"][0]
            body = json.loads(positive["provider_request"]) | {"seed": 7107, "temperature": 0, "cache_prompt": False}
            for mode in (False, True):
                name = "AG-04-direct-" + ("stream" if mode else "json")
                report["cases"][name] = direct(client, {**body, "stream": mode}, run_id + "-" + name)
            if candidate == "A":
                historical = ROOT / "evidence/IJSLM/admission/A/report.json"
                prior = json.loads(historical.read_bytes())["wire"]
                body = next(row["request"] for row in prior if row["request"].get("tools")
                            and not row["request"].get("stream"))
                for mode in (False, True):
                    name = "historical-balance-" + ("stream" if mode else "json")
                    report["cases"][name] = direct(client, {**body, "stream": mode}, run_id + "-" + name)
    counters = output / launch["counter_file"]
    report["gpu_execution"] = "PASS" if verify_gpu({"gpu_launch": output / "launch.json", "gpu_counters": counters},
                                                   "vulkan") else "FAIL"
    report["raw_gpu_counter_sha256"] = digest(counters)
    write_evidence(private, report)
    published = output / "portable"
    published.mkdir()
    report["artifacts"] = {"gpu.jsonl.gz": archive(counters, published / "gpu.jsonl.gz")}
    if observe:
        trace = output / launch["trace_file"]
        report["private_native_trace_sha256"] = digest(trace)
        report["artifacts"]["native.jsonl.gz"] = archive(trace, published / "native.jsonl.gz", redact=True)
    write_evidence(published / "report.json", {**portable(report), "private_report_sha256": digest(private)})
    return report


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("candidate", choices=("A", "B", "D"))
    cli.add_argument("--profile", choices=("ag02-original", "ag02-repaired", "native-on", "native-off"), required=True)
    cli.add_argument("--assets", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    cli.add_argument("--port", type=int, default=18754)
    args = cli.parse_args()
    if args.profile.startswith("ag02-") and args.candidate != "D":
        cli.error("AG-02 comparison is registered for Qwen3.5")
    report = run(args.candidate, args.assets.resolve(), args.output.resolve(), args.port, args.profile)
    print(report["run_id"], "GPU", report["gpu_execution"])
    return 0 if report["gpu_execution"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
