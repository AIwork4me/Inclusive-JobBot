"""Run paired opt-in request adapters through the real isolated SDK development loop."""

import argparse
import asyncio
from dataclasses import asdict
from hashlib import sha256
from importlib.metadata import version
import json
import os
from pathlib import Path
from threading import Event, Lock
from time import monotonic, perf_counter
from uuid import uuid4

from audit import write_evidence
from benchmarks.ij06_sdk.wire_boundary import ApprovalQueue, assemble_reply, wire_boundary
from benchmarks.root_cause.gpu_lease import _named_lease, windows_query
from benchmarks.tool_calling_v2.oracle import equal
from evaluation.aeve.archive import check_text, digest
from evaluation.aeve.gpu_handoff import HANDOFF, require_handoff
from evaluation.aeve.runtime import ROOT, canonical, fingerprint
from model_gateway.errors import ErrorCode, GatewayError
from model_gateway.strict_json import strict_object
from .portable import portable
from .sdk_adapters import (
    CallbackReceipt, MAX_REQUEST_BYTES, REGISTRY, REQUEST_COMPONENTS, RequestContext, Scope, TerminalContext,
    adapt_request, load_profiles, structured_output, termination_decision,
)
from .sdk_causal_metrics import answer_metrics, assign_actions
from .tc_v3 import CONFIG, FIRST_SEED, HERE, LANGUAGES, TOOLS, case_data, verify_freeze
from .tc_verification import delivered_result


PLAN = HERE.parent / "sdk-adapter-lfm3-holdout.json"
VERSION = "IJ-SLM-SDK-ADAPTER-DEVELOPMENT/1.0"
SDK = "0.1.24"
CONTROLLER_LOCK = "InclusiveJobBotSLMCausalController"
DEVELOPMENT_CASES = ("TCV3-D-single-000", "TCV3-D-dependency-001", "TCV3-D-roundtrip-002")
READ_TOOLS = frozenset(("read_dispatch", "read_clearance", "read_handoff", "read_fallback"))
STREAM_LIMIT = 1 << 20
HOLDOUT_WORDING = {
    "single": ("Look up {ref} in the dispatch register and provide its code.",
               "请查调度记录 {ref}，我只需要它的代码。",
               "For dispatch {ref}，查一下并给我 code 即可。"),
    "selection": ("I need the clearance identifier for dispatch {ref}. Retrieve its clearance code.",
                  "请查询调度 {ref} 对应的放行记录，用它的代码作答。",
                  "Find the clearance 记录 for {ref}，只返回 clearance code。"),
    "roundtrip": ("From dispatch {ref}, report both its code and its assigned dock.",
                  "麻烦查询调度 {ref}，给出该单的代码和靠泊位置。",
                  "For dispatch {ref}，取它自己的 code 和 dock，两项都要。"),
    "dependency": ("Open dispatch {ref}, follow its handoff reference and report the handoff record's code.",
                   "打开调度 {ref}，按其中的交接编号找到交接记录，再返回交接代码。",
                   "先从 dispatch {ref} 找到 handoff reference，然后返回该交接记录的 code。"),
}
JSON_SUFFIX = {
    "en": " Output one JSON object with keys {keys}.",
    "zh": " 请只输出一个 JSON 对象，字段为 {keys}。",
    "mixed": " Output only JSON，字段 {keys}。",
}


def _paired(public, world, oracle, index):
    order = ("reference", "treatment") if index % 2 == 0 else ("treatment", "reference")
    return {"public": public, "world": world, "oracle": oracle, "arm_order": list(order), "seed": FIRST_SEED}


def holdout_cases():
    cases = []
    for family, templates in HOLDOUT_WORDING.items():
        for index, (language, text) in enumerate(zip(LANGUAGES, templates, strict=True)):
            public, world, oracle = case_data(family, language, "SDKAD-H1", index)
            keys = ", ".join(oracle["answer"])
            reference = oracle["nodes"][0]["arguments"]["reference"]
            public["prompt"] = text.format(ref=reference) + JSON_SUFFIX[language].format(keys=keys)
            cases.append(_paired(public, world, oracle, len(cases)))
    return cases


