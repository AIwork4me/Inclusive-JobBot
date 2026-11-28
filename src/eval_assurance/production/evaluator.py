"""EA04/EA05 — Production Evaluator.

Typed comparison of a production-parsed answer against the STORED
expectation record (the dataset answer artifact a physical runner
consumes), including declared valid alternatives ("valid alternative
solutions" control family). This is the production counterpart of the
reference oracle: it CONSUMES stored expectations instead of deriving
truth from public payloads, and its comparator is authored independently
of ``oracle._compare_typed`` (rule-table dispatch over stored shapes
below; no oracle imports).

Class discipline (pinned contract + order section 2):
- ``EMPTY_OUTPUT`` is its own class — never INCORRECT, never a parse
  error, never silently conflated with missing evidence;
- a MALFORMED surface is a MODEL-side structural failure
  (``INVALID_OUTPUT``), distinct from semantic wrongness (INCORRECT)
  and distinct from software faults (``EVALUATOR_SOFTWARE_ERROR``);
- exact distinction between empty model output and missing evidence is
  the session's job (dualpath.py); this module never sees missing
  artifacts.
"""
from __future__ import annotations

from dataclasses import dataclass

from .parser import (PARSE_EMPTY, PARSE_MALFORMED, PARSE_OK,
                     PARSE_SOFTWARE, ParsedAnswer)


class ProductionVerdict:
    CORRECT = "CORRECT"
    INCORRECT = "INCORRECT"
    EMPTY_OUTPUT = "EMPTY_OUTPUT"
    INVALID_OUTPUT = "INVALID_OUTPUT"        # model-side structural
    SOFTWARE_ERROR = "EVALUATOR_SOFTWARE_ERROR"

    ALL = (CORRECT, INCORRECT, EMPTY_OUTPUT, INVALID_OUTPUT,
           SOFTWARE_ERROR)


@dataclass(frozen=True)
class EvaluationRecord:
    verdict: str
    matched_alternative: bool = False
    reasons: tuple = ()


class ProductionEvaluator:
    """Compares :class:`ParsedAnswer` against the stored expectation."""

    identity = "eval_assurance.production.evaluator@1"

    def evaluate(self, case: dict, expectation: dict,
                 parsed: ParsedAnswer) -> EvaluationRecord:
        prim = case.get("primitive", "")
        if parsed.parse_class == PARSE_EMPTY:
            return EvaluationRecord(ProductionVerdict.EMPTY_OUTPUT)
        if parsed.parse_class == PARSE_SOFTWARE:
            return EvaluationRecord(ProductionVerdict.SOFTWARE_ERROR,
                                    reasons=("parser software fault",))
        if parsed.parse_class == PARSE_MALFORMED:
            return EvaluationRecord(ProductionVerdict.INVALID_OUTPUT,
                                    reasons=parsed.violations)
        exp = (expectation or {}).get("expected") or {}
        alts = [str(a).lower() for a in
                (expectation or {}).get("alternatives") or [] if a]
        rule = _EVAL_RULES.get(prim)
        if rule is None:
            return EvaluationRecord(ProductionVerdict.SOFTWARE_ERROR,
                                    reasons=(f"primitive {prim} outside "
                                             "Batch A evaluator scope",))
        return rule(parsed.value, exp, alts)


def _eval_label(value, exp: dict, alts: list) -> EvaluationRecord:
    truth = exp.get("label")
    if value == str(truth).lower():
        return EvaluationRecord(ProductionVerdict.CORRECT)
    if value and value in alts:
        return EvaluationRecord(ProductionVerdict.CORRECT,
                                matched_alternative=True)
    return EvaluationRecord(
        ProductionVerdict.INCORRECT,
        reasons=(f"label {value!r} != stored truth {truth!r}",))


def _eval_c02(value, exp: dict, alts: list) -> EvaluationRecord:
    if not isinstance(value, dict):
        return EvaluationRecord(ProductionVerdict.INCORRECT,
                                reasons=("parsed goal is not an object",))
    why = []
    for fld in ("action", "object", "deadline", "completion_criterion"):
        if value.get(fld) != exp.get(fld):
            why.append(f"{fld}: {value.get(fld)!r} != {exp.get(fld)!r}")
    vf = value.get("unknown_flags") or {}
    ef = exp.get("unknown_flags") or {}
    if set(vf) != set(ef):
        why.append(f"unknown_flags keys {sorted(vf)} != {sorted(ef)}")
    else:
        for k in sorted(ef):
            if vf.get(k) != ef.get(k):
                why.append(f"unknown_flags.{k}: {vf.get(k)!r} != "
                           f"{ef.get(k)!r}")
    return EvaluationRecord(
        ProductionVerdict.CORRECT if not why else ProductionVerdict.INCORRECT,
        reasons=tuple(why))


