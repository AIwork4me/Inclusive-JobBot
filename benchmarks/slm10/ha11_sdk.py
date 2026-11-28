"""Antigravity 0.1.24 read-only adapter for the LFM3-HA-1.1 diagnostics."""

import asyncio
from dataclasses import asdict
import json
from pathlib import Path

from google.antigravity import Agent, LocalOpenAIAgentConfig, types
from google.antigravity.hooks import policy
from google.antigravity.tools.tool_runner import ToolWithSchema
from pydantic import PrivateAttr

from benchmarks.ij06_sdk.wire_boundary import ApprovalQueue, assemble_reply, wire_boundary
from benchmarks.tool_calling_v2.oracle import equal
from evaluation.aeve.runtime import canonical
from model_gateway import GatewayError
from model_gateway.callback_binding import BindingContext, CallbackBinder
from model_gateway.openai_protocol import MAX_WIRE_BYTES
from model_gateway.phase_tool_policy import Phase, PhaseToolPolicy
from model_gateway.strict_json import strict_object

from .native_diagnostics import REPAIRED_STREAM_LIMIT, observe_wire
from .tc_execution import adapted_sse
from .tc_verification import delivered_result

ORIGINAL = "ORIGINAL_SDK"
TOOL_CHOICE_ONLY = "SDK_MATCHED_CONTEXT_ToolChoiceOnly"
CORRECTED = "SDK_MATCHED_CONTEXT_PhaseAware"
TYPED = "SDK_MATCHED_CONTEXT_TypedExtension"


class _BoundToolRunner:
    """Retain the call identity before the SDK spreads its arguments into kwargs."""

    def __init__(self, runner, dispatch):
        self._runner = runner
        self._dispatch = dispatch

    def __getattr__(self, name):
        return getattr(self._runner, name)

    async def process_tool_calls(self, calls):
        return [self._dispatch(call) for call in calls]


class _BoundConfig(LocalOpenAIAgentConfig):
    _dispatch = PrivateAttr()

    def create_strategy(self, *, tool_runner, hook_runner):
        return super().create_strategy(tool_runner=_BoundToolRunner(tool_runner, self._dispatch),
                                       hook_runner=hook_runner)


class _PhaseBatch:
    def __init__(self, alias, tools, trial_id, wire, execute, grants):
        self.grants = frozenset(grants)
        self.trial_id, self.wire, self.execute = trial_id, wire, execute
        self.policy = PhaseToolPolicy(alias, tools)
        self.context = BindingContext(trial_id, "synthetic-read-only", 1, "read-only-tool-allowlist", 0)
        schemas = {item["function"]["name"]: item["function"]["parameters"] for item in tools}
        self.binder = CallbackBinder(schemas, lambda ctx, name, _: (
            ctx == self.context and name in self.policy.allowed
        ))
        self.expected = set()
        self.observations = {}
        self.callbacks = []
        self.closed = False

    def publish(self, calls):
        self.binder.publish(calls, self.context)

    def close(self):
        self.binder.close()
        self.closed = True

    def request(self, raw):
        if self.policy.phase == Phase.PLAN:
            self.policy.advance(Phase.ACT, self.grants)
        elif self.policy.phase in {Phase.ACT, Phase.REPLAN} and self.expected:
            self.policy.advance(Phase.OBSERVE)
            source = strict_object(raw, max_bytes=MAX_WIRE_BYTES)
            messages = source.get("messages", [])
            for call_id in sorted(self.expected):
                observed = self.observations.get(call_id)
                linked = [m for m in messages if m.get("role") == "tool" and m.get("tool_call_id") == call_id]
                if observed is None or len(linked) != 1:
                    raise ValueError("Missing unique actual observation before replan")
                if not equal(delivered_result(linked[0], observed, "sdk_streaming"), observed["result"]):
                    raise ValueError("SDK observation differs from actual tool result")
            self.context = BindingContext(self.trial_id, self.context.scope, self.context.revision,
                                          self.context.authorization_binding, self.context.observation_revision + 1)
            self.policy.advance(Phase.REPLAN, self.grants)
        event = self.wire[-1]
        event.update(tool_phase=self.policy.phase.value, authorized_tools=sorted(self.policy.allowed),
                     observation_revision=self.context.observation_revision)
        return self.policy.request(raw)

    def response(self, content_type, raw, event):
        result = assemble_reply(content_type, raw, max_stream_bytes=REPAIRED_STREAM_LIMIT)
        self.expected = {proposal.call_id for proposal in result.calls}
        if not result.calls:
            self.policy.advance(Phase.FINAL)
            self.policy.advance(Phase.STOP)
        return adapted_sse(content_type, raw, event)

    def dispatch(self, call):
        evidence = {"call_id": call.id, "tool": call.name, "sdk_arguments": call.args, "status": "FAIL"}
        self.callbacks.append(evidence)
        try:
            bound = self.binder.claim(call.id, call.name, call.args, self.context)
            if call.id not in self.expected or self.closed:
                raise ValueError("Callback is not part of the active SDK response")
            evidence.update(binding=asdict(bound), status="PASS", execution_status="NOT_RUN")
            observation = self.execute(bound.proposal, len(self.wire) - 1, self.wire)
            self.observations[call.id] = {"tool": call.name, "result": observation}
            evidence["execution_status"] = "PASS"
            return types.ToolResult(id=call.id, name=call.name, result=canonical(observation).decode())
        except (ValueError, GatewayError) as exc:
            evidence["reason"] = str(exc)
            if evidence["status"] == "PASS":
                evidence["execution_status"] = "FAIL"
            return types.ToolResult(id=call.id, name=call.name, error="Tool binding or execution failed")


