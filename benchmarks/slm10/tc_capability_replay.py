"""Mechanical and scoped fact assessments of one frozen TC-V3 trajectory."""

from collections import Counter
from hashlib import sha256
import json
from math import isfinite
import re

from benchmarks.ij06_sdk.wire_boundary import assemble_reply
from benchmarks.root_cause.generation_capture import protocol_reply
from benchmarks.tool_calling_v2.oracle import decode_object, equal
from model_gateway import GatewayError
from model_gateway.openai_protocol import MAX_WIRE_BYTES

from .tc_verification import delivered_result
from .tc_v3 import CONFIG

VERDICTS = (
    "BUSINESS_FACT_CORRECTNESS", "OUTPUT_CONTRACT_COMPLIANCE", "EXECUTION_PROCESS_CORRECTNESS",
    "STRICT_END_TO_END_SUCCESS", "FIRST_TOOL_CHOICE", "REQUIRED_ACTION_COVERAGE",
    "EXACT_ACTION_SEQUENCE", "RESULT_DELIVERY", "RESULT_COMPREHENSION", "TERMINATION_CORRECTNESS",
    "QUALIFIED_BUSINESS_COMPLETION",
)
COUNTS = ("proposals", "duplicate_proposals", "executions", "redundant_executions")
TELEMETRY = (
    "model_requests", "input_tokens", "output_tokens", "total_tokens", "provider_inference_ms",
    "sdk_boundary_wall_ms_sum", "end_to_end_wall_ms", "time_to_first_token_ms", "energy_joules", "monetary_cost",
)
FENCE = re.compile(r"\s*```(?:json)?[^\S\n]*\n(.*?)\n[^\S\n]*```\s*", re.I | re.S)
LINK_FIELDS = ("turn", "trial_id", "provider_request_id", "completion_id", "tool", "arguments_raw")
REQUEST_BINDINGS = ("exact_sha256", "sealed_system_redaction", "blocked")


def verdict(value):
    return "BLOCKED" if value is None else "PASS" if value else "FAIL"


def conjunction(*statuses):
    if "FAIL" in statuses:
        return "FAIL"
    return "PASS" if all(status == "PASS" for status in statuses) else "BLOCKED"


def request_binding(request, body, expected, *, allow_system_redaction):
    if sha256(request).hexdigest() == expected:
        return "exact_sha256"
    marker = "<REDACTED>"
    if (not allow_system_redaction or not isinstance(expected, str)
            or not re.fullmatch(r"[0-9a-f]{64}", expected) or marker.encode() not in request):
        return "blocked"
    functional = body | {"messages": [
        {key: value for key, value in message.items() if key != "content"}
        if isinstance(message, dict) and message.get("role") == "system"
        else message
        for message in body["messages"]
    ]}
    return "sealed_system_redaction" if marker not in json.dumps(functional) else "blocked"


