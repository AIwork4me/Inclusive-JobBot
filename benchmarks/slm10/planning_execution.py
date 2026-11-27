"""Run an SDK planning development case with recovery and an actual user update."""

import argparse
import asyncio
from importlib.metadata import version
import json
from pathlib import Path
from uuid import uuid4

from google.antigravity import Agent, LocalOpenAIAgentConfig, bin as sdk_bin, types
from google.antigravity.hooks import policy

from audit import write_evidence
from benchmarks.agentic_planning_v2.oracle import validate, verify
from benchmarks.agentic_planning_v2.runner import plan_request
from benchmarks.competitive_slm.tc_v2_candidate import server_environment, verify_launch, verify_runtime
from benchmarks.ij06_sdk.wire_boundary import ApprovalQueue, wire_boundary
from benchmarks.root_cause.historical_replay import gpu_server
from benchmarks.tool_calling_v2.oracle import decode_object
from evaluation.aeve.archive import check_text, digest
from evaluation.aeve.gpu_handoff import HANDOFF, require_handoff
from evaluation.aeve.runtime import ROOT, canonical, fingerprint
from model_gateway.openai_protocol import parse_proposal
from scripts.tools.verify_ij06_evidence import verify_gpu

from .admission import archive, git_head
from .native_diagnostics import BASE_ENGINE, OBSERVER_ENGINE, OBSERVER_HASHES, REPAIRED_STREAM_LIMIT, observe_wire
from .portable import portable

SUBJECT = "SYNTHETIC-TICKET-721"
REVISED = "SYNTHETIC-TICKET-944"
SITE = "DESK-LIME"
PRIVATE_STATUS = "RECONCILED-319"
DISCLOSURE = "Run the synthetic ticket recovery. Check the live record first and recover from a local cache if needed. "
TASK = (DISCLOSURE + f"The public ticket is {SUBJECT}. A later user update will specify a site when needed. "
        'If the site is indispensable, return {"ask":"site"} and await the update. '
        'Finish with {"status":"value"} after verification.')
UPDATE = f"Use site {SITE} for the current ticket reference. Continue the task with the current reference from the record."
SOP = (" First attempt inspect_live. If it fails with unavailable, check inspect_cache for the same public reference. "
       "Request a site if it is absent. Use the latest returned reference to verify the supplied site.")
TOOLS = {
    "inspect_live": {"inputs": ["reference"], "outputs": ["code", "current_ref"]},
    "inspect_cache": {"inputs": ["reference"], "outputs": ["code", "current_ref"]},
    "verify_site": {"inputs": ["reference", "site"], "outputs": ["code", "status"]},
}
CONTRACT = {"goal": "recover_ticket", "tools": TOOLS, "public_fields": ["subject"],
            "event_fields": ["site"], "action_budget": 5}
LIMITS = {"tool_calls": 5, "model_requests": 7, "retries": 0, "peak_context_tokens": 8192}
PUBLIC = {"subject": SUBJECT}
WORLD = {
    "public": PUBLIC, "disposition": "completed", "facts": {"status": PRIVATE_STATUS},
    "steps": [
        {"tool": "inspect_live", "args": {"reference": SUBJECT}, "result": {"code": "unavailable"}},
        {"tool": "inspect_cache", "args": {"reference": SUBJECT}, "result": {"code": "ok", "current_ref": REVISED},
         "event": {"site": SITE}},
        {"tool": "verify_site", "args": {"reference": REVISED, "site": SITE}, "result": {"status": PRIVATE_STATUS}},
    ],
}


class Ticket:
    def __init__(self):
        self.public = dict(PUBLIC)
        self.observed = {}
        self.calls = []
        self.phase = "initial"

    def snapshot(self):
        return {"public": dict(self.public), "observed": dict(self.observed)}

    def execute(self, tool, arguments):
        if self.phase == "plan" or len(self.calls) >= LIMITS["tool_calls"]:
            return "DENIED", {"code": "phase_or_budget"}
        if tool in {"inspect_live", "inspect_cache"} and arguments["reference"] == SUBJECT:
            if tool == "inspect_live":
                return "EXECUTED", {"code": "unavailable"}
            self.observed["current_ref"] = REVISED
            return "EXECUTED", {"code": "ok", "current_ref": REVISED}
        if (tool == "verify_site" and "site" in self.public and arguments["site"] == self.public["site"]
                and self.observed.get("current_ref") == arguments["reference"] == REVISED):
            self.observed["status"] = PRIVATE_STATUS
            return "EXECUTED", {"code": "ok", "status": PRIVATE_STATUS}
        return "DENIED", {"code": "unresolved_or_out_of_scope"}


