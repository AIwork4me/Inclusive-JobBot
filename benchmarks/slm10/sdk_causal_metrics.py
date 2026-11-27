"""Versioned offline SDK diagnostics. The frozen TC-V3 scores remain authoritative."""

from collections import Counter, defaultdict
from hashlib import sha256
import json
import re

from benchmarks.ij06_sdk.wire_boundary import assemble_reply
from benchmarks.root_cause.generation_capture import protocol_reply
from benchmarks.tool_calling_v2.oracle import decode_object, equal
from evaluation.aeve.runtime import canonical
from model_gateway import GatewayError

from .tc_verification import delivered_result

VERSION = "IJ-SLM-SDK-CAUSAL-METRICS/1.0"
FENCE = re.compile(r"\s*\x60{3}(?:json)?\s*\n(.*?)\n\s*\x60{3}\s*", re.S | re.I)
NATIVE_FORMS = {
    "A": re.compile(r'<function name="([a-z_]+)"><param name="reference">([^<>]+)</param></function>'),
    "B": re.compile(r"<function=([a-z_]+)>\s*<parameter=reference>\s*([^<\r\n]+)\s*</parameter>"),
    "D": re.compile(r"<function=([a-z_]+)>\s*<parameter=reference>\s*([^<\r\n]+)\s*</parameter>"),
}


def verdict(flag):
    return "BLOCKED" if flag is None else "PASS" if flag else "FAIL"


def answer_metrics(answer, expected, terminal, has_delivery):
    if not terminal or not isinstance(answer, str):
        return dict(result_comprehension="BLOCKED", final_answer="BLOCKED", answer_kind="missing_final")
    try:
        value = decode_object(answer)
        kind = "exact_json"
    except (TypeError, ValueError):
        match = FENCE.fullmatch(answer)
        if match is None:
            return dict(result_comprehension="BLOCKED", final_answer="FAIL", answer_kind="unparsed")
        try:
            value = decode_object(match[1])
        except (TypeError, ValueError):
            return dict(result_comprehension="BLOCKED", final_answer="FAIL", answer_kind="unparsed")
        kind = "fenced_json"
    observable = all(key in value for key in expected)
    return {
        "result_comprehension": verdict(all(equal(value[key], expected[key]) for key in expected))
        if has_delivery and observable else "BLOCKED",
        "final_answer": verdict(kind == "exact_json" and equal(value, expected)),
        "answer_kind": kind if equal(value, expected) else kind + "_wrong_value",
    }


def action_identity(tool, arguments):
    return (tool, canonical(arguments))


def assign_actions(nodes, edges, calls):
    """Match specific occurrences by canonical arguments and dependency order."""
    required = defaultdict(set)
    for left, right in edges:
        required[right].add(left)
    identities = [action_identity(node["tool"], node["arguments"]) for node in nodes]
    assigned_turns, prior = {}, set()
    assignments, duplicates = [], []
    for i, call in enumerate(calls):
        identity = action_identity(call["tool"], call["arguments"])
        candidate = next((n for n, expected in enumerate(identities)
                          if expected == identity and n not in assigned_turns
                          and all(assigned_turns.get(p, call["turn"]) < call["turn"] for p in required[n])), None)
        if candidate is not None:
            assigned_turns[candidate] = call["turn"]
        elif identity in prior:
            duplicates.append(i)
        prior.add(identity)
        assignments.append(candidate)
    return assignments, duplicates


