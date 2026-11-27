"""Independent Radeon controls over captured Antigravity SDK development requests."""

import argparse
import asyncio
from copy import deepcopy
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from time import perf_counter
from urllib.error import HTTPError
from urllib.request import Request
from uuid import uuid4

from google.antigravity import Agent, LocalOpenAIAgentConfig, bin as sdk_bin, types
from google.antigravity.hooks import policy

from audit import write_evidence
from benchmarks.competitive_slm.tc_v2_candidate import server_environment, verify_launch, verify_runtime
from benchmarks.ij06_sdk.wire_boundary import ApprovalQueue, assemble_reply, wire_boundary
from benchmarks.root_cause.historical_replay import gpu_server
from benchmarks.tool_calling_v2.oracle import decode_object
from evaluation.aeve.archive import check_text, digest
from evaluation.aeve.gpu_handoff import HANDOFF, require_handoff
from evaluation.aeve.runtime import ROOT, canonical, fingerprint
from model_gateway import GatewayError
from scripts.tools.verify_ij06_evidence import verify_gpu

from .admission import archive, git_head
from .native_diagnostics import BASE_ENGINE, OBSERVER_ENGINE, OBSERVER_HASHES, REPAIRED_STREAM_LIMIT, observe_wire
from .portable import portable
from .sdk_causal_metrics import action_identity, answer_metrics
from .tc_execution import Sandbox, adapted_sse, execute_trial, provider_profile, public_tools, records
from .tc_v3 import CONFIG, FIRST_SEED, HERE, TOOLS, verify_freeze
from .tc_verification import delivered_result

VERSION = "IJ-SLM-SDK-CAUSAL-ABLATION/1.1"
ARMS = ("A0", "SDK_CONTROL", "A1", "A2", "A3", "A4", "A5", "GUARD")
PILOT = ("TCV3-D-single-000", "TCV3-D-dependency-001", "TCV3-D-authorization-002")
STYLE_LINE = "- Format your responses in github-style markdown.\n"
GUARD_TOOLS = frozenset(("read_dispatch", "read_handoff", "read_clearance"))
GUARD_FAMILIES = frozenset(("single", "selection", "binding", "roundtrip", "dependency", "parallel"))


def compact_message(message):
    call = {"tool": message["name"]}
    return message | {"content": canonical(delivered_result(message, call, "sdk_first")).decode()}


def intervention(raw, arm, callbacks):
    if arm == "A1":
        return raw, []
    body = json.loads(raw)
    changes = []
    for index, message in enumerate(body["messages"]):
        if arm == "A2" and message["role"] == "system" and message["content"].count(STYLE_LINE) == 1:
            message["content"] = message["content"].replace(STYLE_LINE, "", 1)
            changes.append({"message_index": index, "operation": "remove_markdown_style_directive"})
        elif arm in ("A3", "A5") and message["role"] == "tool":
            body["messages"][index] = compact_message(message)
            changes.append({"message_index": index, "operation": "compact_verified_tool_result"})
    if arm == "A4" and callbacks:
        states = [{"tool": call["tool"], "arguments": call["arguments"], "call_id": call["call_id"]}
                  for call in callbacks if call["decision"] == "EXECUTED" and "error" not in call["result"]]
        if states:
            extra = ("\nObserved completed read actions: " + canonical(states).decode() +
                     ". Continue applying the user's requested workflow and any dependencies. "
                     "Repeat a read only when the task requires it or scope has changed.")
            system = next(index for index, msg in enumerate(body["messages"]) if msg["role"] == "system")
            body["messages"][system]["content"] += extra
            changes.append({"message_index": system, "operation": "append_completed_action_state"})
    return (canonical(body) if changes else raw), changes


class GuardedSandbox(Sandbox):
    def __init__(self, public, world, guard):
        super().__init__(public, world)
        self.guard = guard and public["family"] in GUARD_FAMILIES
        self.cache = {}
        self.prevented = []

    def execute(self, proposal, turn, event):
        args = decode_object(proposal.arguments_raw)
        key = action_identity(proposal.name, args)
        if self.guard and proposal.name in GUARD_TOOLS and key in self.cache:
            self.prevented.append({"call_id": proposal.call_id, "turn": turn, "provider_request_id": event["provider_request_id"],
                                   "tool": proposal.name, "arguments": args, "decision": "CACHED_READ"})
            return deepcopy(self.cache[key])
        reply = super().execute(proposal, turn, event)
        if self.guard and proposal.name in GUARD_TOOLS and self.calls[-1]["decision"] == "EXECUTED" and "error" not in reply:
            self.cache[key] = deepcopy(reply)
        return reply


