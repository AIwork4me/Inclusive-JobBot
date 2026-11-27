"""Run a planning trajectory through captured llama.cpp and isolated synthetic tools."""

from collections import defaultdict
from copy import deepcopy
import http.client
import json
import re

from benchmarks.root_cause.generation_capture import CaptureError
from benchmarks.tool_calling_v2.parser.run_wire import split_sse
from model_gateway.openai_protocol import decode_completion, parse_proposal
from model_gateway.strict_json import strict_object
from model_gateway.errors import GatewayError
from model_gateway.streaming import StreamAssembler

from .contract import POLICY, TOOLS, TRACK_PROMPTS, request
from .oracle import score
from .sandbox import SyntheticSandbox

PLAN_FIELDS = {"goal", "subgoals", "actions", "success_conditions", "stop_conditions"}
PLAN_TRANSITION = "Continue with the task. Use the available tools as needed, or return the final JSON."
PROMPT_ARMS = {
    "p0": frozenset(), "p1": frozenset(), "p2": frozenset({"example"}),
    "p3": frozenset({"schema"}), "p4": frozenset({"compact"}),
    "p5-es": frozenset({"example", "schema"}), "p5-ec": frozenset({"example", "compact"}),
    "p5-sc": frozenset({"schema", "compact"}), "p5": frozenset({"example", "schema", "compact"}),
}
PLAN_EXAMPLE = (
    'Format example only. Replace the placeholders and include actions only when needed for the request. '
    '{"goal":{"subject":"<subject>","objective":"<objective>"},"subgoals":["<subgoal>"],'
    '"actions":[{"id":"<step>","tool":"<tool>","arguments":{"<parameter>":"<value>"},'
    '"depends_on":[],"preconditions":[]}],"success_conditions":["<success condition>"],'
    '"stop_conditions":["<stop condition>"]}'
)
COMPACT_TOOL_DESCRIPTIONS = {
    "lookup": "Resolve a public reference to an internal ID. Its kind identifies the service.",
    "status": "Read current status by public reference.",
    "archive": "Read historical classification by public reference.",
    "status_mirror": "Read current status by public reference from the independent status service.",
    "read_record": ("Read primary by ID. Follow linked_id in primary records. Route policy_id to policy, "
                    "partner_id to partner and audit_primary_id to audit."),
    "check_policy": ("Read rules and permissions by ID. Follow policy linked_id. "
                     "Use audit_id for cross-checking. Grants no approval."),
    "inspect_partner": "Read a partner or dependency by ID. Follow partner linked_id. Use audit_id to cross-check.",
    "audit_read": "Cross-check primary audit ID and partner audit peer_id.",
}
THINKING_TAG = re.compile(r"<\s*/?\s*think\b", re.IGNORECASE)
# The reference alphabet is ASCII. Han text can adjoin a complete identifier.
REFERENCES = re.compile(r"(?<![A-Za-z0-9_-])REF-[0-9]+-[0-9]+(?![A-Za-z0-9_-])")
STATEFUL_TOOLS = {"stage", "request_confirmation", "commit"}
ROUTED_FIELDS = {
    "id": {"id", "linked_id", "policy_id", "partner_id", "audit_id", "audit_primary_id"},
    "peer_id": {"partner_id", "audit_id"},
    "draft_id": {"draft_id"}, "audit_ref": {"audit_ref"},
}


def plan_format():
    def object_of(**properties):
        return {"type": "object", "properties": properties,
                "required": list(properties), "additionalProperties": False}

    string = {"type": "string"}
    strings = {"type": "array", "items": string}
    reference = {"anyOf": [object_of(**{"from": string, "field": string}),
                           object_of(**{"from": string, "field": string, "evaluate": string})]}
    arguments = {"type": "object", "additionalProperties": {"anyOf": [string, reference]}}
    item = object_of(id=string, tool=string, arguments=arguments, depends_on=strings, preconditions=strings)
    schema = object_of(goal=object_of(subject=string, objective=string), subgoals=strings,
                       actions={"type": "array", "items": item}, success_conditions=strings,
                       stop_conditions=strings)
    return {"type": "json_schema", "json_schema": {"name": "initial_plan", "strict": True, "schema": schema}}


def compact_tools(tools):
    result = deepcopy(tools)
    for entry in result:
        function = entry["function"]
        name = function["name"]
        if name in COMPACT_TOOL_DESCRIPTIONS:
            outputs = ", ".join(TOOLS[name][2])
            function["description"] = f"{COMPACT_TOOL_DESCRIPTIONS[name]} Result fields can include {outputs}."
    return result