def replay_wire(trial, candidate):
    """Replay both provider output and its SDK-facing adaptation on identical bytes."""
    turns, proposals = [], []
    for n, event in enumerate(trial["wire"]):
        try:
            raw = event["response"].encode("utf-8")
            if (sha256(raw).hexdigest() != event["response_sha256"] or event["http_status"] != 200
                    or event["trial_id"] != trial["trial_id"]):
                raise ValueError("provider capture integrity")
            body = json.loads(event["provider_request"])
            decoded = protocol_reply(raw, body["stream"])
            if decoded["id"] != event["completion_id"]:
                raise ValueError("completion identity")
            reply = assemble_reply(event["content_type"], raw, max_stream_bytes=1048576)
            if "sdk_response" in event:
                forwarded = assemble_reply(event["sdk_content_type"], event["sdk_response"].encode(), max_stream_bytes=1048576)
                adapter = verdict(forwarded == reply)
            else:
                adapter = "NOT_RUN"
            native = event.get("source_generation")
            native_match = "BLOCKED"
            if native and native.get("completion_id") == decoded["id"]:
                generation = bytes.fromhex(native["pre_parser_bytes_hex"]).decode()
                tagged = tuple((tool, reference.strip()) for tool, reference in NATIVE_FORMS[candidate].findall(generation))
                parsed = tuple((call.name, decode_object(call.arguments_raw).get("reference")) for call in reply.calls)
                if tagged or parsed:
                    native_match = verdict(tagged == parsed) if tagged else "BLOCKED"
                elif reply.content and reply.content.strip() == generation.strip():
                    native_match = "PASS"
            tools = body.get("tools", [])
            turns.append({
                "request_sha256": event["provider_request_sha256"], "response_sha256": event["response_sha256"],
                "completion_id": event["completion_id"], "adapter_same_bytes": adapter,
                "native_visible_match": native_match, "native_capture": event.get("native_evidence", {}).get("status"),
                "timings": decoded.get("timings"), "usage": decoded.get("usage"),
                "wall_ms": event.get("wall_ms"), "finish": reply.finish_reason,
                "tool_contract_sha256": sha256(canonical(tools)).hexdigest(),
                "system_bytes": sum(len(item["content"].encode()) for item in body["messages"] if item["role"] == "system"),
                "provider_answer": reply.content, "request_messages": body["messages"],
            })
            proposals.extend({"turn": n, "tool": call.name, "arguments": decode_object(call.arguments_raw),
                              "call_id": call.call_id, "completion_id": event["completion_id"],
                              "provider_request_id": event["provider_request_id"]} for call in reply.calls)
        except (ValueError, KeyError, TypeError, GatewayError):
            turns.append({"capture": "BLOCKED", "http_status": event.get("http_status")})
    return turns, proposals


