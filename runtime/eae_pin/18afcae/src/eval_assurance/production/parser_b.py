"""EA04-B — Production Parser for raw N03 Batch B (C09-C16) responses.

Production leg of the Batch B dual-path. Implements the MINIMUM parser
semantics of the pinned handoff (Batch B ``requirements.md`` @ c772a9a
+ Batch A cross-cutting rules) with a tokenizer + declarative rule
table, structurally distinct from the reference interpreter
(``reference/interpreter_b.py``, regex/extraction-first). Both are
authored from the same pinned spec text (disclosed common-mode risk).
The reference path never imports this module and vice versa.

Contract (pinned, per primitive):
- C09: a single flat JSON object per the declared schema (extra/dropped
  fields are model failures surfaced as violations).
- C10: one nested JSON object; array cardinality violations are model
  failures.
- C11: one DSL statement per line; declared tokens only; lowercased or
  undeclared tokens / missing arguments / arity errors are model
  failures.
- C12: a slot record JSON object; keys within the declared schema.
- C13: one candidate id (bare token or single-field JSON).
- C14: numeric JSON values (string-typed numbers are model failures).
- C15: ``{"value": number, "unit": string}``.
- C16: a grounded short answer (single short line).

Cross-cutting (historical-immunity list): key-based access only; a
single markdown-fence tolerance; duplicate JSON keys are a structural
defect; empty model output is EMPTY_OUTPUT — its own class, never a
parse error, never INCORRECT; substring matching is never sufficient;
software faults raise and the caller classifies them
PARSER_SOFTWARE_ERROR (never model failures).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

PARSE_OK = "OK"
PARSE_EMPTY = "EMPTY_OUTPUT"
PARSE_MALFORMED = "MALFORMED"
PARSE_SOFTWARE = "PARSER_SOFTWARE_ERROR"

BATCH_B = tuple(f"C{i:02d}" for i in range(9, 17))


@dataclass(frozen=True)
class ParsedAnswerB:
    """Production parse result record (typed value + surface class)."""
    primitive: str
    value: object
    parse_class: str
    violations: tuple = field(default_factory=tuple)
    surface: str = ""

    @property
    def ok(self) -> bool:
        return self.parse_class == PARSE_OK


class _DuplicateKey(ValueError):
    pass


def _no_duplicate_keys(pairs):
    seen = set()
    for k, _ in pairs:
        if k in seen:
            raise _DuplicateKey(k)
        seen.add(k)
    return dict(pairs)


def _strip_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        nl = t.find("\n")
        t = t[nl + 1:] if nl >= 0 else ""
    if t.rstrip().endswith("```"):
        t = t.rstrip()[:-3]
    return t


def _norm(token) -> str:
    """Single normalization point: trim + strip quotes (case preserved:
    DSL tokens are case-sensitive; id case-folding happens at exactly
    one comparison point in the evaluator)."""
    return str(token).strip().strip('"').strip("'")


def _json_at_surface(cleaned: str):
    if not cleaned.startswith(("{", "[")):
        return None, "no JSON value at the surface"
    try:
        val = json.loads(cleaned, object_pairs_hook=_no_duplicate_keys)
    except _DuplicateKey as dup:
        return None, f"duplicate JSON key: {dup.args[0]}"
    except ValueError as ve:
        return None, f"invalid JSON: {ve}"
    return val, None


def _tokenize(raw: str) -> dict:
    cleaned = _strip_fence(raw)
    lines = [ln.strip() for ln in cleaned.splitlines()]
    nonempty = [ln for ln in lines if ln]
    val, why = _json_at_surface(cleaned.strip())
    return {"cleaned": cleaned, "lines": nonempty, "json": val,
            "json_reason": why,
            "bare": _norm(nonempty[0]) if len(nonempty) == 1 else None}


def _leaf_type_ok(kind: str, value) -> bool:
    if kind == "string":
        return isinstance(value, str)
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind in ("number",):
        return isinstance(value, (int, float)) and \
            not isinstance(value, bool)
    if kind == "boolean":
        return isinstance(value, bool)
    return True                                    # enum/unknown: stringly


def _check_against_schema(spec, value, path: str, out: list) -> None:
    """Declarative schema walker collecting violations (never raises)."""
    if not isinstance(spec, dict):
        return
    t = spec.get("type")
    if t == "object":
        fields = spec.get("fields") or {}
        if not isinstance(value, dict):
            out.append(f"{path}: expected object")
            return
        for k in fields:
            if k not in value:
                out.append(f"{path}.{k}: missing declared field")
        for k in value:
            if k not in fields:
                out.append(f"{path}.{k}: undeclared field")
        for k, sub in fields.items():
            if k in value:
                _check_against_schema(sub, value[k], f"{path}.{k}", out)
    elif t == "array":
        if not isinstance(value, list):
            out.append(f"{path}: expected array")
            return
        declared_min = spec.get("min")
        if declared_min is not None and len(value) != declared_min:
            out.append(f"{path}: array must contain exactly "
                       f"{declared_min} item(s), got {len(value)}")
        for i, el in enumerate(value):
            _check_against_schema(spec.get("item") or {}, el,
                                  f"{path}[{i}]", out)
    else:
        if not _leaf_type_ok(str(t), value):
            out.append(f"{path}: violates declared type {t!r}")


def _rule_c09(payload: dict, t: dict) -> ParsedAnswerB:
    if t["json"] is None or not isinstance(t["json"], dict):
        return ParsedAnswerB("C09", None, PARSE_MALFORMED,
                             (t["json_reason"] or "non-JSON output",), "")
    obj = t["json"]
    schema = payload.get("schema") or {}
    violations = []
    for k in schema:
        if k not in obj:
            violations.append(f"missing declared field: {k}")
    for k in obj:
        if k not in schema:
            violations.append(f"undeclared field: {k}")
        elif not _leaf_type_ok(str(schema[k]), obj[k]):
            violations.append(f"{k}: violates declared type "
                              f"{schema[k]!r}")
    if violations:
        return ParsedAnswerB("C09", dict(obj), PARSE_MALFORMED,
                             tuple(violations), "json")
    return ParsedAnswerB("C09", dict(obj), PARSE_OK, (), "json")


def _rule_c10(payload: dict, t: dict) -> ParsedAnswerB:
    if t["json"] is None or not isinstance(t["json"], dict):
        return ParsedAnswerB("C10", None, PARSE_MALFORMED,
                             (t["json_reason"] or "non-JSON output",), "")
    obj = t["json"]
    violations: list = []
    _check_against_schema(payload.get("schema") or {}, obj, "$",
                          violations)
    if violations:
        return ParsedAnswerB("C10", dict(obj), PARSE_MALFORMED,
                             tuple(violations), "json")
    return ParsedAnswerB("C10", dict(obj), PARSE_OK, (), "json")


def _rule_c11(payload: dict, t: dict) -> ParsedAnswerB:
    grammar = payload.get("grammar") or {}
    if not t["lines"]:
        return ParsedAnswerB("C11", None, PARSE_MALFORMED,
                             ("no statements emitted",), "text")
    statements, violations = [], []
    for ln in t["lines"]:
        parts = ln.split()
        token = parts[0] if parts else ""
        if token not in grammar:
            violations.append(f"undeclared statement token: {token!r}")
            continue
        arity = grammar[token].count("<")
        args = parts[1:]
        if len(args) != arity:
            violations.append(f"{token}: arity error, expects {arity} "
                              f"argument(s), got {len(args)}")
            continue
        statements.append(" ".join(parts))
    if violations:
        return ParsedAnswerB("C11", statements, PARSE_MALFORMED,
                             tuple(violations), "text")
    return ParsedAnswerB("C11", statements, PARSE_OK, (), "text")


def _rule_c12(payload: dict, t: dict) -> ParsedAnswerB:
    if t["json"] is None or not isinstance(t["json"], dict):
        return ParsedAnswerB("C12", None, PARSE_MALFORMED,
                             (t["json_reason"] or "non-JSON output",), "")
    obj = t["json"]
    schema = payload.get("schema") or {}
    violations = []
    for k in obj:
        if k not in schema:
            violations.append(f"undeclared slot: {k}")
    for k in schema:
        if k not in obj:
            violations.append(f"missing declared slot: {k}")
    if violations:
        return ParsedAnswerB("C12", dict(obj), PARSE_MALFORMED,
                             tuple(violations), "json")
    return ParsedAnswerB("C12", dict(obj), PARSE_OK, (), "json")


_ID_JSON_KEYS = ("resolution", "id", "candidate_id")


def _rule_c13(payload: dict, t: dict) -> ParsedAnswerB:
    if t["json"] is not None and isinstance(t["json"], dict):
        hit = [k for k in _ID_JSON_KEYS if k in t["json"]]
        if len(t["json"]) != 1 or not hit:
            return ParsedAnswerB("C13", None, PARSE_MALFORMED,
                                 ("JSON must carry exactly one "
                                  "resolution/id field",), "json")
        return ParsedAnswerB("C13", _norm(t["json"][hit[0]]),
                             PARSE_OK, (), "json")
    if t["json_reason"] and \
            t["json_reason"] != "no JSON value at the surface":
        return ParsedAnswerB("C13", None, PARSE_MALFORMED,
                             (t["json_reason"],), "")
    if t["bare"] is None or not t["bare"]:
        return ParsedAnswerB("C13", None, PARSE_MALFORMED,
                             ("free text instead of one candidate id",),
                             "text")
    if " " in t["bare"] or "," in t["bare"]:
        return ParsedAnswerB("C13", None, PARSE_MALFORMED,
                             ("multiple ids / id list",), "text")
    return ParsedAnswerB("C13", t["bare"], PARSE_OK, (), "bare")


def _rule_c14(payload: dict, t: dict) -> ParsedAnswerB:
    if t["json"] is None or not isinstance(t["json"], dict):
        return ParsedAnswerB("C14", None, PARSE_MALFORMED,
                             (t["json_reason"] or "non-JSON output",), "")
    obj = t["json"]
    violations = []
    for k, v in obj.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            violations.append(f"{k}: string-typed or non-numeric value")
    if violations:
        return ParsedAnswerB("C14", dict(obj), PARSE_MALFORMED,
                             tuple(violations), "json")
    return ParsedAnswerB("C14", dict(obj), PARSE_OK, (), "json")


def _rule_c15(payload: dict, t: dict) -> ParsedAnswerB:
    if t["json"] is None or not isinstance(t["json"], dict):
        return ParsedAnswerB("C15", None, PARSE_MALFORMED,
                             (t["json_reason"] or "non-JSON output",), "")
    obj = t["json"]
    violations = []
    if set(obj) != {"value", "unit"}:
        violations.append('must be exactly {"value": number, '
                          '"unit": string}')
    else:
        if isinstance(obj["value"], bool) or \
                not isinstance(obj["value"], (int, float)):
            violations.append("value must be a number")
        if not isinstance(obj["unit"], str):
            violations.append("unit must be a string")
    if violations:
        return ParsedAnswerB("C15", dict(obj), PARSE_MALFORMED,
                             tuple(violations), "json")
    return ParsedAnswerB("C15", dict(obj), PARSE_OK, (), "json")


def _rule_c16(payload: dict, t: dict) -> ParsedAnswerB:
    if not t["lines"]:
        return ParsedAnswerB("C16", None, PARSE_MALFORMED,
                             ("no answer text",), "text")
    if len(t["lines"]) != 1:
        return ParsedAnswerB("C16", None, PARSE_MALFORMED,
                             (f"short answer must be one line, got "
                              f"{len(t['lines'])}",), "text")
    return ParsedAnswerB("C16", t["lines"][0], PARSE_OK, (), "text")


_RULES = {
    "C09": _rule_c09, "C10": _rule_c10, "C11": _rule_c11,
    "C12": _rule_c12, "C13": _rule_c13, "C14": _rule_c14,
    "C15": _rule_c15, "C16": _rule_c16,
}


def parse_response(primitive: str, payload: dict,
                   response) -> ParsedAnswerB:
    """Module-level production parse (never raises on model defects)."""
    if response is None:
        return ParsedAnswerB(primitive, None, PARSE_EMPTY,
                             ("response is None",))
    raw = response if isinstance(response, str) else str(response)
    if raw.strip() == "":
        return ParsedAnswerB(primitive, None, PARSE_EMPTY,
                             ("empty model output",))
    rule = _RULES.get(primitive)
    if rule is None:
        return ParsedAnswerB(
            primitive, None, PARSE_SOFTWARE,
            (f"primitive {primitive} outside Batch B production scope",))
    return rule(payload or {}, _tokenize(raw))
