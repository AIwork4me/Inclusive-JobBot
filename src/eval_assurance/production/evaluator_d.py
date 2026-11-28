"""EA05-D — Production Evaluator for N03 Batch D (C25-C32).

Typed comparison against the STORED expectation record (production
consumes stored answers; comparators authored independently of
``oracle_d._compare``). Class discipline: EMPTY_OUTPUT its own class,
INVALID_OUTPUT model-side structural, INCORRECT semantic wrongness,
EVALUATOR_SOFTWARE_ERROR software.

Per-primitive semantics:
- C25: decision token equality.
- C26: decision + missing-set equality.
- C27: decision + triggered-rule-set equality.
- C28: answer string equality (trim/case-normalized).
- C29: ANSWER id equality, or AMBIGUOUS + the conflicting id set
  (order-free).
- C30: canonical string equality (exact tokens; the canonical
  vocabulary is English — zh surface forms are deviations).
- C31: every required citation present, no phantom citations
  (supersets of the required minimum within existing ids accepted per
  the declared alternative).
- C32: ABSTAIN iff the stored class is ABSTAIN; otherwise answer
  equality (no guessing past the marker).
"""
from __future__ import annotations

from dataclasses import dataclass

from .parser_d import (PARSE_EMPTY, PARSE_MALFORMED, PARSE_OK,
                       PARSE_SOFTWARE, ParsedAnswerD)


class ProductionVerdictD:
    CORRECT = "CORRECT"
    INCORRECT = "INCORRECT"
    EMPTY_OUTPUT = "EMPTY_OUTPUT"
    INVALID_OUTPUT = "INVALID_OUTPUT"
    SOFTWARE_ERROR = "EVALUATOR_SOFTWARE_ERROR"


@dataclass(frozen=True)
class EvaluationRecordD:
    verdict: str
    matched_alternative: bool = False
    reasons: tuple = ()


def _eval_c25(value, exp, alts):
    ok = value == exp.get("decision")
    return EvaluationRecordD(
        ProductionVerdictD.CORRECT if ok else ProductionVerdictD.INCORRECT,
        reasons=() if ok else (f"decision {value!r} != "
                               f"{exp.get('decision')!r}",))


def _eval_set_decision(value, exp, alts, key):
    want_d = exp.get("decision")
    want_set = sorted(exp.get(key) or [])
    got_d = (value or {}).get("decision")
    got_set = sorted((value or {}).get(key) or [])
    why = []
    if got_d != want_d:
        why.append(f"decision {got_d!r} != {want_d!r}")
    if got_set != want_set:
        why.append(f"{key} {got_set} != {want_set}")
    ok = not why
    return EvaluationRecordD(
        ProductionVerdictD.CORRECT if ok else ProductionVerdictD.INCORRECT,
        reasons=tuple(why))