def _eval_c03(value, exp: dict, alts: list) -> EvaluationRecord:
    if isinstance(exp.get("field"), str) and "value" in exp:  # formfill
        # typed semantics are the exact (field, value) pair — strict
        # comparison, no silent normalization (reconciled with the
        # reference oracle comparator 2026-11-28)
        ok = (isinstance(value, dict) and len(value) == 1
              and next(iter(value)) == exp["field"]
              and next(iter(value.values())) == exp["value"])
        return EvaluationRecord(
            ProductionVerdict.CORRECT if ok else ProductionVerdict.INCORRECT,
            reasons=() if ok else (f"formfill pair {value!r} != "
                                   f"({exp['field']!r}, "
                                   f"{exp['value']!r})",))
    if "line" in exp:                                         # oneedit
        ok = value == exp["line"] or (
            isinstance(value, str)
            and value.strip() == str(exp["line"]).strip())
        return EvaluationRecord(
            ProductionVerdict.CORRECT if ok else ProductionVerdict.INCORRECT,
            reasons=() if ok else (f"edited line {value!r} != "
                                   f"{exp['line']!r}",))
    truth = exp.get("lines") or []                            # formatting
    ok = list(value or []) == list(truth)
    return EvaluationRecord(
        ProductionVerdict.CORRECT if ok else ProductionVerdict.INCORRECT,
        reasons=() if ok else (f"line sequence {value!r} != {truth!r}",))


def _eval_c04(value, exp: dict, alts: list) -> EvaluationRecord:
    truth = [str(x).lower() for x in exp.get("ids") or []]
    got = [str(x).lower() for x in value or []]
    if exp.get("order"):                                      # sort declared
        ok = got == truth
        why = (f"sorted sequence {got} != {truth}",)
    else:                       # no declared sort: set equality; ties are
        ok = sorted(got) == sorted(truth)   # ordering freedom only
        why = (f"id set {sorted(got)} != {sorted(truth)}",)
    return EvaluationRecord(
        ProductionVerdict.CORRECT if ok else ProductionVerdict.INCORRECT,
        reasons=() if ok else why)


def _eval_c05(value, exp: dict, alts: list) -> EvaluationRecord:
    ok = value is exp.get("decision")
    return EvaluationRecord(
        ProductionVerdict.CORRECT if ok else ProductionVerdict.INCORRECT,
        reasons=() if ok else (f"decision {value!r} != "
                               f"{exp.get('decision')!r}",))


def _eval_c06(value, exp: dict, alts: list) -> EvaluationRecord:
    truth = exp.get("choice")
    if str(value).lower() == str(truth).lower():
        return EvaluationRecord(ProductionVerdict.CORRECT)
    winners = [str(w).lower() for w in exp.get("winners") or []]
    if winners and str(value).lower() in winners:
        return EvaluationRecord(ProductionVerdict.CORRECT,
                                matched_alternative=True,
                                reasons=("declared tie winner",))
    if value and value in alts:
        return EvaluationRecord(ProductionVerdict.CORRECT,
                                matched_alternative=True)
    return EvaluationRecord(
        ProductionVerdict.INCORRECT,
        reasons=(f"choice {value!r} != stored truth {truth!r}",))


_EVAL_RULES = {
    "C01": _eval_label,
    "C02": _eval_c02,
    "C03": _eval_c03,
    "C04": _eval_c04,
    "C05": _eval_c05,
    "C06": _eval_c06,
}


# C07/C08 store action/tool_id under their own keys: dispatch through the
# label rule with the stored expectation rekeyed
def _eval_c07(value, exp: dict, alts: list) -> EvaluationRecord:
    return _eval_label(value, {"label": exp.get("action")}, alts)


def _eval_c08(value, exp: dict, alts: list) -> EvaluationRecord:
    return _eval_label(value, {"label": exp.get("tool_id")}, alts)


_EVAL_RULES["C07"] = _eval_c07
_EVAL_RULES["C08"] = _eval_c08
