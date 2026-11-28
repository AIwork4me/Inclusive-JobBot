"""EA06-B — Batch B dual-path evaluation (C09-C16).

Mirrors the Wave B dual-path semantics (``dualpath.py``) with the
Batch B legs bound: production parser/evaluator
(``production/parser_b.py`` + ``production/evaluator_b.py``, consuming
STORED expectations) vs the independent reference path
(``reference/interpreter_b.py`` + ``reference/oracle_b.py``, deriving
truth from PUBLIC payloads). Any unresolved disagreement is
NOT_EVALUABLE + quarantine; EMPTY_OUTPUT keeps its own class; software
errors are never model failures. The Batch A dual-path module is
imported for its classification vocabulary only — never edited (its
digest is registered in the live Batch A ExecutionEvidence).
"""
from __future__ import annotations

from .dualpath import (CORRECT, EMPTY_OUTPUT, EVALUATOR_SOFTWARE_ERROR,
                       INCORRECT, INVALID_OUTPUT, MISSING,
                       MISSING_EVIDENCE, NOT_EVALUABLE, DualPathResult,
                       _FAMILY)
from .production.evaluator import ProductionVerdict
from .production.parser_b import (PARSE_EMPTY, PARSE_SOFTWARE,
                                  parse_response)
from .reference import oracle_b as _oracle


def _typed_equal(prim: str, a, b) -> bool:
    """Typed-semantics equality at the agreed normalization point."""
    if prim in ("C09", "C10", "C12", "C14", "C15") and \
            isinstance(a, dict) and isinstance(b, dict):
        return dict(a) == dict(b)
    if prim == "C11" and isinstance(a, list) and isinstance(b, list):
        return [str(x) for x in a] == [str(x) for x in b]
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, str) and isinstance(b, str):
        return a.lower() == b.lower()
    return a == b


def evaluate_dual(case: dict, expectation: dict, response,
                  production_parser=None,
                  production_evaluator=None) -> DualPathResult:
    """Run both Batch B paths on one raw response and compare them."""
    prim = case.get("primitive", "")
    case_id = case.get("case_id", "")
    pparse = production_parser or parse_response
    peval = production_evaluator
    if peval is None:
        from .production.evaluator_b import ProductionEvaluatorB
        peval = ProductionEvaluatorB()

    # -- production leg ---------------------------------------------------
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

    # -- reference leg ------------------------------------------------------
    ref = _oracle.evaluate_response(case, expectation, response)
    ref_verdict = ref.verdict.value

    # -- comparison ----------------------------------------------------------
    if prod_class == PARSE_EMPTY:
        classification = EMPTY_OUTPUT
    elif prod_class == PARSE_SOFTWARE:
        classification = EVALUATOR_SOFTWARE_ERROR
    else:
        pf = _FAMILY.get(prod_verdict, "INCORRECT")
        rf = _FAMILY.get(ref_verdict, "NOT_EVALUABLE")
        if pf != rf:
            classification = NOT_EVALUABLE     # unresolved disagreement
        else:
            classification = prod_verdict      # agreed: keep prod's split
    typed_match = _typed_equal(prim, parsed.value,
                               getattr(ref.parsed, "value", ref.parsed))
    reasons = list(prod.reasons) + list(ref.reasons)
    # unique-truth agreements must also agree on the typed value
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