async def trial(client, alias, output, harness, track, capability):
    for name in ("work", "save", "app"):
        (output / name).mkdir(parents=True)
    trial_id = "ijslm-planning-" + uuid4().hex
    service = Ticket()
    service.phase = "plan" if track == "plan_first" else "initial"
    approvals, events, turns = ApprovalQueue(), [], []
    user_messages = []
    validation = None
    constrained = capability == "constrained"
    plan_body = plan_request(alias, TASK, PUBLIC, CONTRACT, LIMITS, constrained, dynamic_tools=True)
    before = service.snapshot()

    def dispatch(tool, arguments):
        proposal = approvals.claim(tool, arguments)
        matching = [event for event in events if proposal.call_id in event.get("parsed_tool_call_ids", ())]
        if len(matching) != 1:
            raise ValueError("SDK tool callback has no unique validated proposal")
        event, = matching
        old = service.snapshot()
        decision, result = service.execute(tool, parse_proposal(proposal))
        service.calls.append({"tool": tool, "arguments": arguments, "result": result, "decision": decision,
                              "trial_id": trial_id, "call_id": proposal.call_id, "before": old,
                              "after": service.snapshot(), "provider_request_id": event["provider_request_id"],
                              "completion_id": event.get("completion_id")})
        return canonical(result).decode()

    def inspect_live(reference: str) -> str:
        """Look up the current live ticket record."""
        return dispatch("inspect_live", {"reference": reference})

    def inspect_cache(reference: str) -> str:
        """Look up a ticket using the fallback cache."""
        return dispatch("inspect_cache", {"reference": reference})

    def verify_site(reference: str, site: str) -> str:
        """Verify the ticket reference at a site the user supplied."""
        return dispatch("verify_site", {"reference": reference, "site": site})

    def profile(raw):
        if len(events) > LIMITS["model_requests"]:
            raise ValueError("model request budget exhausted")
        body = json.loads(raw)
        body.update(max_completion_tokens=1536 if service.phase == "plan" else 480, temperature=0, seed=7107,
                    cache_prompt=False, chat_template_kwargs={"enable_thinking": False})
        if service.phase == "plan":
            body["tool_choice"] = "none"
            if constrained:
                body["response_format"] = plan_body["response_format"]
        return canonical(body)

    failure = None
    with wire_boundary(client.base_url, approvals, events, trial_id=trial_id,
                       observe=lambda event: observe_wire(client, event), max_stream_bytes=REPAIRED_STREAM_LIMIT,
                       adapt_request=profile) as endpoint:
        config = LocalOpenAIAgentConfig(
            model=alias, base_url=endpoint.url, system_instructions=(
                "Operate only within the current task and supplied tools. Use observed results and explicit user updates."
                + (SOP if capability == "sop_assisted" else "")),
            capabilities=types.CapabilitiesConfig(enabled_tools=[], enable_subagents=False,
                                                  agent_behavior=types.AgentBehavior.MINIMAL),
            tools=[inspect_live, inspect_cache, verify_site],
            policies=[policy.deny_all(), *[policy.allow(name) for name in TOOLS]],
            workspaces=[str(output / "work")], save_dir=str(output / "save"), app_data_dir=str(output / "app"),
            mcp_servers=[], subagents=[], skills_paths=[],
            budget_config=types.BudgetConfig(max_model_calls=LIMITS["model_requests"],
                                             max_tool_calls=LIMITS["tool_calls"], max_output_tokens=1536),
            retry_config=types.RetryConfig(api_retry=types.ModelAPIRetryConfig(max_retries=0),
                                          model_output_retry=types.ModelOutputRetryConfig(max_retries=0)),
            env={"ANTIGRAVITY_HARNESS_PATH": str(harness), "OTEL_SDK_DISABLED": "true", "NO_PROXY": "127.0.0.1,localhost",
                 "HTTP_PROXY": "", "HTTPS_PROXY": "", "ALL_PROXY": "", "GEMINI_API_KEY": "", "GOOGLE_API_KEY": "",
                 "OPENAI_API_KEY": "", "GOOGLE_APPLICATION_CREDENTIALS": ""},
        )
        try:
            async with asyncio.timeout(180):
                async with Agent(config) as agent:
                    async def chat(prompt):
                        user_messages.append(prompt)
                        answer = await agent.chat(prompt)
                        chunks = [part async for part in answer]
                        text = "".join(chunks)
                        turns.append({"phase": service.phase, "answer": text})
                        return text

                    if track == "plan_first":
                        prompt = "\n\n".join(message["content"] for message in plan_body["messages"])
                        first = await chat(prompt)
                        try:
                            plan = decode_object(first)
                            errors = validate(plan, CONTRACT)
                            validation = {"status": "FAIL", "errors": errors} if errors else verify(plan, CONTRACT, [WORLD])
                        except ValueError as error:
                            validation = {"status": "FAIL", "errors": [str(error)]}
                    if validation is None or validation["status"] == "PASS":
                        service.phase = "initial"
                        await chat(TASK)
                        service.phase = "user_update"
                        service.public["site"] = SITE
                        await chat(UPDATE)
        except (OSError, TimeoutError, ValueError, types.AntigravityConnectionError, types.AntigravityExecutionError,
                types.AntigravityValidationError) as error:
            failure = {"type": type(error).__name__, "message": str(error)}
    final = turns[-1]["answer"] if turns and turns[-1]["phase"] == "user_update" else None
    initial = next((row["answer"] for row in turns if row["phase"] == "initial"), None)
    tool_path = [row["tool"] for row in service.calls if row["decision"] == "EXECUTED"]
    business_ok = (tool_path == ["inspect_live", "inspect_cache", "verify_site"] and final is not None
                   and service.observed.get("status") == PRIVATE_STATUS)
    if business_ok and initial is not None:
        try:
            business_ok = decode_object(final) == {"status": PRIVATE_STATUS} and decode_object(initial) == {"ask": "site"}
        except ValueError:
            business_ok = False
    return {"trial_id": trial_id, "track": track, "capability": capability, "user_messages": user_messages,
            "turns": turns, "wire": events, "calls": service.calls, "before": before, "after": service.snapshot(),
            "failure": failure, "plan_replay": validation, "business_replay": "PASS" if business_ok else "FAIL",
            "formal_assessment": "BLOCKED"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, default=18754)
    args = parser.parse_args()
    model_info = json.loads((ROOT / "atlas/slm/v1.0/model_registry.json").read_bytes())["models"]["B"]
    model = (args.assets / model_info["local_asset"]).resolve(strict=True)
    runtime = verify_runtime("B", model, args.assets / BASE_ENGINE, require_prior_admission=False)
    engine = args.assets / OBSERVER_ENGINE
    binary = (engine / "llama-server.exe").resolve(strict=True)
    hashes = {file.name: digest(file) for file in engine.iterdir() if file.suffix in {".dll", ".exe"}}
    sdk = version("google-antigravity")
    if (runtime["model"]["model_sha256"] != model_info["asset"]["expected_sha256"] or sdk != "0.1.24"
            or hashes != runtime["engine"]["dll_sha256"] | OBSERVER_HASHES):
        raise ValueError("planning diagnostic runtime differs from its pins")
    handoff = require_handoff(ROOT)
    harness = Path(sdk_bin.__file__).with_name("localharness.exe")
    args.output.mkdir(parents=True, exist_ok=False)
    alias = "ijslm-planning-b"
    run_id = "ijslm-planning-dev-" + uuid4().hex
    report = {"git_sha": git_head(), "evidence_class": "real Radeon model and SDK development diagnostic",
              "run_id": run_id, "formal_trials": 0, "candidate": "B", "backend": "vulkan",
              "model": runtime["model"], "engine_sha256": hashes, "handoff_sha256": digest(ROOT / HANDOFF),
              "sdk": sdk, "harness_sha256": digest(harness), "fixture_sha256": fingerprint([PUBLIC, WORLD, TASK, UPDATE]),
              "results": []}
    private = args.output / "report.json"
    with gpu_server(binary, model, "vulkan", server_environment(), args.output, args.port, "vulkan", True,
                    alias=alias, mission_id="IJ-SLM-1.0", lease_owner="planning-development",
                    runtime_session=run_id) as (client, launch):
        verify_launch(launch, runtime)
        if any(launch["gpu_lease"][key] != handoff["lease"][key] for key in ("host_sha256", "gpu_physical_sha256")):
            raise ValueError("planning diagnostic Radeon lease differs from the handoff")
        report["gpu"] = launch
        write_evidence(args.output / "launch.json", launch | {"status": "PASS"})
        for track, capability in (("acting_first", "native"), ("plan_first", "constrained"),
                                  ("acting_first", "sop_assisted"), ("plan_first", "native")):
            row = asyncio.run(trial(client, alias, args.output / (track + "-" + capability), harness, track, capability))
            report["results"].append(row)
            write_evidence(private, report)
            print(track, capability, len(row["wire"]), len(row["calls"]), row["business_replay"], flush=True)
    counters = args.output / launch["counter_file"]
    report["gpu_execution"] = "PASS" if verify_gpu({"gpu_launch": args.output / "launch.json", "gpu_counters": counters},
                                                   "vulkan") else "FAIL"
    report["artifacts"] = {"gpu.jsonl.gz": archive(counters, args.output / "gpu.jsonl.gz")}
    write_evidence(private, report)
    published = portable(report) | {"private_report_sha256": digest(private)}
    check_text(canonical(published))
    write_evidence(args.output / "portable.json", published)


if __name__ == "__main__":
    main()
