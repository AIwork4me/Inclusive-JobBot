"""EA05-B — Production Evaluator for N03 Batch B (C09-C16).

Typed comparison of a production-parsed answer against the STORED
expectation record (the dataset answer artifact a physical runner
consumes), including declared valid alternatives. Production
counterpart of ``reference/oracle_b.py``: it CONSUMES stored
expectations instead of deriving truth from public payloads, and its
comparators are authored independently of ``oracle_b._compare``
(rule-table dispatch over stored shapes; no oracle_b imports).

Class discipline (pinned contract): EMPTY_OUTPUT is its own class —
never INCORRECT, never a parse error; MALFORMED surfaces are
INVALID_OUTPUT (model-side structural), distinct from semantic
wrongness (INCORRECT) and from software faults
(EVALUATOR_SOFTWARE_ERROR).

Comparison semantics per primitive (declared alternatives honored):
- C09: exact record equality after canonicalization (key order
  irrelevant; types strict — 1 vs true vs "1" all differ).
- C10: document equality AND array_size equality (array order follows
  the details order; no other freedom per the stored alternative).
- C11: statement-sequence equality (tokens are case-sensitive; the
  declared grammar is uppercase) and op_count equality.
- C12: slot-record equality with declared normalizations (null only
  where unstated); a slot omitted without null is a mismatch.
- C13: exact candidate id equality (case-insensitive ids).
- C14: exact numeric equality (1200.50 == 1200.5 trailing-zero forms
  per the stored alternative; sign and magnitude exact, no rounding).
- C15: value equality within the declared rounding tolerance (exact
  for integers, 2dp for division per the stored alternative) and
  exact unit-code equality.
- C16: short-answer equality after trim/case/punctuation
  normalization; numeric answers compare numerically.
"""
from __future__ import annotations

from dataclasses import dataclass

from .parser_b import (PARSE_EMPTY, PARSE_MALFORMED, PARSE_OK,
                       PARSE_SOFTWARE, ParsedAnswerB)


class ProductionVerdictB:
    CORRECT = "CORRECT"
    INCORRECT = "INCORRECT"
    EMPTY_OUTPUT = "EMPTY_OUTPUT"
    INVALID_OUTPUT = "INVALID_OUTPUT"        # model-side structural
    SOFTWARE_ERROR = "EVALUATOR_SOFTWARE_ERROR"

    ALL = (CORRECT, INCORRECT, EMPTY_OUTPUT, INVALID_OUTPUT,
           SOFTWARE_ERROR)


@dataclass(frozen=True)
class EvaluationRecordB:
    verdict: str
    matched_alternative: bool = False
    reasons: tuple = ()


class ProductionEvaluatorB:
    """Compares :class:`ParsedAnswerB` against the stored expectation."""

    identity = "eval_assurance.production.evaluator_b@1"

    def evaluate(self, case: dict, expectation: dict,
                 parsed: ParsedAnswerB) -> EvaluationRecordB:
        prim = case.get("primitive", "")
        if parsed.parse_class == PARSE_EMPTY:
            return EvaluationRecordB(ProductionVerdictB.EMPTY_OUTPUT)
        if parsed.parse_class == PARSE_SOFTWARE:
            return EvaluationRecordB(ProductionVerdictB.SOFTWARE_ERROR,
                                     reasons=("parser software fault",))
        if parsed.parse_class == PARSE_MALFORMED:
            return EvaluationRecordB(ProductionVerdictB.INVALID_OUTPUT,
                                     reasons=parsed.violations)
        exp = (expectation or {}).get("expected") or {}
        alts = [str(a).lower() for a in
                (expectation or {}).get("alternatives") or [] if a]
        rule = _EVAL_RULES.get(prim)
        if rule is None:
            return EvaluationRecordB(ProductionVerdictB.SOFTWARE_ERROR,
                                     reasons=(f"primitive {prim} outside "
                                              "Batch B evaluator scope",))
        return rule(parsed.value, exp, alts)


def _records_equal(a, b) -> tuple:
    if not isinstance(a, dict) or not isinstance(b, dict):
        return False, ("value is not an object",)
    if set(a) != set(b):
        return False, (f"fields {sorted(a)} != {sorted(b)}",)
    for k in sorted(b):
        if a[k] != b[k] or type(a[k]) is not type(b[k]):
            return False, (f"{k}: {a[k]!r} != {b[k]!r}",)
    return True, ()


def _eval_c09(value, exp: dict, alts: list) -> EvaluationRecordB:
    ok, why = _records_equal(value, exp.get("record") or {})
    return EvaluationRecordB(
        ProductionVerdictB.CORRECT if ok else ProductionVerdictB.INCORRECT,
        reasons=() if ok else why)


