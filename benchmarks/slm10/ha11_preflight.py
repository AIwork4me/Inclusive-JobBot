"""Run four matched synthetic diagnostic profiles on Original LFM3 and Radeon."""

import argparse
import asyncio
from importlib.metadata import version
import json
from pathlib import Path
from uuid import uuid4

from google.antigravity import bin as sdk_bin

from audit import write_evidence
from benchmarks.root_cause.generation_capture import CaptureClient
from evaluation.aeve.archive import digest
from evaluation.aeve.gpu_handoff import HANDOFF, require_handoff
from evaluation.aeve.runtime import ROOT, fingerprint
from scripts.tools.verify_ij06_evidence import verify_gpu

from . import lfm3_ha_admission as ha, tc_execution as tc
from .admission import git_head
from .ha11_sdk import CORRECTED, ORIGINAL, TOOL_CHOICE_ONLY, execute_sdk
from .native_diagnostics import OBSERVER_ENGINE
from .tc_capability_replay import assess
from .tc_v3 import CONFIG, FIRST_SEED, LANGUAGES, PROMPTS, case_data


DIRECT = "DIRECT"
PROFILES = (DIRECT, ORIGINAL, TOOL_CHOICE_ONLY, CORRECTED)
FLAGS = (*ha.FLAGS, "--seed", str(FIRST_SEED), "--temp", "0",
         "--chat-template-kwargs", '{"enable_thinking":false}')


class FixedChatClient(CaptureClient):
    def post(self, path, body):
        if path != "/v1/chat/completions":
            raise ValueError("Fixed benchmark sessions only accept chat completions")
        ha.admission_route(json.dumps(body))
        return super().post(path, body)


def checked_runtime(assets):
    registry = json.loads((ha.ATLAS / "MODEL_ADAPTER_REGISTRY.json").read_bytes())
    pin = json.loads((ha.ATLAS / "EVIDENCE_MANIFEST.json").read_bytes())["runtime"]
    base = registry["base"]
    model = ha.pinned_file(assets, base["asset"] | {"local_asset": base["local_asset"]},
                           sha_key="expected_sha256", size_key="size")
    engine = assets / OBSERVER_ENGINE
    binaries = {p.name: digest(p) for p in engine.iterdir() if p.suffix in {".exe", ".dll"}}
    harness = Path(sdk_bin.__file__).with_name("localharness.exe")
    if (binaries != pin["binary_sha256"] or version("google-antigravity") != pin["sdk"]
            or digest(harness) != pin["harness_pin_sha256"]):
        raise ValueError("Pinned LFM3 engine or SDK identity differs")
    return registry, pin, model, engine / "llama-server.exe", harness


def trial(client, public, world, profile, trial_id, target, harness, *, seed=FIRST_SEED, track=None):
    if world["external_approval"] is not None or not set(public["tools"]) <= tc.TOOLS.keys():
        raise ValueError("Preflight requires the synthetic deny-write sandbox")
    sandbox = tc.Sandbox(public, world)
    before = sandbox.snapshot()
    if profile == DIRECT:
        result = tc.direct_trial(client, ha.ALIAS, public, sandbox, trial_id, seed=seed)
        track = "direct_first"
    else:
        controls = None
        if track is not None:
            stream = track == "sdk_streaming"
            controls = tc.provider_profile(stream, seed)
            if stream:
                controls["stream_options"] = {"include_usage": True}
        track = track or "sdk_streaming"
        result = asyncio.run(execute_sdk(
            client, ha.ALIAS, tc.public_tools(public), sandbox.allowed_tools - {"commit_release"},
            lambda proposal, turn, wire: sandbox.execute(proposal, turn, wire[turn]),
            public["prompt"], CONFIG["system"], trial_id, target, harness, profile=profile,
            model_budget=CONFIG["max_model_calls"], tool_budget=CONFIG["max_tool_calls"],
            token_budget=CONFIG["max_completion_tokens"], provider_controls=controls,
        ))
    return result | {"trial_id": trial_id, "case_id": public["case_id"], "track": track,
                     "seed": seed, "calls": sandbox.calls, "before": before, "after": sandbox.snapshot()}


