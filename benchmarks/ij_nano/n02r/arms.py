"""N02R experimental arms P0-P7: request renderers + deterministic
response parsers.

Matched factors across arms (order 1.2 section 3.3): same task semantics,
same available information (tool inventory rendered or passed as tools),
same business entity identities, same generation budget, temperature 0,
seed 42, cache_prompt on. Only the protocol/representation differs.

Decoding: {"temperature": 0, "seed": 42, "cache_prompt": True} on every
arm that accepts them.
"""
from __future__ import annotations

import json
import re

ARMS = ("P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7")
ARM_LABELS = {
    "P0": "native chat completions, default behavior",
    "P1": "chat completions + json_schema",
    "P2": "chat completions + verified thinking-disabled + json_schema",
    "P3": "completion + json_schema",
    "P4": "completion + GBNF",
    "P5": "native function calling",
    "P6": "completion + compact action DSL",
    "P7": "completion + enumerated action",
}
# Budget-sensitivity panel (preregistered): the chat baseline, the failing
# structured path, the thinking-disabled counterfactual and native tools.
BUDGET_PANEL_ARMS = ("P0", "P1", "P2", "P5")
PRIMARY_BUDGET = 1024
BUDGETS = (64, 128, 256, 512, 1024)

_QUANT_RE = re.compile(r"(-?\d+(?:\.\d+)?)\s*([A-Za-z\u4e00-\u9fff%]+|元)")


def _common() -> dict:
    return {"temperature": 0, "seed": 42, "cache_prompt": True}


def _user_text(task: dict) -> str:
    return f"{task['context']}\n{task['instruction']}"


def _candidates(task: dict) -> list[str]:
    k = task["schema_hint"]
    return k.get("candidates") or k.get("labels") or k.get("branches") \
        or k.get("choices") or []


# -- schema builders -----------------------------------------------------------

def json_schema_for(task: dict) -> dict:
    k = task["schema_hint"]
    kind = k["answer_kind"]
    if kind == "tool":
        return {"type": "object",
                "properties": {"tool": {"type": "string", "enum": k["candidates"]}},
                "required": ["tool"], "additionalProperties": False}
    if kind == "slot":
        st = k["slot_type"]
        if st == "quantity":
            return {"type": "object",
                    "properties": {"value": {"type": "number"},
                                   "unit": {"type": "string",
                                            "enum": ["CNY", "USD", "EUR", "pcs", "kg"]}},
                    "required": ["value", "unit"], "additionalProperties": False}
        return {"type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"], "additionalProperties": False}
    if kind == "action":
        props: dict = {"tool": {"type": "string", "enum": _world_tools(task)}}
        for slot in k["slots"]:
            if slot in ("amount", "quantity"):
                props[slot] = {"type": "object",
                               "properties": {"value": {"type": "number"},
                                              "unit": {"type": "string",
                                                       "enum": ["CNY", "USD", "EUR", "pcs", "kg"]}},
                               "required": ["value", "unit"], "additionalProperties": False}
            elif slot == "reason":
                props[slot] = {"type": "string",
                               "enum": ["damaged_item", "late_delivery", "wrong_item",
                                        "duplicate_charge", "price_mismatch"]}
            else:
                props[slot] = {"type": "string"}
        return {"type": "object", "properties": props,
                "required": ["tool"] + list(k["slots"]), "additionalProperties": False}
    if kind == "label":
        return {"type": "object",
                "properties": {"action": {"type": "string", "enum": k["labels"]}},
                "required": ["action"], "additionalProperties": False}
    if kind == "branch":
        return {"type": "object",
                "properties": {"branch": {"type": "string", "enum": k["branches"]}},
                "required": ["branch"], "additionalProperties": False}
    if kind == "decision":
        return {"type": "object",
                "properties": {"decision": {"type": "string", "enum": ["stop", "continue"]}},
                "required": ["decision"], "additionalProperties": False}
    raise ValueError(kind)


def _world_tools(task: dict) -> list[str]:
    from .tasks import TOOLS
    return [t for t, _, _ in TOOLS[task["world"]]]