def _eval_c10(value, exp: dict, alts: list) -> EvaluationRecordB:
    ok, why = _records_equal(value, exp.get("document") or {})
    if not ok:
        return EvaluationRecordB(ProductionVerdictB.INCORRECT, reasons=why)
    want_size = exp.get("array_size")

    def _arrays(v):
        out = []
        if isinstance(v, dict):
            for x in v.values():
                if isinstance(x, list):
                    out.append(len(x))
                out.extend(_arrays(x))
        elif isinstance(v, list):
            for x in v:
                out.extend(_arrays(x))
        return out

    if want_size is not None and any(c != want_size for c in _arrays(value)):
        return EvaluationRecordB(
            ProductionVerdictB.INCORRECT,
            reasons=(f"array cardinality != declared {want_size}",))
    return EvaluationRecordB(ProductionVerdictB.CORRECT)


def _eval_c11(value, exp: dict, alts: list) -> EvaluationRecordB:
    want = [ln for ln in str(exp.get("program") or "").splitlines()
            if ln.strip()]
    got = [str(s) for s in (value or [])]
    if got != want:
        return EvaluationRecordB(
            ProductionVerdictB.INCORRECT,
            reasons=(f"program {got!r} != {want!r}",))
    if exp.get("op_count") is not None and \
            exp["op_count"] != len(got):
        return EvaluationRecordB(
            ProductionVerdictB.INCORRECT,
            reasons=(f"op_count {len(got)} != stored "
                     f"{exp['op_count']}",))
    return EvaluationRecordB(ProductionVerdictB.CORRECT)


def _eval_c12(value, exp: dict, alts: list) -> EvaluationRecordB:
    ok, why = _records_equal(value, exp.get("slots") or {})
    return EvaluationRecordB(
        ProductionVerdictB.CORRECT if ok else ProductionVerdictB.INCORRECT,
        reasons=() if ok else why)


def _eval_c13(value, exp: dict, alts: list) -> EvaluationRecordB:
    truth = exp.get("resolution")
    if str(value).lower() == str(truth).lower():
        return EvaluationRecordB(ProductionVerdictB.CORRECT)
    return EvaluationRecordB(
        ProductionVerdictB.INCORRECT,
        reasons=(f"resolution {value!r} != stored truth {truth!r}",))


def _eval_c14(value, exp: dict, alts: list) -> EvaluationRecordB:
    truth = exp.get("values") or {}
    if not isinstance(value, dict):
        return EvaluationRecordB(ProductionVerdictB.INCORRECT,
                                 reasons=("values not an object",))
    why = []
    if set(value) != set(truth):
        why.append(f"value fields {sorted(value)} != {sorted(truth)}")
    for k in sorted(set(value) & set(truth)):
        v, t = value[k], truth[k]
        if isinstance(v, bool) or isinstance(t, bool) or \
                not isinstance(v, (int, float)) or \
                not isinstance(t, (int, float)):
            why.append(f"{k}: non-numeric value")
        elif float(v) != float(t):
            why.append(f"{k}: {v!r} != {t!r} (no rounding tolerance)")
    return EvaluationRecordB(
        ProductionVerdictB.CORRECT if not why else
        ProductionVerdictB.INCORRECT, reasons=tuple(why))


def _eval_c15(value, exp: dict, alts: list) -> EvaluationRecordB:
    con = exp.get("conversion") or {}
    if not isinstance(value, dict):
        return EvaluationRecordB(ProductionVerdictB.INCORRECT,
                                 reasons=("conversion not an object",))
    if value.get("unit") != con.get("unit"):
        return EvaluationRecordB(
            ProductionVerdictB.INCORRECT,
            reasons=(f"unit {value.get('unit')!r} != {con.get('unit')!r}",))
    v, t = value.get("value"), con.get("value")
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return EvaluationRecordB(ProductionVerdictB.INCORRECT,
                                 reasons=("value is not a number",))
    if abs(float(v) - float(t)) > 0.005 + 1e-9:
        return EvaluationRecordB(
            ProductionVerdictB.INCORRECT,
            reasons=(f"value {v!r} != {t!r} (declared tolerance "
                     f"exceeded)",))
    return EvaluationRecordB(ProductionVerdictB.CORRECT)


def _norm_answer(x) -> str:
    return str(x).strip().strip('"').strip("'").rstrip("。.").strip()


def _eval_c16(value, exp: dict, alts: list) -> EvaluationRecordB:
    truth = exp.get("answer")
    nv, nt = _norm_answer(value), _norm_answer(truth)
    if nv.lower() == nt.lower():
        return EvaluationRecordB(ProductionVerdictB.CORRECT)
    try:
        if float(nv) == float(nt):
            return EvaluationRecordB(ProductionVerdictB.CORRECT)
    except (ValueError, TypeError):
        pass
    return EvaluationRecordB(
        ProductionVerdictB.INCORRECT,
        reasons=(f"answer {value!r} != stored truth {truth!r}",))


_EVAL_RULES = {
    "C09": _eval_c09, "C10": _eval_c10, "C11": _eval_c11,
    "C12": _eval_c12, "C13": _eval_c13, "C14": _eval_c14,
    "C15": _eval_c15, "C16": _eval_c16,
}
