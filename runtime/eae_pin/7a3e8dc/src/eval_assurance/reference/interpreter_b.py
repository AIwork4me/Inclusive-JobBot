"""EA03-B — independent Interpreter for raw N03 Batch B (C09-C16) responses.

Independently authored reference-path parser for the Batch B output
contracts (handoff ``requirements.md`` @ c772a9a, cross-cutting rules
from the Batch A ``parser_semantics.md`` apply unchanged: key-based
access, no substring membership, EMPTY_OUTPUT separation,
exception-masking immunity, duplicate JSON keys are a structural
defect, markdown-fence tolerance).

Parser surfaces (pinned per primitive):
- C09: flat JSON object conforming to the declared schema.
- C10: nested JSON object; array cardinality is checked downstream
  against the declared exact count (the parser surfaces the document).
- C11: one DSL statement per line, declared tokens only; lowercase /
  undeclared tokens are model defects surfaced as violations.
- C12: slot record JSON object; declared normalizations (null only
  when unstated) are semantic, checked downstream.
- C13: one candidate id (bare token or single-field JSON).
- C14: JSON object of numeric values; string-typed numbers are a
  model-side structural defect (the public instruction demands
  "numbers not strings").
- C15: JSON object with ``value`` (number) and ``unit`` (string).
- C16: grounded short answer — a single short line of text.

``parse_response`` returns ``(typed_value, parse_class, reasons)`` with
parse_class OK / EMPTY_OUTPUT / MALFORMED / PARSER_SOFTWARE_ERROR;
MALFORMED is a MODEL-side contract violation (INCORRECT downstream),
PARSER_SOFTWARE_ERROR is interpreter failure (NOT_EVALUABLE). No
IJ-NANO imports; independence from ``production/parser_b.py`` is
structural (this module: regex/extraction-first with a bilingual
surface table; the production module: tokenizer + declarative rule
table), disclosed common-mode risk: both authored from the same pinned
handoff text.
"""
from __future__ import annotations

import json
import re

BATCH_B = tuple(f"C{i:02d}" for i in range(9, 17))

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


def _json_value(text: str):
    """Extract one top-level JSON value (object or array), fence-tolerant.

    Duplicate keys are a structural defect. Returns (value, reason).
    """
    cleaned = _strip_fences(text).strip()
    if not cleaned.startswith(("{", "[")):
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
    val, why = _json_value(text)
    if val is None:
        return None, why
    if not isinstance(val, dict):
        return None, "JSON value is not an object"
    return val, None


def parse_response(primitive: str, payload: dict, response) -> tuple:
    """Parse a raw Batch B model response into typed semantics.

    Never raises for model-side defects; software faults raise and the
    caller maps them to PARSER_SOFTWARE_ERROR.
    """
    if response is None:
        return None, "EMPTY_OUTPUT", ("response is None",)
    raw = response if isinstance(response, str) else str(response)
    if raw.strip() == "":
        return None, "EMPTY_OUTPUT", ("empty model output",)
    if primitive == "C09":
        return _parse_c09(raw)
    if primitive == "C10":
        return _parse_c10(raw)
    if primitive == "C11":
        return _parse_c11(raw, payload)
    if primitive == "C12":
        return _parse_c12(raw)
    if primitive == "C13":
        return _parse_c13(raw, payload)
    if primitive == "C14":
        return _parse_c14(raw)
    if primitive == "C15":
        return _parse_c15(raw)
    if primitive == "C16":
        return _parse_c16(raw)
    return None, "PARSER_SOFTWARE_ERROR", (
        f"primitive {primitive} outside Batch B interpreter scope",)


# -- C09: flat JSON record ---------------------------------------------------
def _parse_c09(raw: str) -> tuple:
    obj, why = _json_object(raw)
    if obj is None:
        return None, "MALFORMED", (why or "non-JSON output",)
    return obj, "OK", ()


# -- C10: nested JSON document ----------------------------------------------
def _parse_c10(raw: str) -> tuple:
    obj, why = _json_object(raw)
    if obj is None:
        return None, "MALFORMED", (why or "non-JSON output",)
    return obj, "OK", ()