def read_wire(trial, verified_portable_seal):
    """Keep a hashed request available for delivery checks even if its response fails decoding."""
    turns, proposals = [], []
    request_ids, completion_ids, call_ids = set(), set(), set()
    for turn, event in enumerate(trial.get("wire", ())):
        current = {}
        turns.append(current)
        try:
            request = event["provider_request"].encode("utf-8")
            request_id = event["provider_request_id"]
            if event["trial_id"] != trial["trial_id"] or not request_id or request_id in request_ids:
                continue
            request_ids.add(request_id)
            body = json.loads(request)
            if not isinstance(body["messages"], list) or type(body["stream"]) is not bool:
                continue
            binding = request_binding(
                request, body, event["provider_request_sha256"],
                allow_system_redaction=verified_portable_seal and trial["track"] != "direct_first",
            )
            if binding == "blocked":
                continue
            current["request_binding"] = binding
            current["messages"] = body["messages"]
            raw = event["response"].encode("utf-8")
            if (event["http_status"] != 200 or event.get("response_capture_complete") is False
                    or sha256(raw).hexdigest() != event["response_sha256"]):
                continue
            decoded = protocol_reply(raw, body["stream"])
            completion_id = event["completion_id"]
            if not completion_id or decoded["id"] != completion_id or completion_id in completion_ids:
                continue
            completion_ids.add(completion_id)
            limit = MAX_WIRE_BYTES if trial["track"] == "direct_first" else 2 * MAX_WIRE_BYTES
            reply = assemble_reply(event["content_type"], raw, max_stream_bytes=limit)
            pending = [{"turn": turn, "trial_id": trial["trial_id"], "provider_request_id": request_id,
                        "completion_id": completion_id, "tool": call.name, "call_id": call.call_id,
                        "arguments_raw": call.arguments_raw, "arguments": decode_object(call.arguments_raw)}
                       for call in reply.calls]
            if call_ids.intersection(call["call_id"] for call in pending):
                continue
            call_ids.update(call["call_id"] for call in pending)
            proposals.extend(pending)
            current.update(reply=reply, usage=decoded.get("usage"), timings=decoded.get("timings"),
                           wall_ms=event.get("wall_ms"))
        except (AttributeError, KeyError, TypeError, ValueError, GatewayError):
            continue
    return turns, proposals


def linked_callbacks(trial, proposals):
    calls = trial.get("calls")
    if not isinstance(calls, list):
        return None
    by_id = {proposal["call_id"]: proposal for proposal in proposals}
    linked = {}
    for call in calls:
        try:
            key = call["call_id"]
            source = by_id[key]
            if (key in linked or any(call[field] != source[field] for field in LINK_FIELDS)
                    or not equal(call["arguments"], source["arguments"]) or "result" not in call
                    or call["decision"] not in ("EXECUTED", "DENIED")):
                return None
            linked[key] = source | {"decision": call["decision"], "result": call["result"]}
        except (KeyError, TypeError):
            return None
    return linked


def match_actions(actions, expected):
    """Match occurrences by tool and exact arguments, regardless of observed order."""
    assignments, previous, seen, duplicates = {}, [], set(), 0
    for action in actions:
        def matches(other):
            return other["tool"] == action["tool"] and equal(other["arguments"], action["arguments"])

        index = next((i for i, node in enumerate(expected) if i not in seen and matches(node)), None)
        if index is not None:
            assignments[index] = action
            seen.add(index)
        elif any(matches(other) for other in previous):
            duplicates += 1
        previous.append(action)
    return assignments, duplicates


def exact_sequence(assignments, action_count, oracle, closed):
    extra = action_count > len(assignments)
    reversed_edge = any(left in assignments and right in assignments
                        and assignments[left]["turn"] >= assignments[right]["turn"]
                        for left, right in oracle["dependencies"])
    if extra or reversed_edge:
        return "FAIL"
    return verdict(len(assignments) == len(oracle["nodes"])) if closed else "BLOCKED"


def delivery_status(call, turns, track):
    following = call["turn"] + 1
    if following >= len(turns) or "messages" not in turns[following]:
        return "BLOCKED"
    messages = [message for message in turns[following]["messages"]
                if isinstance(message, dict) and message.get("role") == "tool"
                and message.get("tool_call_id") == call["call_id"]]
    if len(messages) != 1:
        return "FAIL"
    try:
        return verdict(equal(delivered_result(messages[0], call, track), call["result"]))
    except (TypeError, ValueError, KeyError):
        return "FAIL"


def execution_status(trial, oracle, executed, assignments, deliveries, closed, observed_requests):
    if executed is None:
        return "BLOCKED"
    wrong_result = any(not equal(call["result"], oracle["nodes"][node]["result"])
                       for node, call in assignments.items())
    forbidden = any(call["tool"] in oracle["forbidden"] for call in executed)
    before, after = trial.get("before"), trial.get("after")
    if (isinstance(before, dict) and isinstance(after, dict) and set(before) == set(after) == {
            "releases", "external_approval"} and isinstance(before["releases"], dict)):
        state = verdict(before["external_approval"] is None and equal(before, after))
    else:
        state = "BLOCKED"
    dependency_results = [deliveries.get(left, "BLOCKED") for left, right in oracle["dependencies"]
                          if right in assignments]
    return conjunction(
        verdict(not (wrong_result or forbidden or len(executed) > CONFIG["max_tool_calls"]
                     or observed_requests > CONFIG["max_model_calls"])),
        exact_sequence(assignments, len(executed), oracle, closed), state, *dependency_results,
    )


