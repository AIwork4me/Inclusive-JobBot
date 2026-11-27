"""N02R corrected protocol arms (addendum PR-D01..PR-D05 repairs).

New module by design: the original arms.py is the audited implementation
of experiment 36bfed1d55a9987b and stays untouched; this module is the
corrected implementation for the re-execution experiment.

Repairs:
- PR-D01: information-matched arms (M-*) render the same legitimate
  tool/action/candidate information into every arm's prompt (schemas and
  grammars remain request-side constraints, not prompt information). The
  original arms are kept as the "native-usability" scope.
- PR-D02: P5 split into P5A (native business tools with typed schemas,
  applicable families only) and P5B (declared record_answer structured
  answer recording, never labeled business tool execution). A response
  valid per the SUPPLIED contract is never rejected.
- PR-D03: P7_APPLICABILITY preregistered per task contract; P7S is the
  separately identified two-stage enumerate-then-fill protocol for
  structured actions. No candidate list ever contains the hidden expected
  argument value.
- PR-D04/D05: parser v2 - ambiguity and negation detection, strict
  duplicate-key JSON parsing, duplicate/unknown DSL key handling,
  trailing-contradiction detection, multi-tool-call flagging, contract-
  name verification, punctuation-tolerant closed-set boundaries; results
  carry warnings + raw_content + normalizations; unknown fields always
  reach the evaluator.
"""
from __future__ import annotations

import json
import re

try:
    from .tasks import TOOLS
    from . import arms as _v1
except ImportError:                     # top-level import (controller)
    from tasks import TOOLS
    import arms as _v1

# -- corrected arm registry --------------------------------------------------

# native-usability scope (original renderers, parser v2 applied)
NATIVE_ARMS = ("P0", "P1", "P2", "P3", "P4", "P6", "P7")
# information-matched causal scope
MATCHED_ARMS = ("M-P0", "M-P1", "M-P2", "M-P3", "M-P4", "M-P6", "M-P7")
# function-calling arms: A = native business tools, B = record_answer
P5_ARMS = ("P5A", "P5B")
# two-stage enumerated protocol for structured actions
TWO_STAGE_ARMS = ("P7S",)

ARM_LABELS = dict(_v1.ARM_LABELS)
ARM_LABELS.update({
    "P5A": "native function calling - business tools with typed schemas",
    "P5B": "function calling - declared record_answer structured answer "
           "(NOT business tool execution)",
    "M-P0": "info-matched: native chat, default behavior",
    "M-P1": "info-matched: chat + json_schema",
    "M-P2": "info-matched: chat + verified thinking-disabled + json_schema",
    "M-P3": "info-matched: completion + json_schema",
    "M-P4": "info-matched: completion + GBNF",
    "M-P6": "info-matched: completion + compact action DSL",
    "M-P7": "info-matched: completion + enumerated action",
    "P7S": "two-stage: enumerated tool selection then slot filling",
})

# PR-D03: preregistered applicability by task family. Slot extraction and
# structured action cannot be enumerated without exposing the hidden
# expected argument; P7S covers structured action as a separate protocol.
P7_APPLICABILITY = {
    "tool_selection": True,
    "slot_extraction": False,
    "structured_action": False,        # use P7S instead
    "enumerated_action": True,
    "conditional_branch": True,
    "stop_continue": True,
}
P5A_APPLICABILITY = {
    "tool_selection": True,
    "slot_extraction": True,           # business tool supplied, args typed
    "structured_action": True,
    "enumerated_action": False,        # no business tool exists for labels
    "conditional_branch": False,
    "stop_continue": False,
}
P5B_APPLICABILITY = {f: True for f in
                     ("tool_selection", "slot_extraction", "structured_action",
                      "enumerated_action", "conditional_branch", "stop_continue")}
P7S_APPLICABILITY = {"structured_action": True}

BUDGET_PANEL_ARMS = ("M-P0", "M-P1", "M-P2", "P5A")
PRIMARY_BUDGET = 1024
BUDGETS = (64, 128, 256, 512, 1024)
REASONING_BUDGET_T2 = 256             # T2 server-profile thinking budget

_QUANT_RE = re.compile(r"(-?\d+(?:\.\d+)?)\s*([A-Za-z]+|元)")
_NEG_CUES = ("not ", "don't", "dont", "never", "instead of", "avoid",
             "rather than", "except", "不要", "别", "拒绝", "而不是", "不能用")