class ProductionEvaluatorD:
    identity = "eval_assurance.production.evaluator_d@1"

    def evaluate(self, case, expectation, parsed: ParsedAnswerD
                 ) -> EvaluationRecordD:
        prim = case.get("primitive", "")
        if parsed.parse_class == PARSE_EMPTY:
            return EvaluationRecordD(ProductionVerdictD.EMPTY_OUTPUT)
        if parsed.parse_class == PARSE_SOFTWARE:
            return EvaluationRecordD(ProductionVerdictD.SOFTWARE_ERROR,
                                     reasons=("parser software fault",))
        if parsed.parse_class == PARSE_MALFORMED:
            return EvaluationRecordD(ProductionVerdictD.INVALID_OUTPUT,
                                     reasons=parsed.violations)
        exp = (expectation or {}).get("expected") or {}
        if prim == "C25":
            return _eval_c25(parsed.value, exp, [])
        if prim == "C26":
            return _eval_set_decision(parsed.value, exp, [], "missing")
        if prim == "C27":
            return _eval_set_decision(parsed.value, exp, [], "rules")
        if prim == "C28":
            ok = str(parsed.value).strip() == str(exp.get("answer",
                                                          "")).strip()
            return EvaluationRecordD(
                ProductionVerdictD.CORRECT if ok else
                ProductionVerdictD.INCORRECT,
                reasons=() if ok else (f"answer {parsed.value!r} != "
                                       f"{exp.get('answer')!r}",))
        if prim == "C29":
            if exp.get("class") == "AMBIGUOUS":
                if (parsed.value or {}).get("class") != "AMBIGUOUS":
                    return EvaluationRecordD(
                        ProductionVerdictD.INCORRECT,
                        reasons=("genuinely ambiguous request silently "
                                 "disambiguated",))
                want = sorted(exp.get("readings") or [])
                got = sorted((parsed.value or {}).get("readings") or [])
                ok = got == want
                return EvaluationRecordD(
                    ProductionVerdictD.CORRECT if ok else
                    ProductionVerdictD.INCORRECT,
                    reasons=() if ok else (f"conflicting ids {got} != "
                                           f"{want}",))
            if (parsed.value or {}).get("class") == "AMBIGUOUS":
                return EvaluationRecordD(
                    ProductionVerdictD.INCORRECT,
                    reasons=("over-flagging: unique resolution exists",))
            ok = (parsed.value or {}).get("answer") == exp.get("answer")
            return EvaluationRecordD(
                ProductionVerdictD.CORRECT if ok else
                ProductionVerdictD.INCORRECT,
                reasons=() if ok else (f"answer "
                                       f"{(parsed.value or {}).get('answer')!r}"
                                       f" != {exp.get('answer')!r}",))
        if prim == "C30":
            ok = parsed.value == exp.get("canonical")
            return EvaluationRecordD(
                ProductionVerdictD.CORRECT if ok else
                ProductionVerdictD.INCORRECT,
                reasons=() if ok else (f"canonical {parsed.value!r} != "
                                       f"{exp.get('canonical')!r}",))
        if prim == "C31":
            cited = set((parsed.value or {}).get("citations") or [])
            required = set(exp.get("required_citations") or [])
            ids = {str(e.get("id")) for e in
                   (case.get("public_payload") or {}).get("evidence")
                   or []}
            why = []
            if required - cited:
                why.append(f"claims left uncited: "
                           f"{sorted(required - cited)}")
            phantom = cited - ids
            if phantom:
                why.append(f"phantom citations {sorted(phantom)}")
            # declared alternative: citation SUPERSETS of the required
            # minimum restricted to existing ids are acceptable
            ok = not why
            superset = ok and bool(cited - required)
            return EvaluationRecordD(
                ProductionVerdictD.CORRECT if ok else
                ProductionVerdictD.INCORRECT,
                matched_alternative=superset, reasons=tuple(why))
        if prim == "C32":
            if exp.get("output_class") == "ABSTAIN":
                ok = (parsed.value or {}).get("class") == "ABSTAIN"
                return EvaluationRecordD(
                    ProductionVerdictD.CORRECT if ok else
                    ProductionVerdictD.INCORRECT,
                    reasons=() if ok else ("must ABSTAIN: the evidence "
                                           "lacks the fact",))
            if (parsed.value or {}).get("class") == "ABSTAIN":
                return EvaluationRecordD(
                    ProductionVerdictD.INCORRECT,
                    reasons=("over-abstention: the evidence contains "
                             "the fact",))
            ok = (parsed.value or {}).get("answer") == exp.get("answer")
            return EvaluationRecordD(
                ProductionVerdictD.CORRECT if ok else
                ProductionVerdictD.INCORRECT,
                reasons=() if ok else (f"answer "
                                       f"{(parsed.value or {}).get('answer')!r}"
                                       f" != {exp.get('answer')!r}",))
        return EvaluationRecordD(ProductionVerdictD.SOFTWARE_ERROR,
                                 reasons=(f"primitive {prim} outside "
                                          "Batch D evaluator scope",))
