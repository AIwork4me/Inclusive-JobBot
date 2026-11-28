"""Execute a TC-V3 development trajectory using the real Direct or SDK loop."""

import argparse
import asyncio
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from uuid import uuid4

from google.antigravity import Agent, LocalOpenAIAgentConfig, bin as sdk_bin, types
from google.antigravity.hooks import policy
from jsonschema import Draft202012Validator

from audit import write_evidence
from benchmarks.competitive_slm.tc_v2_candidate import server_environment, verify_launch, verify_runtime
from benchmarks.ij06_sdk.wire_boundary import ApprovalQueue, assemble_reply, wire_boundary
from benchmarks.root_cause.historical_replay import gpu_server
from evaluation.aeve.archive import digest
from evaluation.aeve.gpu_handoff import HANDOFF, require_handoff
from evaluation.aeve.runtime import ROOT, canonical
from model_gateway import GatewayError
from model_gateway.openai_protocol import parse_proposal
from model_gateway.strict_json import strict_object
from scripts.tools.verify_ij06_evidence import verify_gpu

from .admission import archive, git_head
from .native_diagnostics import (BASE_ENGINE, OBSERVER_ENGINE, OBSERVER_HASHES, REPAIRED_STREAM_LIMIT,
                                 direct, observe_wire)
from .portable import portable
from .tc_v3 import CONFIG, FIRST_SEED, HERE, PARAMETERS, TOOLS, verify_freeze

TRACKS = ("direct_first", "sdk_first", "sdk_streaming")
SCHEMA = Draft202012Validator(PARAMETERS)


def provider_profile(stream, seed):
    return {
        "stream": stream, "seed": seed, "temperature": CONFIG["temperature"],
        "max_completion_tokens": CONFIG["max_completion_tokens"], "cache_prompt": CONFIG["cache_prompt"],
        "chat_template_kwargs": {"enable_thinking": CONFIG["thinking"]},
        "parallel_tool_calls": True, "tool_choice": "auto",
    }


def public_tools(public):
    return [{"type": "function", "function": {"name": name, "description": TOOLS[name], "parameters": PARAMETERS}}
            for name in public["tools"]]


class Sandbox:
    """A fixture-backed local tool service with a fail-closed release boundary."""

    def __init__(self, public, world):
        self.allowed_tools = set(public["tools"])
        self.records = world["records"]
        self.approval = world["external_approval"]
        self.calls = []
        self.releases = {}
        self.seen = set()

    def snapshot(self):
        return {"releases": dict(self.releases), "external_approval": self.approval}

    def execute(self, proposal, turn, event):
        arguments = parse_proposal(proposal)
        if (len(self.calls) >= CONFIG["max_tool_calls"] or proposal.call_id in self.seen
                or proposal.name not in self.allowed_tools or not SCHEMA.is_valid(arguments)):
            decision, result = "DENIED", {"error": "call_contract"}
        elif proposal.name == "commit_release":
            decision, result = "DENIED", {"error": "external_approval_required"}
        else:
            decision = "EXECUTED"
            result = self.records.get(proposal.name, {}).get(arguments["reference"], {"error": "not_found"})
        self.seen.add(proposal.call_id)
        self.calls.append({
            "turn": turn, "call_id": proposal.call_id, "tool": proposal.name, "arguments": arguments,
            "arguments_raw": proposal.arguments_raw, "decision": decision, "result": result,
            "trial_id": event["trial_id"], "provider_request_id": event["provider_request_id"],
            "completion_id": event.get("completion_id"),
        })
        return result


def adapted_sse(content_type, response, event):
    """Deliver validated provider JSON to the SDK's streaming API without changing its payload."""
    sdk_request = json.loads(event["request"])
    if content_type.startswith("text/event-stream") or sdk_request.get("stream") is not True:
        return content_type, response
    envelope = json.loads(response)
    choice, = envelope["choices"]
    message = choice["message"]
    meta = {key: envelope[key] for key in ("id", "model", "created")}
    meta["object"] = "chat.completion.chunk"
    delta = {key: message[key] for key in ("role", "content", "reasoning_content") if message.get(key) is not None}
    if message.get("tool_calls"):
        delta["tool_calls"] = [dict(call, index=index) for index, call in enumerate(message["tool_calls"])]
    frames = [
        meta | {"choices": [{"index": 0, "delta": delta, "finish_reason": None}]},
        meta | {"choices": [{"index": 0, "delta": {}, "finish_reason": choice["finish_reason"]}]},
    ]
    if sdk_request.get("stream_options", {}).get("include_usage") and envelope.get("usage"):
        frames.append(meta | {"choices": [], "usage": envelope["usage"]})
    return "text/event-stream", b"".join(b"data: " + canonical(frame) + b"\n\n" for frame in frames) + b"data: [DONE]\n\n"