_QUANTITY_ENUM = ["CNY", "USD", "EUR", "pcs", "kg"]


def _common() -> dict:
    return {"temperature": 0, "seed": 42, "cache_prompt": True}


def _base_arm(arm: str) -> str:
    return arm[2:] if arm.startswith("M-") else arm


def _world_tools(task: dict) -> list[str]:
    return [t for t, _, _ in TOOLS[task["world"]]]


# -- PR-D01 information block -------------------------------------------------

def info_block(task: dict) -> str:
    """The legitimate, prompt-visible information EVERY matched arm
    carries. Never contains the expected answer value."""
    k = task["schema_hint"]
    kind = k["answer_kind"]
    lines: list[str] = []
    if kind in ("tool", "action"):
        lines.append("Available tools:")
        for name, desc, params in TOOLS[task["world"]]:
            lines.append(f"- {name}: {desc} (params: {', '.join(params)})")
    if kind == "slot":
        unit = "; state value and unit" if k["slot_type"] == "quantity" else ""
        lines.append(f"The answer is the value of the slot '{k['slot']}' "
                     f"(type {k['slot_type']}{unit}).")
    if kind == "label":
        labels = ", ".join(lid for lid, _ in
                           [(l.split(". ", 1)[0], l)
                            for l in task["context"].splitlines()
                            if re.match(r"^A\d+\.", l)])
        lines.append(f"Allowed action labels: {labels}.")
    if kind == "branch":
        lines.append("Allowed branches: " + ", ".join(k["branches"]) + ".")
    if kind == "decision":
        lines.append("Allowed decisions: stop, continue.")
    return "\n".join(lines)


def _user_text(task: dict, matched: bool) -> str:
    parts = [task["context"]]
    if matched:
        parts.append(info_block(task))
    parts.append(task["instruction"])
    return "\n".join(parts)


# -- schemas & grammars (per answer kind; shared by v1-style and M arms) -------

def json_schema_for(task: dict) -> dict:
    return _v1.json_schema_for(task)


def gbnf_for(task: dict) -> str:
    return _v1.gbnf_for(task)


# -- request builders ----------------------------------------------------------

def build_request(arm: str, task: dict, budget: int,
                  thinking_kwarg: str | None,
                  stage: int = 1,
                  selected_tool: str | None = None) -> tuple[str, dict]:
    """stage 2 is used only by the P7S composite protocol and requires the
    tool SELECTED in stage 1 (never the hidden expected tool)."""
    matched = arm.startswith("M-")
    base = _base_arm(arm)
    kind = task["schema_hint"]["answer_kind"]
    k = task["schema_hint"]

    if arm == "P7S":
        if stage == 1:
            tools = _world_tools(task)
            nums = "\n".join(f"{i+1}. {t}" for i, t in enumerate(tools))
            prompt = (f"{_user_text(task, matched=False)}\n"
                      f"Tools:\n{nums}\n"
                      "Answer with the NUMBER of the tool to call only "
                      f"(1-{len(tools)}).")
            return "/completion", {"prompt": prompt, "n_predict": 8,
                                   **_common()}
        if selected_tool is None:
            raise ValueError("P7S stage 2 requires the stage-1 selection")
        schema = _v1.json_schema_for(task)
        prompt = (f"{_user_text(task, matched=False)}\n"
                  f"Use the tool {selected_tool}. Produce the full action "
                  "as JSON (tool fixed, fill the arguments).")
        return "/completion", {"prompt": prompt, "n_predict": budget,
                               "json_schema": schema, **_common()}

    if base in ("P0", "P1", "P2"):
        body: dict = {"messages": [
            {"role": "user", "content": _user_text(task, matched)}],
            "max_tokens": budget, **_common()}
        if base == "P0":
            return "/v1/chat/completions", body
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "answer", "strict": True,
                            "schema": json_schema_for(task)}}
        if base == "P2" and thinking_kwarg:
            body["chat_template_kwargs"] = {thinking_kwarg: False}
        return "/v1/chat/completions", body

    if arm == "P5A":
        body = {"messages": [
            {"role": "user", "content": _user_text(task, matched=False)}],
            "max_tokens": budget, **_common()}
        body["tools"] = [
            {"type": "function", "function": _typed_tool_schema(task, name)}
            for name, _, _ in TOOLS[task["world"]]]
        if fam_of(task) == "slot_extraction":
            body["tool_choice"] = {"type": "function",
                                   "function": {"name": k["tool"]}}
        else:
            body["tool_choice"] = "auto"
        return "/v1/chat/completions", body

    if arm == "P5B":
        body = {"messages": [
            {"role": "user", "content": _user_text(task, matched=False)}],
            "max_tokens": budget, **_common()}
        body["tools"] = [{"type": "function", "function":
                          _record_answer_schema(task)}]
        body["tool_choice"] = "auto"
        return "/v1/chat/completions", body

    # completion-family arms
    if base == "P7":
        if not P7_APPLICABILITY.get(task["family"], False):
            raise ValueError(
                f"P7 inapplicable for {task['family']} (preregistered "
                f"applicability; enumerated protocols must not expose the "
                f"hidden expected argument)")
        cands = _p7_candidates(task)
        nums = "\n".join(f"{i+1}. {c}" for i, c in enumerate(cands))
        prompt = (f"{_user_text(task, matched)}\n"
                  f"Answer options:\n{nums}\n"
                  f"{task['instruction']}\nAnswer with the NUMBER only "
                  f"(1-{len(cands)}).")
        return "/completion", {"prompt": prompt, "n_predict": budget,
                               **_common()}
    prompt = (f"{_user_text(task, matched)}\n"
              "Respond with the answer only, no explanation.")
    if base == "P3":
        return "/completion", {"prompt": prompt, "n_predict": budget,
                               "json_schema": json_schema_for(task),
                               **_common()}
    if base == "P4":
        return "/completion", {"prompt": prompt, "n_predict": budget,
                               "grammar": gbnf_for(task), **_common()}
    if base == "P6":
        spec = _dsl_spec(task)
        prompt = (f"{_user_text(task, matched)}\n"
                  f"Answer in compact DSL on one line. DSL spec: {spec}\n"
                  "Output the DSL line only.")
        return "/completion", {"prompt": prompt, "n_predict": budget,
                               **_common()}
    raise ValueError(arm)