def gbnf_for(task: dict) -> str:
    """GBNF grammars using char-class quotes (["]) for quote characters.
    N02R source-level correction: escaped quotes ARE supported by b12359
    for simple literals, but the N02-record grammar construction was
    invalid; char-class quotes remain the robust form."""
    k = task["schema_hint"]
    kind = k["answer_kind"]
    q = '["]'
    unit_rule = 'unit ::= "CNY" | "USD" | "EUR" | "pcs" | "kg"'
    if kind in ("tool", "label", "branch", "decision"):
        vals = k["candidates"] if kind == "tool" else \
            k["labels"] if kind == "label" else \
            k["branches"] if kind == "branch" else ["stop", "continue"]
        field = {"tool": "tool", "label": "action", "branch": "branch",
                 "decision": "decision"}[kind]
        choices = " | ".join(f'"{v}"' for v in vals)
        return ('root ::= "{" ' + q + f' "{field}" ' + q + ' ":" ' + q
                + ' choice ' + q + ' "}"\n'
                + 'choice ::= ' + choices + '\n')
    if kind == "slot":
        st = k["slot_type"]
        if st == "quantity":
            return ('root ::= "{" ' + q + ' "value" ' + q
                    + ' ":" [0-9.]+ "," ' + q + ' "unit" ' + q + ' ":" ' + q
                    + ' unit ' + q + ' "}"\n' + unit_rule + '\n')
        return ('root ::= "{" ' + q + ' "value" ' + q + ' ":" ' + q
                + ' [A-Za-z0-9-]+ ' + q + ' "}"\n')
    if kind == "action":
        parts = [q + ' "tool" ' + q + ' ":" ' + q + ' toolname ' + q]
        for slot in k["slots"]:
            if slot in ("amount", "quantity"):
                parts.append(q + f' "{slot}" ' + q + ' ":" ' + '"{" ' + q
                             + ' "value" ' + q + ' ":" [0-9.]+ "," ' + q
                             + ' "unit" ' + q + ' ":" ' + q + ' unit ' + q
                             + ' "}"')
            else:
                parts.append(q + f' "{slot}" ' + q + ' ":" ' + q
                             + ' [A-Za-z0-9_-]+ ' + q)
        tools = " | ".join(f'"{t}"' for t in _world_tools(task))
        sep = ' "," '
        return ('root ::= "{" ' + sep.join(parts) + ' "}"\n'
                + 'toolname ::= ' + tools + '\n' + unit_rule + '\n')
    raise ValueError(kind)


# -- arm request builders --------------------------------------------------------

