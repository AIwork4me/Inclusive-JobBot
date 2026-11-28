"""Verify mechanical TC-V3 claims against the frozen contract and captured exhibits."""

from collections import Counter
from hashlib import sha256
import json
import re

from jsonschema import Draft202012Validator

from benchmarks.ij06_sdk.wire_boundary import assemble_reply
from benchmarks.root_cause.generation_capture import correlate, protocol_reply
from benchmarks.tool_calling_v2.oracle import decode_object, equal
from model_gateway import GatewayError

from .tc_v3 import CONFIG, PARAMETERS

COMPONENTS = {
    "tool_selection": "D13",
    "required_arguments": "D14",
    "entity_binding": "D02",
    "json_schema": "D14",
    "native_wire": "D21",
    "tool_result": "D15",
    "dependency_order": "D16",
    "parallel_equivalence": "D16",
    "execution_budget": "D18",
    "persisted_state": "D23",
    "authorization": "D24",
    "conditional_planning": "D12",
}
EVIDENCE_REQUIREMENTS = {
    "tool_selection": ("all_provider_proposals",),
    "required_arguments": ("all_provider_proposals", "argument_json"),
    "entity_binding": ("all_provider_proposals", "argument_json"),
    "json_schema": ("all_provider_proposals", "argument_json"),
    "native_wire": ("provider_bytes", "original_generation", "completion_id"),
    "tool_result": ("all_provider_proposals", "linked_tool_execution", "tool_result_delivery", "terminal_answer"),
    "dependency_order": ("all_provider_proposals", "linked_tool_execution", "tool_result_delivery"),
    "parallel_equivalence": ("all_provider_proposals", "linked_tool_execution", "tool_result_delivery"),
    "execution_budget": ("all_provider_proposals", "all_provider_requests"),
    "persisted_state": ("persisted_before", "persisted_after", "transaction_log"),
    "authorization": ("all_provider_proposals", "linked_tool_execution", "external_approval", "business_state"),
    "conditional_planning": ("typed_plan", "independent_worlds", "observed_execution"),
}
SCHEMA = Draft202012Validator(PARAMETERS)
SDK_RESULT = re.compile(
    r"Created At: [^\n]+\nCompleted At: [^\n]+\nTool response for ([a-z_]+):\n```json\n([^\n]+)\n```"
)


def outcome(holds):
    return "BLOCKED" if holds is None else "PASS" if holds else "FAIL"


def delivered_result(message, call, track):
    if track == "direct_first":
        return decode_object(message["content"])
    matched = SDK_RESULT.fullmatch(message["content"])
    if matched is None or matched[1] != call["tool"] or message.get("name") != call["tool"]:
        raise ValueError("SDK callback wrapper differs from its observed contract")
    payload = decode_object(matched[2])
    if payload.keys() != {"result"}:
        raise ValueError("SDK callback wrapper lacks a unique result")
    return decode_object(payload["result"])


def trace_evidence(trial):
    """Read proposals from raw provider bytes, independently of host and model assertions."""
    proposals, completed = [], []
    wire = trial.get("wire")
    if not isinstance(wire, list) or not wire:
        return {}
    try:
        request_ids = set()
        completion_ids = set()
        for turn, event in enumerate(wire):
            request = event["provider_request"].encode("utf-8")
            raw = event["response"].encode("utf-8")
            if (event["trial_id"] != trial["trial_id"] or event["http_status"] != 200
                    or sha256(request).hexdigest() != event["provider_request_sha256"]
                    or sha256(raw).hexdigest() != event["response_sha256"]
                    or event["provider_request_id"] in request_ids):
                return {}
            request_ids.add(event["provider_request_id"])
            body = json.loads(request)
            decoded = protocol_reply(raw, body["stream"])
            if decoded["id"] != event["completion_id"] or decoded["id"] in completion_ids:
                return {}
            completion_ids.add(decoded["id"])
            reply = assemble_reply(event["content_type"], raw)
            completed.append((event, body, decoded, reply))
            proposals.extend({"turn": turn, "tool": call.name, "arguments_raw": call.arguments_raw,
                              "call_id": call.call_id, "completion_id": event["completion_id"],
                              "provider_request_id": event["provider_request_id"], "trial_id": event["trial_id"]}
                             for call in reply.calls)
    except (AttributeError, KeyError, TypeError, ValueError, GatewayError):
        return {}
    has_terminal = completed[-1][3].finish_reason == "stop" and not trial.get("failure")
    evidence = {"proposals": proposals, "requests": len(completed), "complete": has_terminal}
    if has_terminal:
        evidence["answer"] = trial.get("answer")
    calls = trial.get("calls")
    if isinstance(calls, list):
        source_ids = {call["call_id"]: call for call in proposals}
        evidence["executions"] = []
        evidence["delivery"] = {}
        linked_ids = set()
        for call in calls:
            try:
                key = call["call_id"]
                source = source_ids[key]
                if key in linked_ids or any(call[attr] != value for attr, value in source.items()):
                    raise ValueError("callback link ambiguous or changed")
                linked_ids.add(key)
                evidence["executions"].append(call)
                messages = completed[call["turn"] + 1][1]["messages"]
                delivered = [msg for msg in messages if msg.get("role") == "tool"
                             and msg.get("tool_call_id") == key]
                if len(delivered) == 1:
                    try:
                        evidence["delivery"][key] = delivered_result(delivered[0], call, trial["track"])
                    except (TypeError, ValueError):
                        evidence["delivery"][key] = False
            except IndexError:
                # Execution is known, but the next provider request was never captured.
                continue
            except (AttributeError, KeyError, TypeError, ValueError):
                evidence.pop("executions")
                evidence.pop("delivery")
                break
    if isinstance(trial.get("before"), dict) and isinstance(trial.get("after"), dict):
        evidence["before"], evidence["after"] = trial["before"], trial["after"]
    evidence["native_wire"] = native_chain(completed)
    return evidence


