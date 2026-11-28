"""EA07/EA09/EA14 — named production-logic fault injections.

One library of deliberately reintroduced historical/critical defects,
shared by the EA07 semantic-mutation campaign, the EA09 canary controls
and the early-catastrophe/EA14 pilots. Every fault wraps the CLEAN
production leg (parser or evaluator) and reintroduces exactly one
well-known defect mode; the surrounding assurance system (dual-path
comparison, class discipline, canaries) must DETECT the change — a
fault that changes no observable outcome is an escape and is reported
honestly.

Fault catalogue (order section 6 "common-mode fault injections" and the
historical-immunity list):

P-series (production parser):
  P02 duplicate_keys_accepted   — duplicate JSON keys silently merged
  P03 drop_extra_fields         — unauthorized argument silently dropped
  P04 default_missing_fields    — missing schema fields fabricated
  P05 empty_as_incorrect        — EMPTY_OUTPUT collapsed to model failure
  P06 empty_as_software         — empty output conflated with missing
                                  evidence (software error)
  P08 hedge_unparseable         — C05 hedge becomes a software error
  P09 markers_tolerated         — C03 bullet/enumeration markers kept
  P10 multiline_label_first     — free text answered with its first line
  P11 identity_case_change      — token normalization changes identity
  P12 fences_not_stripped       — markdown fences no longer tolerated
  P13 predicate_dropped         — unknown_flags predicate disappears
  P14 empty_list_not_explicit   — C04 empty result surfaces as a guess

E-series (production evaluator):
  E01 any_catalog_member        — catalog membership accepted as correct
  E02 c04_subset_match          — subset of the id set accepted
  E03 flags_ignored             — unknown_flags comparison skipped
  E04 structural_conflation     — INVALID_OUTPUT scored INCORRECT
  E05 alternatives_ignored      — declared tie winners rejected
  E06 inverted_decision         — C05 stored truth inverted (coupled
                                  corruption on the production side)
  E07 c03_order_insensitive     — formatting line sequence treated as a
                                  set
  E08 c02_action_only           — only the action field compared
"""
from __future__ import annotations

import json
import re

from .production.evaluator import (EvaluationRecord, ProductionEvaluator,
                                   ProductionVerdict)
from .production.parser import (PARSE_EMPTY, PARSE_MALFORMED, PARSE_OK,
                                ParsedAnswer, parse_response)

PARSER_FAULTS = (
    "P02_duplicate_keys_accepted",
    "P03_drop_extra_fields",
    "P04_default_missing_fields",
    "P05_empty_as_incorrect",
    "P06_empty_as_software",
    "P08_hedge_unparseable",
    "P09_markers_tolerated",
    "P10_multiline_label_first",
    "P11_identity_case_change",
    "P12_fences_not_stripped",
    "P13_predicate_dropped",
    "P14_empty_list_not_explicit",
)

EVALUATOR_FAULTS = (
    "E01_any_catalog_member",
    "E02_c04_subset_match",
    "E03_flags_ignored",
    "E04_structural_conflation",
    "E05_alternatives_ignored",
    "E06_inverted_decision",
    "E07_c03_order_insensitive",
    "E08_c02_action_only",
)


def _ok(prim, value, surface=""):
    return ParsedAnswer(prim, value, PARSE_OK, (), surface)


def _malformed(prim, value, reasons):
    return ParsedAnswer(prim, value, PARSE_MALFORMED, tuple(reasons))


def _reasons(parsed: ParsedAnswer) -> str:
    return " ".join(parsed.violations)