# -- C11: DSL program lines ---------------------------------------------------
_DSL_TOKEN = re.compile(r"^([A-Z][A-Z0-9_]*)(?:\s+(.+))?$")


def _parse_c11(raw: str, payload: dict) -> tuple:
    grammar = payload.get("grammar") or {}
    cleaned = _strip_fences(raw)
    lines = [ln.strip() for ln in cleaned.splitlines() if ln.strip()]
    if not lines:
        return None, "MALFORMED", ("no statements emitted",)
    statements, reasons = [], []
    for ln in lines:
        m = _DSL_TOKEN.match(ln)
        if not m:
            reasons.append(f"line is not a declared statement form: "
                           f"{ln[:30]!r}")
            continue
        token, rest = m.group(1), (m.group(2) or "").split()
        if token not in grammar:
            reasons.append(f"undeclared token {token!r}")
            continue
        arity = grammar[token].count("<")
        if len(rest) != arity:
            reasons.append(f"{token} expects {arity} argument(s), got "
                           f"{len(rest)}: {ln[:30]!r}")
            continue
        statements.append(" ".join([token] + rest))
    if reasons:
        return statements, "MALFORMED", tuple(reasons)
    return statements, "OK", ()


# -- C12: slot record ---------------------------------------------------------
def _parse_c12(raw: str) -> tuple:
    obj, why = _json_object(raw)
    if obj is None:
        return None, "MALFORMED", (why or "non-JSON output",)
    return obj, "OK", ()


# -- C13: one candidate id ----------------------------------------------------
def _parse_c13(raw: str, payload: dict) -> tuple:
    obj, why = _json_object(raw)
    if obj is not None:
        hit = [k for k in ("resolution", "id", "candidate_id") if k in obj]
        if len(obj) != 1 or not hit:
            return None, "MALFORMED", (
                "JSON must carry exactly one resolution/id field",)
        return str(obj[hit[0]]).strip(), "OK", ()
    if why and why != "no JSON value at the surface" and \
            why != "no JSON object at the surface":
        return None, "MALFORMED", (why,)
    cleaned = _strip_fences(raw).strip().strip('"').strip("'")
    if not cleaned or "\n" in cleaned or " " in cleaned:
        return None, "MALFORMED", (
            "resolution must be exactly one candidate id",)
    return cleaned, "OK", ()


# -- C14: numeric JSON object ---------------------------------------------------
def _parse_c14(raw: str) -> tuple:
    obj, why = _json_object(raw)
    if obj is None:
        return None, "MALFORMED", (why or "non-JSON output",)
    reasons = []
    for k, v in obj.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            reasons.append(f"{k}: numbers not strings/booleans")
    if reasons:
        return obj, "MALFORMED", tuple(reasons)
    return obj, "OK", ()


# -- C15: value + unit ----------------------------------------------------------
def _parse_c15(raw: str) -> tuple:
    obj, why = _json_object(raw)
    if obj is None:
        return None, "MALFORMED", (why or "non-JSON output",)
    if set(obj) != {"value", "unit"}:
        return obj, "MALFORMED", ('must be exactly {"value": number, '
                                  '"unit": string}',)
    if isinstance(obj["value"], bool) or \
            not isinstance(obj["value"], (int, float)):
        return obj, "MALFORMED", ("value must be a number",)
    if not isinstance(obj["unit"], str):
        return obj, "MALFORMED", ("unit must be a string",)
    return obj, "OK", ()


# -- C16: grounded short answer ---------------------------------------------------
def _parse_c16(raw: str) -> tuple:
    cleaned = _strip_fences(raw).strip()
    lines = [ln.strip() for ln in cleaned.splitlines() if ln.strip()]
    if not lines:
        return None, "MALFORMED", ("no answer text",)
    if len(lines) > 1:
        return None, "MALFORMED", (
            f"short answer must be one line, got {len(lines)}",)
    return lines[0], "OK", ()