def build_request(arm: str, task: dict, budget: int,
                  thinking_kwarg: str | None) -> tuple[str, dict]:
    """Return (http_path, body). thinking_kwarg is the model-verified
    chat-template keyword for P2 (None until verified)."""
    kind = task["schema_hint"]["answer_kind"]
    if arm in ("P0", "P1", "P2", "P5"):
        body: dict = {"messages": [{"role": "user", "content": _user_text(task)}],
                      "max_tokens": budget, **_common()}
        if arm == "P0":
            return "/v1/chat/completions", body
        if arm in ("P1", "P2"):
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "answer", "strict": True,
                                "schema": json_schema_for(task)}}
            if arm == "P2" and thinking_kwarg:
                body["chat_template_kwargs"] = {thinking_kwarg: False}
            return "/v1/chat/completions", body
        # P5 native function calling
        if kind == "tool":
            try:
                from .tasks import TOOLS
            except ImportError:                     # top-level import (controller)
                from tasks import TOOLS
            body["tools"] = [
                {"type": "function", "function": {
                    "name": name, "description": desc,
                    "parameters": {"type": "object",
                                   "properties": {p: {"type": "string"}
                                                  for p in params},
                                   "required": list(params),
                                   "additionalProperties": False}}}
                for name, desc, params in TOOLS[task["world"]]]
            body["tool_choice"] = "auto"
        else:
            if kind == "label":
                param, values = "action", task["schema_hint"]["labels"]
            elif kind == "branch":
                param, values = "branch", task["schema_hint"]["branches"]
            elif kind == "decision":
                param, values = "decision", ["stop", "continue"]
            elif kind == "slot":
                param, values = "value", None
            else:                                   # action
                param, values = "args_json", None
            props = ({"type": "string", "enum": values}
                     if values else {"type": "string"})
            body["tools"] = [{"type": "function", "function": {
                "name": "record_answer",
                "description": "Record the chosen answer.",
                "parameters": {"type": "object",
                               "properties": {param: props},
                               "required": [param],
                               "additionalProperties": False}}}]
            body["tool_choice"] = "auto"
        return "/v1/chat/completions", body

    # completion arms share a plain-text prompt
    if arm == "P7":
        k = task["schema_hint"]
        if k["answer_kind"] == "label":
            acts = [l for l in task["context"].splitlines()
                    if re.match(r"^A\d+\.", l)]
            nums = "\n".join(f"{i+1}. {l.split('. ', 1)[1]}"
                             for i, l in enumerate(acts))
            prompt = (f"Available actions:\n{nums}\nScenario: "
                      f"{task['instruction']}\nAnswer with the action NUMBER only (1-6).")
        else:
            cands = _candidates(task)
            nums = "\n".join(f"{i+1}. {c}" for i, c in enumerate(cands))
            prompt = (f"{task['context']}\nAvailable answers:\n{nums}\n"
                      f"{task['instruction']}\nAnswer with the NUMBER only "
                      f"(1-{len(cands)}).")
        return "/completion", {"prompt": prompt, "n_predict": budget, **_common()}
    prompt = (f"{_user_text(task)}\n"
              "Respond with the answer only, no explanation.")
    if arm == "P3":
        return "/completion", {"prompt": prompt, "n_predict": budget,
                               "json_schema": json_schema_for(task), **_common()}
    if arm == "P4":
        return "/completion", {"prompt": prompt, "n_predict": budget,
                               "grammar": gbnf_for(task), **_common()}
    if arm == "P6":
        k = task["schema_hint"]
        kind = k["answer_kind"]
        if kind == "action":
            spec = (f"TOOL <name> {' '.join('<' + s + '=[value][@unit]>' for s in k['slots'])}"
                    f"; tool must be one of: {', '.join(_world_tools(task))}")
        elif kind == "tool":
            spec = "TOOL <name>; tool must be one of: " + ", ".join(k["candidates"])
        elif kind == "slot":
            spec = ("SLOT <name>=<value>; slot name is " + k["slot"]
                    + ("; quantities as <number>@<unit>" if k["slot_type"] == "quantity" else ""))
        else:
            spec = "ACTION <choice>; choice must be one of: " + ", ".join(_candidates(task))
        prompt = (f"{_user_text(task)}\n"
                  f"Answer in compact DSL on one line. DSL spec: {spec}\n"
                  "Output the DSL line only.")
        return "/completion", {"prompt": prompt, "n_predict": budget, **_common()}
    raise ValueError(arm)


# -- response parsing ------------------------------------------------------------

def _closed_set_find(text: str, candidates: list[str]) -> str | None:
    found = []
    for c in candidates:
        if re.search(r"(?<![A-Za-z0-9_.\-])" + re.escape(c) + r"(?![A-Za-z0-9_.\-])", text):
            found.append(c)
    return found[0] if len(set(found)) == 1 else (found[0] if found else None)


def _coerce_slot_value(kind_slot: str, stype: str, raw) -> object:
    if stype != "quantity":
        return raw if isinstance(raw, str) else str(raw)
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        m = _QUANT_RE.search(raw)
        if m:
            try:
                return {"value": float(m.group(1)), "unit": m.group(2)}
            except ValueError:
                return raw
    return raw


