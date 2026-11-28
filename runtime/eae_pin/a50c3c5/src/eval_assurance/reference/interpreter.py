"""EA04/EA05 — independent Interpreter for raw N03 Batch A responses.

Implements the MINIMUM parser semantics of the pinned handoff contract
(``parser_semantics.md`` @ d23de5a) as an independently authored module
(no IJ-NANO imports). Production path comparison happens elsewhere; this
is the reference-path interpreter:

    Raw response -> Independent Interpreter -> Reference Oracle

Contract highlights (pinned):
- C01: bare label OR single-field JSON ``{"intent"|"label": ...}``; the
  label must be a catalog member; multiple labels / free text / labels
  outside the catalog are INCORRECT (model failures), not parse errors.
- C02: JSON object with exactly the five schema fields; unknown_flags is
  an object of booleans.
- C03 formatting: newline-separated plain-text lines (no bullets, no
  enumeration markers; leading/trailing whitespace tolerated, blank lines
  ignored); formfill: single-field JSON; oneedit: exactly one line.
- C04: comma- or newline-separated ids; empty result must surface as an
  explicit empty list, never a fallback guess.
- C05: TRUE/FALSE (case-tolerant) or ``{"decision": bool}``; narrated
  hedges are INCORRECT, not unparseable.
- C06/C07/C08: bare id/name or single-field JSON.

Cross-cutting:
- No positional unpacking; key-based access only.
- JSON extraction tolerates markdown fences; duplicate keys are a
  structural defect.
- Empty model output is EMPTY_OUTPUT (its own class), not a parse error
  and not INCORRECT.
- Substring matching is NEVER sufficient for label/id membership: exact
  token equality after trim/case-normalization.
- Interpreter software exceptions must surface as PARSER_SOFTWARE_ERROR,
  never as model failures.

``parse_response`` returns ``(typed_value, parse_class, reasons)`` where
parse_class is one of OK / EMPTY_OUTPUT / MALFORMED /
PARSER_SOFTWARE_ERROR. MALFORMED means the MODEL violated the output
contract (semantic INCORRECT downstream); PARSER_SOFTWARE_ERROR means the
interpreter itself failed (NOT_EVALUABLE downstream).
"""
from __future__ import annotations

import json
import re

_PARSE_CLASSES = ("OK", "EMPTY_OUTPUT", "MALFORMED", "PARSER_SOFTWARE_ERROR")

_FENCE = re.compile(r"^\s*```[a-zA-Z0-9_-]*\s*|\s*```\s*$")
_ENUM_MARKER = re.compile(r"^\s*(?:[-*+•]|\d+[.)])\s+")


def _strip_fences(text: str) -> str:
    return _FENCE.sub("", text)


def _json_object(text: str):
    """Extract a single JSON object, tolerating markdown fences.

    Duplicate keys are a structural defect (None). Returns (obj, reason).
    """
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


class _DuplicateKey(ValueError):
    pass


def _reject_duplicate_keys(pairs):
    seen = set()
    for k, _ in pairs:
        if k in seen:
            raise _DuplicateKey(k)
        seen.add(k)
    return dict(pairs)


def _norm_token(tok) -> str:
    return str(tok).strip().strip('"').strip("'").lower()


def parse_response(primitive: str, payload: dict, response) -> tuple:
    """Parse a raw model response into typed semantics.

    Never raises for model-side defects; only software faults raise, and
    the caller maps those to PARSER_SOFTWARE_ERROR.
    """
    if response is None:
        return None, "EMPTY_OUTPUT", ("response is None",)
    raw = response if isinstance(response, str) else str(response)
    if raw.strip() == "":
        return None, "EMPTY_OUTPUT", ("empty model output",)
    if primitive == "C01":
        return _parse_catalog_label(raw, payload.get("intent_catalog") or {},
                                    ("intent", "label"))
    if primitive == "C02":
        return _parse_c02(raw, payload)
    if primitive == "C03":
        return _parse_c03(raw, payload)
    if primitive == "C04":
        return _parse_c04(raw)
    if primitive == "C05":
        return _parse_c05(raw)
    if primitive == "C06":
        return _parse_catalog_label(raw, None, ("choice",))
    if primitive == "C07":
        return _parse_catalog_label(raw, payload.get("action_catalog") or {},
                                    ("action",))
    if primitive == "C08":
        return _parse_catalog_label(raw, None, ("tool_id",))
    return None, "PARSER_SOFTWARE_ERROR", (
        f"primitive {primitive} outside Batch A interpreter scope",)