def make_parser_fault(name: str):
    """Return a fault-injected production parser callable with the same
    signature as :func:`parse_response`."""
    if name == "P02_duplicate_keys_accepted":
        def fault(prim, payload, response):
            parsed = parse_response(prim, payload, response)
            if parsed.parse_class == PARSE_MALFORMED and \
                    "duplicate JSON key" in _reasons(parsed):
                raw = str(response).strip().strip("```").strip()
                try:
                    obj = json.loads(raw)      # dup keys silently merged
                except ValueError:
                    return parsed
                if prim == "C02":
                    return _ok(prim, obj, "json")
                keys = {"C01": ("intent", "label"), "C06": ("choice",),
                        "C07": ("action",), "C08": ("tool_id",)}
                for k in keys.get(prim, ()):
                    if isinstance(obj, dict) and k in obj:
                        return _ok(prim, str(obj[k]).strip().lower(),
                                   "json")
                return parsed
            return parsed
        return fault

    if name == "P03_drop_extra_fields":
        def fault(prim, payload, response):
            parsed = parse_response(prim, payload, response)
            if prim == "C02" and parsed.parse_class == PARSE_MALFORMED \
                    and "unexpected fields" in _reasons(parsed) \
                    and isinstance(parsed.value, dict):
                schema = ("action", "object", "deadline",
                          "completion_criterion", "unknown_flags")
                return _ok(prim, {k: v for k, v in parsed.value.items()
                                  if k in schema}, "json")
            return parsed
        return fault

    if name == "P04_default_missing_fields":
        def fault(prim, payload, response):
            parsed = parse_response(prim, payload, response)
            if prim == "C02" and parsed.parse_class == PARSE_MALFORMED \
                    and "missing schema fields" in _reasons(parsed) \
                    and isinstance(parsed.value, dict):
                v = dict(parsed.value)
                for f in ("action", "object", "deadline",
                          "completion_criterion"):
                    v.setdefault(f, None)      # fabricated defaults
                v.setdefault("unknown_flags", {})
                return _ok(prim, v, "json")
            return parsed
        return fault

    if name == "P05_empty_as_incorrect":
        def fault(prim, payload, response):
            parsed = parse_response(prim, payload, response)
            if parsed.parse_class == PARSE_EMPTY:
                return _malformed(prim, None, ("empty output treated as "
                                               "model failure",))
            return parsed
        return fault

    if name == "P06_empty_as_software":
        def fault(prim, payload, response):
            parsed = parse_response(prim, payload, response)
            if parsed.parse_class == PARSE_EMPTY:
                raise RuntimeError(
                    "empty output conflated with missing evidence")
            return parsed
        return fault

    if name == "P08_hedge_unparseable":
        def fault(prim, payload, response):
            parsed = parse_response(prim, payload, response)
            if prim == "C05" and parsed.parse_class == PARSE_MALFORMED:
                raise RuntimeError("hedged boolean treated as software "
                                   "fault instead of model failure")
            return parsed
        return fault

    if name == "P09_markers_tolerated":
        _marker = re.compile(r"^\s*(?:[-*+•]|\d+[.)])\s+")

        def fault(prim, payload, response):
            parsed = parse_response(prim, payload, response)
            if prim == "C03" and parsed.parse_class == PARSE_MALFORMED \
                    and "enumeration/bullet marker" in _reasons(parsed):
                raw = str(response).strip().strip("```").strip()
                lines = [_marker.sub("", ln).strip()
                         for ln in raw.splitlines() if ln.strip()]
                return _ok(prim, lines, "text")
            return parsed
        return fault

    if name == "P10_multiline_label_first":
        def fault(prim, payload, response):
            parsed = parse_response(prim, payload, response)
            if parsed.parse_class == PARSE_MALFORMED and prim in \
                    ("C01", "C06", "C07", "C08") and (
                        "multiple labels" in _reasons(parsed)
                        or "free text" in _reasons(parsed)
                        or "comma-separated label list" in
                        _reasons(parsed)):
                raw = str(response).strip().strip("```").strip()
                first = raw.splitlines()[0].split(",")[0].strip()
                if first and " " not in first:
                    return _ok(prim, first.lower(), "text")
            return parsed
        return fault

    if name == "P11_identity_case_change":
        def fault(prim, payload, response):
            parsed = parse_response(prim, payload, response)
            if parsed.parse_class == PARSE_OK and \
                    isinstance(parsed.value, str):
                return ParsedAnswer(prim, parsed.value.upper(), PARSE_OK,
                                    (), parsed.surface)  # identity change
            return parsed
        return fault

    if name == "P12_fences_not_stripped":
        def fault(prim, payload, response):
            raw = response if isinstance(response, str) else \
                ("" if response is None else str(response))
            if "```" in raw:
                return _malformed(prim, None,
                                  ("markdown fence no longer tolerated",))
            return parse_response(prim, payload, response)
        return fault

    if name == "P13_predicate_dropped":
        def fault(prim, payload, response):
            parsed = parse_response(prim, payload, response)
            if prim == "C02" and parsed.parse_class == PARSE_OK and \
                    isinstance(parsed.value, dict):
                flags = dict(parsed.value.get("unknown_flags") or {})
                if flags:
                    flags.pop(next(iter(flags)))   # predicate disappears
                    v = dict(parsed.value)
                    v["unknown_flags"] = flags
                    return ParsedAnswer(prim, v, PARSE_OK, (),
                                        parsed.surface)
            return parsed
        return fault

    if name == "P14_empty_list_not_explicit":
        def fault(prim, payload, response):
            parsed = parse_response(prim, payload, response)
            if prim == "C04" and parsed.parse_class == PARSE_OK and \
                    parsed.value == []:
                items = (payload or {}).get("items") or []
                guess = str(items[0].get("id") or
                            items[0].get("name") or "x").lower() \
                    if items else "x"
                return _ok(prim, [guess], "list")   # fallback guess
            return parsed
        return fault

    raise KeyError(f"unknown parser fault {name!r}")