async def sdk_trial(client, alias, public, tool_service, trial_id, target, harness, *, stream, seed):
    approvals, wire, chunks = ApprovalQueue(), [], []
    tools = public_tools(public)
    settings = provider_profile(stream, seed)
    for name in ("work", "save", "app"):
        (target / name).mkdir(parents=True)

    def request_adapter(raw):
        if len(wire) > CONFIG["max_model_calls"]:
            raise ValueError("TC-V3 model request budget exhausted")
        body = dict(strict_object(raw)) | settings
        offered = {item["function"]["name"] for item in body.get("tools", [])}
        if offered != tool_service.allowed_tools:
            raise ValueError("SDK tool set differs from the public TC-V3 contract")
        body["tools"] = tools
        if stream:
            body["stream_options"] = {"include_usage": True}
        else:
            body.pop("stream_options", None)
        return canonical(body)

    def make_callback(name):
        def callback(reference: str) -> str:
            proposal = approvals.claim(name, {"reference": reference})
            matches = [(turn, event) for turn, event in enumerate(wire)
                       if proposal.call_id in event.get("parsed_tool_call_ids", ())]
            if len(matches) != 1:
                raise ValueError("SDK callback is missing unique wire provenance")
            turn, event = matches[0]
            return canonical(tool_service.execute(proposal, turn, event)).decode()

        callback.__name__ = name
        callback.__doc__ = TOOLS[name]
        return callback

    failure = None
    with wire_boundary(client.base_url, approvals, wire, trial_id=trial_id,
                       observe=lambda event: observe_wire(client, event), max_stream_bytes=REPAIRED_STREAM_LIMIT,
                       adapt_request=request_adapter, adapt_response=None if stream else adapted_sse) as endpoint:
        config = LocalOpenAIAgentConfig(
            model=alias, base_url=endpoint.url, system_instructions=CONFIG["system"],
            capabilities=types.CapabilitiesConfig(enabled_tools=[], enable_subagents=False,
                                                  agent_behavior=types.AgentBehavior.MINIMAL),
            tools=[make_callback(name) for name in public["tools"]],
            policies=[policy.deny_all(), *[policy.allow(name) for name in public["tools"]]],
            workspaces=[str(target / "work")], save_dir=str(target / "save"), app_data_dir=str(target / "app"),
            mcp_servers=[], subagents=[], skills_paths=[],
            budget_config=types.BudgetConfig(max_model_calls=CONFIG["max_model_calls"],
                                             max_tool_calls=CONFIG["max_tool_calls"],
                                             max_output_tokens=CONFIG["max_completion_tokens"]),
            retry_config=types.RetryConfig(api_retry=types.ModelAPIRetryConfig(max_retries=0),
                                          model_output_retry=types.ModelOutputRetryConfig(max_retries=0)),
            env={
                "ANTIGRAVITY_HARNESS_PATH": str(harness), "OTEL_SDK_DISABLED": "true",
                "HTTP_PROXY": "", "HTTPS_PROXY": "", "ALL_PROXY": "", "NO_PROXY": "localhost,127.0.0.1",
                "GEMINI_API_KEY": "", "GOOGLE_API_KEY": "", "OPENAI_API_KEY": "", "GOOGLE_APPLICATION_CREDENTIALS": "",
            },
        )
        try:
            async with asyncio.timeout(90):
                async with Agent(config) as agent:
                    reply = await agent.chat(public["prompt"])
                    async for chunk in reply:
                        chunks.append(chunk)
        except (OSError, TimeoutError, ValueError, types.AntigravityConnectionError, types.AntigravityExecutionError,
                types.AntigravityValidationError) as error:
            failure = {"type": type(error).__name__, "message": str(error)}
    return {"answer": "".join(chunks), "sdk_chunks": len(chunks), "wire": wire, "failure": failure}


def direct_trial(client, alias, public, tool_service, trial_id, *, seed):
    messages = [{"role": "system", "content": CONFIG["system"]}, {"role": "user", "content": public["prompt"]}]
    wire = []
    for turn in range(CONFIG["max_model_calls"]):
        event = direct(client, {"model": alias, "messages": messages, "tools": public_tools(public),
                                **provider_profile(False, seed)}, trial_id)
        wire.append(event)
        try:
            response = assemble_reply(event["content_type"], event["response"].encode())
            event["status"] = "PASS"
        except GatewayError as error:
            event["status"] = "FAIL"
            return {"wire": wire, "answer": None, "failure": {"type": type(error).__name__, "message": str(error)}}
        if not response.calls:
            return {"wire": wire, "answer": response.content, "failure": None}
        messages = [*messages, event["parsed_response"][0]["message"]]
        for proposal in response.calls:
            result = tool_service.execute(proposal, turn, event)
            messages.append({"role": "tool", "tool_call_id": proposal.call_id, "content": canonical(result).decode()})
    return {"wire": wire, "answer": None, "failure": {"type": "BudgetExceeded"}}


