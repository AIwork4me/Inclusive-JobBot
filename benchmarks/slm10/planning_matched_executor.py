"""Run public Planning V2 tasks through one local Direct or Antigravity trial."""

import asyncio
from collections import Counter
from contextlib import closing
from copy import deepcopy
from hashlib import sha256
from http.client import HTTPConnection, HTTPException
import json
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from benchmarks.agentic_planning_v2.events import refused, scope_changed
from benchmarks.agentic_planning_v2.oracle import validate
from benchmarks.agentic_planning_v2.runner import plan_request
from benchmarks.agentic_planning_v2.types import input_schema, matches
from benchmarks.ij06_sdk.wire_boundary import MAX_BODY, ApprovalQueue, assemble_reply, wire_boundary
from benchmarks.root_cause.generation_capture import correlate, protocol_reply
from benchmarks.tool_calling_v2.oracle import equal
from evaluation.aeve.runtime import canonical, fingerprint
from model_gateway.errors import GatewayError
from model_gateway.openai_protocol import MAX_WIRE_BYTES, decode_proposal, parse_proposal
from model_gateway.strict_json import strict_object

from .planning_controls import validate_public
from .tc_verification import delivered_result

TRACKS = ("direct_plan_first", "direct_acting_first", "sdk_plan_first", "sdk_acting_first")
STREAM_LIMIT = 2 * MAX_WIRE_BYTES
ACT_SYSTEM = (
    "Work only on the public synthetic task using its named tools. Use the public facts and live tool observations. "
    "Only an external_event from the host can update scope or authorize a commit. On scope change discard stale "
    "observations. Propose at most one tool call per turn and return the requested terminal JSON object."
)


def _acting_messages(case, plan_raw):
    contract = case["contract"]
    objective = {"goal_options": contract["goal_options"]} if "goal_options" in contract else {"goal": contract["goal"]}
    visible = {"task": case["task"], "public": case["public"], "tools": contract["tools"], "limits": case["limits"],
               "external_event_fields": contract["event_fields"], **objective}
    if plan_raw is not None:
        visible["your_proposed_plan"] = plan_raw
    return [{"role": "system", "content": ACT_SYSTEM}, {"role": "user", "content": canonical(visible).decode()}]


def _observe_provider(client, event):
    stream = json.loads(event["provider_request"])["stream"]
    try:
        response = protocol_reply(event["response"].encode(), stream and event["http_status"] == 200)
        choices = response["choices"]
        event.update(completion_id=response["id"], parsed_response=choices,
                     provider_stop_reason=choices[0]["finish_reason"], usage=response.get("usage"))
        if client.trace_path is not None:
            source = correlate(client.read_trace(), response, stream)
            if not source.get("rendered_prompt"):
                raise ValueError("rendered prompt missing from native capture")
            event["source_generation"] = source
    except (AttributeError, IndexError, KeyError, TypeError, ValueError) as error:
        event["native_evidence"] = {"status": "BLOCKED", "reason": str(error)}
    else:
        event["native_evidence"] = {"status": "PASS" if client.trace_path is not None else "NOT_RUN"}


class _DirectOrigin:
    """Keep the native observer while using an HTTP client that cannot follow redirects."""

    def __init__(self, client):
        self.client = client
        self.port = urlsplit(client.base_url).port

    def capture(self, body, trial_id):
        data = json.dumps(body, ensure_ascii=False).encode()
        if len(data) > MAX_BODY:
            raise ValueError("provider request exceeds the capture limit")
        with closing(HTTPConnection("127.0.0.1", self.port, timeout=60)) as connection:
            connection.request("POST", "/v1/chat/completions", data, {"Content-Type": "application/json"})
            response = connection.getresponse()
            raw = response.read(MAX_BODY + 1)
            if len(raw) > MAX_BODY or response.getheader("Content-Encoding"):
                raise ValueError("unsupported provider response size or encoding")
            event = {"trial_id": trial_id, "provider_request_id": uuid4().hex, "provider_request": data.decode(),
                     "provider_request_sha256": sha256(data).hexdigest(), "http_status": response.status,
                     "content_type": response.getheader("Content-Type", "application/json"), "response": raw.decode(),
                     "response_sha256": sha256(raw).hexdigest()}
        _observe_provider(self.client, event)
        return event