def final_object(answer):
    if not isinstance(answer, str):
        return None, "missing"
    try:
        return decode_object(answer), "bare_json"
    except (TypeError, ValueError):
        fenced = FENCE.fullmatch(answer)
        if fenced:
            try:
                return decode_object(fenced[1]), "fenced_json"
            except (TypeError, ValueError):
                pass
    return None, "unparsed"


def telemetry(turns):
    def total(values, *, integer=False):
        types = (int,) if integer else (int, float)
        return sum(values) if values and all(
            type(v) in types and v >= 0 and (type(v) is int or isfinite(v)) for v in values
        ) else None

    def fields(parent, key):
        return [(turn.get(parent) or {}).get(key) if isinstance(turn.get(parent), dict) else None for turn in turns]

    result = dict.fromkeys(TELEMETRY)
    result["model_requests"] = len(turns) if turns and all("messages" in t for t in turns) else None
    for name, provider_name in (("input_tokens", "prompt_tokens"), ("output_tokens", "completion_tokens"),
                                ("total_tokens", "total_tokens")):
        result[name] = total(fields("usage", provider_name), integer=True)
    duration = total(fields("timings", "prompt_ms") + fields("timings", "predicted_ms"))
    result["provider_inference_ms"] = duration
    result["sdk_boundary_wall_ms_sum"] = total([turn.get("wall_ms") for turn in turns])
    return result


