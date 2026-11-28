"""EA04-C — Production Parser for raw N03 Batch C (C17-C24) responses.

Production leg of the Batch C dual-path: tokenizer + declarative rule
table, structurally distinct from ``reference/interpreter_c.py``
(regex/extraction-first). Both authored from the same pinned handoff
text (disclosed common-mode risk). No cross-imports, no IJ-NANO
imports.

Surfaces (pinned):
- C17: JSON list of booleans (per queried predicate id).
- C18: JSON list of [a, b] pairs or "a before b" lines.
- C19/C21: JSON list of action names or one action per line.
- C20: JSON list or comma/newline-separated branch ids.
- C22: {"is_error": boolean, "code": string}.
- C23: flat JSON object (corrected argument record).
- C24: {"fallback_id", "action", "arguments"} object.

Cross-cutting: fence tolerance, duplicate-key rejection, EMPTY_OUTPUT
own class, no substring matching, software faults raise.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

PARSE_OK = "OK"
PARSE_EMPTY = "EMPTY_OUTPUT"
PARSE_MALFORMED = "MALFORMED"
PARSE_SOFTWARE = "PARSER_SOFTWARE_ERROR"

BATCH_C = tuple(f"C{i:02d}" for i in range(17, 25))


@dataclass(frozen=True)
class ParsedAnswerC:
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
    return str(token).strip().strip('"').strip("'")


def _json_at_surface(cleaned: str):
    if not cleaned.startswith(("[", "{")):
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


def _rule_c17(payload: dict, t: dict) -> ParsedAnswerC:
    val = t["json"]
    if val is not None and isinstance(val, list):
        if any(not isinstance(x, bool) for x in val):
            return ParsedAnswerC("C17", list(val), PARSE_MALFORMED,
                                 ("truths must be booleans",), "json")
        return ParsedAnswerC("C17", list(val), PARSE_OK, (), "json")
    if t["json_reason"] and \
            t["json_reason"] != "no JSON value at the surface":
        return ParsedAnswerC("C17", None, PARSE_MALFORMED,
                             (t["json_reason"],), "")
    toks = [x for x in re.split(r"[\s,]+", t["cleaned"].strip()) if x]
    if toks and all(x.lower() in ("true", "false") for x in toks):
        return ParsedAnswerC("C17", [x.lower() == "true" for x in toks],
                             PARSE_OK, (), "text")
    return ParsedAnswerC("C17", None, PARSE_MALFORMED,
                         ("truths must be booleans",), "text")


def _rule_c18(payload: dict, t: dict) -> ParsedAnswerC:
    val = t["json"]
    if val is not None and isinstance(val, list):
        out = []
        for el in val:
            if isinstance(el, list) and len(el) == 2 and \
                    all(isinstance(x, str) and x.strip() for x in el):
                out.append((_norm(el[0]), _norm(el[1])))
            else:
                return ParsedAnswerC("C18", None, PARSE_MALFORMED,
                                     ("edges must be [a, b] string "
                                      "pairs",), "json")
        return ParsedAnswerC("C18", out, PARSE_OK, (), "json")
    if t["json_reason"] and \
            t["json_reason"] != "no JSON value at the surface":
        return ParsedAnswerC("C18", None, PARSE_MALFORMED,
                             (t["json_reason"],), "")
    out = []
    for ln in t["lines"]:
        m = re.match(r"^(\S+)\s+before\s+(\S+)$", ln)
        if not m:
            return ParsedAnswerC("C18", None, PARSE_MALFORMED,
                                 (f"edge line must be 'a before b': "
                                  f"{ln[:30]!r}",), "text")
        out.append((m.group(1), m.group(2)))
    if not out:
        return ParsedAnswerC("C18", None, PARSE_MALFORMED,
                             ("no edges emitted",), "text")
    return ParsedAnswerC("C18", out, PARSE_OK, (), "text")


def _rule_plan(prim: str, payload: dict, t: dict) -> ParsedAnswerC:
    val = t["json"]
    if val is not None and isinstance(val, list):
        if any(not isinstance(x, str) or not x.strip() for x in val):
            return ParsedAnswerC(prim, None, PARSE_MALFORMED,
                                 ("plan entries must be action names",),
                                 "json")
        return ParsedAnswerC(prim, [x.strip() for x in val], PARSE_OK,
                             (), "json")
    if t["json_reason"] and \
            t["json_reason"] != "no JSON value at the surface":
        return ParsedAnswerC(prim, None, PARSE_MALFORMED,
                             (t["json_reason"],), "")
    if not t["lines"]:
        return ParsedAnswerC(prim, None, PARSE_MALFORMED,
                             ("no plan emitted",), "text")
    bad = [ln for ln in t["lines"] if " " in ln or "," in ln]
    if bad:
        return ParsedAnswerC(prim, None, PARSE_MALFORMED,
                             (f"plan lines must be bare action names: "
                              f"{bad[0][:30]!r}",), "text")
    return ParsedAnswerC(prim, list(t["lines"]), PARSE_OK, (), "text")


def _rule_c20(payload: dict, t: dict) -> ParsedAnswerC:
    val = t["json"]
    if val is not None and isinstance(val, list):
        if any(not isinstance(x, str) for x in val):
            return ParsedAnswerC("C20", None, PARSE_MALFORMED,
                                 ("branch ids must be strings",), "json")
        return ParsedAnswerC("C20", [_norm(x) for x in val], PARSE_OK,
                             (), "json")
    if t["json_reason"] and \
            t["json_reason"] != "no JSON value at the surface":
        return ParsedAnswerC("C20", None, PARSE_MALFORMED,
                             (t["json_reason"],), "")
    ids = [_norm(x) for x in
           re.split(r"[,\n]", t["cleaned"].strip()) if x.strip()]
    if not ids:
        return ParsedAnswerC("C20", None, PARSE_MALFORMED,
                             ("no branch ids emitted",), "text")
    bad = [x for x in ids if " " in x]
    if bad:
        return ParsedAnswerC("C20", None, PARSE_MALFORMED,
                             (f"id with embedded space: {bad[0]!r}",),
                             "text")
    return ParsedAnswerC("C20", ids, PARSE_OK, (), "text")


def _rule_c22(payload: dict, t: dict) -> ParsedAnswerC:
    if not isinstance(t["json"], dict):
        return ParsedAnswerC("C22", None, PARSE_MALFORMED,
                             (t["json_reason"] or "non-JSON output",), "")
    obj = t["json"]
    violations = []
    if set(obj) != {"is_error", "code"}:
        violations.append('must be exactly {"is_error": boolean, '
                          '"code": string}')
    else:
        if not isinstance(obj["is_error"], bool):
            violations.append("is_error must be a boolean")
        if not isinstance(obj["code"], str):
            violations.append("code must be a string")
    if violations:
        return ParsedAnswerC("C22", dict(obj), PARSE_MALFORMED,
                             tuple(violations), "json")
    return ParsedAnswerC("C22", dict(obj), PARSE_OK, (), "json")


def _rule_c23(payload: dict, t: dict) -> ParsedAnswerC:
    if not isinstance(t["json"], dict):
        return ParsedAnswerC("C23", None, PARSE_MALFORMED,
                             (t["json_reason"] or "non-JSON output",), "")
    return ParsedAnswerC("C23", dict(t["json"]), PARSE_OK, (), "json")


def _rule_c24(payload: dict, t: dict) -> ParsedAnswerC:
    if not isinstance(t["json"], dict):
        return ParsedAnswerC("C24", None, PARSE_MALFORMED,
                             (t["json_reason"] or "non-JSON output",), "")
    obj = t["json"]
    missing = {"fallback_id", "action", "arguments"} - set(obj)
    extra = set(obj) - {"fallback_id", "action", "arguments"}
    violations = []
    if missing:
        violations.append(f"missing fields: {sorted(missing)}")
    if extra:
        violations.append(f"undeclared fields: {sorted(extra)}")
    if not missing and (
            not isinstance(obj["fallback_id"], str) or
            not isinstance(obj["action"], str) or
            not isinstance(obj["arguments"], dict)):
        violations.append("fallback_id/action must be strings, arguments "
                          "an object")
    if violations:
        return ParsedAnswerC("C24", dict(obj), PARSE_MALFORMED,
                             tuple(violations), "json")
    return ParsedAnswerC("C24", dict(obj), PARSE_OK, (), "json")


_RULES = {
    "C17": _rule_c17, "C18": _rule_c18,
    "C19": lambda p, t: _rule_plan("C19", p, t),
    "C20": _rule_c20, "C22": _rule_c22, "C23": _rule_c23,
    "C24": _rule_c24,
    "C21": lambda p, t: _rule_plan("C21", p, t),
}


def parse_response(primitive: str, payload: dict,
                   response) -> ParsedAnswerC:
    if response is None:
        return ParsedAnswerC(primitive, None, PARSE_EMPTY,
                             ("response is None",))
    raw = response if isinstance(response, str) else str(response)
    if raw.strip() == "":
        return ParsedAnswerC(primitive, None, PARSE_EMPTY,
                             ("empty model output",))
    rule = _RULES.get(primitive)
    if rule is None:
        return ParsedAnswerC(
            primitive, None, PARSE_SOFTWARE,
            (f"primitive {primitive} outside Batch C production scope",))
    return rule(payload or {}, _tokenize(raw))