def fam_of(task: dict) -> str:
    return task["family"]


def _p7_candidates(task: dict) -> list[str]:
    k = task["schema_hint"]
    kind = k["answer_kind"]
    if kind == "label":
        return [l.split(". ", 1)[0] for l in task["context"].splitlines()
                if re.match(r"^A\d+\.", l)]
    if kind == "tool":
        return k["candidates"]
    if kind == "branch":
        return k["branches"]
    if kind == "decision":
        return ["stop", "continue"]
    raise ValueError(f"P7 inapplicable for {task['family']}")


def _dsl_spec(task: dict) -> str:
    k = task["schema_hint"]
    kind = k["answer_kind"]
    if kind == "action":
        return (f"TOOL <name> {' '.join('<' + s + '=[value][@unit]>' for s in k['slots'])}"
                f"; tool must be one of: {', '.join(_world_tools(task))}")
    if kind == "tool":
        return "TOOL <name>; tool must be one of: " + ", ".join(k["candidates"])
    if kind == "slot":
        return ("SLOT <name>=<value>; slot name is " + k["slot"]
                + ("; quantities as <number>@<unit>"
                   if k["slot_type"] == "quantity" else ""))
    return "ACTION <choice>; choice must be one of: " + ", ".join(
        _p7_candidates(task) if kind == "label" else
        k.get("branches") or k.get("candidates") or ["stop", "continue"])


def _typed_tool_schema(task: dict, name: str) -> dict:
    """PR-D02 repair: business tools carry real typed parameter schemas."""
    entry = next((n, d, p) for n, d, p in TOOLS[task["world"]] if n == name)
    _, desc, params = entry
    props: dict = {}
    for p in params:
        if p in ("amount", "quantity"):
            props[p] = {"type": "object",
                        "properties": {"value": {"type": "number"},
                                       "unit": {"type": "string",
                                                "enum": _QUANTITY_ENUM}},
                        "required": ["value", "unit"],
                        "additionalProperties": False}
        else:
            props[p] = {"type": "string"}
    return {"name": name, "description": desc,
            "parameters": {"type": "object", "properties": props,
                           "required": list(params),
                           "additionalProperties": False}}