class Boundary:
    """Check arguments against the public contract and prior trusted observations."""

    def __init__(self, case):
        self.tools = set(case["tools"])
        self.references = set(REFERENCES.findall(case["prompt"]))
        self.seen = defaultdict(set)
        self.call_ids = set()
        self.backup_ids = set()
        self.grants = {}
        self.has_audit = False
        self.terminal_denial = False

    def validate(self, calls, remaining):
        if self.terminal_denial:
            raise ValueError("policy denial requires termination")
        if len(calls) > remaining:
            raise ValueError("action budget exceeded")
        if sum(call.name in STATEFUL_TOOLS for call in calls) > 1:
            raise ValueError("state-changing and confirmation actions must be in separate turns")
        arguments = []
        for call in calls:
            args = parse_proposal(call)
            if (call.call_id in self.call_ids or call.name not in self.tools
                    or args.keys() != set(TOOLS[call.name][1]) or any(type(v) is not str or not v for v in args.values())):
                raise ValueError("duplicate call ID, unavailable tool, or argument schema mismatch")
            if "reference" in args and args["reference"] not in self.references:
                raise ValueError("reference was unavailable when proposed")
            for field, sources in ROUTED_FIELDS.items():
                if field in args and not any(args[field] in self.seen[name] for name in sources):
                    raise ValueError(f"{field} was unavailable when proposed")
            if call.name == "read_backup" and args["id"] not in self.backup_ids:
                raise ValueError("backup was not permitted by an earlier primary observation")
            if call.name == "stage" and not self.has_audit:
                raise ValueError("staging requires a prior cross-check observation")
            if call.name == "commit" and self.grants.get(args["draft_id"]) != args["approval"]:
                raise ValueError("approval for the exact draft was unavailable when proposed")
            arguments.append(args)
        return arguments

    def observe(self, call, args, observation):
        self.call_ids.add(call.call_id)
        event = observation.get("external_event", {})
        data = observation["data"]
        code = observation["code"]
        if event.get("source") == "synthetic_external_user" and type(event.get("revised_reference")) is str:
            self.references = {event["revised_reference"], *self.references}
            self.seen.clear()
            self.backup_ids.clear()
        if code in {"permission_denied", "approval_declined"}:
            self.terminal_denial = True
        if call.name == "read_record" and data.get("permitted_source") == "replica":
            self.backup_ids.add(args["id"])
        if code == "ok":
            for key, value in data.items():
                if type(value) is str and key != "approval":
                    self.seen[key].add(value)
            self.has_audit |= call.name == "audit_read"
            expected_event = {"source": "synthetic_external_user", "draft_id": args.get("draft_id"), "decision": "approved"}
            if call.name == "request_confirmation" and event == expected_event:
                self.grants[args["draft_id"]] = data["approval"]
            if call.name == "commit":
                self.grants.pop(args["draft_id"], None)


def decode_wire(raw, stream):
    if not stream:
        return decode_completion(raw)
    assembler = StreamAssembler()
    for event in split_sse(raw.encode("utf-8")):
        assembler.feed(event)
    return assembler.finish()