def expected_plan(cases):
    return {
        "version": VERSION, "candidate": "B", "treatment": "compact_result_codec", "sdk_version": SDK,
        "formal_trial_attribution": 0, "physical_dispatch": "NOT_RUN",
        "dataset_sha256": fingerprint(cases),
        "dataset_manifest_sha256": digest(HERE / "manifest.json"),
        "profile_registry_sha256": digest(REGISTRY),
        "cases": [{"case_id": row["public"]["case_id"], "family": row["public"]["family"],
                   "language": row["public"]["language"], "seed": row["seed"], "arm_order": row["arm_order"]}
                  for row in cases],
    }


def load_plan():
    cases = holdout_cases()
    plan = json.loads(PLAN.read_bytes())
    if plan != expected_plan(cases):
        raise ValueError("synthetic adapter holdout differs from the pinned comparison plan")
    return plan, cases


def _development_cases():
    public, worlds, oracles = ({row["case_id"]: row for row in read_cases(f"development-{kind}.jsonl")}
                               for kind in ("public", "worlds", "oracle"))
    return [_paired(public[key], worlds[key], oracles[key], index) for index, key in enumerate(DEVELOPMENT_CASES)]


def read_cases(name):
    return [json.loads(line) for line in (HERE / name).read_bytes().splitlines()]


def require_synthetic_read_only(public, world):
    if (public["case_id"] != world["case_id"] or not set(public["tools"]) or set(public["tools"]) - READ_TOOLS
            or len(set(public["tools"])) != len(public["tools"]) or world["external_approval"] is not None):
        raise ValueError("adapter development requires the pinned synthetic read-only callback scope")


class RequestBoundary:
    def __init__(self, profile, public, service, approvals, wire, trial_id, checkpoint, provider_settings, tool_contract):
        self.profile = profile
        self.public = public
        self.service = service
        self.approvals = approvals
        self.wire = wire
        self.trial_id = trial_id
        self.checkpoint = checkpoint
        self.provider_settings = provider_settings
        self.tool_contract = tool_contract
        self.scope = Scope(trial_id, trial_id, "synthetic-adapter", public["case_id"], "executive")
        self.system_digest = None
        self.receipts = []
        self.lock = Lock()

    def adapt(self, raw):
        with self.lock:
            self.checkpoint()
            if not 1 <= len(self.wire) <= CONFIG["max_model_calls"]:
                raise ValueError("adapter development model request budget exhausted")
            event = self.wire[-1]
            body = strict_object(raw, max_bytes=MAX_REQUEST_BYTES, max_depth=48)
            tools = body.get("tools", [])
            messages = body.get("messages")
            if (not isinstance(tools, list) or any(not isinstance(tool, dict)
                    or not isinstance(tool.get("function"), dict) for tool in tools)
                    or not isinstance(messages, list) or any(not isinstance(message, dict) for message in messages)):
                raise ValueError("SDK request tool or message contract is malformed")
            offered = [tool.get("function", {}).get("name") for tool in tools]
            if (any(not isinstance(name, str) for name in offered) or set(offered) != self.service.allowed_tools
                    or len(offered) != len(set(offered))):
                raise ValueError("SDK tool scope differs from the authorized synthetic tools")
            body.update(self.provider_settings, tools=self.tool_contract)
            body.pop("stream_options", None)
            systems = [message.get("content") for message in messages if message.get("role") == "system"]
            if (len(systems) != 1 or not isinstance(systems[0], str) or CONFIG["system"] not in systems[0]):
                raise ValueError("SDK system message omits the expected workflow policy")
            current_digest = sha256(systems[0].encode()).hexdigest()
            if self.system_digest is None:
                self.system_digest = current_digest
            if self.system_digest != current_digest:
                raise ValueError("SDK system message changed within the trial")
            context = RequestContext(self.scope, event["sdk_request_id"], self.system_digest, tuple(self.receipts))
            result, audit = adapt_request(self.profile, canonical(body), context)
            event["adapter_audit"] = asdict(audit) | {
                "sdk_request_id": event["sdk_request_id"], "provider_request_id": None,
                "sdk_system_sha256": self.system_digest,
            }
            self.checkpoint()
            return result

    def callback(self, name, reference):
        with self.lock:
            self.checkpoint()
            proposal = self.approvals.claim(name, {"reference": reference})
            matches = [(turn, event) for turn, event in enumerate(self.wire)
                       if proposal.call_id in event.get("parsed_tool_call_ids", ())]
            if len(matches) != 1:
                raise ValueError("SDK callback lacks a unique provider provenance")
            turn, event = matches[0]
            if (event.get("trial_id") != self.trial_id or event.get("status") != "PASS"
                    or event.get("http_status") != 200 or not event.get("completion_id")
                    or not event.get("provider_request_id")):
                raise ValueError("SDK callback lacks completed provider provenance")
            result = canonical(self.service.execute(proposal, turn, event))
            call = self.service.calls[-1]
            expected = {"call_id": proposal.call_id, "tool": proposal.name, "arguments_raw": proposal.arguments_raw,
                        "turn": turn, "trial_id": self.trial_id, "provider_request_id": event["provider_request_id"],
                        "completion_id": event["completion_id"]}
            if (any(call[key] != value for key, value in expected.items())
                    or canonical(call["result"]) != result or call["decision"] not in {"EXECUTED", "DENIED"}):
                raise ValueError("SDK callback lacks matching host audit provenance")
            self.checkpoint()
            self.receipts.append(CallbackReceipt(self.scope, event["provider_request_id"], event["completion_id"],
                                                  proposal.call_id, name, proposal.arguments_raw.encode(), result,
                                                  call["decision"]))
            return result.decode()


