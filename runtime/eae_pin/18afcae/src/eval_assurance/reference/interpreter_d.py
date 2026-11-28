"""EA03-D — independent Interpreter for raw N03 Batch D (C25-C32)
responses.

Reference-path parser for the Batch D output contracts (handoff
``requirements.md`` @ c772a9a; Batch A cross-cutting rules apply).

Parser surfaces (pinned):
- C25: single token STOP or CONTINUE.
- C26: ACT (bare) or ASK + the missing slot names (JSON
  ``{"decision","missing"}`` or "ASK: a, b" text).
- C27: PROCEED or ESCALATE + the triggered rule ids (JSON
  ``{"decision","rules"}`` or "ESCALATE: R-X" text).
- C28: a single-line typed answer.
- C29: a candidate id, or AMBIGUOUS + the conflicting ids (JSON
  ``{"class","readings"}`` or "AMBIGUOUS: RM-1, RM-2" text).
- C30: the canonical op string ``op:entity[:extra]`` (single token).
- C31: an answer whose factual claims carry trailing ``(EV-n)``
  citations (surface free, citations extracted).
- C32: ABSTAIN or a single-line answer value.

Returns ``(typed_value, parse_class, reasons)``. No IJ-NANO imports.
"""
from __future__ import annotations

import json
import re

BATCH_D = tuple(f"C{i:02d}" for i in range(25, 33))

_FENCE = re.compile(r"^\s*```[a-zA-Z0-9_-]*\s*|\s*```\s*$")


class _DuplicateKey(ValueError):
    pass


def _reject_duplicate_keys(pairs):
    seen = set()
    for k, _ in pairs:
        if k in seen:
            raise _DuplicateKey(k)
        seen.add(k)
    return dict(pairs)


def _strip_fences(text: str) -> str:
    return _FENCE.sub("", text)


def _json_object(text: str):
    cleaned = _strip_fences(text).strip()
    if not cleaned.startswith("{"):
        return None, "no JSON object at the surface"
    try:
        obj = json.loads(cleaned,
                         object_pairs_hook=_reject_duplicate_keys)
    except _DuplicateKey as dup:
        return None, f"duplicate JSON key: {dup.args[0]}"
    except ValueError as ve:
        return None, f"invalid JSON: {ve}"
    if not isinstance(obj, dict):
        return None, "JSON value is not an object"
    return obj, None


def _norm(token) -> str:
    return str(token).strip().strip('"').strip("'")


def parse_response(primitive: str, payload: dict, response) -> tuple:
    if response is None:
        return None, "EMPTY_OUTPUT", ("response is None",)
    raw = response if isinstance(response, str) else str(response)
    if raw.strip() == "":
        return None, "EMPTY_OUTPUT", ("empty model output",)
    if primitive == "C25":
        return _parse_c25(raw)
    if primitive == "C26":
        return _parse_c26(raw)
    if primitive == "C27":
        return _parse_c27(raw)
    if primitive == "C28":
        return _parse_line(raw, "C28")
    if primitive == "C29":
        return _parse_c29(raw)
    if primitive == "C30":
        return _parse_c30(raw)
    if primitive == "C31":
        return _parse_c31(raw)
    if primitive == "C32":
        return _parse_c32(raw)
    return None, "PARSER_SOFTWARE_ERROR", (
        f"primitive {primitive} outside Batch D interpreter scope",)


def _single_line(raw: str):
    cleaned = _strip_fences(raw).strip()
    lines = [ln.strip() for ln in cleaned.splitlines() if ln.strip()]
    if len(lines) != 1:
        return None, f"must be exactly one line, got {len(lines)}"
    return lines[0], None


def _parse_c25(raw: str) -> tuple:
    line, why = _single_line(raw)
    if line is None:
        return None, "MALFORMED", (why,)
    tok = _norm(line).upper()
    if tok in ("STOP", "CONTINUE"):
        return tok, "OK", ()
    return None, "MALFORMED", ("decision must be STOP or CONTINUE",)


def _parse_c26(raw: str) -> tuple:
    obj, why = _json_object(raw)
    if obj is not None:
        if set(obj) != {"decision", "missing"}:
            return None, "MALFORMED", (
                'must be {"decision": ACT|ASK, "missing": [slots]}',)
        if obj["decision"] not in ("ACT", "ASK"):
            return None, "MALFORMED", ("decision must be ACT or ASK",)
        m = obj.get("missing")
        if not isinstance(m, list) or \
                any(not isinstance(x, str) for x in m):
            return None, "MALFORMED", ("missing must be a list of slots",)
        if obj["decision"] == "ACT" and m:
            return None, "MALFORMED", ("ACT with missing slots",)
        return {"decision": obj["decision"], "missing":
                [x.strip() for x in m]}, "OK", ()
    line, w2 = _single_line(raw)
    if line is None:
        return None, "MALFORMED", (why or w2,)
    tok = _norm(line)
    up = tok.upper()
    if up == "ACT":
        return {"decision": "ACT", "missing": []}, "OK", ()
    if up.startswith("ASK"):
        rest = tok[3:].lstrip(":：,， ").strip()
        slots = [s.strip() for s in re.split(r"[,，]", rest) if s.strip()]
        if not slots:
            return None, "MALFORMED", ("ASK must name the missing "
                                       "slot(s)",)
        return {"decision": "ASK", "missing": slots}, "OK", ()
    return None, "MALFORMED", ("decision must be ACT or ASK(+slots)",)