def run(assets, output, port):
    registry, pin, model, binary, harness = checked_runtime(assets)
    cases = [case_data(family, LANGUAGES[i % len(LANGUAGES)], "HA-SCOPE-V1", 0)
             for i, family in enumerate(PROMPTS)]
    old = json.loads((ha.ATLAS / "SDK_ACTION_PHASE_PREFLIGHT.json").read_bytes())
    dataset_sha = fingerprint(cases)
    if {arm["dataset_sha256"] for arm in old["profiles"].values()} != {dataset_sha}:
        raise ValueError("New diagnostic comparison must reuse the exact preflight scope inputs")

    output.mkdir(parents=True, exist_ok=False)
    run_id = "lfm3-ha11-preflight-" + uuid4().hex
    handoff = require_handoff(ROOT)
    trace = output / "native.jsonl"
    report = {
        "run_id": run_id, "git_sha": git_head(), "runtime": pin, "base": registry["base"]["asset"],
        "backend": "vulkan", "weights": "Original", "flags": list(FLAGS), "seed": FIRST_SEED,
        "dataset_sha256": dataset_sha, "handoff_sha256": digest(ROOT / HANDOFF),
        "evidence_class": "real Radeon and SDK supplemental synthetic diagnostic",
        "registered_m4_trials": 0, "formal_core_trials": 0, "gpu_execution": "NOT_RUN", "results": [],
    }
    write_evidence(output / "report.json", report)
    with ha.server(binary, model, None, port, output, pin, run_id, handoff, launch_flags=FLAGS,
                   trace_path=trace, sampler_seconds=3600) as (_, launch):
        client = FixedChatClient(port, trace, max_nonstream_calls=12)
        for index, (public, world, oracle) in enumerate(cases):
            orders = ((0, 1, 3, 2), (1, 2, 0, 3), (2, 3, 1, 0), (3, 0, 2, 1))
            for position in orders[index % len(orders)]:
                profile = PROFILES[position]
                trial_id = fingerprint([run_id, public["case_id"], profile])
                result = trial(client, public, world, profile, trial_id, output / trial_id, harness)
                assessment = assess(result, oracle, "BLOCKED")
                target = output / f"{trial_id}.json"
                write_evidence(target, result)
                row = {
                    "case_id": public["case_id"], "family": public["family"], "profile": profile,
                    "trial_id": trial_id, "capture_sha256": digest(target),
                    "failure_type": (result["failure"] or {}).get("type"),
                    "requests": len(result["wire"]),
                    "native_requests": sum(event.get("native_evidence", {}).get("status") == "PASS"
                                           for event in result["wire"]),
                    "wire_validations": [event.get("status") for event in result["wire"]],
                    "callback_bindings": [event["status"] for event in result.get("callbacks", [])],
                    "executed_calls": len(result["calls"]), "assessment": assessment,
                }
                report["results"].append(row)
                write_evidence(output / "report.json", report)
                print(row["family"], profile, row["native_requests"], row["executed_calls"],
                      assessment["metrics"]["EXECUTION_PROCESS_CORRECTNESS"], flush=True)
    launch_path = output / "launch.json"
    write_evidence(launch_path, launch)
    counters = output / "gpu.jsonl"
    report["gpu_execution"] = "PASS" if verify_gpu(
        {"gpu_launch": launch_path, "gpu_counters": counters}, "vulkan") else "BLOCKED"
    report["private_sha256"] = {path.name: digest(path) for path in (launch_path, counters, trace)}
    write_evidence(output / "report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, default=18757)
    args = parser.parse_args()
    result = run(args.assets.resolve(strict=True), args.output.resolve(), args.port)
    print(result["gpu_execution"], len(result["results"]), result["run_id"])
    return 0 if result["gpu_execution"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