def execute_trial(client, alias, public, world, trial_id, track, target, harness, seed):
    service = Sandbox(public, world)
    before = service.snapshot()
    if track == "direct_first":
        result = direct_trial(client, alias, public, service, trial_id, seed=seed)
    else:
        result = asyncio.run(sdk_trial(client, alias, public, service, trial_id, target, harness,
                                       stream=track == "sdk_streaming", seed=seed))
    return {**result, "calls": service.calls, "before": before, "after": service.snapshot(), "trial_id": trial_id,
            "case_id": public["case_id"], "track": track, "seed": seed}


def development(candidate, assets, out, port):
    verify_freeze()
    handoff = require_handoff(ROOT)
    model_spec = json.loads((ROOT / "atlas/slm/v1.0/model_registry.json").read_bytes())["models"][candidate]
    model = (assets / model_spec["local_asset"]).resolve(strict=True)
    runtime = verify_runtime(candidate, model, assets / BASE_ENGINE, require_prior_admission=False)
    sdk_version = version("google-antigravity")
    if sdk_version != "0.1.24" or runtime["model"]["model_sha256"] != model_spec["asset"]["expected_sha256"]:
        raise ValueError("development model or SDK differs from the pinned identity")
    harness = Path(sdk_bin.__file__).with_name("localharness.exe")
    engine = assets / OBSERVER_ENGINE
    expected = (runtime["engine"]["dll_sha256"] | OBSERVER_HASHES)
    actual = {f.name: digest(f) for f in engine.iterdir() if f.suffix in {".dll", ".exe"}}
    if actual != expected:
        raise ValueError("TC-V3 native observer package differs from its pins")
    out.mkdir(parents=True, exist_ok=False)
    run_id = "ijslm-tcv3-dev-" + uuid4().hex
    alias = "ijslm-candidate-" + candidate.lower()
    report = {"run_id": run_id, "candidate": candidate, "git_sha": git_head(), "sdk_version": sdk_version,
              "harness_sha256": digest(harness), "engine_sha256": actual, "model": runtime["model"],
              "evidence_class": "synthetic physical development", "formal_core_recorded": 0,
              "dataset_manifest_sha256": digest(HERE / "manifest.json"), "handoff_sha256": digest(ROOT / HANDOFF),
              "results": []}
    report_path = out / "report.json"
    worlds = {row["case_id"]: row for row in records("development-worlds.jsonl")}
    cases = [row for row in records("development-public.jsonl")
             if row["case_id"].endswith("-000") and row["family"] in ("dependency", "authorization", "parallel")]
    with gpu_server(engine / "llama-server.exe", model, "vulkan", server_environment(), out, port, "vulkan", True,
                    alias=alias, mission_id="IJ-SLM-1.0", lease_owner="tc-v3-development",
                    runtime_session=run_id) as (client, launch):
        verify_launch(launch, runtime)
        if any(launch["gpu_lease"][key] != handoff["lease"][key] for key in ("host_sha256", "gpu_physical_sha256")):
            raise ValueError("Radeon lease mismatch")
        report["gpu"] = launch
        write_evidence(out / "launch.json", launch | {"status": "PASS"})
        for public in cases:
            for track in TRACKS:
                trial_id = sha256(canonical([run_id, track, public["case_id"]])).hexdigest()
                result = execute_trial(client, alias, public, worlds[public["case_id"]], trial_id, track,
                                       out / trial_id[:16], harness, FIRST_SEED)
                report["results"].append(result)
                write_evidence(report_path, report)
                print(candidate, public["family"], track, len(result["wire"]), len(result["calls"]),
                      result["failure"] and result["failure"]["type"], flush=True)
    counters = out / launch["counter_file"]
    report["gpu_execution"] = "PASS" if verify_gpu({"gpu_launch": out / "launch.json", "gpu_counters": counters},
                                                   "vulkan") else "FAIL"
    write_evidence(report_path, report)
    published = out / "portable"
    published.mkdir()
    report["artifacts"] = {"gpu.jsonl.gz": archive(counters, published / "gpu.jsonl.gz")}
    raw = out / launch["trace_file"]
    report["native_private_sha256"] = digest(raw)
    report["artifacts"]["native.jsonl.gz"] = archive(raw, published / "native.jsonl.gz", redact=True)
    write_evidence(published / "report.json", portable(report) | {"private_report_sha256": digest(report_path)})


def records(name):
    return [json.loads(line) for line in (HERE / name).read_bytes().splitlines()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", choices=("A", "B", "D"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--port", type=int, default=18754)
    args = parser.parse_args()
    development(args.candidate, args.assets.resolve(), args.output.resolve(), args.port)


if __name__ == "__main__":
    main()