class _FaultEvaluator(ProductionEvaluator):
    def __init__(self, fault: str):
        super().__init__()
        self.fault = fault

    def evaluate(self, case, expectation, parsed):
        if self.fault == "E04_structural_conflation":
            rec = super().evaluate(case, expectation, parsed)
            if rec.verdict == ProductionVerdict.INVALID_OUTPUT:
                return EvaluationRecord(ProductionVerdict.INCORRECT,
                                        rec.matched_alternative,
                                        rec.reasons)
            return rec
        if self.fault == "E03_flags_ignored":
            if case.get("primitive") == "C02" and \
                    parsed.parse_class == PARSE_OK:
                exp = dict((expectation or {}).get("expected") or {})
                exp["unknown_flags"] = \
                    dict(parsed.value.get("unknown_flags") or {})
                return super().evaluate(case, {"expected": exp,
                                               "alternatives": []}, parsed)
            return super().evaluate(case, expectation, parsed)
        if self.fault == "E08_c02_action_only":
            if case.get("primitive") == "C02" and \
                    parsed.parse_class == PARSE_OK:
                exp = dict((expectation or {}).get("expected") or {})
                got = parsed.value or {}
                for f in ("object", "deadline", "completion_criterion"):
                    exp[f] = got.get(f)
                exp["unknown_flags"] = dict(got.get("unknown_flags") or {})
                return super().evaluate(case, {"expected": exp,
                                               "alternatives": []}, parsed)
            return super().evaluate(case, expectation, parsed)
        if self.fault == "E06_inverted_decision":
            if case.get("primitive") == "C05":
                exp = dict((expectation or {}).get("expected") or {})
                exp["decision"] = not exp.get("decision")
                return super().evaluate(case, {"expected": exp,
                                               "alternatives": []}, parsed)
            return super().evaluate(case, expectation, parsed)
        if self.fault == "E05_alternatives_ignored":
            return super().evaluate(case, {"expected":
                                           (expectation or {}).get(
                                               "expected") or {},
                                           "alternatives": []}, parsed)
        if self.fault == "E02_c04_subset_match":
            if case.get("primitive") == "C04" and \
                    parsed.parse_class == PARSE_OK:
                truth = [str(x).lower() for x in
                         ((expectation or {}).get("expected") or {})
                         .get("ids") or []]
                got = [str(x).lower() for x in parsed.value or []]
                if set(got) <= set(truth):
                    return EvaluationRecord(ProductionVerdict.CORRECT)
            return super().evaluate(case, expectation, parsed)
        if self.fault == "E07_c03_order_insensitive":
            if case.get("primitive") == "C03" and \
                    parsed.parse_class == PARSE_OK and \
                    isinstance(parsed.value, list):
                exp = dict((expectation or {}).get("expected") or {})
                if "lines" in exp:
                    exp["lines"] = sorted(exp["lines"],
                                          key=lambda s: str(s).lower())
                    v = ParsedAnswer("C03", sorted(
                        parsed.value, key=lambda s: str(s).lower()),
                        PARSE_OK, (), parsed.surface)
                    return super().evaluate(case, {"expected": exp,
                                                   "alternatives": []}, v)
            return super().evaluate(case, expectation, parsed)
        if self.fault == "E01_any_catalog_member":
            prim = case.get("primitive", "")
            if prim in ("C01", "C07") and parsed.parse_class == PARSE_OK:
                cat = (case.get("public_payload") or {}).get(
                    "intent_catalog" if prim == "C01" else
                    "action_catalog") or {}
                if parsed.value in {str(k).lower() for k in cat}:
                    return EvaluationRecord(ProductionVerdict.CORRECT)
            return super().evaluate(case, expectation, parsed)
        raise KeyError(f"unknown evaluator fault {self.fault!r}")


def make_evaluator_fault(name: str) -> ProductionEvaluator:
    return _FaultEvaluator(name)


class RaisingParser:
    """Deterministic software-fault injection: every parse raises."""

    identity = "fault.raising-parser"

    def parse_response(self, prim, payload, response):   # pragma: no cover
        raise RuntimeError("injected parser software exception")