def analyze(trial, oracle, candidate, old, peak_bytes=None):
    turns, proposals = replay_wire(trial, candidate)
    complete_capture = bool(turns) and all("finish" in event for event in turns)
    terminal = complete_capture and turns[-1]["finish"] == "stop" and not trial.get("failure")
    nodes = oracle["nodes"]
    assigned, duplicates = assign_actions(nodes, oracle["dependencies"], proposals)
    calls = {row["call_id"]: row for row in trial.get("calls", ())}
    args, delivery, proof, executed = [], [], [], []
    deliveries = {}
    for index, (proposal, node) in enumerate(zip(proposals, assigned, strict=True)):
        call = calls.get(proposal["call_id"])
        linked = call and all(call.get(k) == proposal[k] for k in
                              ("turn", "tool", "arguments", "completion_id", "provider_request_id"))
        tool_result = None
        if linked:
            if call["decision"] == "EXECUTED":
                executed.append(index)
            # Scope delivery to the first provider request after this callback.
            next_turn = proposal["turn"] + 1
            if next_turn < len(turns) and "request_messages" in turns[next_turn]:
                messages = [m for m in turns[next_turn]["request_messages"]
                            if m["role"] == "tool" and m.get("tool_call_id") == proposal["call_id"]]
                if len(messages) == 1:
                    try:
                        tool_result = equal(delivered_result(messages[0], call, trial["track"]), call["result"])
                    except (ValueError, TypeError):
                        tool_result = False
                else:
                    tool_result = False
        if node is not None:
            delivery.append(tool_result)
            deliveries[node] = (verdict(tool_result) == "PASS" and linked and call["decision"] == "EXECUTED"
                                and equal(call["result"], nodes[node]["result"]))
        candidates = [n for n in nodes if n["tool"] == proposal["tool"]]
        arg_status = verdict(any(equal(n["arguments"], proposal["arguments"]) for n in candidates)) if candidates else "BLOCKED"
        args.append(arg_status)
        proof.append(proposal | {"action_id": f"node-{node}" if node is not None else None, "argument_accuracy": arg_status,
                                 "callback": verdict(bool(linked)) if call is not None else "BLOCKED",
                                 "decision": call["decision"] if linked else None,
                                 "result_delivery": verdict(tool_result)})
    scope = "APPLICABLE" if nodes else "NOT_APPLICABLE"
    coverage = len(set(assigned) - {None}) == len(nodes)
    sequence = coverage and all(node is not None for node in assigned)
    edges = set(map(tuple, oracle["dependencies"]))
    if sequence:
        order = dict(zip(assigned, [row["turn"] for row in proposals], strict=True))
        sequence = all(order[left] < order[right] for left, right in edges)
    qualifying_delivery = bool(nodes) and coverage and all(deliveries.get(i) for i in range(len(nodes)))
    answer = answer_metrics(trial.get("answer"), oracle["answer"], terminal, qualifying_delivery)
    budget_stop = any(event.get("http_status") is None and "capture" in event for event in turns) and len(turns) > 4
    stops = verdict(coverage and sequence) if terminal else verdict(False) if budget_stop else "BLOCKED"
    delivery_verdict = verdict(False) if False in delivery else verdict(
        True if coverage and len(delivery) == len(nodes) and all(delivery) and nodes else None)
    required = {
        "first_tool_choice": verdict(proposals[0]["tool"] in {n["tool"] for i, n in enumerate(nodes)
                                                            if all(right != i for _, right in edges)}) if proposals else verdict(
            not nodes if terminal else None),
        "required_tool_coverage": verdict(coverage if complete_capture else None),
        "exact_tool_sequence": verdict(sequence if complete_capture or duplicates else None),
        "argument_accuracy_per_call": verdict(all(s == "PASS" for s in args)) if args and "BLOCKED" not in args else "BLOCKED",
        "result_delivery": delivery_verdict, "stop_decision": stops, **answer,
        "business_correctness": "BLOCKED", "strict_end_to_end": old.get("strict_end_to_end", "BLOCKED"),
    }
    if oracle["risk_scope"] == "synthetic-read-only" and qualifying_delivery and required["final_answer"] in ("PASS", "FAIL"):
        required["business_correctness"] = required["final_answer"]
    failed = sorted(name for name in ("required_tool_coverage", "exact_tool_sequence", "result_delivery",
                                      "final_answer", "stop_decision") if required[name] == "FAIL")
    summary_turns = [{k: v for k, v in turn.items() if k not in ("request_messages", "provider_answer")} for turn in turns]
    usage = [t.get("usage") for t in turns]
    timings = [t.get("timings") for t in turns]
    totals = {}
    if turns and all(isinstance(u, dict) and "prompt_tokens" in u and "completion_tokens" in u for u in usage):
        totals["input_tokens"] = sum(u["prompt_tokens"] for u in usage)
        totals["output_tokens"] = sum(u["completion_tokens"] for u in usage)
    if turns and all(isinstance(t, dict) and "prompt_ms" in t and "predicted_ms" in t for t in timings):
        totals["provider_inference_ms"] = sum(t["prompt_ms"] + t["predicted_ms"] for t in timings)
    if turns and all(isinstance(t.get("wall_ms"), (int, float)) for t in turns):
        totals["sdk_boundary_wall_ms_sum"] = sum(t["wall_ms"] for t in turns)
    return {"version": VERSION, "candidate": candidate, "case_id": trial["case_id"], "track": trial["track"],
            "trial_id": trial["trial_id"], "metrics": required, "call_applicability": scope,
            "business_scope": oracle["risk_scope"], "counterfactual_status": "NOT_RUN",
            "PROVEN_NECESSARY_CONDITION_FAILURE": failed, "old_assessment": old,
            "turns": summary_turns, "actions": proof, "duplicate_proposals": len(duplicates),
            "redundant_executions": sum(index in executed for index in duplicates),
            "model_requests": len(turns), "session_peak_gpu_committed_bytes": peak_bytes, **totals}


def summary(rows):
    def rate(count, total):
        return {"count": count, "denominator": total, "rate": count / total if total else None}

    cells = {}
    for candidate in sorted({row["candidate"] for row in rows}):
        selected = [row for row in rows if row["candidate"] == candidate]
        for track in sorted({row["track"] for row in selected}):
            arm = [row for row in selected if row["track"] == track]
            successes = [r for r in arm if r["metrics"]["business_correctness"] == "PASS"]
            counts = {name: dict(Counter(r["metrics"][name] for r in arm)) for name in arm[0]["metrics"]}
            cells[candidate + "/" + track] = {
                "trials": len(arm), "metrics": counts,
                "duplicate_proposal_rate": rate(sum(r["duplicate_proposals"] for r in arm), sum(len(r["actions"]) for r in arm)),
                "redundant_execution_rate": rate(sum(r["redundant_executions"] for r in arm),
                                                 sum(c.get("decision") == "EXECUTED" for r in arm for c in r["actions"])),
                "requests_per_scoped_success": rate(sum(r["model_requests"] for r in arm), len(successes)),
                "tokens_per_scoped_success": {
                    metric: rate(sum(r[metric] for r in arm), len(successes))
                    if all(metric in r for r in arm) else {"status": "BLOCKED"}
                    for metric in ("input_tokens", "output_tokens")
                },
            }
    return cells