def verify_request_audits(wire):
    audits = []
    for event in wire:
        audit = event.get("adapter_audit")
        request_id = event.get("provider_request_id")
        if audit is None and request_id is None:
            continue
        if audit is None or audit["sdk_request_id"] != event["sdk_request_id"]:
            raise ValueError("provider request lacks matching SDK adapter audit")
        if request_id is not None:
            raw = event["provider_request"].encode()
            if sha256(raw).hexdigest() != audit["after_sha256"] or audit["after_sha256"] != event["provider_request_sha256"]:
                raise ValueError("wire payload differs from the adapter receipt")
        audits.append(audit | {"provider_request_id": request_id,
                               "status": "PASS" if request_id is not None else "BLOCKED"})
    return audits


async def sdk_trial(client, alias, public, world, trial_id, target, harness, seed, profile):
    from google.antigravity import Agent, LocalOpenAIAgentConfig, types
    from google.antigravity.hooks import policy

    from .native_diagnostics import observe_wire
    from .tc_execution import Sandbox, adapted_sse, provider_profile, public_tools

    require_synthetic_read_only(public, world)
    if profile.component not in REQUEST_COMPONENTS | {"reference"}:
        raise ValueError("physical development supports the reference and request profiles only")
    service, approvals, wire, chunks = Sandbox(public, world), ApprovalQueue(), [], []
    stop = Event()
    started = perf_counter()
    deadline = monotonic() + 90
    for directory in ("work", "save", "app"):
        (target / directory).mkdir(parents=True)

    def checkpoint():
        if stop.is_set():
            raise GatewayError(ErrorCode.CANCELLED, "SDK adapter trial cancelled")
        if monotonic() >= deadline:
            raise GatewayError(ErrorCode.TIMEOUT, "SDK adapter trial deadline exceeded")

    boundary = RequestBoundary(profile, public, service, approvals, wire, trial_id, checkpoint,
                               provider_profile(False, seed), public_tools(public))

    def make_callback(name):
        def callback(reference: str) -> str:
            return boundary.callback(name, reference)
        callback.__name__ = name
        callback.__doc__ = TOOLS[name]
        return callback

    before = service.snapshot()
    failure, first_chunk = None, None
    with wire_boundary(client.base_url, approvals, wire, trial_id=trial_id,
                       observe=lambda event: observe_wire(client, event), max_stream_bytes=STREAM_LIMIT,
                       adapt_request=boundary.adapt, adapt_response=adapted_sse) as endpoint:
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
            env={"ANTIGRAVITY_HARNESS_PATH": str(harness), "OTEL_SDK_DISABLED": "true",
                 "HTTP_PROXY": "", "HTTPS_PROXY": "", "ALL_PROXY": "", "NO_PROXY": "localhost,127.0.0.1",
                 "GEMINI_API_KEY": "", "GOOGLE_API_KEY": "", "OPENAI_API_KEY": "", "GOOGLE_APPLICATION_CREDENTIALS": ""},
        )
        try:
            async with asyncio.timeout(90):
                async with Agent(config) as agent:
                    reply = await agent.chat(public["prompt"])
                    async for chunk in reply:
                        checkpoint()
                        if chunk and first_chunk is None:
                            first_chunk = round((perf_counter() - started) * 1000, 3)
                        chunks.append(chunk)
        except (OSError, TimeoutError, ValueError, types.AntigravityConnectionError, types.AntigravityExecutionError,
                types.AntigravityValidationError) as error:
            failure = {"type": type(error).__name__, "message": str(error)}
        finally:
            stop.set()
            endpoint.abort()
    return {"trial_id": trial_id, "profile": asdict(profile), "seed": seed, "wire": wire,
            "request_audits": verify_request_audits(wire), "answer": "".join(chunks), "failure": failure,
            "calls": service.calls, "before": before, "after": service.snapshot(), "host_protected_callbacks": [],
            "wall_ms": round((perf_counter() - started) * 1000, 3), "sdk_first_visible_text_ms_buffered": first_chunk}