def _parse_catalog_label(raw: str, catalog, json_keys) -> tuple:
    """C01/C06/C07/C08: bare token or single-field JSON. Membership in the
    catalog (when provided) decides CORRECTNESS downstream; here a bare
    multi-token free-text answer is MALFORMED."""
    obj, why = _json_object(raw)
    if obj is not None:
        keys = [k for k in json_keys if k in obj]
        if len(obj) != 1 or not keys:
            return None, "MALFORMED", (
                f"JSON object must have exactly one field of {json_keys}",)
        return _norm_token(obj[keys[0]]), "OK", ()
    if why and why != "no JSON object at the surface":
        return None, "MALFORMED", (why,)
    cleaned = _strip_fences(raw).strip()
    if "\n" in cleaned or "," in cleaned:
        return None, "MALFORMED", ("multiple labels / free text",)
    tok = cleaned.strip().strip('"').strip("'")
    if not tok or " " in tok.strip():
        return None, "MALFORMED", ("free text instead of a single label",)
    return _norm_token(tok), "OK", ()


def _parse_c02(raw: str, payload: dict) -> tuple:
    schema_fields = payload.get("schema_fields") or [
        "action", "object", "deadline", "completion_criterion",
        "unknown_flags"]
    obj, why = _json_object(raw)
    if obj is None:
        return None, "MALFORMED", (why or "non-JSON output",)
    extra = set(obj) - set(schema_fields)
    missing = set(schema_fields) - set(obj)
    reasons = []
    if extra:
        reasons.append(f"unexpected fields: {sorted(extra)}")
    if missing:
        reasons.append(f"missing schema fields: {sorted(missing)}")
    flags = obj.get("unknown_flags")
    if flags is not None and not isinstance(flags, dict):
        reasons.append("unknown_flags is not an object")
    elif isinstance(flags, dict):
        for k, v in flags.items():
            if not isinstance(v, bool):
                reasons.append(f"unknown_flags.{k} is not boolean")
    if reasons:
        return obj, "MALFORMED", tuple(reasons)
    # typed normalization: deadline stays ISO or None
    return obj, "OK", ()


def _parse_c03(raw: str, payload: dict) -> tuple:
    form_fields = payload.get("form_fields")
    if form_fields is not None:                       # formfill family
        obj, why = _json_object(raw)
        if obj is None:
            return None, "MALFORMED", (why or "non-JSON output",)
        if len(obj) != 1:
            return obj, "MALFORMED", (
                "formfill must be a single-field JSON object",)
        return obj, "OK", ()
    if "source_line" in payload or "record_line" in payload or \
            "line_to_edit" in payload:                # oneedit family
        cleaned = _strip_fences(raw).strip()
        lines = [ln for ln in cleaned.splitlines() if ln.strip()]
        if len(lines) != 1:
            return lines, "MALFORMED", (
                f"oneedit must be exactly one line, got {len(lines)}",)
        return lines[0].strip(), "OK", ()
    # formatting family
    cleaned = _strip_fences(raw)
    lines = []
    for ln in cleaned.splitlines():
        s = ln.rstrip()
        if not s.strip():
            continue                                  # blank lines ignored
        if _ENUM_MARKER.match(s):
            return None, "MALFORMED", (
                f"enumeration/bullet marker not allowed: {s.strip()[:30]!r}",)
        lines.append(s.strip())
    return lines, "OK", ()


def _parse_c04(raw: str) -> tuple:
    cleaned = _strip_fences(raw).strip()
    if cleaned.startswith("["):
        try:
            arr = json.loads(cleaned)
        except ValueError as ve:
            return None, "MALFORMED", (f"invalid JSON list: {ve}",)
        if not isinstance(arr, list):
            return None, "MALFORMED", ("JSON value is not a list",)
        return [_norm_token(x) for x in arr], "OK", ()
    if cleaned in ("[]",):
        return [], "OK", ()
    ids = []
    for chunk in re.split(r"[,\n]", cleaned):
        tok = chunk.strip()
        if not tok:
            continue
        if " " in tok:
            return None, "MALFORMED", (f"id with embedded space: {tok!r}",)
        ids.append(_norm_token(tok))
    return ids, "OK", ()


def _parse_c05(raw: str) -> tuple:
    cleaned = _strip_fences(raw).strip()
    obj, why = _json_object(raw)
    if obj is not None:
        if set(obj) != {"decision"} or not isinstance(obj["decision"], bool):
            return None, "MALFORMED", (
                'C05 JSON must be exactly {"decision": boolean}',)
        return obj["decision"], "OK", ()
    if why and why != "no JSON object at the surface":
        return None, "MALFORMED", (why,)
    tok = cleaned.strip().strip('"').strip("'").upper()
    if tok == "TRUE":
        return True, "OK", ()
    if tok == "FALSE":
        return False, "OK", ()
    return None, "MALFORMED", (
        "narrated hedge or non-boolean output",)