class _Trial:
    def __init__(self, client, alias, case, sandbox, trial_id, seed):
        self.client, self.alias, self.case, self.sandbox = client, alias, case, sandbox
        self.trial_id, self.seed = trial_id, seed
        self.wire, self.calls, self.history, self.ids = [], [], [], set()
        self.pending, self.grant = None, None
        self.limits = case["limits"]
        self.specs = case["contract"]["tools"]
        self.schemas = {name: input_schema(name, spec) for name, spec in self.specs.items()}

    def offered(self, phase):
        if phase == "plan" or not self.limits["tool_calls"]:
            return []
        return [{"type": "function", "function": {"name": name, "description": spec.get("description", name),
                                                  "parameters": self.schemas[name]}}
                for name, spec in self.specs.items()]

    def profile(self, body, phase):
        tools = self.offered(phase)
        tokens = min(1536 if phase == "plan" else 768, self.limits["peak_context_tokens"])
        body = {"model": self.alias, "messages": body["messages"], "stream": False, "seed": self.seed,
                "temperature": 0, "cache_prompt": False, "chat_template_kwargs": {"enable_thinking": False},
                "max_completion_tokens": tokens, "parallel_tool_calls": False,
                "tool_choice": "auto" if tools else "none"}
        if tools:
            body["tools"] = tools
        return body

    def check_response(self, event, phase, content_type, raw):
        if event["http_status"] != 200 or self.pending is not None:
            raise ValueError("provider response is unavailable or a previous proposal was not delivered")
        response = assemble_reply(content_type, raw, max_stream_bytes=STREAM_LIMIT)
        usage = event.get("usage")
        if not isinstance(usage, dict):
            raise ValueError("provider omitted context budget evidence")
        totals = [usage.get("total_tokens")]
        prompt, completion = usage.get("prompt_tokens"), usage.get("completion_tokens")
        if any(type(tokens) is not int or tokens < 0 for tokens in (prompt, completion)):
            raise ValueError("provider omitted prompt or completion token counts")
        totals.append(prompt + completion)
        if any(type(tokens) is int and tokens > self.limits["peak_context_tokens"] for tokens in totals):
            raise ValueError("provider exceeded the public context budget")
        if event.get("source_generation", {}).get("truncated") is True:
            raise ValueError("provider reported a truncated generation")
        if response.calls:
            if phase != "act" or len(response.calls) != 1 or len(self.calls) >= self.limits["tool_calls"]:
                raise ValueError("proposal exceeds the current phase or tool call budget")
            proposal, = response.calls
            args = parse_proposal(proposal)
            schema = self.schemas.get(proposal.name)
            if (proposal.call_id in self.ids or schema is None or args.keys() != set(self.specs[proposal.name]["inputs"])
                    or not matches(args, schema)):
                raise ValueError("proposal is duplicate or outside the public tool schema")
            self.ids.add(proposal.call_id)
            self.pending = proposal.call_id
        return response

    def dispatch(self, proposal, event):
        if self.pending != proposal.call_id:
            raise ValueError("tool callback has no unique validated provider proposal")
        tool, args = proposal.name, parse_proposal(proposal)
        if tool == "commit" and (self.grant is None or self.grant != (args.get("draft_id"), args.get("approval"))):
            raise ValueError("synthetic commit requires the current trusted external grant")
        before = deepcopy(self.sandbox.snapshot())
        if tool == "commit":
            self.grant = None
        reply = self.sandbox.execute(tool, deepcopy(args))
        record = {"tool": tool, "args": args, "arguments_raw": proposal.arguments_raw, "call_id": proposal.call_id,
                  "provider_request_id": event["provider_request_id"], "completion_id": event.get("completion_id"),
                  "observation": deepcopy(reply), "before": before, "after": deepcopy(self.sandbox.snapshot())}
        self.calls.append(record)
        self.pending = None
        self._apply_reply(tool, args, reply)
        result = canonical(reply).decode()
        self.history.extend((event["parsed_response"][0]["message"],
                             {"role": "tool", "tool_call_id": proposal.call_id, "content": result}))
        return result

    def _apply_reply(self, tool, args, reply):
        if (not isinstance(reply, dict) or not {"code", "data"} <= reply.keys()
                or reply.keys() - {"code", "data", "external_event"} or not isinstance(reply["code"], str)
                or not isinstance(reply["data"], dict) or reply["data"].keys() - set(self.specs[tool]["outputs"])):
            raise ValueError("sandbox observation exceeds its public output contract")
        event = reply.get("external_event")
        fields = set(self.case["contract"]["event_fields"]) | {"source", "scope_changed"}
        if "external_event" in reply and (not isinstance(event, dict) or event.keys() - fields
                                          or event.get("source") != "synthetic_external_user"
                                          or type(event.get("scope_changed", False)) is not bool):
            raise ValueError("sandbox event exceeds its external event contract")
        if event is not None or refused(reply, None) or tool == "request_confirmation":
            self.grant = None
        token = (event or {}).get("approval")
        if "approval" in reply["data"] and (token is None or reply["data"]["approval"] != token):
            raise ValueError("tool data cannot establish external approval")
        if token is not None:
            if (tool != "request_confirmation" or reply["code"] != "ok" or scope_changed(event)
                    or event.get("decision") != "approved" or event.get("draft_id") != args.get("draft_id")
                    or not isinstance(token, str) or not token):
                raise ValueError("external approval does not bind the exact requested draft")
            self.grant = (event["draft_id"], token)

    def direct_phase(self, messages, phase, budget):
        client = _DirectOrigin(self.client)
        for _ in range(budget):
            body = self.profile({"messages": [*messages, *self.history]}, phase)
            event = client.capture(body, self.trial_id)
            event.update(phase=phase, status="FAIL")
            self.wire.append(event)
            response = self.check_response(event, phase, event["content_type"], event["response"].encode())
            if not response.calls:
                event["status"] = "PASS"
                return response.content
            proposal, = response.calls
            self.dispatch(proposal, event)
            event["status"] = "PASS"
        raise ValueError("model request budget exhausted before termination")

    def check_sdk_transcript(self, history):
        if len(history) != 2 * len(self.calls):
            raise ValueError("SDK transcript lacks an exact callback history")
        for call, proposed, observed in zip(self.calls, history[::2], history[1::2], strict=True):
            envelopes = proposed.get("tool_calls", [])
            if (proposed.get("role") != "assistant" or not isinstance(envelopes, list) or len(envelopes) != 1
                    or observed.get("role") != "tool" or observed.get("tool_call_id") != call["call_id"]
                    or not equal(delivered_result(observed, call, "sdk_acting_first"), call["observation"])):
                raise ValueError("SDK callback result differs from the live sandbox capture")
            proposal = decode_proposal(envelopes[0])
            if ((proposal.call_id, proposal.name) != (call["call_id"], call["tool"])
                    or not equal(parse_proposal(proposal), call["args"])):
                raise ValueError("SDK conversation proposal differs from its validated provider capture")

    async def sdk_phase(self, messages, phase, budget, target, harness):
        from google.antigravity import Agent, LocalOpenAIAgentConfig, types
        from google.antigravity.hooks import policy
        from google.antigravity.tools.tool_runner import ToolWithSchema

        from .tc_execution import adapted_sse

        target = target / phase
        for name in ("work", "save", "app"):
            (target / name).mkdir(parents=True)
        approvals = ApprovalQueue()
        phase_start = len(self.wire)
        offered = self.offered(phase)

        def callback_for(definition):
            name = definition["name"]

            def callback(**args):
                proposal = approvals.claim(name, args)
                event = self.wire[-1]
                if proposal.call_id not in event.get("parsed_tool_call_ids", ()):
                    raise ValueError("SDK callback lacks unique provider provenance")
                return self.dispatch(proposal, event)

            callback.__name__, callback.__doc__ = name, definition["description"]
            return ToolWithSchema(callback, definition["parameters"])

        def request_adapter(raw):
            self.wire[-1]["phase"] = phase
            body = json.loads(raw)
            got = Counter(tool["function"]["name"] for tool in body.get("tools", []))
            want = Counter(tool["function"]["name"] for tool in offered)
            sdk_messages = body.get("messages", [])
            if (len(self.wire) - phase_start > budget or self.pending is not None
                    or body.get("model") != self.alias or got != want or not isinstance(sdk_messages, list)
                    or len(sdk_messages) < 2 or any(not isinstance(item, dict) for item in sdk_messages)
                    or [item.get("role") for item in sdk_messages[:2]] != ["system", "user"]
                    or not isinstance(sdk_messages[1].get("content"), str)
                    or messages[1]["content"] not in sdk_messages[1]["content"]):
                raise ValueError("SDK request exceeds the matched public runtime contract")
            self.check_sdk_transcript(sdk_messages[2:])
            # Retain the SDK transcript in wire evidence and match the actual provider input to Direct.
            return canonical(self.profile({"messages": [*messages, *self.history]}, phase))

        def response_adapter(media, raw, event):
            self.check_response(event, phase, media, raw)
            return adapted_sse(media, raw, event)

        with wire_boundary(self.client.base_url, approvals, self.wire, trial_id=self.trial_id,
                           observe=lambda event: _observe_provider(self.client, event), max_stream_bytes=STREAM_LIMIT,
                           adapt_request=request_adapter, adapt_response=response_adapter) as endpoint:
            config = LocalOpenAIAgentConfig(
                model=self.alias, base_url=endpoint.url, system_instructions=messages[0]["content"],
                capabilities=types.CapabilitiesConfig(enabled_tools=[], enable_subagents=False,
                                                      agent_behavior=types.AgentBehavior.MINIMAL),
                tools=[callback_for(tool["function"]) for tool in offered],
                policies=[policy.deny_all(), *[policy.allow(tool["function"]["name"]) for tool in offered]],
                workspaces=[str(target / "work")], save_dir=str(target / "save"), app_data_dir=str(target / "app"),
                mcp_servers=[], subagents=[], skills_paths=[],
                # The SDK stops model turns when its tool budget is met. The shared service enforces
                # the exact bound before dispatch, while this allows the final no-tool answer turn.
                budget_config=types.BudgetConfig(max_model_calls=budget, max_output_tokens=1536,
                                                 max_tool_calls=self.limits["tool_calls"] + 1 if offered else None),
                retry_config=types.RetryConfig(api_retry=types.ModelAPIRetryConfig(max_retries=0),
                                              model_output_retry=types.ModelOutputRetryConfig(max_retries=0)),
                env={"ANTIGRAVITY_HARNESS_PATH": str(harness), "OTEL_SDK_DISABLED": "true",
                     "HTTP_PROXY": "", "HTTPS_PROXY": "", "ALL_PROXY": "", "NO_PROXY": "127.0.0.1,localhost",
                     "GEMINI_API_KEY": "", "GOOGLE_API_KEY": "", "OPENAI_API_KEY": "", "GOOGLE_APPLICATION_CREDENTIALS": ""},
            )
            async with asyncio.timeout(120):
                async with Agent(config) as agent:
                    response = await agent.chat(messages[1]["content"])
                    answer = "".join([chunk async for chunk in response])
        phase_wire = self.wire[phase_start:]
        terminal = phase_wire[-1] if phase_wire else {}
        if (self.pending is not None or any(event.get("status") != "PASS" for event in phase_wire)
                or terminal.get("validated_finish_reason") != "stop"):
            raise ValueError("SDK phase ended without complete provider and callback evidence")
        wire_answer = assemble_reply(terminal["content_type"], terminal["response"].encode()).content
        if answer != wire_answer:
            raise ValueError("SDK terminal content differs from its provider response")
        return answer