def _workflow(capture, oracle):
    wire = capture["wire"]
    proposals, delivered = [], {}
    calls = {call["call_id"]: call for call in capture["calls"]}
    has_capture = bool(wire) and all(event.get("status") == "PASS" and event.get("http_status") == 200
                                    and event.get("response_capture_complete") is True for event in wire)
    last = None
    if not has_capture:
        return False, False, False, 0, None
    for turn, event in enumerate(wire):
        last = assemble_reply(event["content_type"], event["response"].encode(), max_stream_bytes=STREAM_LIMIT)
        proposals.extend({"call_id": call.call_id, "tool": call.name, "turn": turn,
                          "arguments": strict_object(call.arguments_raw)} for call in last.calls)
        body = json.loads(event["provider_request"])
        transformed = event["adapter_audit"]["message_indices"]
        for index, message in enumerate(body["messages"]):
            call = calls.get(message.get("tool_call_id"))
            if message["role"] != "tool" or call is None or call["turn"] + 1 != turn:
                continue
            is_compact = capture["profile"]["component"] == "compact_result_codec" and index in transformed
            result = strict_object(message["content"]) if is_compact else delivered_result(message, call, "sdk_first")
            if equal(call["result"], result):
                delivered[call["call_id"]] = (turn, result)
    assignments, _ = assign_actions(oracle["nodes"], oracle["dependencies"], proposals)
    valid = len(assignments) == len(oracle["nodes"]) and all(node is not None for node in assignments)
    if valid:
        for proposal, index in zip(proposals, assignments, strict=True):
            call_id = proposal["call_id"]
            if (call_id not in delivered or calls[call_id]["decision"] != "EXECUTED"
                    or not equal(delivered[call_id][1], oracle["nodes"][index]["result"])):
                valid = False
    workflow = valid and capture["before"] == capture["after"] and len(calls) == len(proposals)
    terminal = last.finish_reason == "stop" and not last.calls and capture["failure"] is None
    return workflow, bool(delivered), terminal, len(proposals), last


def assess(capture, oracle, profiles):
    workflow, has_delivery, terminal, proposals, last = _workflow(capture, oracle)
    native_answer = last.content if last is not None else None
    counts = {call["call_id"] for call in capture["calls"]}
    termination = termination_decision(profiles["termination_policy"], TerminalContext(
        last.finish_reason if last is not None else "unavailable", max(0, proposals - len(counts)),
        len(last.calls) if last is not None else 0, len(capture["wire"]), len(counts),
        CONFIG["max_model_calls"], CONFIG["max_tool_calls"],
        capture["failure"] is not None and capture["failure"]["type"] == "CancelledError",
        capture["failure"] is not None and capture["failure"]["type"] == "TimeoutError",
        False, workflow, terminal or (last is not None and capture["failure"] is None),
    ))
    output = "BLOCKED"
    if terminal:
        schema = {"type": "object", "required": list(oracle["answer"]),
                  "properties": {key: {"type": "string"} for key in oracle["answer"]},
                  "additionalProperties": False}
        try:
            structured_output(profiles["structured_output_contract"], native_answer, schema, terminal_allowed=True)
        except GatewayError:
            output = "FAIL"
        else:
            output = "PASS"
    sdk = answer_metrics(capture["answer"], oracle["answer"], terminal, has_delivery)
    same_answer = terminal and capture["answer"] == native_answer
    source_statuses = [row.get("native_evidence", {}).get("status") for row in capture["wire"]]
    if source_statuses and all(status == "PASS" for status in source_statuses):
        source_status = "PASS"
    elif source_statuses and all(status == "NOT_RUN" for status in source_statuses):
        source_status = "NOT_RUN"
    else:
        source_status = "BLOCKED"
    return {
        "workflow": "PASS" if workflow else "FAIL" if last is not None else "BLOCKED",
        "model": answer_metrics(native_answer, oracle["answer"], terminal, has_delivery),
        "sdk": sdk,
        "terminal_observer": asdict(termination),
        "structured_output_observer": output,
        "native_source": source_status,
        "sdk_visible_matches_provider": "PASS" if same_answer else "FAIL" if terminal else "BLOCKED",
        "business_completion": ("PASS" if workflow and same_answer and sdk["final_answer"] == "PASS"
                                else "FAIL" if last else "BLOCKED"),
        "profile_application": "PASS" if any(audit["message_indices"] for audit in capture["request_audits"]) else "NOT_RUN",
        "model_proposals": proposals if last is not None else None,
        "host_executed_callbacks": sum(call["decision"] == "EXECUTED" for call in capture["calls"]),
    }