async def execute_sdk(client, alias, tools, grants, execute, prompt, system, trial_id, target: Path, harness,
                      *, profile, model_budget, tool_budget, token_budget, provider_controls=None):
    """Run a clean SDK session and keep raw, effective, native and callback provenance."""
    wire, chunks = [], []
    corrected = profile in {CORRECTED, TYPED}
    batch = _PhaseBatch(alias, tools, trial_id, wire, execute, grants) if corrected else ApprovalQueue()
    tool_names = [item["function"]["name"] for item in tools]
    for name in ("work", "save", "app"):
        (target / name).mkdir(parents=True)

    def adapter(raw):
        source = strict_object(raw, max_bytes=MAX_WIRE_BYTES)
        actual_names = sorted(item["function"]["name"] for item in source.get("tools", []))
        if (source.get("model") != alias or "lora" in source or actual_names != sorted(tool_names)
                or len(wire) > model_budget):
            raise ValueError("Request exceeds the fixed read-only SDK contract")
        if profile == ORIGINAL:
            return raw
        if profile == TOOL_CHOICE_ONLY:
            return canonical(json.loads(raw) | ({"tool_choice": "auto"} if tool_names else {}))
        if provider_controls:
            data = json.loads(raw) | provider_controls
            if not data["stream"]:
                data.pop("stream_options", None)
            raw = canonical(data)
        return batch.request(raw)

    def make_tool(definition):
        name = definition["name"]

        def callback(reference: str) -> str:
            proposal = batch.claim(name, {"reference": reference})
            return canonical(execute(proposal, len(wire) - 1, wire)).decode()

        callback.__name__, callback.__doc__ = name, definition["description"]
        return ToolWithSchema(callback, definition["parameters"]) if profile == TYPED else callback

    failure = None
    with wire_boundary(client.base_url, batch, wire, trial_id=trial_id, max_stream_bytes=REPAIRED_STREAM_LIMIT,
                       observe=lambda event: observe_wire(client, event), adapt_request=adapter,
                       adapt_response=batch.response if corrected else None) as endpoint:
        config_type = _BoundConfig if corrected else LocalOpenAIAgentConfig
        config = config_type(
            model=alias, base_url=endpoint.url, system_instructions=system,
            capabilities=types.CapabilitiesConfig(enabled_tools=[], enable_subagents=False,
                                                  agent_behavior=types.AgentBehavior.MINIMAL),
            tools=[make_tool(item["function"]) for item in tools],
            policies=[policy.deny_all(), *[policy.allow(name) for name in sorted(grants if corrected else tool_names)]],
            workspaces=[str(target / "work")], save_dir=str(target / "save"), app_data_dir=str(target / "app"),
            mcp_servers=[], subagents=[], skills_paths=[],
            budget_config=types.BudgetConfig(max_model_calls=model_budget, max_tool_calls=tool_budget,
                                             max_output_tokens=token_budget),
            retry_config=types.RetryConfig(api_retry=types.ModelAPIRetryConfig(max_retries=0),
                                          model_output_retry=types.ModelOutputRetryConfig(max_retries=0)),
            env={"ANTIGRAVITY_HARNESS_PATH": str(harness), "OTEL_SDK_DISABLED": "true",
                 "HTTP_PROXY": "", "HTTPS_PROXY": "", "ALL_PROXY": "", "NO_PROXY": "localhost,127.0.0.1",
                 "GEMINI_API_KEY": "", "GOOGLE_API_KEY": "", "OPENAI_API_KEY": "", "GOOGLE_APPLICATION_CREDENTIALS": ""},
        )
        if corrected:
            # Agent deep-copies its config. A function retains the trial-local batch.
            def dispatch(call):
                return batch.dispatch(call)

            config._dispatch = dispatch
        try:
            async with asyncio.timeout(120), Agent(config) as agent:
                reply = await agent.chat(prompt)
                async for delta in reply:
                    chunks.append(delta)
        except (OSError, ValueError, types.AntigravityConnectionError, types.AntigravityExecutionError,
                types.AntigravityValidationError) as exc:
            failure = {"type": type(exc).__name__, "message": str(exc)}
    return {"trial_id": trial_id, "wire": wire, "answer": "".join(chunks), "failure": failure,
            "callbacks": batch.callbacks if corrected else [], "sdk_chunks": len(chunks)}