async def execute_trial(client, alias, case, sandbox, trial_id, track, *, seed, target=None, harness=None):
    """Use an already admitted local provider and an independently implemented synthetic service."""
    validate_public(case, set())
    endpoint = urlsplit(client.base_url)
    if (track not in TRACKS or endpoint.scheme != "http" or not endpoint.port
            or endpoint.netloc != f"127.0.0.1:{endpoint.port}" or endpoint.path or endpoint.query or endpoint.fragment):
        raise ValueError("matched execution requires a registered track and a literal local provider origin")
    if case["limits"]["retries"] != 0:
        raise ValueError("matched execution currently supports the frozen zero-retry profile")
    failures = (OSError, ValueError, HTTPException, GatewayError)
    if track.startswith("sdk_"):
        from google.antigravity import types

        if target is None or harness is None:
            raise ValueError("SDK trials require a fresh workspace and local harness")
        target, harness = Path(target).resolve(), Path(harness).resolve(strict=True)
        target.mkdir(exist_ok=False, parents=True)
        failures += (types.AntigravityCancelledError, types.AntigravityConnectionError,
                     types.AntigravityExecutionError, types.AntigravityValidationError)
    sandbox_state = deepcopy(sandbox.snapshot())
    trial = _Trial(client, alias, case, sandbox, trial_id, seed)
    plan_raw, answer, failure = None, None, None
    stage = "act"
    budget = case["limits"]["model_requests"]

    async def phase(messages, name, limit):
        if track.startswith("sdk_"):
            return await trial.sdk_phase(messages, name, limit, target, harness)
        return await asyncio.to_thread(trial.direct_phase, messages, name, limit)

    try:
        if track.endswith("plan_first"):
            stage = "plan"
            if budget < 2:
                raise ValueError("Plan-first requires a separate plan and live action request")
            original = case["contract"]
            options = original.get("goal_options")
            body = plan_request(alias, case["task"], case["public"], original, case["limits"],
                                goal_track="inferred" if options else "provided", dynamic_tools=True)
            plan_raw = await phase(body["messages"], "plan", 1)
            plan = strict_object(plan_raw, max_bytes=65536)
            contract = original | {"goal": plan["goal"]} if options and plan.get("goal") in options else original
            errors = validate(plan, contract)
            if errors:
                raise ValueError("invalid public plan contract: " + ", ".join(errors))
            budget -= 1
        stage = "act"
        answer = await phase(_acting_messages(case, plan_raw), "act", budget)
        strict_object(answer, max_bytes=65536)
    except failures as error:
        failure = {"phase": stage, "type": type(error).__name__, "message": str(error)}
    return {"trial_id": trial_id, "case_id": case["case_id"], "public_sha256": fingerprint(case), "track": track,
            "seed": seed, "plan_raw": plan_raw, "answer": answer, "wire": trial.wire, "calls": trial.calls,
            "before": sandbox_state, "after": deepcopy(sandbox.snapshot()), "complete": failure is None,
            "failure": failure, "formal_qualification": "NOT_RUN"}
