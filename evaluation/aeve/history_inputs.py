"""Project archived captures into identity-blind, citable evidence events."""
import hashlib
import json
import re


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf8")


def fingerprint(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def family_name(identity):
    lower = str(identity).lower()
    for token, name in (("minicpm", "MiniCPM"), ("aion", "Aion"), ("qwen", "Qwen"), ("lfm", "LFM"),
                        ("ministral", "Mistral"), ("gemma", "Gemma"), ("granite", "Granite")):
        if token in lower:
            return name
    return "unknown"


def packet(trial_id, family, row, public, source_sha):
    events = []

    def event(kind, content):
        if content is None or content == "" or content == []:
            return
        events.append({"id": "ev-" + fingerprint([len(events), kind, content])[:20], "kind": kind, "content": content})

    requests = row.get("requests") or row.get("capture") or []
    if isinstance(requests, dict):
        requests = [requests]
    first = requests[0].get("request", {}) if requests and isinstance(requests[0], dict) else {}
    if first.get("messages"):
        for message in first["messages"]:
            if message.get("role") in {"user", "system"}:
                event("task" if message["role"] == "user" else "policy", message.get("content"))
        event("tools", first.get("tools"))
    else:
        event("task", public.get("prompt") or row.get("initial_input") or public.get("messages"))
        event("policy", public.get("policy") or public.get("system"))
        event("tools", public.get("tools"))
    event("plan", row.get("plan_raw"))
    for update in row.get("delivered_followups") or row.get("delivered_events") or []:
        event("delivered_update", update)
    calls = row.get("records") or row.get("calls") or row.get("model_tool_trace") or []
    if not calls and row.get("steps"):
        calls = [c for step in row["steps"] for c in step.get("tool_calls", [])]
    for call in calls if isinstance(calls, list) else []:
        if not isinstance(call, dict):
            continue
        name = call.get("name") or call.get("tool")
        if name:
            event("action", {"tool": name, "arguments": call.get("args", call.get("arguments", call.get("arguments_raw"))),
                             "turn": call.get("turn")})
        event("observation", call.get("observation", call.get("result", call.get("tool_result"))))
    for key in ("final_raw", "final", "answer", "final_text", "content"):
        if row.get(key) is not None:
            event("answer", row[key])
            break
    kinds = {e["kind"] for e in events}
    if "task" not in kinds or not kinds.intersection({"answer", "plan", "action"}):
        return None
    dimensions = ["D01", "D02", "D03", "D04", "D05"]
    if "plan" in kinds:
        dimensions.extend(["D06", "D07", "D08", "D09", "D10", "D11", "D12", "D19"])
    if "action" in kinds:
        dimensions.extend(["D13", "D14"])
    if "observation" in kinds:
        dimensions.append("D15")
    if sum(e["kind"] == "action" for e in events) > 1:
        dimensions.append("D16")
    if "delivered_update" in kinds or any(isinstance(e["content"],dict) and e["content"].get("code") not in (None,"ok")
                                           for e in events if e["kind"] == "observation"):
        dimensions.append("D17")
    if "answer" in kinds:
        dimensions.append("D20")
    return {"trial_id": trial_id, "source_sha256": source_sha, "source_family": family, "events": events,
            "dimensions": dimensions}

def request_body(capture):
    body = capture.get("request") if isinstance(capture, dict) else None
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except ValueError:
            return {}
    return body if isinstance(body, dict) else {}


_ENVIRONMENT_PATH = re.compile(r"""(?i)(?:[a-z]:[\\/](?:users|workspace)[\\/]|(?:[a-z]:)?[\\/]?[^\s"'<>]*?\.runtime[\\/])[^\r\n"'\s]*""")
_SUBJECT_NAME = re.compile(r"(?i)\b(?:qwen[\w.-]*|lfm[0-9][\w.-]*|minicpm[\w.-]*|ministral[\w.-]*|gemma[\d.-][\w.-]*|aion-[0-9][\w.-]*|granite-[0-9][\w.-]*)")


def blind_content(value):
    if isinstance(value,str):
        if ".runtime" in value or ":\\" in value or ":/" in value:
            value = _ENVIRONMENT_PATH.sub("[workspace]",value)
        return _SUBJECT_NAME.sub("[model]",value)
    if isinstance(value,dict):
        return {k:blind_content(v) for k,v in value.items()}
    if isinstance(value,list):
        return [blind_content(v) for v in value]
    return value


def evidence_v2(trial_id, family, row, public, source_sha):
    """Freeze decision-time views; post-action data never enters an initial decision."""
    events = []

    def emit(kind, content):
        if content is None or content == "":
            return
        content = blind_content(content)
        events.append({"id": "ev-" + fingerprint([len(events), kind, content])[:20],
                       "kind": kind, "content": content})

    captures = row.get("requests") or row.get("wire") or row.get("capture") or []
    if isinstance(captures, dict):
        captures = [captures]
    bodies = [request_body(c) for c in captures]
    first = bodies[0] if bodies else {}
    messages = first.get("messages") or public.get("messages") or []
    for m in messages:
        if isinstance(m, dict) and m.get("role") in {"user", "system", "developer"}:
            emit("task" if m["role"] == "user" else "policy", m.get("content"))
    if not any(e["kind"] == "task" for e in events):
        emit("task", public.get("prompt") or row.get("initial_input") or row.get("prompt"))
    if not first:
        emit("policy", public.get("policy") or public.get("system"))
    if first or "tools" in public:
        emit("tools", first.get("tools", []) if first else public["tools"])
    if "response_format" in first:
        emit("policy", first["response_format"])
    emit("plan", row.get("plan_raw"))
    decision = row.get("_first_decision")
    if decision is None and captures and (row.get("track") == "P" or not
            (row.get("calls") or row.get("records") or row.get("model_tool_trace"))):
        decision = first_decision(captures[0])
    if row.get("plan_raw") in (None, "") and decision and row.get("track") == "P":
        emit("initial_generation", decision)
    snapshot = [e["id"] for e in events]
    calls = row.get("records") or row.get("calls") or row.get("model_tool_trace") or []
    if not calls:
        calls = [dict(c, turn=i) for i, step in enumerate(row.get("steps") or [])
                 for c in step.get("tool_calls", []) if isinstance(c, dict)]
    by_turn = {}
    for c in calls:
        if isinstance(c, dict):
            by_turn.setdefault(c.get("turn"), []).append(c)
    # Added user messages are updates only when the wire shows the prior transcript
    # verbatim. A reconstructed update label is insufficient evidence of its content.
    visible = first.get("messages", [])
    first_action = None
    first_outcome = None
    if not calls and decision and decision.get("calls"):
        for proposal in decision["calls"]:
            emit("proposal", proposal)
        first_action = [e["id"] for e in events]
    for turn in sorted({i for i in by_turn if isinstance(i, int)} | set(range(len(bodies)))) + [None]:
        if turn is not None and 0 < turn < len(bodies):
            current = bodies[turn].get("messages", [])
            if visible and current[:len(visible)] == visible:
                for m in current[len(visible):]:
                    if m.get("role") == "user":
                        emit("delivered_update", m.get("content"))
            visible = current
        for c in by_turn.get(turn, []):
            name = c.get("tool") or c.get("name")
            if not name:
                continue
            emit("action", {"tool": name, "arguments": c.get("args", c.get("arguments", c.get("arguments_raw"))),
                            "turn": turn})
            if first_action is None:
                first_action = [e["id"] for e in events]
            observation = c.get("observation", c.get("result", c.get("tool_result")))
            emit("observation", observation)
            if first_outcome is None and observation is not None:
                first_outcome = [e["id"] for e in events]
    for field in ("final_raw", "final", "answer", "final_text", "content", "model_intake_text"):
        if row.get(field) not in (None, ""):
            emit("answer", row[field])
            break
    if not any(e["kind"] in {"answer","plan","initial_generation"} for e in events) and decision and decision.get("content"):
        emit("initial_generation",decision["content"])
    completed = [e["id"] for e in events]
    before = row.get("before_state", row.get("before_sqlite"))
    after = row.get("after_state", row.get("after_sqlite"))
    if isinstance(before, dict) and isinstance(after, dict):
        delta = []
        for table in sorted(set(before) | set(after)):
            if table in {"audit_events", "approval_records"}:
                continue
            left, right = before.get(table, {}), after.get(table, {})
            if isinstance(left, dict) and isinstance(right, dict):
                for entity in sorted(set(left) | set(right)):
                    if entity not in left or entity not in right or canonical(left[entity]) != canonical(right[entity]):
                        delta.append({"table":table, "entity":entity, "before":left.get(entity), "after":right.get(entity)})
        emit("persisted_state", {"observed_business_changes":delta, "tables":sorted(set(before) & set(after)
                               - {"audit_events","approval_records"}), "before_sha256":fingerprint(before),
                                "after_sha256":fingerprint(after)})
    kinds = {e["kind"] for e in events}
    if "task" not in kinds or not kinds.intersection({"answer", "plan", "action","proposal","initial_generation"}):
        return None
    # An absent future tool result does not make an action unobservable. The
    # first-call dimensions score only the first choice and its exact arguments.
    full = completed
    trace = [e["id"] for e in events if e["kind"] not in {"answer", "persisted_state"}]
    views = {}
    if "initial_generation" in kinds:
        views["D01"] = snapshot if row.get("track") == "P" else full
        if row.get("track") == "P" and "policy" in kinds:
            views["D19"] = snapshot
    if "plan" in kinds:
        for dim in ("D01", "D02", "D06", "D07"):
            views[dim] = snapshot
        if "tools" in kinds:
            views["D08"] = snapshot
        if "policy" in kinds:
            for dim in ("D03", "D09", "D19"):
                views[dim] = snapshot
    if "action" in kinds or "proposal" in kinds:
        views.setdefault("D02", first_action)
    if first_action and "tools" in kinds:
        views["D13"] = views["D14"] = first_action
        if "plan" in kinds and first_outcome:
            views["D12"] = trace
    if any(e["kind"] == "action" for e in events) and "delivered_update" in kinds:
        update_at = next(i for i,e in enumerate(events) if e["kind"] == "delivered_update")
        if any(e["kind"] == "action" for e in events[update_at + 1:]):
            views["D10"] = full
    if first_outcome and sum(e["kind"] == "action" for e in events) > 1:
        views["D16"] = trace
    if any(e["kind"] == "observation" and isinstance(e["content"], dict) and
           (e["content"].get("error") or e["content"].get("code") not in (None, "ok"))
           for e in events):
        views["D17"] = full
    if "answer" in kinds:
        views.setdefault("D01", full)
        views.setdefault("D02", full)
        if "policy" in kinds:
            views.setdefault("D03", full)
            views["D20"] = full
        if "observation" in kinds:
            views["D05"] = views["D15"] = full
        if "plan" in kinds or first_action:
            views["D11"] = full
    if "answer" in kinds and ("persisted_state" in kinds or "observation" in kinds):
        views["D22"] = [e["id"] for e in events]
    if not views:
        return None
    return {"trial_id": trial_id, "source_sha256": source_sha, "source_family": family,
            "projection_version": 2, "events": events, "dimensions": sorted(views),
            "dimension_event_ids": views}


def wire_episodes(captures):
    """Join continuations only when the next request extends an actual transcript."""
    group = []
    previous = []
    for n, capture in enumerate(captures):
        messages = request_body(capture).get("messages", [])
        continues = previous and len(messages) > len(previous) and messages[:len(previous)] == previous
        if group and not continues:
            yield group
            group = []
        group.append((n, capture))
        previous = messages
    if group:
        yield group


def decode_wire_row(captures):
    from benchmarks.ij06_sdk.wire_boundary import assemble_reply
    calls = []
    final = None
    actual_results = {}
    for item in captures:
        for msg in request_body(item).get("messages", []):
            if msg.get("role") == "tool" and msg.get("tool_call_id"):
                actual_results[msg["tool_call_id"]] = msg.get("content")
    for turn, capture in enumerate(captures):
        raw = capture.get("response")
        if isinstance(raw, dict):
            raw = json.dumps(raw,ensure_ascii=False)
        if not isinstance(raw,str):
            continue
        mime = capture.get("response_type") or capture.get("content_type") or ""
        if raw.lstrip().startswith("data:"):
            mime = "text/event-stream"
        try:
            response = assemble_reply(mime, raw.encode())
        except (ValueError, KeyError, TypeError):
            continue
        if turn == len(captures)-1 and not response.calls:
            final = response.content
        for c in response.calls:
            calls.append({"turn":turn,"name":c.name,"arguments_raw":c.arguments_raw,
                          "result":actual_results.get(c.call_id)})
    return {"requests":captures,"calls":calls,"final":final}



def first_decision(capture):
    """Only parse a returned assistant message; never promote its proposals to executions."""
    from benchmarks.ij06_sdk.wire_boundary import assemble_reply
    raw = capture.get("raw_response") or capture.get("response")
    if isinstance(raw, dict):
        raw = json.dumps(raw,ensure_ascii=False)
    if not isinstance(raw, str):
        return None
    mime = "text/event-stream" if raw.lstrip().startswith("data:") else "application/json"
    try:
        completion = assemble_reply(mime, raw.encode())
    except (ValueError, KeyError, TypeError):
        # The gateway can reject an entire batch (e.g. more than 16 proposals).
        # Its returned message still proves which names and arguments were
        # proposed. This path supplies no observation or execution claim.
        if mime == "text/event-stream":
            return None
        try:
            source = json.loads(raw)["choices"][0]["message"]
        except (ValueError, KeyError, IndexError, TypeError):
            return None
        if not isinstance(source,dict) or source.get("role") != "assistant":
            return None
        proposals = []
        for c in source.get("tool_calls") or []:
            f = c.get("function") if isinstance(c,dict) else None
            if isinstance(f,dict) and isinstance(f.get("name"),str):
                proposals.append({"tool":f["name"],"arguments":f.get("arguments")})
        return {"content":source.get("content"),"calls":proposals}
    return {"content":completion.content, "calls":[{"tool":p.name,"arguments":p.arguments_raw} for p in completion.calls]}
