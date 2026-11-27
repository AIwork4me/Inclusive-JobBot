"""Measure Radeon SSE delivery and check the revised SDK wire limit."""

import argparse
import asyncio
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
import json
from time import perf_counter
from urllib.request import Request

from google.antigravity import Agent, LocalOpenAIAgentConfig, bin as sdk_bin, types
from google.antigravity.hooks import policy

from audit import write_evidence
from benchmarks.competitive_slm.tc_v2_candidate import server_environment, verify_launch, verify_runtime
from benchmarks.ij06_sdk.wire_boundary import ApprovalQueue, MAX_BODY, wire_boundary
from benchmarks.root_cause.historical_replay import gpu_server
from evaluation.aeve.archive import check_text, digest
from evaluation.aeve.gpu_handoff import require_handoff
from evaluation.aeve.runtime import ROOT, canonical, fingerprint
from scripts.tools.verify_ij06_evidence import verify_gpu

from .admission import archive, git_head
from .native_diagnostics import BASE_ENGINE, OBSERVER_ENGINE, OBSERVER_HASHES, observe_wire, replay_budget
from .portable import portable
from .tc_execution import provider_profile
from .tc_v3 import FIRST_SEED

HEADERS = {"Content-Type": "application/json"}
EXPECTED = {"text": "alpha" + " alpha" * 1899}


def native_stream(client, raw, trial_id):
    req = Request(client.base_url + "/v1/chat/completions", data=raw, headers=HEADERS)
    start = perf_counter()
    first = None
    delivery = []
    size = 0
    with client.opener.open(req, timeout=120) as reply:
        media = reply.headers.get("Content-Type", "")
        if not media.startswith("text/event-stream"):
            raise ValueError("native transport control received a different media type")
        while line := reply.readline(MAX_BODY + 1):
            size += len(line)
            if size > MAX_BODY:
                raise ValueError("native transport crossed its total resource boundary")
            delivery.append(line)
            if first is None and line.startswith(b"data: {"):
                part = json.loads(line[6:])
                choices = part.get("choices") or []
                if choices and (choices[0].get("delta", {}).get("content") or
                                choices[0].get("delta", {}).get("reasoning_content")):
                    first = round((perf_counter() - start) * 1000, 3)
    data = b"".join(delivery)
    event = {"trial_id": trial_id, "provider_request": raw.decode(), "provider_request_sha256": sha256(raw).hexdigest(),
             "response": data.decode(), "response_sha256": sha256(data).hexdigest(), "response_capture_complete": True,
             "http_status": 200, "content_type": media, "response_bytes": len(data),
             "native_first_content_delta_ms": first, "wall_ms": round((perf_counter() - start) * 1000, 3)}
    observe_wire(client, event)
    return event


async def large_sdk(client, alias, target, harness, trial_id):
    wire, chunks = [], []
    first = None
    start = perf_counter()
    for name in ("work", "save", "app"):
        (target / name).mkdir()
    schema = {"type": "object", "additionalProperties": False, "required": ["text"],
              "properties": {"text": {"const": EXPECTED["text"]}}}

    def constrained(raw):
        body = json.loads(raw) | provider_profile(True, FIRST_SEED)
        body.update(max_completion_tokens=2400, stream_options={"include_usage": True},
                    response_format={"type": "json_schema", "json_schema": {"name": "transport", "schema": schema}})
        return canonical(body)

    with wire_boundary(client.base_url, ApprovalQueue(), wire, trial_id=trial_id,
                       observe=lambda event: observe_wire(client, event), max_stream_bytes=1 << 20,
                       adapt_request=constrained) as boundary:
        config = LocalOpenAIAgentConfig(
            model=alias, base_url=boundary.url, system_instructions="Return the synthetic JSON transport payload.",
            capabilities=types.CapabilitiesConfig(enabled_tools=[], enable_subagents=False,
                                                  agent_behavior=types.AgentBehavior.MINIMAL),
            tools=[], policies=[policy.deny_all()], workspaces=[str(target / "work")],
            save_dir=str(target / "save"), app_data_dir=str(target / "app"),
            mcp_servers=[], subagents=[], skills_paths=[],
            budget_config=types.BudgetConfig(max_model_calls=1, max_tool_calls=1, max_output_tokens=2400),
            retry_config=types.RetryConfig(api_retry=types.ModelAPIRetryConfig(max_retries=0),
                                          model_output_retry=types.ModelOutputRetryConfig(max_retries=0)),
            env={"ANTIGRAVITY_HARNESS_PATH": str(harness), "OTEL_SDK_DISABLED": "true",
                 "HTTP_PROXY": "", "HTTPS_PROXY": "", "ALL_PROXY": "", "NO_PROXY": "localhost,127.0.0.1",
                 "GEMINI_API_KEY": "", "GOOGLE_API_KEY": "", "OPENAI_API_KEY": "", "GOOGLE_APPLICATION_CREDENTIALS": ""},
        )
        failure = None
        try:
            async with asyncio.timeout(100):
                async with Agent(config) as agent:
                    response = await agent.chat("Produce the exact synthetic transport payload specified by the JSON schema.")
                    async for part in response:
                        if part and first is None:
                            first = round((perf_counter() - start) * 1000, 3)
                        chunks.append(part)
        except (TimeoutError, ValueError, types.AntigravityConnectionError, types.AntigravityExecutionError,
                types.AntigravityValidationError) as exc:
            failure = str(exc)
    try:
        success = json.loads("".join(chunks)) == EXPECTED
    except ValueError:
        success = False
    replay = replay_budget(wire[0]) if len(wire) == 1 and wire[0].get("response_capture_complete") else {}
    criterion = (success and not failure and replay.get(str(1 << 19), {}).get("status") == "FAIL"
                 and replay.get(str(1 << 20), {}).get("status") == "PASS")
    return {"status": "PASS" if criterion else "FAIL", "sdk_visible_text_ms_buffered": first,
            "sdk_task_wall_ms": round((perf_counter() - start) * 1000, 3), "wire": wire,
            "answer_matches_payload": success, "failure": failure, "same_byte_limit_replay": replay}


