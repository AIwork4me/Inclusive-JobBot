"""EA03-C — independent Interpreter for raw N03 Batch C (C17-C24)
responses.

Reference-path parser for the Batch C output contracts (handoff
``requirements.md`` @ c772a9a; Batch A cross-cutting rules apply:
fence tolerance, duplicate-key rejection, EMPTY_OUTPUT separation, no
substring membership, key-based access only).

Parser surfaces (pinned per primitive):
- C17: JSON list of booleans aligned with the queried predicate ids.
- C18: dependency edges — JSON list of [a, b] pairs OR one
  "a before b" per line.
- C19 / C21: ordered action list — JSON list of action-name strings
  OR one action name per line.
- C20: ids of holding branches — JSON list or comma/newline separated.
- C22: ``{"is_error": boolean, "code": string}``.
- C23: corrected argument record — flat JSON object.
- C24: ``{"fallback_id", "action", "arguments"}`` JSON object.

Returns ``(typed_value, parse_class, reasons)``; MALFORMED is a
model-side contract violation, PARSER_SOFTWARE_ERROR an interpreter
fault. No IJ-NANO imports.
"""
from __future__ import annotations

import json
import re

BATCH_C = tuple(f"C{i:02d}" for i in range(17, 25))

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


def _json_any(text: str):
    cleaned = _strip_fences(text).strip()
    if not cleaned.startswith(("[", "{")):
        return None, "no JSON value at the surface"
    try:
        val = json.loads(cleaned,
                         object_pairs_hook=_reject_duplicate_keys)
    except _DuplicateKey as dup:
        return None, f"duplicate JSON key: {dup.args[0]}"
    except ValueError as ve:
        return None, f"invalid JSON: {ve}"
    return val, None


def _json_object(text: str):
    val, why = _json_any(text)
    if val is None:
        return None, why
    if not isinstance(val, dict):
        return None, "JSON value is not an object"
    return val, None


def parse_response(primitive: str, payload: dict, response) -> tuple:
    if response is None:
        return None, "EMPTY_OUTPUT", ("response is None",)
    raw = response if isinstance(response, str) else str(response)
    if raw.strip() == "":
        return None, "EMPTY_OUTPUT", ("empty model output",)
    if primitive == "C17":
        return _parse_c17(raw)
    if primitive == "C18":
        return _parse_c18(raw)
    if primitive in ("C19", "C21"):
        return _parse_plan(raw)
    if primitive == "C20":
        return _parse_c20(raw)
    if primitive == "C22":
        return _parse_c22(raw)
    if primitive == "C23":
        return _parse_c23(raw)
    if primitive == "C24":
        return _parse_c24(raw)
    return None, "PARSER_SOFTWARE_ERROR", (
        f"primitive {primitive} outside Batch C interpreter scope",)


def _parse_c17(raw: str) -> tuple:
    val, why = _json_any(raw)
    if val is not None and isinstance(val, list):
        bad = [v for v in val if not isinstance(v, bool)]
        if bad:
            return val, "MALFORMED", ("predicate truths must be "
                                      "booleans",)
        return val, "OK", ()
    # tolerate per-line "true/false" only if it parses wholly
    cleaned = _strip_fences(raw).strip().lower()
    tokens = [t.strip() for t in re.split(r"[\s,]+", cleaned) if t.strip()]
    if tokens and all(t in ("true", "false") for t in tokens):
        return [t == "true" for t in tokens], "OK", ()
    return None, "MALFORMED", (why or "truths must be booleans",)


