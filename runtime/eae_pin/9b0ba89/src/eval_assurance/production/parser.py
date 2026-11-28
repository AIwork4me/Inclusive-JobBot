"""EA04 — Production Parser for raw N03 Batch A responses.

Implements the MINIMUM parser semantics of the pinned handoff contract
(``parser_semantics.md`` @ d23de5a) as the PRODUCTION leg of the dual-path
evaluation (order section 2: Raw response -> Production Parser ->
Production Evaluator).

Independence statement (EA06): this module is structurally distinct from
the reference interpreter (``reference/interpreter.py``) — tokenizer-first
surface classification through a declarative rule table with a single
normalization point, ``ParsedAnswer`` records instead of bare tuples —
but both implementations are authored from the SAME pinned spec text, a
disclosed common-mode risk (spec authorship), and both share the corpus
vocabulary. The reference path never imports this module and vice versa.

Contract (pinned, per primitive):
- C01/C06/C07/C08: bare label token OR single-field JSON with the
  primitive's key; catalog membership is decided downstream (multiple
  labels / free text / out-of-catalog labels are model failures, not
  parse errors).
- C02: JSON object with exactly the five schema fields; ``unknown_flags``
  is an object of booleans.
- C03: family-dependent (formatting lines / formfill single-field JSON /
  oneedit exactly one line).
- C04: comma- or newline-separated ids or a JSON list; an empty result
  must surface as an explicit empty list.
- C05: ``TRUE``/``FALSE`` (case-tolerant) or ``{"decision": bool}``;
  narrated hedges are model failures.

Cross-cutting (historical-immunity list):
- key-based access only (no positional unpacking anywhere);
- markdown-fence tolerance; duplicate JSON keys are a structural defect;
- empty model output is ``EMPTY_OUTPUT`` — its own class, never a parse
  error, never INCORRECT;
- substring matching is never sufficient: exact token equality after
  trim/case-normalization, applied at exactly one point (``_normalize``);
- software faults raise; the caller classifies them
  ``PARSER_SOFTWARE_ERROR`` (never model failures).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

#: parse classes shared with the reference interpreter's vocabulary so
#: dual-path comparison is well defined
PARSE_OK = "OK"
PARSE_EMPTY = "EMPTY_OUTPUT"
PARSE_MALFORMED = "MALFORMED"
PARSE_SOFTWARE = "PARSER_SOFTWARE_ERROR"

_C02_SCHEMA = ("action", "object", "deadline", "completion_criterion",
               "unknown_flags")

#: single-field JSON key accepted per label-like primitive
_LABEL_JSON_KEY = {"C01": ("intent", "label"), "C06": ("choice",),
                   "C07": ("action",), "C08": ("tool_id",)}


@dataclass(frozen=True)
class ParsedAnswer:
    """Production parse result record (typed value + surface class)."""
    primitive: str
    value: object                       # typed semantics (label, record,
    #                                       lines, ids, bool...)
    parse_class: str                    # OK / EMPTY_OUTPUT / MALFORMED /
    #                                   # PARSER_SOFTWARE_ERROR
    violations: tuple = field(default_factory=tuple)
    surface: str = ""                   # json | bare | text | list | ""

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
    """Tolerate a single surrounding markdown fence (pinned contract)."""
    t = text.strip()
    if t.startswith("```"):
        nl = t.find("\n")
        t = t[nl + 1:] if nl >= 0 else ""
    if t.rstrip().endswith("```"):
        t = t.rstrip()[:-3]
    return t


def _normalize(token) -> str:
    """The single normalization point: trim + case-fold for token equality.

    Substring matching is NEVER performed anywhere in this module.
    """
    return str(token).strip().strip('"').strip("'").lower()


def _surface_json(cleaned: str):
    """Parse a top-level JSON object; duplicate keys are structural."""
    if not cleaned.startswith("{"):
        return None, "no JSON object at the surface"
    try:
        obj = json.loads(cleaned, object_pairs_hook=_no_duplicate_keys)
    except _DuplicateKey as dup:
        return None, f"duplicate JSON key: {dup.args[0]}"
    except ValueError as ve:
        return None, f"invalid JSON: {ve}"
    if not isinstance(obj, dict):
        return None, "top-level JSON is not an object"
    return obj, None


# ---------------------------------------------------------------------------
# tokenizer: one pass over the raw surface shared by all rules
# ---------------------------------------------------------------------------
def _tokenize(raw: str) -> dict:
    cleaned = _strip_fence(raw)
    lines = [ln.strip() for ln in cleaned.splitlines()]
    nonempty = [ln for ln in lines if ln]
    obj, why = _surface_json(cleaned.strip())
    return {"cleaned": cleaned, "lines": nonempty, "json": obj,
            "json_reason": why, "bare": _normalize(nonempty[0])
            if len(nonempty) == 1 else None}


# ---------------------------------------------------------------------------
# rule table (declarative surface rules per primitive)
# ---------------------------------------------------------------------------
def _rule_label(prim: str, payload: dict, t: dict) -> ParsedAnswer:
    keys = _LABEL_JSON_KEY[prim]
    if t["json"] is not None:
        hit = [k for k in keys if k in t["json"]]
        if len(t["json"]) != 1 or not hit:
            return ParsedAnswer(
                prim, None, PARSE_MALFORMED,
                (f"JSON must carry exactly one field of {keys}",), "json")
        return ParsedAnswer(prim, _normalize(t["json"][hit[0]]),
                            PARSE_OK, (), "json")
    if t["json_reason"] and t["json_reason"] != \
            "no JSON object at the surface":
        return ParsedAnswer(prim, None, PARSE_MALFORMED,
                            (t["json_reason"],), "")
    if t["bare"] is None:                      # free text / multiple lines
        return ParsedAnswer(prim, None, PARSE_MALFORMED,
                            ("multiple labels or free text",), "text")
    if "," in t["cleaned"]:
        return ParsedAnswer(prim, None, PARSE_MALFORMED,
                            ("comma-separated label list",), "text")
    return ParsedAnswer(prim, t["bare"], PARSE_OK, (), "bare")


def _rule_c02(payload: dict, t: dict) -> ParsedAnswer:
    schema = tuple(payload.get("schema_fields") or _C02_SCHEMA)
    if t["json"] is None:
        return ParsedAnswer("C02", None, PARSE_MALFORMED,
                            (t["json_reason"] or "non-JSON output",), "")
    extra = sorted(set(t["json"]) - set(schema))
    missing = sorted(set(schema) - set(t["json"]))
    violations = []
    if extra:
        violations.append(f"unexpected fields: {extra}")
    if missing:
        violations.append(f"missing schema fields: {missing}")
    flags = t["json"].get("unknown_flags")
    if flags is not None and not isinstance(flags, dict):
        violations.append("unknown_flags is not an object")
    elif isinstance(flags, dict):
        bad = sorted(k for k, v in flags.items()
                     if not isinstance(v, bool))
        if bad:
            violations.append(f"non-boolean unknown_flags: {bad}")
    if violations:
        return ParsedAnswer("C02", dict(t["json"]), PARSE_MALFORMED,
                            tuple(violations), "json")
    return ParsedAnswer("C02", dict(t["json"]), PARSE_OK, (), "json")


def _rule_c03(payload: dict, t: dict) -> ParsedAnswer:
    if payload.get("form_fields") is not None:          # formfill family
        if t["json"] is None:
            return ParsedAnswer("C03", None, PARSE_MALFORMED,
                                (t["json_reason"] or "non-JSON output",),
                                "")
        if len(t["json"]) != 1:
            return ParsedAnswer("C03", dict(t["json"]), PARSE_MALFORMED,
                                ("formfill must be a single-field object",),
                                "json")
        return ParsedAnswer("C03", dict(t["json"]), PARSE_OK, (), "json")
    if any(k in payload for k in ("source_line", "record_line",
                                  "line_to_edit")):      # oneedit family
        if len(t["lines"]) != 1:
            return ParsedAnswer("C03", list(t["lines"]), PARSE_MALFORMED,
                                (f"oneedit must be exactly one line, got "
                                 f"{len(t['lines'])}",), "text")
        return ParsedAnswer("C03", t["lines"][0], PARSE_OK, (), "text")
    # formatting family: plain lines, no bullets / enumeration markers
    out, violations = [], []
    for ln in t["lines"]:
        s = ln.lstrip()
        if s[:2] in ("- ", "* ", "+ ") or s[:1] in ("•",) or \
                (len(s) > 1 and s[0].isdigit() and s[1] in ".)"):
            violations.append(f"enumeration/bullet marker: {s[:20]!r}")
            continue
        out.append(ln.strip())
    if violations:
        return ParsedAnswer("C03", out, PARSE_MALFORMED, tuple(violations),
                            "text")
    return ParsedAnswer("C03", out, PARSE_OK, (), "text")


def _rule_c04(payload: dict, t: dict) -> ParsedAnswer:
    cleaned = t["cleaned"].strip()
    if cleaned.startswith("["):
        try:
            arr = json.loads(cleaned)
        except ValueError as ve:
            return ParsedAnswer("C04", None, PARSE_MALFORMED,
                                (f"invalid JSON list: {ve}",), "")
        if not isinstance(arr, list):
            return ParsedAnswer("C04", None, PARSE_MALFORMED,
                                ("JSON value is not a list",), "json")
        return ParsedAnswer("C04", [_normalize(x) for x in arr],
                            PARSE_OK, (), "list")
    ids, violations = [], []
    for chunk in cleaned.replace("\n", ",").split(","):
        tok = chunk.strip()
        if not tok:
            continue                              # explicit empty slots
        if " " in tok:
            violations.append(f"id with embedded space: {tok!r}")
            continue
        ids.append(_normalize(tok))
    if violations:
        return ParsedAnswer("C04", ids, PARSE_MALFORMED, tuple(violations),
                            "text")
    return ParsedAnswer("C04", ids, PARSE_OK, (), "text")


def _rule_c05(payload: dict, t: dict) -> ParsedAnswer:
    if t["json"] is not None:
        if set(t["json"]) != {"decision"} or \
                not isinstance(t["json"]["decision"], bool):
            return ParsedAnswer("C05", None, PARSE_MALFORMED,
                                ('C05 JSON must be exactly '
                                 '{"decision": boolean}',), "json")
        return ParsedAnswer("C05", t["json"]["decision"], PARSE_OK, (),
                            "json")
    if t["json_reason"] and t["json_reason"] != \
            "no JSON object at the surface":
        return ParsedAnswer("C05", None, PARSE_MALFORMED,
                            (t["json_reason"],), "")
    tok = t["cleaned"].strip().strip('"').strip("'").upper()
    if tok == "TRUE":
        return ParsedAnswer("C05", True, PARSE_OK, (), "bare")
    if tok == "FALSE":
        return ParsedAnswer("C05", False, PARSE_OK, (), "bare")
    return ParsedAnswer("C05", None, PARSE_MALFORMED,
                        ("narrated hedge or non-boolean output",), "text")


_RULES = {
    "C01": lambda p, t: _rule_label("C01", p, t),
    "C02": _rule_c02,
    "C03": _rule_c03,
    "C04": _rule_c04,
    "C05": _rule_c05,
    "C06": lambda p, t: _rule_label("C06", p, t),
    "C07": lambda p, t: _rule_label("C07", p, t),
    "C08": lambda p, t: _rule_label("C08", p, t),
}


def parse_response(primitive: str, payload: dict,
                   response) -> ParsedAnswer:
    """Module-level production parse (never raises on model defects)."""
    if response is None:
        return ParsedAnswer(primitive, None, PARSE_EMPTY,
                            ("response is None",))
    raw = response if isinstance(response, str) else str(response)
    if raw.strip() == "":
        return ParsedAnswer(primitive, None, PARSE_EMPTY,
                            ("empty model output",))
    rule = _RULES.get(primitive)
    if rule is None:
        return ParsedAnswer(
            primitive, None, PARSE_SOFTWARE,
            (f"primitive {primitive} outside Batch A production scope",))
    return rule(payload or {}, _tokenize(raw))


class ProductionParser:
    """Runner-shaped production parser (the leg the physical runner
    scores with; identical semantics to :func:`parse_response`)."""

    identity = "eval_assurance.production.parser@1"

    def parse(self, case_id: str, content: str):
        """Runner-compatible signature. ``case`` metadata is bound by the
        session, not smuggled through positional unpacking (N02R rule)."""
        raise NotImplementedError(
            "use parse_response(primitive, payload, response) or the "
            "dual-path session; runner adapters live in dualpath.py")