def run(assets, target, port):
    require_handoff(ROOT)
    target.mkdir()
    model_record = json.loads((ROOT / "atlas/slm/v1.0/model_registry.json").read_bytes())["models"]["D"]
    model = (assets / model_record["local_asset"]).resolve(strict=True)
    runtime = verify_runtime("D", model, assets / BASE_ENGINE, require_prior_admission=False)
    engine = assets / OBSERVER_ENGINE
    hashes = {p.name: digest(p) for p in engine.iterdir() if p.suffix in {".dll", ".exe"}}
    if hashes != runtime["engine"]["dll_sha256"] | OBSERVER_HASHES:
        raise ValueError("transport runtime differs from pinned files")
    sdk = version("google-antigravity")
    if sdk != "0.1.24":
        raise ValueError("unregistered SDK version")
    harness = Path(sdk_bin.__file__).with_name("localharness.exe")
    alias = "ijslm-candidate-d"
    raw = canonical({"model": alias, "messages": [{"role": "user", "content": "Return JSON with code CONTROL."}],
                     **provider_profile(True, FIRST_SEED), "max_completion_tokens": 96,
                     "stream_options": {"include_usage": True}})
    report = {"version": "IJ-SLM-SDK-TRANSPORT/1.0", "git_sha": git_head(), "candidate": "D",
              "formal_trials": 0, "engine_sha256": hashes, "model": runtime["model"], "sdk": sdk,
              "harness_sha256": digest(harness), "variants": {}, "artifacts": {}}
    for observe in (False, True):
        tag = "on" if observe else "off"
        output = target / tag
        output.mkdir()
        trial_id = fingerprint([target.name, tag, sha256(raw).hexdigest()])
        with gpu_server(engine / "llama-server.exe", model, "vulkan", server_environment(), output, port, tag, observe,
                        alias=alias, mission_id="IJ-SLM-1.0", lease_owner="sdk-transport-development",
                        runtime_session=trial_id) as (client, launch):
            verify_launch(launch, runtime, require_trace=observe)
            write_evidence(output / "launch.json", launch | {"status": "PASS"})
            report["variants"][tag] = {"launch": launch, "stream": native_stream(client, raw, trial_id)}
            if observe:
                report["large_sdk_control"] = asyncio.run(large_sdk(client, alias, output, harness, trial_id + "-sdk"))
        counters = output / launch["counter_file"]
        report["variants"][tag]["gpu_execution"] = "PASS" if verify_gpu({"gpu_launch": output / "launch.json",
                                                                           "gpu_counters": counters}, "vulkan") else "FAIL"
        report["artifacts"][tag + "-gpu.jsonl.gz"] = archive(counters, target / (tag + "-gpu.jsonl.gz"))
    first, second = (report["variants"][tag]["stream"] for tag in ("off", "on"))
    flags = [report["variants"][tag]["gpu_execution"] for tag in ("off", "on")]
    report["observer_visible_equivalence"] = (
        "BLOCKED" if any(flag != "PASS" for flag in flags) or any("parsed_response" not in r for r in (first, second))
        else "PASS" if all(first.get(key) == second.get(key) for key in (
            "provider_request_sha256", "parsed_response", "usage", "provider_stop_reason")) else "FAIL")
    check_text(canonical(portable(report)))
    write_evidence(target / "private.json", report)
    write_evidence(target / "report.json", portable(report) | {"private_sha256": digest(target / "private.json")})
    print(report["observer_visible_equivalence"], report["large_sdk_control"]["status"], flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--port", type=int, default=18754)
    args = parser.parse_args()
    run(args.assets.resolve(), args.output.resolve(), args.port)


if __name__ == "__main__":
    main()