def parse_response(arm: str, task: dict, http_json: dict | None,
                   http_error: str | None) -> dict:
    """Deterministic per-arm parse. Returns:
    {structural_ok, payload (evaluator Response kwargs) | None, notes}"""
    out = {"structural_ok": False, "payload": None}
    if http_json is None:
        out["notes"] = f"http_error: {http_error}"
        return out
    kind = task["schema_hint"]["answer_kind"]
    k = task["schema_hint"]

    if arm in ("P0", "P1", "P2"):
        ch = (http_json.get("choices") or [{}])[0]
        msg = ch.get("message", {}) or {}
        content = msg.get("content") or ""
        if not content.strip():
            out["notes"] = "empty content"
            return out
        if arm == "P0":
            # free text: deterministic closed-set extraction
            if kind == "tool":
                tool = _closed_set_find(content, k["candidates"])
                if tool is None:
                    out["notes"] = "no unique tool token in free text"
                    return out
                out.update(structural_ok=True, payload={"tool": tool})
                return out
            if kind in ("label", "branch", "decision"):
                val = _closed_set_find(content, _candidates(task))
                if val is None:
                    out["notes"] = "no unique closed-vocab token in free text"
                    return out
                key = {"label": "intent", "branch": "branch",
                       "decision": "decision"}[kind]
                out.update(structural_ok=True, payload={key: val})
                return out
            if kind == "slot":
                if k["slot_type"] == "quantity":
                    m = _QUANT_RE.search(content)
                    if not m:
                        out["notes"] = "no quantity in free text"
                        return out
                    out.update(structural_ok=True,
                               payload={"args": {k["slot"]: {"value": float(m.group(1)),
                                                              "unit": m.group(2)}}})
                    return out
                m = re.search(r"[A-Za-z]+-[A-Za-z0-9]+|north|south|east|west|central",
                              content)
                if not m:
                    out["notes"] = "no identifier-like token in free text"
                    return out
                out.update(structural_ok=True,
                           payload={"args": {k["slot"]: m.group(0)}})
                return out
            if kind == "action":
                tool = _closed_set_find(content, _world_tools(task))
                if tool is None:
                    out["notes"] = "no tool token in free text"
                    return out
                args = _kv_scan(content)
                out.update(structural_ok=bool(args),
                           payload={"tool": tool, "args": args},
                           notes=None if args else "no key=value pairs found")
                return out
        # P1/P2: strict JSON answer
        try:
            j = json.loads(content)
        except Exception:
            out["notes"] = "content not valid JSON"
            return out
        return _payload_from_json(task, j, out)

    if arm == "P5":
        ch = (http_json.get("choices") or [{}])[0]
        msg = ch.get("message", {}) or {}
        tcs = msg.get("tool_calls") or []
        if not tcs:
            out["notes"] = "no tool_calls in message"
            return out
        fn = tcs[0].get("function", {})
        name = fn.get("name", "")
        try:
            fargs = json.loads(fn.get("arguments") or "{}")
        except Exception:
            out["notes"] = "tool_call arguments not valid JSON"
            return out
        if kind == "tool":
            out.update(structural_ok=True, payload={"tool": name})
            return out
        if kind == "slot":
            val = fargs.get("value")
            if val is None:
                out["notes"] = "record_answer without value"
                return out
            out.update(structural_ok=True,
                       payload={"args": {k["slot"]: _coerce_slot_value(
                           k["slot"], k["slot_type"], val)}})
            return out
        if kind == "action":
            if name not in _world_tools(task):
                out["notes"] = "unknown tool name in tool_call"
                return out
            out.update(structural_ok=True, payload={"tool": name, "args": fargs})
            return out
        key = {"label": "intent", "branch": "branch", "decision": "decision"}[kind]
        val = fargs.get("action") or fargs.get("branch") or fargs.get("decision")
        if val is None:
            out["notes"] = "record_answer without enum value"
            return out
        out.update(structural_ok=True, payload={key: val})
        return out

    # completion arms
    content = (http_json.get("content") or "").strip()
    if not content:
        out["notes"] = "empty completion content"
        return out
    if arm in ("P3", "P4"):
        try:
            j = json.loads(content)
        except Exception:
            out["notes"] = "completion content not valid JSON"
            return out
        return _payload_from_json(task, j, out)
    if arm == "P6":
        line = content.strip().splitlines()[0].strip()
        m = re.match(r"^(TOOL|SLOT|ACTION)\s+(.*)$", line)
        if not m:
            out["notes"] = "no DSL header on first line"
            return out
        head, rest = m.group(1), m.group(2)
        if head == "ACTION":
            val = _closed_set_find(rest, _candidates(task)) or rest.split()[0]
            key = {"label": "intent", "branch": "branch",
                   "decision": "decision",
                   "tool": "tool", "slot": "intent", "action": "intent"}[
                task["schema_hint"]["answer_kind"]]
            if task["schema_hint"]["answer_kind"] == "tool":
                out.update(structural_ok=True, payload={"tool": val})
            else:
                out.update(structural_ok=True, payload={key: val})
            return out
        if head == "SLOT":
            mm = re.match(r"^([A-Za-z_]+)=(.+)$", rest)
            if not mm:
                out["notes"] = "SLOT not name=value"
                return out
            out.update(structural_ok=True,
                       payload={"args": {k["slot"]: _coerce_slot_value(
                           k["slot"], k["slot_type"], mm.group(2))}})
            return out
        # TOOL
        tokens = rest.split()
        name = tokens[0]
        args = _kv_scan(" ".join(tokens[1:]))
        if kind == "tool":
            out.update(structural_ok=True, payload={"tool": name})
        else:
            out.update(structural_ok=bool(args), payload={"tool": name, "args": args},
                       notes=None if args else "TOOL line without key=value args")
        return out
    if arm == "P7":
        m = re.search(r"\d+", content)
        if not m:
            out["notes"] = "no integer in output"
            return out
        idx = int(m.group(0))
        cands = _candidates(task) if task["schema_hint"]["answer_kind"] != "label" \
            else [lid for lid, _ in
                  [(l.split(". ", 1)[0], l) for l in task["context"].splitlines()]]
        if idx < 1 or idx > len(cands):
            out["notes"] = f"index {idx} out of range"
            return out
        val = cands[idx - 1]
        kind2 = task["schema_hint"]["answer_kind"]
        if kind2 == "tool":
            out.update(structural_ok=True, payload={"tool": val})
        else:
            key = {"label": "intent", "branch": "branch", "decision": "decision",
                   "slot": "intent", "action": "intent"}[kind2]
            out.update(structural_ok=True, payload={key: val})
        return out
    raise ValueError(arm)


