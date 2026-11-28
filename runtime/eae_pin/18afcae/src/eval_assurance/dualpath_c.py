"""EA06-C — Batch C dual-path evaluation (C17-C24).

Mirrors the Wave B dual-path semantics with the Batch C legs bound:
production parser_c/evaluator_c (stored expectations + payload-state
recomputation) vs reference interpreter_c/oracle_c (public-payload
truth derivation + plan simulation). Unresolved disagreement is
NOT_EVALUABLE + quarantine; EMPTY_OUTPUT keeps its own class; software
errors are never model failures. The Batch A/B qualified modules are
imported for vocabulary only — never edited.
"""
from __future__ import annotations

from .dualpath import (CORRECT, EMPTY_OUTPUT, EVALUATOR_SOFTWARE_ERROR,
                       INCORRECT, INVALID_OUTPUT, MISSING,
                       MISSING_EVIDENCE, NOT_EVALUABLE, DualPathResult,
                       _FAMILY)
from .production.evaluator import ProductionVerdict
from .production.parser_c import (PARSE_EMPTY, PARSE_SOFTWARE,
                                  parse_response)
from .reference import oracle_c as _oracle


def _typed_equal(prim: str, a, b) -> bool:
    if prim in ("C19", "C21") and isinstance(a, list) and \
            isinstance(b, list):
        return [str(x) for x in a] == [str(x) for x in b]
    if prim == "C18" and isinstance(a, list) and isinstance(b, list):
        return {tuple(map(str, x)) for x in a} == \
            {tuple(map(str, x)) for x in b}
    if prim in ("C22", "C23", "C24") and isinstance(a, dict) and \
            isinstance(b, dict):
        return dict(a) == dict(b)
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, str) and isinstance(b, str):
        return a.lower() == b.lower()
    return a == b


def evaluate_dual(case: dict, expectation: dict, response,
                  production_parser=None,
                  production_evaluator=None) -> DualPathResult:
    prim = case.get("primitive", "")
    case_id = case.get("case_id", "")
    pparse = production_parser or parse_response
    peval = production_evaluator
    if peval is None:
        from .production.evaluator_c import ProductionEvaluatorC
        peval = ProductionEvaluatorC()

    try:
        parsed = pparse(prim, case.get("public_payload") or {}, response)
        prod = peval.evaluate(case, expectation, parsed)
        prod_verdict = prod.verdict
        prod_class = parsed.parse_class
    except Exception as exc:                          # software, never model
        return DualPathResult(
            case_id, prim, EVALUATOR_SOFTWARE_ERROR,
            ProductionVerdict.SOFTWARE_ERROR, "NOT_EVALUABLE", False, True,
            reasons=(f"production software error: "
                     f"{type(exc).__name__}: {exc}",))

    ref = _oracle.evaluate_response(case, expectation, response)
    ref_verdict = ref.verdict.value

    if prod_class == PARSE_EMPTY:
        classification = EMPTY_OUTPUT
    elif prod_class == PARSE_SOFTWARE:
        classification = EVALUATOR_SOFTWARE_ERROR
    else:
        pf = _FAMILY.get(prod_verdict, "INCORRECT")
        rf = _FAMILY.get(ref_verdict, "NOT_EVALUABLE")
        if pf != rf:
            classification = NOT_EVALUABLE
        else:
            classification = prod_verdict
    typed_match = _typed_equal(prim, parsed.value,
                               getattr(ref.parsed, "value", ref.parsed))
    reasons = list(prod.reasons) + list(ref.reasons)
    if classification == CORRECT and not typed_match and \
            not getattr(prod, "matched_alternative", False):
        classification = NOT_EVALUABLE
        reasons.append("paths agree on CORRECT but typed values differ "
                       "without a declared alternative")
    quarantine = classification in (NOT_EVALUABLE, EVALUATOR_SOFTWARE_ERROR)
    return DualPathResult(
        case_id, prim, classification, prod_verdict, ref_verdict,
        typed_match, quarantine, tuple(reasons),
        parsed_production=getattr(parsed, "value", None),
        parsed_reference=getattr(ref.parsed, "value", ref.parsed),
        truth_reference=ref.truth)