def _parse_c27(raw: str) -> tuple:
    obj, why = _json_object(raw)
    if obj is not None:
        if set(obj) != {"decision", "rules"}:
            return None, "MALFORMED", (
                'must be {"decision": PROCEED|ESCALATE, "rules": [ids]}',)
        if obj["decision"] not in ("PROCEED", "ESCALATE"):
            return None, "MALFORMED", ("decision must be PROCEED or "
                                       "ESCALATE",)
        r = obj.get("rules")
        if not isinstance(r, list) or \
                any(not isinstance(x, str) for x in r):
            return None, "MALFORMED", ("rules must be a list of ids",)
        if obj["decision"] == "PROCEED" and r:
            return None, "MALFORMED", ("PROCEED with rule ids",)
        if obj["decision"] == "ESCALATE" and not r:
            return None, "MALFORMED", ("ESCALATE must name rule id(s)",)
        return {"decision": obj["decision"], "rules":
                [x.strip() for x in r]}, "OK", ()
    line, w2 = _single_line(raw)
    if line is None:
        return None, "MALFORMED", (why or w2,)
    tok = _norm(line)
    up = tok.upper()
    if up == "PROCEED":
        return {"decision": "PROCEED", "rules": []}, "OK", ()
    if up.startswith("ESCALATE"):
        rest = tok[9:].lstrip(":：,， ").strip()
        rules = [s.strip() for s in re.split(r"[,，]", rest) if s.strip()]
        if not rules:
            return None, "MALFORMED", ("ESCALATE must name the rule "
                                       "id(s)",)
        return {"decision": "ESCALATE", "rules": rules}, "OK", ()
    return None, "MALFORMED", ("decision must be PROCEED or "
                               "ESCALATE(+rule ids)",)


def _parse_line(raw: str, prim: str) -> tuple:
    line, why = _single_line(raw)
    if line is None:
        return None, "MALFORMED", (why,)
    return _norm(line), "OK", ()


def _parse_c29(raw: str) -> tuple:
    obj, why = _json_object(raw)
    if obj is not None:
        if set(obj) == {"class", "readings"}:
            if obj["class"] != "AMBIGUOUS" or \
                    not isinstance(obj["readings"], list):
                return None, "MALFORMED", (
                    'AMBIGUOUS must carry {"class","readings"}',)
            return {"class": "AMBIGUOUS",
                    "readings": [str(x).strip()
                                 for x in obj["readings"]]}, "OK", ()
        if set(obj) == {"class", "answer"}:
            if obj["class"] != "ANSWER" or \
                    not isinstance(obj["answer"], str):
                return None, "MALFORMED", (
                    'ANSWER must carry {"class","answer"}',)
            return {"class": "ANSWER",
                    "answer": obj["answer"].strip()}, "OK", ()
        return None, "MALFORMED", (
            "must be {class,answer} or {class,readings}",)
    line, w2 = _single_line(raw)
    if line is None:
        return None, "MALFORMED", (why or w2,)
    tok = _norm(line)
    up = tok.upper()
    if up == "AMBIGUOUS" or up.startswith("AMBIGUOUS"):
        rest = tok[9:].lstrip(":：,， ").strip()
        ids = [s.strip() for s in re.split(r"[,，]", rest) if s.strip()]
        if not ids:
            return None, "MALFORMED", ("AMBIGUOUS must name the "
                                       "conflicting ids",)
        return {"class": "AMBIGUOUS", "readings": ids}, "OK", ()
    if " " in tok or "," in tok:
        return None, "MALFORMED", ("must be one id or AMBIGUOUS + ids",)
    return {"class": "ANSWER", "answer": tok}, "OK", ()


_CANON_RE = re.compile(r"^[a-z][a-z0-9_]*:\S+(?::\S+)?$")


def _parse_c30(raw: str) -> tuple:
    line, why = _single_line(raw)
    if line is None:
        return None, "MALFORMED", (why,)
    tok = _norm(line)
    if not _CANON_RE.match(tok):
        return None, "MALFORMED", (
            "canonical string must be op:entity[:extra] with exact "
            "ids/numbers",)
    return tok, "OK", ()


_CITE_RE = re.compile(r"\((EV-[A-Za-z0-9-]+)\)")


def _parse_c31(raw: str) -> tuple:
    cleaned = _strip_fences(raw).strip()
    if not cleaned:
        return None, "MALFORMED", ("no answer text",)
    citations = _CITE_RE.findall(cleaned)
    return {"text": cleaned, "citations": citations}, "OK", ()


def _parse_c32(raw: str) -> tuple:
    line, why = _single_line(raw)
    if line is None:
        return None, "MALFORMED", (why,)
    tok = _norm(line)
    if tok.upper() == "ABSTAIN":
        return {"class": "ABSTAIN", "answer": None}, "OK", ()
    return {"class": "ANSWER", "answer": tok}, "OK", ()