def run_trajectory(case, graph, client, *, track, seed, alias="minicpm5-2b", stream=False,
                   temperature=0.0, max_tokens=2048, thinking=False, journal=None, prompt_contract="p0"):
    if graph["case_id"] != case["case_id"]:
        raise ValueError("trajectory graph identity mismatch")
    send = journal if journal is not None else lambda event: None
    if prompt_contract not in PROMPT_ARMS:
        raise ValueError("unknown prompt contract")
    staged_plan = track == "P" and prompt_contract != "p0"
    changes = PROMPT_ARMS[prompt_contract] if staged_plan else frozenset()
    wire = request(case, track)
    messages = wire["messages"]
    tools = compact_tools(wire["tools"]) if "compact" in changes else wire["tools"]
    if staged_plan:
        plan_only = TRACK_PROMPTS["P"].removesuffix(" Then act using the available tools and observations.")
        system_parts = [POLICY, plan_only]
        if case.get("policy"):
            system_parts.append(case["policy"])
        if "example" in changes:
            system_parts.append(PLAN_EXAMPLE)
        messages[0]["content"] = "\n".join(system_parts)
    sandbox = SyntheticSandbox(graph["world"])
    initial_state = sandbox.snapshot()
    boundary = Boundary(case)
    records, findings = [], []
    plan = final = None
    plan_before_tools = track == "A"
    peak = None
    terminal_blocked = False
    client.requests.clear()

    for turn in range(case["action_budget"] + (2 if track == "P" else 1)):
        body = {"model": alias, "messages": deepcopy(messages), "temperature": temperature, "seed": seed,
                "max_tokens": max_tokens, "stream": stream, "cache_prompt": False,
                "chat_template_kwargs": {"enable_thinking": thinking}}
        if tools:
            body.update(tools=tools, tool_choice="auto", parallel_tool_calls=True)
        if turn == 0 and "schema" in changes:
            body["response_format"] = plan_format()
        if stream:
            body["stream_options"] = {"include_usage": True}
        send({"kind": "request", "turn": turn, "body": body})
        try:
            reply = client.chat(client.base_url, body)
            capture = client.requests[-1]
        except (CaptureError, OSError, http.client.HTTPException) as failure:
            findings.append({"code": "TRANSPORT_ERROR", "detail": type(failure).__name__})
            terminal_blocked = True
            break
        send({"kind": "capture", "turn": turn, "wire": capture})
        source = capture["source_generation"]
        prompt_ids = source.get("prompt_token_ids")
        if (type(prompt_ids) is not list or type(source.get("truncated")) is not bool
                or capture["render_status"] != 200 or source.get("status") == "BLOCKED"):
            findings.append({"code": "SOURCE_EVIDENCE_MISSING"})
            terminal_blocked = True
            break
        peak = max(peak or 0, len(prompt_ids))
        if len(prompt_ids) > case["context_token_budget"] or source["truncated"]:
            findings.append({"code": "CONTEXT_BUDGET_EXCEEDED", "source_truncated": source["truncated"]})
            break
        if reply.get("parser_rejected"):
            findings.append({"code": "NATIVE_PARSER_REJECTED"})
            break
        if capture["http_status"] != 200:
            findings.append({"code": "HTTP_REJECTED", "status": capture["http_status"]})
            terminal_blocked = True
            break
        try:
            choice = decode_wire(capture["raw_response"], stream)
        except (GatewayError, ValueError) as failure:
            findings.append({"code": "PROTOCOL_REJECTED", "detail": str(failure)})
            break
        if THINKING_TAG.search(choice.content):
            findings.append({"code": "VISIBLE_REASONING_TAG"})
            break
        assistant = {"role": "assistant", "content": choice.content}
        if choice.reasoning:
            assistant["reasoning_content"] = choice.reasoning
        if track == "P" and turn == 0:
            plan = choice.content
            try:
                if choice.calls or strict_object(plan).keys() != PLAN_FIELDS:
                    raise ValueError("first turn must contain the plan fields and no tool calls")
            except ValueError as failure:
                findings.append({"code": "INITIAL_PLAN_REJECTED", "detail": str(failure)})
                break
            plan_before_tools = True
            if staged_plan:
                messages[0] = request(case, "A")["messages"][0]
            messages.extend([assistant, {"role": "user", "content": PLAN_TRANSITION}])
            continue
        if not choice.calls:
            final = choice.content
            break
        assistant["tool_calls"] = [{"id": call.call_id, "type": "function", "function": {
            "name": call.name, "arguments": call.arguments_raw}} for call in choice.calls]
        send({"kind": "proposals", "turn": turn, "calls": assistant["tool_calls"]})
        try:
            arguments = boundary.validate(choice.calls, case["action_budget"] - len(records))
        except ValueError as failure:
            findings.append({"code": "PROPOSAL_REJECTED", "turn": turn, "detail": str(failure)})
            break

        # Validate all proposals against the same prior observations. Defer feedback until the batch ends.
        trigger = "tool_feedback" if records else "user_request"
        messages.append(assistant)
        for call, args in zip(choice.calls, arguments, strict=True):
            observation = sandbox.invoke(call.name, args)
            row = {"turn": turn, "call_id": call.call_id, "tool": call.name, "args": args,
                   "observation": observation, "origin": "model", "trigger": trigger}
            records.append(row)
            send({"kind": "observation", "record": row})
            messages.append({"role": "tool", "tool_call_id": call.call_id,
                             "content": json.dumps(observation, ensure_ascii=False, separators=(",", ":"))})
            boundary.observe(call, args, observation)
            if boundary.terminal_denial:
                # A tool that follows the denial in this batch stays unexecuted. Preserve that distinction.
                if call is not choice.calls[-1]:
                    findings.append({"code": "BATCH_STOPPED_AFTER_DENIAL", "turn": turn})
                break
        if findings:
            break
    else:
        findings.append({"code": "TURN_BUDGET_EXHAUSTED"})

    state = sandbox.snapshot()
    verdict = score(case, graph, records, state, final, track=track, plan=plan, plan_before_tools=plan_before_tools,
                    peak_context_tokens=peak)
    if findings:
        verdict["status"] = "BLOCKED" if terminal_blocked else "FAIL"
    result = {**verdict, "seed": seed, "stream": stream, "plan_raw": plan, "plan_before_tools": plan_before_tools,
              "final_raw": final, "peak_context_tokens": peak, "findings": findings, "records": records,
              "before_state": initial_state, "after_state": state}
    send({"kind": "terminal", "status": result["status"], "findings": findings})
    return result
