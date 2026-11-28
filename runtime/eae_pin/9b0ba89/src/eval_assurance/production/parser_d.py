"""EA04-D — Production Parser for raw N03 Batch D (C25-C32) responses.

Production leg of the Batch D dual-path: tokenizer + declarative rule
table, structurally distinct from ``reference/interpreter_d.py``. No
cross-imports, no IJ-NANO imports; both authored from the same pinned
handoff (disclosed common-mode risk).

Surfaces (pinned):
- C25: STOP / CONTINUE single token.
- C26: ACT bare; ASK + missing slot names (JSON or text).
- C27: PROCEED; ESCALATE + rule ids (JSON or text).
- C28: single-line typed answer.
- C29: id, or AMBIGUOUS + conflicting ids (JSON or text).
- C30: canonical op:entity[:extra] single token.
- C31: cited answer (citations extracted from "(EV-n)" markers).
- C32: ABSTAIN or single-line answer.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

PARSE_OK = "OK"
PARSE_EMPTY = "EMPTY_OUTPUT"
PARSE_MALFORMED = "MALFORMED"
PARSE_SOFTWARE = "PARSER_SOFTWARE_ERROR"

BATCH_D = tuple(f"C{i:02d}" for i in range(25, 33))


@dataclass(frozen=True)
class ParsedAnswerD:
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


def _tokenize(raw: str) -> dict:
    cleaned = _strip_fence(raw)
    lines = [ln.strip() for ln in cleaned.splitlines()]
    nonempty = [ln for ln in lines if ln]
    stripped = cleaned.strip()
    obj = None
    why = None
    if stripped.startswith("{"):
        try:
            val = json.loads(stripped,
                             object_pairs_hook=_no_duplicate_keys)
        except _DuplicateKey as dup:
            why = f"duplicate JSON key: {dup.args[0]}"
        except ValueError as ve:
            why = f"invalid JSON: {ve}"
        else:
            if isinstance(val, dict):
                obj = val
            else:
                why = "JSON value is not an object"
    elif nonempty and nonempty[0].startswith("{"):
        why = "invalid JSON at the surface"
    return {"cleaned": cleaned, "lines": nonempty, "json": obj,
            "json_reason": why}


def _one_line(t: dict):
    if len(t["lines"]) != 1:
        return None, f"must be exactly one line, got {len(t['lines'])}"
    return t["lines"][0], None


def _rule_c25(payload, t):
    line, why = _one_line(t)
    if line is None:
        return ParsedAnswerD("C25", None, PARSE_MALFORMED, (why,))
    tok = _norm(line).upper()
    if tok not in ("STOP", "CONTINUE"):
        return ParsedAnswerD("C25", None, PARSE_MALFORMED,
                             ("decision must be STOP or CONTINUE",))
    return ParsedAnswerD("C25", tok, PARSE_OK, (), "bare")


def _parse_decision_json(prim, t, fields, dec_values, bare_word):
    """Shared JSON/bare decision+list parsing (C26/C27)."""
    if t["json"] is not None:
        obj = t["json"]
        if set(obj) != set(fields):
            return ParsedAnswerD(
                prim, None, PARSE_MALFORMED,
                (f"JSON must carry exactly {sorted(fields)}",), "json")
        d, lst = obj[fields[0]], obj[fields[1]]
        if d not in dec_values:
            return ParsedAnswerD(prim, None, PARSE_MALFORMED,
                                 (f"decision must be one of "
                                  f"{sorted(dec_values)}",), "json")
        if not isinstance(lst, list) or \
                any(not isinstance(x, str) for x in lst):
            return ParsedAnswerD(prim, None, PARSE_MALFORMED,
                                 (f"{fields[1]} must be a list of "
                                  "names",), "json")
        return ParsedAnswerD(prim, {fields[0]: d,
                                    fields[1]: [x.strip() for x in lst]},
                             PARSE_OK, (), "json")
    if t["json_reason"]:
        return ParsedAnswerD(prim, None, PARSE_MALFORMED,
                             (t["json_reason"],), "")
    line, why = _one_line(t)
    if line is None:
        return ParsedAnswerD(prim, None, PARSE_MALFORMED, (why,))
    tok = _norm(line)
    up = tok.upper()
    if up == dec_values[0]:                      # ACT / PROCEED
        return ParsedAnswerD(prim, {fields[0]: dec_values[0],
                                    fields[1]: []}, PARSE_OK, (), "bare")
    if up.startswith(bare_word):
        rest = tok[len(bare_word):].lstrip(":：,， ").strip()
        names = [s.strip() for s in re.split(r"[,，]", rest) if s.strip()]
        if not names:
            return ParsedAnswerD(prim, None, PARSE_MALFORMED,
                                 (f"{bare_word} must name the "
                                  "required item(s)",))
        return ParsedAnswerD(prim, {fields[0]: dec_values[1],
                                    fields[1]: names}, PARSE_OK, (),
                             "bare")
    return ParsedAnswerD(prim, None, PARSE_MALFORMED,
                         (f"decision must be {dec_values[0]} or "
                          f"{dec_values[1]}(+items)",))


def _rule_c26(payload, t):
    p = _parse_decision_json("C26", t, ("decision", "missing"),
                             ("ACT", "ASK"), "ASK")
    if p.parse_class == PARSE_OK and p.value["decision"] == "ACT" and \
            p.value["missing"]:
        return ParsedAnswerD("C26", None, PARSE_MALFORMED,
                             ("ACT with missing slots",), p.surface)
    return p


def _rule_c27(payload, t):
    p = _parse_decision_json("C27", t, ("decision", "rules"),
                             ("PROCEED", "ESCALATE"), "ESCALATE")
    if p.parse_class == PARSE_OK:
        d, r = p.value["decision"], p.value["rules"]
        if d == "PROCEED" and r:
            return ParsedAnswerD("C27", None, PARSE_MALFORMED,
                                 ("PROCEED with rule ids",), p.surface)
        if d == "ESCALATE" and not r:
            return ParsedAnswerD("C27", None, PARSE_MALFORMED,
                                 ("ESCALATE must name rule id(s)",),
                                 p.surface)
    return p


def _rule_line(prim):
    def _r(payload, t):
        line, why = _one_line(t)
        if line is None:
            return ParsedAnswerD(prim, None, PARSE_MALFORMED, (why,))
        return ParsedAnswerD(prim, _norm(line), PARSE_OK, (), "text")
    return _r


def _rule_c29(payload, t):
    if t["json"] is not None:
        obj = t["json"]
        if set(obj) == {"class", "readings"} and \
                obj["class"] == "AMBIGUOUS" and \
                isinstance(obj["readings"], list):
            return ParsedAnswerD("C29", {"class": "AMBIGUOUS",
                                         "readings": [str(x).strip()
                                                      for x in
                                                      obj["readings"]]},
                                 PARSE_OK, (), "json")
        if set(obj) == {"class", "answer"} and \
                obj["class"] == "ANSWER" and \
                isinstance(obj["answer"], str):
            return ParsedAnswerD("C29", {"class": "ANSWER",
                                         "answer":
                                             obj["answer"].strip()},
                                 PARSE_OK, (), "json")
        return ParsedAnswerD("C29", None, PARSE_MALFORMED,
                             ("must be {class,answer} or "
                              "{class,readings}",), "json")
    if t["json_reason"]:
        return ParsedAnswerD("C29", None, PARSE_MALFORMED,
                             (t["json_reason"],), "")
    line, why = _one_line(t)
    if line is None:
        return ParsedAnswerD("C29", None, PARSE_MALFORMED, (why,))
    tok = _norm(line)
    if tok.upper().startswith("AMBIGUOUS"):
        rest = tok[9:].lstrip(":：,， ").strip()
        ids = [s.strip() for s in re.split(r"[,，]", rest) if s.strip()]
        if not ids:
            return ParsedAnswerD("C29", None, PARSE_MALFORMED,
                                 ("AMBIGUOUS must name the conflicting "
                                  "ids",))
        return ParsedAnswerD("C29", {"class": "AMBIGUOUS", "readings":
                                     ids}, PARSE_OK, (), "bare")
    if " " in tok or "," in tok:
        return ParsedAnswerD("C29", None, PARSE_MALFORMED,
                             ("must be one id or AMBIGUOUS + ids",))
    return ParsedAnswerD("C29", {"class": "ANSWER", "answer": tok},
                         PARSE_OK, (), "bare")


_CANON = re.compile(r"^[a-z][a-z0-9_]*:\S+(?::\S+)?$")


def _rule_c30(payload, t):
    line, why = _one_line(t)
    if line is None:
        return ParsedAnswerD("C30", None, PARSE_MALFORMED, (why,))
    tok = _norm(line)
    if not _CANON.match(tok):
        return ParsedAnswerD("C30", None, PARSE_MALFORMED,
                             ("canonical string must be "
                              "op:entity[:extra]",))
    return ParsedAnswerD("C30", tok, PARSE_OK, (), "bare")


_CITE = re.compile(r"\((EV-[A-Za-z0-9-]+)\)")


def _rule_c31(payload, t):
    cleaned = t["cleaned"].strip()
    if not cleaned:
        return ParsedAnswerD("C31", None, PARSE_MALFORMED,
                             ("no answer text",))
    return ParsedAnswerD("C31", {"text": cleaned,
                                 "citations": _CITE.findall(cleaned)},
                         PARSE_OK, (), "text")


def _rule_c32(payload, t):
    line, why = _one_line(t)
    if line is None:
        return ParsedAnswerD("C32", None, PARSE_MALFORMED, (why,))
    tok = _norm(line)
    if tok.upper() == "ABSTAIN":
        return ParsedAnswerD("C32", {"class": "ABSTAIN", "answer": None},
                             PARSE_OK, (), "bare")
    return ParsedAnswerD("C32", {"class": "ANSWER", "answer": tok},
                         PARSE_OK, (), "bare")


_RULES = {
    "C25": _rule_c25, "C26": _rule_c26, "C27": _rule_c27,
    "C28": _rule_line("C28"), "C29": _rule_c29, "C30": _rule_c30,
    "C31": _rule_c31, "C32": _rule_c32,
}


def parse_response(primitive: str, payload: dict,
                   response) -> ParsedAnswerD:
    if response is None:
        return ParsedAnswerD(primitive, None, PARSE_EMPTY,
                             ("response is None",))
    raw = response if isinstance(response, str) else str(response)
    if raw.strip() == "":
        return ParsedAnswerD(primitive, None, PARSE_EMPTY,
                             ("empty model output",))
    rule = _RULES.get(primitive)
    if rule is None:
        return ParsedAnswerD(
            primitive, None, PARSE_SOFTWARE,
            (f"primitive {primitive} outside Batch D production scope",))
    return rule(payload or {}, _tokenize(raw))