def require_idle_controller():
    if os.name != "nt":
        raise ValueError("physical SDK adapter development requires the registered Windows workstation")
    running = windows_query(
        "$ErrorActionPreference='Stop'; (Get-CimInstance Win32_Process | Where-Object { "
        "$_.ProcessId -ne $PID -and $_.CommandLine -match "
        r"'(?i)(-m\s+benchmarks\.slm10\.(tc_queue|tc_five_model_queue|sdk_causal_ablation|sdk_wave_queue)\b"
        r"|-File\s+[^\r\n]*run_slm_sdk_causal_waves\.ps1\b)' }).ProcessId"
    )
    if running:
        raise BlockingIOError("a frozen or causal controller still owns the physical schedule")


def run(candidate, treatment, cases, assets, output, port, *, independent_holdout):
    from google.antigravity import bin as sdk_bin

    from benchmarks.competitive_slm.tc_v2_candidate import server_environment, verify_launch, verify_runtime
    from benchmarks.root_cause.historical_replay import gpu_server
    from scripts.tools.verify_ij06_evidence import verify_gpu

    from .admission import archive, git_head
    from .native_diagnostics import BASE_ENGINE, OBSERVER_ENGINE, OBSERVER_HASHES
    from .tc_execution import provider_profile

    verify_freeze()
    for case in cases:
        require_synthetic_read_only(case["public"], case["world"])
    handoff = require_handoff(ROOT)
    profiles = load_profiles()
    model_spec = json.loads((HERE.parent / "model_registry.json").read_bytes())["models"][candidate]
    model = (assets / model_spec["local_asset"]).resolve(strict=True)
    runtime = verify_runtime(candidate, model, assets / BASE_ENGINE, require_prior_admission=False)
    engine = assets / OBSERVER_ENGINE
    hashes = {file.name: digest(file) for file in engine.iterdir() if file.suffix in {".dll", ".exe"}}
    if hashes != runtime["engine"]["dll_sha256"] | OBSERVER_HASHES or model_spec["asset"]["expected_sha256"] != runtime[
            "model"]["model_sha256"] or version("google-antigravity") != SDK:
        raise ValueError("physical SDK adapter runtime differs from the pinned identities")
    harness = Path(sdk_bin.__file__).with_name("localharness.exe")
    identity = "ijslm-adapters-" + uuid4().hex
    alias = "ijslm-candidate-" + candidate.lower()
    report = {
        "version": VERSION, "run_id": identity, "git_sha": git_head(), "candidate": candidate,
        "formal_trial_attribution": 0, "independent_holdout": independent_holdout, "gpu_execution": "NOT_RUN",
        "engine_sha256": hashes, "model": runtime["model"], "sdk": SDK, "harness_sha256": digest(harness),
        "dataset_sha256": fingerprint(cases), "dataset_manifest_sha256": digest(HERE / "manifest.json"),
        "handoff_sha256": digest(ROOT / HANDOFF), "profile_registry_sha256": digest(REGISTRY),
        "holdout_plan_sha256": digest(PLAN) if independent_holdout else None,
        "source_sha256": {name: digest(Path(__file__).with_name(name)) for name in
                          ("sdk_adapter_development.py", "sdk_adapters.py", "tc_execution.py", "native_diagnostics.py")},
        "wire_boundary_sha256": digest(ROOT / "benchmarks/ij06_sdk/wire_boundary.py"),
        "provider_configuration": provider_profile(False, FIRST_SEED),
        "profiles": {arm: asdict(profiles[key]) for arm, key in (("reference", "reference"), ("treatment", treatment))},
        "planned_case_ids": [case["public"]["case_id"] for case in cases], "results": [],
    }
    with _named_lease(CONTROLLER_LOCK):
        require_idle_controller()
        output.mkdir(parents=True, exist_ok=False)
        private = output / "report.json"
        write_evidence(private, report)
        with gpu_server(engine / "llama-server.exe", model, "vulkan", server_environment(), output, port, "vulkan",
                        True, alias=alias, mission_id="IJ-SLM-1.0", lease_owner="sdk-adapter-development",
                        runtime_session=identity) as (client, launch):
            verify_launch(launch, runtime)
            if any(launch["gpu_lease"][key] != handoff["lease"][key] for key in ("host_sha256", "gpu_physical_sha256")):
                raise ValueError("adapter Radeon lease differs from the handoff")
            report["gpu"] = launch
            write_evidence(output / "launch.json", launch | {"status": "PASS"})
            for case in cases:
                case_id = case["public"]["case_id"]
                for arm in case["arm_order"]:
                    key = "reference" if arm == "reference" else treatment
                    trial = fingerprint([identity, case_id, arm, case["seed"]])
                    capture = asyncio.run(sdk_trial(client, alias, case["public"], case["world"], trial,
                                                    output / trial[:16], harness, case["seed"], profiles[key]))
                    try:
                        assessment = assess(capture, case["oracle"], profiles)
                    except (KeyError, TypeError, ValueError) as error:
                        assessment = {"status": "BLOCKED", "type": type(error).__name__, "reason": str(error)}
                    report["results"].append({"case_id": case_id, "arm": arm,
                                              "assessment": assessment, "capture": capture})
                    write_evidence(private, report)
        counters, trace = (output / launch[name] for name in ("counter_file", "trace_file"))
        report["gpu_execution"] = "PASS" if verify_gpu({"gpu_launch": output / "launch.json", "gpu_counters": counters},
                                                       "vulkan") else "FAIL"
        report["private_native_trace_sha256"] = digest(trace)
        write_evidence(private, report)
        dest = output / "portable"
        dest.mkdir()
        report["artifacts"] = {"gpu.jsonl.gz": archive(counters, dest / "gpu.jsonl.gz"),
                               "native.jsonl.gz": archive(trace, dest / "native.jsonl.gz", redact=True)}
        published = portable(report) | {"private_report_sha256": digest(private)}
        check_text(canonical(published))
        write_evidence(dest / "report.json", published)
    return 0 if report["gpu_execution"] == "PASS" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--print-plan", action="store_true")
    parser.add_argument("--dispatch", action="store_true", help="explicitly run a physical paired experiment")
    parser.add_argument("--development", action="store_true", help="use development cases instead of independent holdout")
    parser.add_argument("--candidate", choices=("A", "B", "D"), default="B")
    parser.add_argument("--treatment", choices=sorted(REQUEST_COMPONENTS), default="compact_result_codec")
    parser.add_argument("--assets", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--port", type=int, default=18754)
    args = parser.parse_args()
    if args.print_plan and not args.dispatch:
        print(json.dumps(expected_plan(holdout_cases()), indent=2, sort_keys=True))
        return 0
    plan, cases = load_plan()
    if not args.dispatch:
        print(json.dumps({"audit": "PASS", "physical_dispatch": "NOT_RUN", "plan_sha256": digest(PLAN),
                          "planned_trials": 2 * len(cases)}, sort_keys=True))
        return 0
    if args.assets is None or args.output is None:
        parser.error("dispatch requires --assets and --output")
    if not args.development and (args.candidate != plan["candidate"] or args.treatment != plan["treatment"]):
        parser.error("independent holdout is frozen for LFM3 and Compact Result Codec")
    return run(args.candidate, args.treatment, _development_cases() if args.development else cases, args.assets.resolve(),
               args.output.resolve(), args.port, independent_holdout=not args.development)


if __name__ == "__main__":
    raise SystemExit(main())
