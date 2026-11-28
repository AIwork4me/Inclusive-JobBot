"""Execute complete TC-V2 trajectories through the strict model gateway."""

from dataclasses import asdict
import http.client
import json
import re

from benchmarks.root_cause.generation_capture import CaptureError
from business_tools import encode_state
from model_gateway import GatewayError, StreamAssembler, decode_completion
from model_gateway.openai_protocol import decode_proposal

from ..evaluator import Call, VALIDATOR
from ..oracle import decode_object
from ..parser.assessment import typed_equal
from ..parser.run_wire import split_sse
from .host import SYSTEM, TOOLS, Session, wire_tools
from .oracle import score


ALIAS = "minicpm5-2b"
MAX_TURNS = 7
MAX_TOKENS = 768
THINK_TAGS = re.compile(r"<\s*/?\s*think\b[^>]*>", re.IGNORECASE)


def request(messages, case, stream, seed):
    body = {
        "model": ALIAS, "messages": messages, "tools": wire_tools(case),
        "tool_choice": "auto", "parallel_tool_calls": True, "temperature": 0, "seed": seed,
        "max_tokens": MAX_TOKENS, "stream": stream, "cache_prompt": False,
        "chat_template_kwargs": {"enable_thinking": case["reasoning_required"]},
    }
    if stream:
        body["stream_options"] = {"include_usage": True}
    return body


def decode_wire(raw, stream):
    if not stream:
        return decode_completion(raw)
    assembler = StreamAssembler()
    for event in split_sse(raw.encode("utf-8")):
        assembler.feed(event)
    return assembler.finish()


def parser_rejections(capture):
    """Count source-observed native tool-call attempts when the parser rejects."""
    source = capture["source_generation"]
    raw = bytes.fromhex(source.get("pre_parser_bytes_hex", ""))
    opens = len(re.findall(rb"<function\s+name\s*=", raw))
    return opens or int(b"<tool_call>" in raw)


def proposals_in_reply(reply, case):
    choices = reply.get("choices") or []
    message = (choices[0].get("message") or {}) if choices else {}
    calls = message.get("tool_calls") or []
    if not isinstance(calls, list):
        return 1, 1
    invalid = 0
    seen = set()
    for row in calls:
        try:
            proposal = decode_proposal(row)
            args = decode_object(proposal.arguments_raw)
            if (proposal.call_id in seen or proposal.name not in case["tools"]
                    or not VALIDATOR(TOOLS[proposal.name].schema).is_valid(args)):
                invalid += 1
            seen.add(proposal.call_id)
        except (GatewayError, ValueError):
            invalid += 1
    return len(calls), invalid


def run_trajectory(case, client, database, *, stream, seed):
    session = Session(case, database)
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": case["prompt"]}]
    calls, notes = [], []
    final = ""
    completed = separated = leaked = parser_rejected = False
    transport_failure = source_missing = False
    protocol_status = "PASS"
    proposal_count = invalid_count = 0
    client.requests.clear()
    for turn in range(MAX_TURNS):
        try:
            reply = client.chat(client.base_url, request(list(messages), case, stream, seed))
        except (OSError, http.client.HTTPException, CaptureError) as failure:
            notes.append({"code": "F04_TRANSPORT_ERROR", "detail": type(failure).__name__})
            transport_failure = True
            break
        capture = client.requests[-1]
        source_missing |= (
            capture["source_generation"].get("status") == "BLOCKED" or capture["render_status"] != 200
        )
        if reply.get("parser_rejected"):
            count = parser_rejections(capture)
            invalid_count += count
            proposal_count += count
            parser_rejected = True
            notes.append({"code": "F06_NATIVE_PARSER_ERROR", "detail": "native parser rejected generated output"})
            break
        if capture["http_status"] != 200:
            notes.append({"code": "F04_TRANSPORT_ERROR", "detail": f"HTTP {capture['http_status']}"})
            transport_failure = True
            break
        count, invalid = proposals_in_reply(reply, case)
        proposal_count += count
        invalid_count += invalid
        try:
            choice = decode_wire(capture["raw_response"], stream)
        except (GatewayError, ValueError) as failure:
            protocol_status = "FAIL"
            notes.append({"code": "F05_PROTOCOL_ERROR", "detail": str(failure)})
            break
        separated |= bool(choice.reasoning.strip())
        leaked |= bool(THINK_TAGS.search(choice.content))
        if not choice.calls:
            final = choice.content
            completed = True
            break
        assistant = {"role": "assistant", "content": choice.content, "tool_calls": [
            {"id": call.call_id, "type": "function",
             "function": {"name": call.name, "arguments": call.arguments_raw}}
            for call in choice.calls
        ]}
        if choice.reasoning:
            assistant["reasoning_content"] = choice.reasoning
        messages.append(assistant)
        for call in choice.calls:
            observed = session.execute(call.call_id, call.name, call.arguments_raw)
            calls.append(Call(turn, call.call_id, call.name, call.arguments_raw, observed))
            messages.append({"role": "tool", "tool_call_id": call.call_id,
                             "content": encode_state(observed)})
    else:
        notes.append({"code": "F12_FINAL_ANSWER_ERROR", "detail": "turn budget exhausted"})
    reasoning_ok = not leaked and (not case["reasoning_required"] or separated)
    if not reasoning_ok:
        notes.append({"code": "F05_PROTOCOL_ERROR", "detail": "reasoning missing or leaked into visible content"})
    verdict = score(case, calls, final, session)
    if notes:
        verdict["findings"].extend(notes)
        verdict["trace_status"] = "FAIL"
        verdict["status"] = "FAIL"
    if transport_failure or source_missing:
        verdict["status"] = "BLOCKED"
    return {
        **verdict, "completed": completed, "seed": seed, "stream": stream,
        "protocol_status": protocol_status, "reasoning_status": "PASS" if reasoning_ok else "FAIL",
        "native_parser_rejected": parser_rejected, "source_evidence_missing": source_missing,
        "transport_failure": transport_failure, "proposal_count": proposal_count, "invalid_proposal_count": invalid_count,
        "required_tool_steps": len(case["oracle"]["steps"]),
        "final": final, "calls": [asdict(call) for call in calls],
        "before_sqlite": session.before, "after_sqlite": session.store.snapshot(),
        "requests": list(client.requests),
    }


def paired(complete, stream):
    def signatures(row):
        return [{"turn": call["turn"], "tool": call["name"], "arguments": decode_object(call["arguments_raw"])}
                for call in row["calls"]]

    if any(row.get("status") == "BLOCKED" for row in (complete, stream)):
        return {"status": "BLOCKED", "reason": "pair missing assessable evidence"}
    if not all(row["completed"] and row["protocol_status"] == "PASS" and row["reasoning_status"] == "PASS"
               for row in (complete, stream)):
        return {"status": "FAIL", "reason": "response was incomplete or protocol/reasoning integrity failed"}
    if any(row.get("required_tool_steps") and not row["calls"] for row in (complete, stream)):
        return {"status": "FAIL", "reason": "required calls absent from paired observations"}
    ids_ok = all(
        all(isinstance(call["call_id"], str) and call["call_id"].strip() for call in row["calls"])
        and len({call["call_id"] for call in row["calls"]}) == len(row["calls"])
        for row in (complete, stream)
    )
    try:
        matches = ids_ok and typed_equal(signatures(complete), signatures(stream))
    except ValueError:
        matches = False
    return {"status": "PASS" if matches else "FAIL",
            "reason": "typed function and turn parity" if matches else "tool sequence or identity differs"}