def _record_answer_schema(task: dict) -> dict:
    """PR-D02 repair B: record_answer mirrors the answer contract with
    typed fields; explicitly NOT business tool execution."""
    k = task["schema_hint"]
    kind = k["answer_kind"]
    props: dict = {}
    if kind == "tool":
        props["tool"] = {"type": "string", "enum": _world_tools(task)}
    elif kind == "slot":
        if k["slot_type"] == "quantity":
            props["value"] = {"type": "object",
                              "properties": {
                                  "value": {"type": "number"},
                                  "unit": {"type": "string",
                                           "enum": _QUANTITY_ENUM}},
                              "required": ["value", "unit"],
                              "additionalProperties": False}
        else:
            props["value"] = {"type": "string"}
    elif kind == "action":
        props["tool"] = {"type": "string", "enum": _world_tools(task)}
        for slot in k["slots"]:
            if slot in ("amount", "quantity"):
                props[slot] = {"type": "object",
                               "properties": {"value": {"type": "number"},
                                              "unit": {"type": "string",
                                                       "enum": _QUANTITY_ENUM}},
                               "required": ["value", "unit"],
                               "additionalProperties": False}
            elif slot == "reason":
                props[slot] = {"type": "string",
                               "enum": ["damaged_item", "late_delivery",
                                        "wrong_item", "duplicate_charge",
                                        "price_mismatch"]}
            else:
                props[slot] = {"type": "string"}
    elif kind == "label":
        props["action"] = {"type": "string",
                           "enum": _p7_candidates(task)}
    elif kind == "branch":
        props["branch"] = {"type": "string", "enum": k["branches"]}
    else:
        props["decision"] = {"type": "string", "enum": ["stop", "continue"]}
    return {"name": "record_answer",
            "description": "Record the chosen answer (structured answer "
                           "recording, not business tool execution).",
            "parameters": {"type": "object", "properties": props,
                           "required": list(props),
                           "additionalProperties": False}}


# -- parser v2 ------------------------------------------------------------------

def _strict_loads(text: str):
    """JSON parse rejecting duplicate object keys; returns (obj, warning)."""
    def hook(pairs):
        keys = [kk for kk, _ in pairs]
        if len(set(keys)) != len(keys):
            raise _DuplicateKey(tuple(keys))
        return dict(pairs)
    try:
        return json.loads(text, object_pairs_hook=hook), None
    except _DuplicateKey as e:
        return None, f"duplicate JSON key(s): {e.args[0]}"
    except Exception as e:
        return None, f"invalid JSON: {str(e)[:80]}"


class _DuplicateKey(Exception):
    pass


def _find_candidates(text: str, candidates: list[str]):
    """PR-D04: all-match closed-set search with ambiguity, negation and
    punctuation-tolerant boundaries. Returns (value, warnings)."""
    matches: list[tuple[int, str]] = []
    for c in candidates:
        for m in re.finditer(r"(?<![A-Za-z0-9_\-])" + re.escape(c)
                             + r"(?![A-Za-z0-9_\-])", text):
            matches.append((m.start(), c))
    distinct = sorted({c for _, c in matches})
    if not distinct:
        return None, ["no candidate token found in text"]
    if len(distinct) > 1:
        return None, [f"ambiguous: multiple distinct candidates present "
                      f"{distinct}"]
    value = distinct[0]
    first_pos = min(p for p, c in matches if c == value)
    window = text[max(0, first_pos - 28):first_pos].lower()
    for cue in _NEG_CUES:
        if cue in window:
            return None, [f"negated candidate (cue {cue!r} immediately "
                          f"before match)"]
    return value, []


def _extract_quantity(text: str):
    m = _QUANT_RE.search(text)
    if not m:
        return None, ["no quantity pattern in text"]
    try:
        return {"value": float(m.group(1)), "unit": m.group(2)}, []
    except ValueError:
        return None, ["quantity value not numeric"]


def _kv_scan(text: str):
    """DSL key=value scan. Returns (args, warnings, normalizations)."""
    args: dict = {}
    warnings: list[str] = []
    norms: list[str] = []
    for m in re.finditer(r"([A-Za-z_][A-Za-z0-9_]*)=([^\s@]+)(?:@([A-Za-z]+))?",
                         text):
        key, val, unit = m.group(1), m.group(2), m.group(3)
        if key in args:
            warnings.append(f"duplicate DSL key: {key}")
            continue
        if unit:
            try:
                args[key] = {"value": float(val), "unit": unit}
                norms.append(f"{key}: parsed {val}@{unit}")
                continue
            except ValueError:
                warnings.append(f"malformed quantity for {key}: {val}@{unit}")
                args[key] = val
                continue
        if re.fullmatch(r"-?\d+", val):
            args[key] = int(val)
            norms.append(f"{key}: int literal")
        elif re.fullmatch(r"-?\d+\.\d+", val):
            args[key] = float(val)
            norms.append(f"{key}: float literal")
        else:
            args[key] = val
    return args, warnings, norms