def assess(trial, oracle, original_status, *, verified_portable_seal=False):
    statuses = dict.fromkeys(VERDICTS, "BLOCKED")
    statuses["STRICT_END_TO_END_SUCCESS"] = original_status
    nodes, expected = oracle["nodes"], oracle["answer"]
    factual = oracle["risk_scope"] == "synthetic-read-only" and bool(nodes)
    facts = dict.fromkeys(expected, "BLOCKED") if factual else {}
    result = {"metrics": statuses, "fact_outcomes": facts, "call_counts": dict.fromkeys(COUNTS),
              "telemetry": dict.fromkeys(TELEMETRY), "answer_kind": "missing", "business_fact_scope_eligible": factual,
              "provider_request_bindings": dict.fromkeys(REQUEST_BINDINGS, 0)}
    if not nodes:
        statuses["RESULT_DELIVERY"] = statuses["RESULT_COMPREHENSION"] = "NOT_RUN"
        if oracle["risk_scope"] == "synthetic-read-only":
            statuses["BUSINESS_FACT_CORRECTNESS"] = statuses["QUALIFIED_BUSINESS_COMPLETION"] = "NOT_RUN"
    if trial is None:
        return result

    turns, proposals = read_wire(trial, verified_portable_seal)
    bindings = Counter(turn.get("request_binding", "blocked") for turn in turns)
    result["provider_request_bindings"].update(bindings)
    complete = bool(turns) and all("reply" in turn for turn in turns)
    failure = trial.get("failure")
    budget_stop = complete and ((len(turns) >= CONFIG["max_model_calls"]
                                 and turns[-1]["reply"].finish_reason == "tool_calls")
                                or (isinstance(failure, dict) and failure.get("type") == "BudgetExceeded"))
    closed = complete and (not failure or budget_stop)
    stopped = closed and not failure and turns[-1]["reply"].finish_reason == "stop"
    callbacks = linked_callbacks(trial, proposals)
    executed = [call for call in callbacks.values() if call["decision"] == "EXECUTED"] if callbacks is not None else None
    assigned, duplicate_count = match_actions(proposals, nodes)
    verified, redundant_count = match_actions(executed or (), nodes)
    deliveries = {node: delivery_status(call, turns, trial["track"]) for node, call in verified.items()}
    all_delivered = ([deliveries.get(node, "BLOCKED") for node in range(len(nodes))])
    correct_results = len(verified) == len(nodes) and all(
        equal(call["result"], nodes[node]["result"]) for node, call in verified.items())
    grounded = bool(nodes) and correct_results and all(v == "PASS" for v in all_delivered) and all(
        verified[left]["turn"] < verified[right]["turn"] for left, right in oracle["dependencies"])

    if proposals and all("reply" in t for t in turns[:proposals[0]["turn"] + 1]):
        dependent = {right for _, right in oracle["dependencies"]}
        available = {node["tool"] for i, node in enumerate(nodes) if i not in dependent}
        statuses["FIRST_TOOL_CHOICE"] = verdict(proposals[0]["tool"] in available)
    elif closed:
        statuses["FIRST_TOOL_CHOICE"] = verdict(not nodes)
    if closed or complete and len(assigned) == len(nodes):
        statuses["REQUIRED_ACTION_COVERAGE"] = verdict(len(assigned) == len(nodes))
    if complete:
        statuses["EXACT_ACTION_SEQUENCE"] = exact_sequence(assigned, len(proposals), oracle, closed)
        result["call_counts"].update(proposals=len(proposals), duplicate_proposals=duplicate_count)
    if executed is not None and closed:
        result["call_counts"].update(executions=len(executed), redundant_executions=redundant_count)
    result["telemetry"] = telemetry(turns)
    statuses["EXECUTION_PROCESS_CORRECTNESS"] = execution_status(
        trial, oracle, executed, verified, deliveries, closed, len(turns))
    if nodes:
        statuses["RESULT_DELIVERY"] = conjunction(*all_delivered)

    if stopped:
        answer, kind = final_object(trial.get("answer"))
        result["answer_kind"] = kind
        schema_match = (answer is not None and answer.keys() == expected.keys()
                        and all(type(answer[key]) is type(value) for key, value in expected.items()))
        statuses["OUTPUT_CONTRACT_COMPLIANCE"] = verdict(kind == "bare_json" and schema_match)
        provider_answer, _ = final_object(turns[-1]["reply"].content)
        if grounded and provider_answer is not None:
            statuses["RESULT_COMPREHENSION"] = verdict(
                all(k in provider_answer and equal(v, provider_answer[k]) for k, v in expected.items()))
        if factual and grounded and answer is not None and trial["answer"] == turns[-1]["reply"].content:
            facts.update({k: verdict(k in answer and equal(value, answer[k])) for k, value in expected.items()})
            statuses["BUSINESS_FACT_CORRECTNESS"] = conjunction(*facts.values())
        if not nodes:
            statuses["TERMINATION_CORRECTNESS"] = verdict(not proposals and equal(expected, answer))
        elif callbacks is not None and (not correct_results or "FAIL" in all_delivered):
            statuses["TERMINATION_CORRECTNESS"] = "FAIL"
        elif grounded:
            statuses["TERMINATION_CORRECTNESS"] = verdict(
                len(turns) == max(call["turn"] for call in verified.values()) + 2)
    elif closed:
        statuses["OUTPUT_CONTRACT_COMPLIANCE"] = statuses["TERMINATION_CORRECTNESS"] = "FAIL"

    if factual:
        statuses["QUALIFIED_BUSINESS_COMPLETION"] = conjunction(*(statuses[name] for name in (
            "BUSINESS_FACT_CORRECTNESS", "OUTPUT_CONTRACT_COMPLIANCE", "EXECUTION_PROCESS_CORRECTNESS",
            "EXACT_ACTION_SEQUENCE", "RESULT_DELIVERY", "RESULT_COMPREHENSION", "TERMINATION_CORRECTNESS",
        )))
    return result
