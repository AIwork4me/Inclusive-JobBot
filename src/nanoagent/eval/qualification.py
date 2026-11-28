"""Dataset-level qualification rules for the cognitive evaluator
(N05A-R, EV07) and the comparator-level mutation gate (EV06).

The 41-case v1 battery established preliminary comparator behaviour; it
does not qualify every future N03 case. For each new N03 task family this
module defines what a qualified dataset scope must contain, and enforces
the declared/reachable/tested reconciliation of reason codes.
"""
from __future__ import annotations

from .comparators import MUTANTS, apply_mutant, clear_mutant, evaluate_family, \
    predicate_truth
from .contracts import (ControlCase, FAMILIES, REASON_CODES,
                        REASON_CODE_DISPOSITIONS)
from .evaluator import CognitiveEvaluator


# -- control-battery validation ------------------------------------------------

def validate_control_battery(cases: list[ControlCase]) -> None:
    """Structural validation of a control battery. Raises ValueError
    listing every problem (fail closed on malformed evaluator inputs)."""
    problems: list[str] = []
    seen: set[str] = set()
    for c in cases:
        if c.case_id in seen:
            problems.append(f"duplicate case id: {c.case_id}")
        seen.add(c.case_id)
        if c.family not in FAMILIES:
            problems.append(f"{c.case_id}: unknown family {c.family!r}")
        if c.control_class == "positive":
            pass
        elif c.control_class.startswith("negative:"):
            reason = c.control_class.split(":", 1)[1]
            if reason not in REASON_CODES:
                problems.append(
                    f"{c.case_id}: negative control declares unknown/obsolete "
                    f"reason {reason!r}")
        else:
            problems.append(f"{c.case_id}: malformed control_class "
                            f"{c.control_class!r}")
        if c.family != c.expectation.family:
            problems.append(f"{c.case_id}: family/expectation mismatch")
    if problems:
        raise ValueError("; ".join(problems))


# -- reason-code reconciliation ---------------------------------------------------

def reason_coverage(cases: list[ControlCase]) -> dict:
    """EV07 reconciliation: declared vs reachable vs tested reason codes."""
    tested = set()
    for c in cases:
        if c.control_class.startswith("negative:"):
            tested.add(c.control_class.split(":", 1)[1])
    declared = set(REASON_CODES)
    return {
        "declared": sorted(declared),
        "tested": sorted(tested),
        "declared_but_untested": sorted(declared - tested),
        "tested_but_undeclared": sorted(tested - declared),
        "obsolete_with_disposition": sorted(REASON_CODE_DISPOSITIONS),
        "reconciled": not (declared - tested) and not (tested - declared),
    }


# -- per-family dataset scope qualification ----------------------------------------

def qualify_family_scope(declaration: dict) -> dict:
    """Qualification rules every new N03 task-family dataset scope must
    satisfy before its cases may be scored:

    - ``task_family``: stable identifier of the task family;
    - ``evaluator_identity``: versioned evaluator scope identity
      (``name@version``);
    - ``positive_witness``: >=1 executable or independently verified
      positive witness case id;
    - ``negative_controls``: >=1 relevant critical negative control id;
    - ``semantic_mutations``: >=1 semantic mutation of the positive
      witness that must fail;
    - ``alternative_responses`` (optional): valid alternative-response
      case ids where the family admits them.

    Returns a record with status QUALIFIED or REJECTED plus reasons.
    """
    problems: list[str] = []
    for key in ("task_family", "evaluator_identity"):
        v = declaration.get(key)
        if not isinstance(v, str) or not v.strip():
            problems.append(f"{key} missing or not a non-empty string")
    ident = declaration.get("evaluator_identity", "")
    if isinstance(ident, str) and "@" not in ident:
        problems.append("evaluator_identity must be versioned (name@version)")
    for key in ("positive_witness", "negative_controls", "semantic_mutations"):
        v = declaration.get(key)
        if not isinstance(v, (list, tuple)) or not v:
            problems.append(f"{key} must list >=1 case id")
        elif not all(isinstance(x, str) and x for x in v):
            problems.append(f"{key} entries must be non-empty strings")
    alt = declaration.get("alternative_responses", [])
    if not isinstance(alt, (list, tuple)):
        problems.append("alternative_responses must be a list")
    status = "REJECTED" if problems else "QUALIFIED"
    return {"status": status,
            "task_family": declaration.get("task_family"),
            "evaluator_identity": declaration.get("evaluator_identity"),
            "problems": problems,
            "contract_version": 2}


# -- comparator-level mutation gate (EV06) -------------------------------------------

def mutation_gate(cases: list[ControlCase] | None = None,
                  truth_controls: list[dict] | None = None) -> dict:
    """Run the qualification gate against every intentionally weakened
    comparator implementation.

    A mutant is DETECTED when it wrongly accepts at least one control that
    the true evaluator rejects (battery controls are scored through the
    full family evaluator; truth controls exercise ``predicate_truth``
    directly). The gate must reject every mutant class.
    """
    if cases is None:
        from .controls import battery
        cases = battery()
    if truth_controls is None:
        from .controls import TRUTH_CONTROLS
        truth_controls = TRUTH_CONTROLS

    true_eval = CognitiveEvaluator(list(cases))
    true_battery = {c.case_id: true_eval.evaluate(c.case_id, c.response)
                    for c in cases}
    true_truth = {tc["name"]: predicate_truth(tc["pred"], tc["world"])
                  for tc in truth_controls}

    report: dict[str, dict] = {}
    for name in MUTANTS:
        witness = None
        channel = None
        apply_mutant(name)
        try:
            for c in cases:
                if true_battery[c.case_id].passed:
                    continue
                if not evaluate_family(c.expectation, c.response):
                    witness, channel = c.case_id, "battery"
                    break
            if witness is None:
                for tc in truth_controls:
                    if not true_truth[tc["name"]]:
                        continue
                    if not predicate_truth(tc["pred"], tc["world"]):
                        witness, channel = tc["name"], "predicate_truth"
                        break
        finally:
            clear_mutant()
        report[name] = {"detected": witness is not None,
                        "witness": witness, "channel": channel}
    return report