def exact_request(client, raw, trial_id, request_id):
    body = json.loads(raw)
    request = Request(client.base_url + "/v1/chat/completions", data=raw,
                      headers={"Content-Type": "application/json"})
    started = perf_counter()
    try:
        opened = client.opener.open(request, timeout=90)
    except HTTPError as failure:
        opened = failure
    with opened as reply:
        media = reply.headers.get("Content-Type", "application/json")
        status = reply.status
        response = reply.read((1 << 20) + 1)
    wall_ms = round((perf_counter() - started) * 1000, 3)
    if len(response) > (1 << 20):
        raise ValueError("diagnostic provider response exceeded size limit")
    event = {"trial_id": trial_id, "provider_request_id": request_id, "provider_request": raw.decode(),
             "provider_request_sha256": sha256(raw).hexdigest(), "http_status": status,
             "content_type": media, "response": response.decode(), "response_sha256": sha256(response).hexdigest(),
             "wall_ms": wall_ms}
    observe_wire(client, event)
    try:
        result = assemble_reply(media, response, max_stream_bytes=REPAIRED_STREAM_LIMIT)
    except (ValueError, GatewayError) as failure:
        event["assembly_error"] = str(failure)
        result = None
    return event, result, body


async def sdk_control(client, alias, setup, service, identity, target, harness, compact):
    approvals = ApprovalQueue()
    offered = public_tools(setup)
    wire, chunks, adapter_ms, callback_ms, interventions = [], [], [], [], []
    for name in ("work", "save", "app"):
        (target / name).mkdir(parents=True)
    first_chunk_ms = None
    start = perf_counter()

    def request_adapter(raw):
        began = perf_counter()
        if len(wire) > CONFIG["max_model_calls"]:
            raise ValueError("causal runtime request budget exceeded")
        body = json.loads(raw) | provider_profile(False, FIRST_SEED)
        if {definition["function"]["name"] for definition in body.get("tools", ())} != set(setup["tools"]):
            raise ValueError("SDK tools differ from the frozen development contract")
        body["tools"] = offered
        body.pop("stream_options", None)
        payload = canonical(body)
        changes = []
        if compact:
            payload, changes = intervention(payload, "A5", ())
        interventions.append(changes)
        adapter_ms.append(round((perf_counter() - began) * 1000, 3))
        return payload

    def make_callback(name):
        def callback(reference: str) -> str:
            began = perf_counter()
            proposal = approvals.claim(name, {"reference": reference})
            matches = [(turn, event) for turn, event in enumerate(wire)
                       if proposal.call_id in event.get("parsed_tool_call_ids", ())]
            if len(matches) != 1:
                raise ValueError("callback lacks a unique wire proposal")
            turn, event = matches[0]
            result = canonical(service.execute(proposal, turn, event)).decode()
            callback_ms.append(round((perf_counter() - began) * 1000, 3))
            return result
        callback.__name__ = name
        callback.__doc__ = TOOLS[name]
        return callback

    failure = None
    with wire_boundary(client.base_url, approvals, wire, trial_id=identity,
                       observe=lambda event: observe_wire(client, event), max_stream_bytes=REPAIRED_STREAM_LIMIT,
                       adapt_request=request_adapter, adapt_response=adapted_sse) as endpoint:
        config = LocalOpenAIAgentConfig(
            model=alias, base_url=endpoint.url, system_instructions=CONFIG["system"],
            capabilities=types.CapabilitiesConfig(enabled_tools=[], enable_subagents=False,
                                                  agent_behavior=types.AgentBehavior.MINIMAL),
            tools=[make_callback(name) for name in setup["tools"]],
            policies=[policy.deny_all(), *[policy.allow(name) for name in setup["tools"]]],
            workspaces=[str(target / "work")], save_dir=str(target / "save"), app_data_dir=str(target / "app"),
            mcp_servers=[], subagents=[], skills_paths=[],
            budget_config=types.BudgetConfig(max_model_calls=CONFIG["max_model_calls"], max_tool_calls=CONFIG["max_tool_calls"],
                                             max_output_tokens=CONFIG["max_completion_tokens"]),
            retry_config=types.RetryConfig(api_retry=types.ModelAPIRetryConfig(max_retries=0),
                                          model_output_retry=types.ModelOutputRetryConfig(max_retries=0)),
            env={"ANTIGRAVITY_HARNESS_PATH": str(harness), "OTEL_SDK_DISABLED": "true",
                 "HTTP_PROXY": "", "HTTPS_PROXY": "", "ALL_PROXY": "", "NO_PROXY": "localhost,127.0.0.1",
                 "GEMINI_API_KEY": "", "GOOGLE_API_KEY": "", "OPENAI_API_KEY": "", "GOOGLE_APPLICATION_CREDENTIALS": ""},
        )
        try:
            async with asyncio.timeout(90):
                async with Agent(config) as agent:
                    reply = await agent.chat(setup["prompt"])
                    async for chunk in reply:
                        if chunk and first_chunk_ms is None:
                            first_chunk_ms = round((perf_counter() - start) * 1000, 3)
                        chunks.append(chunk)
        except (OSError, TimeoutError, ValueError, types.AntigravityConnectionError, types.AntigravityExecutionError,
                types.AntigravityValidationError) as exc:
            failure = {"type": type(exc).__name__, "message": str(exc)}
    return {"answer": "".join(chunks), "wire": wire, "calls": service.calls, "failure": failure,
            "before": {"releases": {}, "external_approval": service.approval}, "after": service.snapshot(),
            "guard_protected_callbacks": service.prevented, "sdk_first_visible_text_ms_buffered": first_chunk_ms,
            "wall_ms": round((perf_counter() - start) * 1000, 3),
            "request_adapter_ms": adapter_ms, "callback_ms": callback_ms, "interventions": interventions}