def _kv_scan(text: str) -> dict:
    args: dict = {}
    for m in re.finditer(r"([A-Za-z_][A-Za-z0-9_]*)=([^\s@]+)(?:@([A-Za-z]+))?", text):
        key, val, unit = m.group(1), m.group(2), m.group(3)
        if unit:
            try:
                args[key] = {"value": float(val), "unit": unit}
                continue
            except ValueError:
                pass
        try:
            args[key] = float(val) if "." in val else val
        except ValueError:
            args[key] = val
    return args


def _payload_from_json(task: dict, j, out: dict) -> dict:
    kind = task["schema_hint"]["answer_kind"]
    k = task["schema_hint"]
    if kind == "tool":
        if not isinstance(j, dict) or "tool" not in j:
            out["notes"] = "json without tool field"
            return out
        out.update(structural_ok=True, payload={"tool": str(j["tool"])})
        return out
    if kind == "slot":
        if not isinstance(j, dict) or "value" not in j:
            out["notes"] = "json without value field"
            return out
        out.update(structural_ok=True,
                   payload={"args": {k["slot"]: _coerce_slot_value(
                       k["slot"], k["slot_type"], j["value"])
                       if k["slot_type"] != "quantity" else
                       {"value": j.get("value"), "unit": j.get("unit", "")}}})
        return out
    if kind == "action":
        if not isinstance(j, dict) or "tool" not in j:
            out["notes"] = "json without tool field"
            return out
        # the action schema is flat: tool + slot fields at top level
        slots = task["schema_hint"]["slots"]
        args = {s: j[s] for s in slots if s in j}
        out.update(structural_ok=True,
                   payload={"tool": str(j["tool"]), "args": args})
        return out
    if kind == "label":
        if not isinstance(j, dict) or "action" not in j:
            out["notes"] = "json without action field"
            return out
        out.update(structural_ok=True, payload={"intent": str(j["action"])})
        return out
    if kind == "branch":
        if not isinstance(j, dict) or "branch" not in j:
            out["notes"] = "json without branch field"
            return out
        out.update(structural_ok=True, payload={"branch": str(j["branch"])})
        return out
    if kind == "decision":
        if not isinstance(j, dict) or "decision" not in j:
            out["notes"] = "json without decision field"
            return out
        out.update(structural_ok=True, payload={"decision": str(j["decision"])})
        return out
    raise ValueError(kind)