def _parse_edges(raw: str):
    """Edges as JSON [[a,b],...] or 'a before b' lines (shared by
    C18)."""
    val, why = _json_any(raw)
    if val is not None and isinstance(val, list):
        out = []
        for el in val:
            if isinstance(el, list) and len(el) == 2 and \
                    all(isinstance(x, str) for x in el):
                out.append((el[0].strip(), el[1].strip()))
            else:
                return None, "MALFORMED", ("edge entries must be "
                                           "[a, b] string pairs",)
        return out, "OK", ()
    if val is None and why != "no JSON value at the surface":
        return None, "MALFORMED", (why,)
    lines = [ln.strip() for ln in _strip_fences(raw).splitlines()
             if ln.strip()]
    out = []
    for ln in lines:
        m = re.match(r"^(\S+)\s+before\s+(\S+)$", ln)
        if not m:
            return None, "MALFORMED", (
                f"edge line must be 'a before b': {ln[:30]!r}",)
        out.append((m.group(1), m.group(2)))
    if not out:
        return None, "MALFORMED", ("no edges emitted",)
    return out, "OK", ()


def _parse_c18(raw: str) -> tuple:
    return _parse_edges(raw)


def _parse_plan(raw: str) -> tuple:
    """Ordered action list: JSON [name, ...] or one name per line."""
    val, why = _json_any(raw)
    if val is not None and isinstance(val, list):
        bad = [x for x in val if not isinstance(x, str) or not x.strip()]
        if bad:
            return None, "MALFORMED", ("plan entries must be non-empty "
                                       "action names",)
        return [x.strip() for x in val], "OK", ()
    if val is None and why != "no JSON value at the surface":
        return None, "MALFORMED", (why,)
    lines = [ln.strip() for ln in _strip_fences(raw).splitlines()
             if ln.strip()]
    if not lines:
        return None, "MALFORMED", ("no plan emitted",)
    bad = [ln for ln in lines if (" " in ln or "," in ln)]
    if bad:
        return None, "MALFORMED", ("plan lines must be bare action "
                                   f"names: {bad[0][:30]!r}",)
    return lines, "OK", ()


def _parse_c20(raw: str) -> tuple:
    val, why = _json_any(raw)
    if val is not None and isinstance(val, list):
        bad = [x for x in val if not isinstance(x, str)]
        if bad:
            return None, "MALFORMED", ("branch ids must be strings",)
        return [x.strip() for x in val], "OK", ()
    if val is None and why != "no JSON value at the surface":
        return None, "MALFORMED", (why,)
    cleaned = _strip_fences(raw).strip()
    ids = [t.strip() for t in re.split(r"[,\n]", cleaned) if t.strip()]
    if not ids:
        return None, "MALFORMED", ("no branch ids emitted",)
    bad = [t for t in ids if " " in t]
    if bad:
        return None, "MALFORMED", (f"id with embedded space: {bad[0]!r}",)
    return ids, "OK", ()


def _parse_c22(raw: str) -> tuple:
    obj, why = _json_object(raw)
    if obj is None:
        return None, "MALFORMED", (why or "non-JSON output",)
    if set(obj) != {"is_error", "code"}:
        return obj, "MALFORMED", (
            'must be exactly {"is_error": boolean, "code": string}',)
    if not isinstance(obj["is_error"], bool):
        return obj, "MALFORMED", ("is_error must be a boolean",)
    if not isinstance(obj["code"], str):
        return obj, "MALFORMED", ("code must be a string "
                                  "(catalog id or empty)",)
    return obj, "OK", ()


def _parse_c23(raw: str) -> tuple:
    obj, why = _json_object(raw)
    if obj is None:
        return None, "MALFORMED", (why or "non-JSON output",)
    return obj, "OK", ()


def _parse_c24(raw: str) -> tuple:
    obj, why = _json_object(raw)
    if obj is None:
        return None, "MALFORMED", (why or "non-JSON output",)
    missing = {"fallback_id", "action", "arguments"} - set(obj)
    extra = set(obj) - {"fallback_id", "action", "arguments"}
    if missing or extra:
        return obj, "MALFORMED", (
            f"fields missing={sorted(missing)} extra={sorted(extra)}",)
    if not isinstance(obj["fallback_id"], str) or \
            not isinstance(obj["action"], str) or \
            not isinstance(obj["arguments"], dict):
        return obj, "MALFORMED", ("fallback_id/action must be strings, "
                                  "arguments an object",)
    return obj, "OK", ()