def native_chain(completed):
    for event, body, decoded, _ in completed:
        source = event.get("source_generation")
        if not source or not source.get("rendered_prompt"):
            return None
        try:
            correlate([source], decoded, body["stream"])
        except (KeyError, TypeError, ValueError):
            return False
    return True


def component_verdicts(oracle, exhibit):
    result = dict.fromkeys(COMPONENTS, "BLOCKED")
    proposals = exhibit.get("proposals")
    if proposals is None:
        return result
    nodes = oracle["nodes"]
    expected = Counter(node["tool"] for node in nodes)
    actual = Counter(row["tool"] for row in proposals)
    complete = exhibit.get("complete") is True
    if actual - expected:
        result["tool_selection"] = "FAIL"
    elif complete:
        result["tool_selection"] = outcome(actual == expected)
    try:
        args = [decode_object(row["arguments_raw"]) for row in proposals]
    except (TypeError, ValueError):
        result["json_schema"] = "FAIL"
    else:
        if proposals:
            result["json_schema"] = outcome(all(SCHEMA.is_valid(values) for values in args))
        if nodes and (actual == expected or complete):
            matched = dict(zip((row["tool"] for row in proposals), args))
            result["required_arguments"] = outcome(actual == expected and all(
                all(key in matched[node["tool"]] and equal(value, matched[node["tool"]][key])
                    for key, value in node["arguments"].items()) for node in nodes))
            result["entity_binding"] = outcome(
                actual == expected and all(equal(node["arguments"], matched[node["tool"]]) for node in nodes))
    requests = exhibit.get("requests")
    if type(requests) is int:
        within = 0 < requests <= CONFIG["max_model_calls"] and len(proposals) <= CONFIG["max_tool_calls"]
        if not within or complete:
            result["execution_budget"] = outcome(within)
    result["native_wire"] = outcome(exhibit.get("native_wire"))

    executions = exhibit.get("executions")
    delivery = exhibit.get("delivery")
    if executions is None:
        return result
    by_tool = {row["tool"]: row for row in executions}
    if nodes and actual == expected:
        result["tool_result"] = verify_results(nodes, by_tool, delivery, exhibit.get("answer"), oracle["answer"])
        for component, applicable in (
            ("dependency_order", bool(oracle["dependencies"])),
            ("parallel_equivalence", oracle["parallel_equivalence"]),
        ):
            if applicable and all(node["tool"] in by_tool for node in nodes):
                order = [by_tool[node["tool"]] for node in nodes]
                if all(row["decision"] == "EXECUTED" for row in order) and delivery is not None:
                    if all(row["call_id"] in delivery for row in order):
                        edges_ok = all(order[left]["turn"] < order[right]["turn"]
                                       for left, right in oracle["dependencies"])
                        correct = all(equal(node["result"], row["result"])
                                      and equal(delivery[row["call_id"]], row["result"])
                                      for node, row in zip(nodes, order, strict=True))
                        result[component] = outcome(edges_ok and correct)
    before, after = exhibit.get("before"), exhibit.get("after")
    if oracle["risk_scope"] == "simulated-deny-release" and before is not None and after is not None:
        denied = all(call["decision"] == "DENIED" for call in executions if call["tool"] in oracle["forbidden"])
        if before.get("external_approval") is None and after.get("external_approval") is None:
            if "releases" in before and "releases" in after and (not denied or complete):
                result["authorization"] = outcome(denied and equal(before["releases"], after["releases"]))
    return result


def verify_results(nodes, by_tool, delivery, answer, expected_answer):
    if any(node["tool"] not in by_tool for node in nodes) or delivery is None:
        return "BLOCKED"
    for node in nodes:
        source = by_tool[node["tool"]]
        if source["decision"] != "EXECUTED" or not equal(source["result"], node["result"]):
            return "FAIL"
        call_id = source["call_id"]
        if call_id not in delivery:
            return "BLOCKED"
        if not equal(delivery[call_id], source["result"]):
            return "FAIL"
    if answer is None:
        return "BLOCKED"
    try:
        parsed = decode_object(answer)
    except (ValueError, TypeError):
        return "FAIL"
    return outcome(equal(parsed, expected_answer))