def execute_case(client, alias, harness, setup, world, oracle, out, run_id):
    case = setup["case_id"]
    began = perf_counter()
    rows = []
    a0_id = fingerprint([run_id, case, "A0"])
    a0 = execute_trial(client, alias, setup, world, a0_id, "direct_first", out / "A0", harness, FIRST_SEED)
    rows.append({"arm": "A0", "capture": a0, "wall_ms": round((perf_counter() - began) * 1000, 3)})
    for arm in ("SDK_CONTROL", "A5", "GUARD"):
        trial_id = fingerprint([run_id, case, arm])
        if arm == "GUARD" and setup["family"] not in GUARD_FAMILIES:
            rows.append({"arm": arm, "status": "NOT_RUN", "applicability": "NOT_APPLICABLE"})
            continue
        service = GuardedSandbox(setup, world, arm == "GUARD")
        trace = asyncio.run(sdk_control(client, alias, setup, service, trial_id, out / arm, harness, arm == "A5"))
        rows.append({"arm": arm, "capture": trace | {"trial_id": trial_id, "case_id": case, "track": "sdk_first"}})
    control = rows[1]["capture"]
    event = next((entry for entry in control["wire"] if entry.get("provider_request") and any(
        msg["role"] == "tool" for msg in json.loads(entry["provider_request"])["messages"])), None)
    observation_present = event is not None
    event = event or next((e for e in control["wire"] if e.get("provider_request")), None)
    for arm in ("A1", "A2", "A3", "A4"):
        if event is None or (arm in ("A3", "A4") and not observation_present):
            rows.append({"arm": arm, "status": "BLOCKED", "reason": "missing matched request history"})
            continue
        raw = event["provider_request"].encode()
        transformed, changes = intervention(raw, arm, [call for call in control["calls"] if call["turn"] < control["wire"].index(event)])
        if arm != "A1" and not changes:
            rows.append({"arm": arm, "status": "NOT_RUN", "reason": "planned intervention absent in source request"})
            continue
        replay, reply, _ = exact_request(client, transformed, fingerprint([run_id, case, arm]), uuid4().hex)
        if arm == "A1" and replay["provider_request_sha256"] != event["provider_request_sha256"]:
            raise ValueError("byte-identical effective SDK request did not replay unchanged")
        if reply is None:
            rows.append({"arm": arm, "status": "BLOCKED", "source_request_sha256": event["provider_request_sha256"],
                         "changes": changes, "capture": replay, "reason": "provider response failed assembly"})
            continue
        rows.append({"arm": arm, "status": "PASS" if replay["native_evidence"]["status"] == "PASS" else "BLOCKED",
                     "source_request_sha256": event["provider_request_sha256"], "source_completion_id": event["completion_id"],
                     "source_response_sha256": event.get("response_sha256"),
                     "source_has_tool_result": observation_present, "changes": changes, "capture": replay,
                     "next_call_count": len(reply.calls), "next_finish_reason": reply.finish_reason,
                     "next_answer": answer_metrics(reply.content, oracle["answer"], reply.finish_reason == "stop",
                                                  observation_present)})
    return {"case_id": case, "family": setup["family"], "language": setup["language"], "arms": rows}