def _content_of(http_json: dict, arm: str):
    """Extract the raw response channels per endpoint shape."""
    if arm in ("P5A", "P5B") or _base_arm(arm) in ("P0", "P1", "P2"):
        ch = (http_json.get("choices") or [{}])[0]
        msg = ch.get("message") or {}
        return {"content": msg.get("content") or "",
                "reasoning": msg.get("reasoning_content") or "",
                "tool_calls": msg.get("tool_calls") or []}
    return {"content": (http_json.get("content") or ""),
            "reasoning": "", "tool_calls": []}


def parse_response(arm: str, task: dict, http_json: dict | None,
                   http_error: str | None) -> dict:
    """Parser v2. Result fields: structural_ok, payload, warnings,
    raw_content, normalizations. Unknown fields are preserved in payload
    args so the evaluator can inspect them (PR-D05)."""
    out = {"structural_ok": False, "payload": None, "warnings": [],
           "raw_content": None, "normalizations": []}
    if http_json is None:
        out["warnings"].append(f"http_error: {http_error}")
        return out
    kind = task["schema_hint"]["answer_kind"]
    k = task["schema_hint"]
    raw = _content_of(http_json, arm)
    out["raw_content"] = raw

    if arm == "P5A" or arm == "P5B":
        calls = raw["tool_calls"]
        if not calls:
            out["warnings"].append("no tool_calls in message")
            return out
        if len(calls) > 1:
            out["warnings"].append(
                f"multiple tool calls ({len(calls)}): "
                + ", ".join(c.get("function", {}).get("name", "?")
                            for c in calls))
            return out
        fn = calls[0].get("function", {})
        name = fn.get("name", "")
        expected_name = ("record_answer" if arm == "P5B"
                         else None)  # P5A: validated against inventory below
        if expected_name and name != expected_name:
            out["warnings"].append(f"tool name {name!r} != supplied contract "
                                   f"{expected_name!r}")
            return out
        if arm == "P5A" and name not in _world_tools(task):
            out["warnings"].append(f"tool name {name!r} not in the supplied "
                                   f"business inventory")
            return out
        fargs, warn = _strict_loads(fn.get("arguments") or "{}")
        if warn:
            out["warnings"].append(f"tool_call arguments: {warn}")
            return out
        if arm == "P5A":
            out["structural_ok"] = True
            out["payload"] = {"tool": name, "args": fargs}
            return out
        # P5B: map record_answer fields to the evaluator channels; keep
        # unknown fields visible through args where a slot channel exists
        if kind == "tool":
            out["structural_ok"] = "tool" in fargs
            out["payload"] = {"tool": str(fargs.get("tool", "")),
                              "args": fargs}
        elif kind == "slot":
            out["structural_ok"] = "value" in fargs
            out["payload"] = {"args": {k["slot"]: fargs.get("value"),
                                       **{kk: vv for kk, vv in fargs.items()
                                          if kk != "value"}}}
        elif kind == "action":
            tool = fargs.pop("tool", None)
            out["structural_ok"] = tool is not None
            out["payload"] = {"tool": str(tool), "args": fargs}
        else:
            key = {"label": "intent", "branch": "branch",
                   "decision": "decision"}[kind]
            val = (fargs.get("action") or fargs.get("branch")
                   or fargs.get("decision"))
            out["structural_ok"] = val is not None
            rest = {kk: vv for kk, vv in fargs.items()
                    if kk not in ("action", "branch", "decision")}
            payload = {key: val}
            if rest:
                payload["args"] = rest       # unknown fields stay visible
            out["payload"] = payload
        return out

    content = (raw["content"] or "").strip()
    if not content:
        out["warnings"].append("empty content")
        return out

    base = _base_arm(arm)

    if base == "P0":
        if kind == "tool":
            val, warns = _find_candidates(content, k["candidates"])
            out["warnings"].extend(warns)
            if val is None:
                return out
            out["structural_ok"] = True
            out["payload"] = {"tool": val}
            return out
        if kind in ("label", "branch", "decision"):
            val, warns = _find_candidates(content, _p7_candidates(task))
            out["warnings"].extend(warns)
            if val is None:
                return out
            key = {"label": "intent", "branch": "branch",
                   "decision": "decision"}[kind]
            out["structural_ok"] = True
            out["payload"] = {key: val}
            return out
        if kind == "slot":
            if k["slot_type"] == "quantity":
                q, warns = _extract_quantity(content)
                out["warnings"].extend(warns)
                if q is None:
                    return out
                out["structural_ok"] = True
                out["payload"] = {"args": {k["slot"]: q}}
                return out
            m = re.search(r"[A-Za-z]+-[A-Za-z0-9]+|north|south|east|west|central",
                          content)
            if not m:
                out["warnings"].append("no identifier-like token in text")
                return out
            out["structural_ok"] = True
            out["payload"] = {"args": {k["slot"]: m.group(0)}}
            return out
        if kind == "action":
            tool, warns = _find_candidates(content, _world_tools(task))
            out["warnings"].extend(warns)
            if tool is None:
                return out
            first_line = content.strip().splitlines()[0]
            args, kwarns, norms = _kv_scan(first_line if "=" in first_line
                                           else content)
            out["warnings"].extend(kwarns)
            out["normalizations"].extend(norms)
            trailing = "\n".join(content.strip().splitlines()[1:]) \
                if "=" in first_line else ""
            if trailing.strip():
                tval, twarns = _find_candidates(trailing, _world_tools(task))
                if twarns and twarns[0].startswith("ambiguous"):
                    out["warnings"].append("trailing contradictory content")
                    return out
            out["structural_ok"] = bool(args) and not kwarns
            out["payload"] = {"tool": tool, "args": args}
            return out

    if base in ("P1", "P2", "P3", "P4"):
        j, warn = _strict_loads(content)
        if warn:
            out["warnings"].append(warn)
            return out
        return _payload_from_json(task, j, out)

    if base == "P6":
        lines = content.strip().splitlines()
        line = lines[0].strip()
        m = re.match(r"^(TOOL|SLOT|ACTION)\s+(.*)$", line)
        if not m:
            out["warnings"].append("no DSL header on first line")
            return out
        head, rest = m.group(1), m.group(2)
        remainder = "\n".join(lines[1:])
        if remainder.strip():
            cands = (_world_tools(task) if kind in ("tool", "action")
                     else _p7_candidates(task))
            rval, rwarns = _find_candidates(remainder, cands)
            if rwarns and rwarns[0].startswith("ambiguous"):
                out["warnings"].append("trailing contradictory DSL content")
                return out
            if rwarns and rwarns[0].startswith("negated"):
                out["warnings"].append("trailing negated candidate")
                return out
        if head == "ACTION":
            val, warns = _find_candidates(rest, _p7_candidates(task))
            out["warnings"].extend(warns)
            if val is None:
                return out
            if kind == "tool":
                out["structural_ok"] = True
                out["payload"] = {"tool": val}
            else:
                key = {"label": "intent", "branch": "branch",
                       "decision": "decision",
                       "slot": "intent", "action": "intent"}[kind]
                out["structural_ok"] = True
                out["payload"] = {key: val}
            return out
        if head == "SLOT":
            mm = re.match(r"^([A-Za-z_]+)=(.+)$", rest)
            if not mm:
                out["warnings"].append("SLOT not name=value")
                return out
            if mm.group(1) != k["slot"]:
                out["warnings"].append(
                    f"DSL slot name {mm.group(1)!r} != declared "
                    f"{k['slot']!r}")
                # keep the wrong-named key visible to the evaluator
                out["structural_ok"] = True
                out["payload"] = {"args": {mm.group(1): mm.group(2)}}
                return out
            if k["slot_type"] == "quantity":
                q, warns = _extract_quantity(mm.group(2))
                out["warnings"].extend(warns)
                if q is None:
                    return out
                out["structural_ok"] = True
                out["payload"] = {"args": {k["slot"]: q}}
                return out
            out["structural_ok"] = True
            out["payload"] = {"args": {k["slot"]: mm.group(2)}}
            return out
        # TOOL
        tokens = rest.split()
        name = tokens[0]
        rest_args = " ".join(tokens[1:])
        args, kwarns, norms = _kv_scan(rest_args)
        out["warnings"].extend(kwarns)
        out["normalizations"].extend(norms)
        # same-line trailing contradiction: scrub the recognized DSL tokens
        # and scan the remainder for competing closed-set candidates
        scrubbed = rest_args
        for m in re.finditer(r"[A-Za-z_][A-Za-z0-9_]*=[^\s@]+(?:@[A-Za-z]+)?",
                             rest_args):
            scrubbed = scrubbed.replace(m.group(0), " ", 1)
        if scrubbed.strip():
            cands = (_world_tools(task) if kind in ("tool", "action")
                     else _p7_candidates(task))
            sval, swarns = _find_candidates(scrubbed, cands)
            if swarns and (swarns[0].startswith("ambiguous")
                           or swarns[0].startswith("negated")):
                out["warnings"].append(
                    "trailing contradictory DSL content: " + swarns[0])
                return out
            if sval is not None and sval != name:
                out["warnings"].append(
                    f"trailing contradictory DSL content (mentions {sval})")
                return out
        if kind == "tool":
            if name not in k["candidates"]:
                out["warnings"].append("TOOL name outside declared inventory")
                return out
            out["structural_ok"] = True
            out["payload"] = {"tool": name}
            return out
        wrong = [kk for kk in args if kk not in k["slots"]]
        if wrong:
            out["warnings"].append(f"DSL keys outside declared slots: {wrong}")
        out["structural_ok"] = bool(args) and not kwarns
        out["payload"] = {"tool": name, "args": args}
        return out

    if base == "P7":
        m = re.search(r"\d+", content)
        if not m:
            out["warnings"].append("no integer in output")
            return out
        idx = int(m.group(0))
        cands = _p7_candidates(task)
        if idx < 1 or idx > len(cands):
            out["warnings"].append(f"index {idx} out of range 1-{len(cands)}")
            return out
        val = cands[idx - 1]
        if kind == "tool":
            out["structural_ok"] = True
            out["payload"] = {"tool": val}
        else:
            key = {"label": "intent", "branch": "branch",
                   "decision": "decision"}[kind]
            out["structural_ok"] = True
            out["payload"] = {key: val}
        return out

    raise ValueError(arm)


def _payload_from_json(task: dict, j, out: dict) -> dict:
    kind = task["schema_hint"]["answer_kind"]
    k = task["schema_hint"]
    if kind == "tool":
        if not isinstance(j, dict) or "tool" not in j:
            out["warnings"].append("json without tool field")
            return out
        extra = {kk: vv for kk, vv in j.items() if kk != "tool"}
        payload = {"tool": str(j["tool"])}
        if extra:
            payload["args"] = extra       # unknown fields stay visible
        out.update(structural_ok=True, payload=payload)
        return out
    if kind == "slot":
        if not isinstance(j, dict) or "value" not in j:
            out["warnings"].append("json without value field")
            return out
        extra = {kk: vv for kk, vv in j.items() if kk not in ("value", "unit")}
        args = {k["slot"]: ({"value": j.get("value"), "unit": j.get("unit", "")}
                            if k["slot_type"] == "quantity"
                            else j.get("value"))}
        args.update(extra)
        out.update(structural_ok=True, payload={"args": args})
        return out
    if kind == "action":
        if not isinstance(j, dict) or "tool" not in j:
            out["warnings"].append("json without tool field")
            return out
        args = {s: j[s] for s in k["slots"] if s in j}
        args.update({kk: vv for kk, vv in j.items()
                     if kk != "tool" and kk not in k["slots"]})
        out.update(structural_ok=True,
                   payload={"tool": str(j["tool"]), "args": args})
        return out
    if kind == "label":
        if not isinstance(j, dict) or "action" not in j:
            out["warnings"].append("json without action field")
            return out
        out.update(structural_ok=True, payload={"intent": str(j["action"])})
        return out
    if kind == "branch":
        if not isinstance(j, dict) or "branch" not in j:
            out["warnings"].append("json without branch field")
            return out
        out.update(structural_ok=True, payload={"branch": str(j["branch"])})
        return out
    if kind == "decision":
        if not isinstance(j, dict) or "decision" not in j:
            out["warnings"].append("json without decision field")
            return out
        out.update(structural_ok=True, payload={"decision": str(j["decision"])})
        return out
    raise ValueError(kind)