def run(candidate, assets, output, port, case_ids):
    verify_freeze()
    handoff = require_handoff(ROOT)
    record = json.loads((ROOT / "atlas/slm/v1.0/model_registry.json").read_bytes())["models"][candidate]
    model = (assets / record["local_asset"]).resolve(strict=True)
    runtime = verify_runtime(candidate, model, assets / BASE_ENGINE, require_prior_admission=False)
    engine = assets / OBSERVER_ENGINE
    hashes = {p.name: digest(p) for p in engine.iterdir() if p.suffix in {".dll", ".exe"}}
    if hashes != runtime["engine"]["dll_sha256"] | OBSERVER_HASHES or runtime["model"]["model_sha256"] != record["asset"]["expected_sha256"]:
        raise ValueError("Radeon diagnostic runtime differs from registered assets")
    sdk = version("google-antigravity")
    if sdk != "0.1.24":
        raise ValueError("Antigravity version mismatch")
    harness = Path(sdk_bin.__file__).with_name("localharness.exe")
    setups, worlds, oracles = ({r["case_id"]: r for r in records(f"development-{kind}.jsonl")}
                               for kind in ("public", "worlds", "oracle"))
    if not case_ids or len(case_ids) != len(set(case_ids)) or set(case_ids) - setups.keys():
        raise ValueError("causal experiments require unique development case identities")
    output.mkdir(parents=True, exist_ok=False)
    identity = "ijslm-causal-" + uuid4().hex
    alias = "ijslm-candidate-" + candidate.lower()
    report = {"version": VERSION, "run_id": identity, "candidate": candidate, "git_sha": git_head(),
              "formal_trials": 0, "engine_sha256": hashes, "model": runtime["model"], "sdk": sdk,
              "harness_sha256": digest(harness), "handoff_sha256": digest(ROOT / HANDOFF),
              "dataset_manifest_sha256": digest(HERE / "manifest.json"), "case_ids": case_ids,
              "source_sha256": digest(Path(__file__)), "results": [], "gpu_execution": "NOT_RUN"}
    path = output / "report.json"
    with gpu_server(engine / "llama-server.exe", model, "vulkan", server_environment(), output, port, "vulkan", True,
                    alias=alias, mission_id="IJ-SLM-1.0", lease_owner="sdk-causal-development",
                    runtime_session=identity) as (client, launch):
        verify_launch(launch, runtime)
        if any(launch["gpu_lease"][key] != handoff["lease"][key] for key in ("host_sha256", "gpu_physical_sha256")):
            raise ValueError("diagnostic Radeon lease differs from handoff")
        report["gpu"] = launch
        write_evidence(output / "launch.json", launch | {"status": "PASS"})
        for case in case_ids:
            folder = output / case
            folder.mkdir()
            row = execute_case(client, alias, harness, setups[case], worlds[case], oracles[case], folder, identity)
            report["results"].append(row)
            write_evidence(path, report)
            print(candidate, case, [r["arm"] for r in row["arms"] if "capture" in r], flush=True)
    counters = output / launch["counter_file"]
    report["gpu_execution"] = "PASS" if verify_gpu({"gpu_launch": output / "launch.json", "gpu_counters": counters},
                                                   "vulkan") else "FAIL"
    trace = output / launch["trace_file"]
    report["private_native_trace_sha256"] = digest(trace)
    write_evidence(path, report)
    dest = output / "portable"
    dest.mkdir()
    report["artifacts"] = {"gpu.jsonl.gz": archive(counters, dest / "gpu.jsonl.gz"),
                           "native.jsonl.gz": archive(trace, dest / "native.jsonl.gz", redact=True)}
    published = portable(report) | {"private_report_sha256": digest(path)}
    check_text(canonical(published))
    write_evidence(dest / "report.json", published)
    return report["gpu_execution"]


def main():
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("candidate", choices=("A", "B", "D"))
    command.add_argument("--assets", type=Path, required=True)
    command.add_argument("--output", type=Path, required=True)
    command.add_argument("--port", type=int, default=18754)
    command.add_argument("--case", action="append")
    args = command.parse_args()
    status = run(args.candidate, args.assets.resolve(), args.output.resolve(), args.port, args.case or list(PILOT))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
