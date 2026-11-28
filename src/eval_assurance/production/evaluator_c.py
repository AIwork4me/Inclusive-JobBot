"""EA05-C — Production Evaluator for N03 Batch C (C17-C24).

Typed comparison against the STORED expectation record (production
consumes stored answers; the reference oracle derives truth from
public payloads — the two comparator implementations are authored
independently). Class discipline identical to the Batch B evaluator:
EMPTY_OUTPUT its own class, INVALID_OUTPUT = model-side structural,
INCORRECT = semantic wrongness, EVALUATOR_SOFTWARE_ERROR = software.

Per-primitive semantics:
- C17: truth vector equality (exact booleans, declared order).
- C18: edge SET equality (stored alternative: order irrelevant).
- C19: SIMULATION of the emitted plan against the STORED action
  semantics (initial state, preconditions/effects, goal predicate) —
  any simulated-valid goal-reaching plan is CORRECT; the stored
  reference_plan is never string-matched.
- C20: holding set equality; a selected branch whose condition cannot
  hold (absent slot / false condition) is INCORRECT via the stored
  holding set.
- C21: simulation of the continuation from the STORED current_state;
  prefix re-execution refused.
- C22: is_error + code equality (200 status never clears a body
  error; code null normalizes to "").
- C23: corrected-arguments equality (exactly the diagnosed fix).
- C24: fallback_id/action/arguments equality with the first
  condition-holding declared fallback (recomputed from the payload
  state — production does not trust the stored applicable list for
  scoring).
"""
from __future__ import annotations

from dataclasses import dataclass

from .parser_c import (PARSE_EMPTY, PARSE_MALFORMED, PARSE_OK,
                       PARSE_SOFTWARE, ParsedAnswerC)


class ProductionVerdictC:
    CORRECT = "CORRECT"
    INCORRECT = "INCORRECT"
    EMPTY_OUTPUT = "EMPTY_OUTPUT"
    INVALID_OUTPUT = "INVALID_OUTPUT"
    SOFTWARE_ERROR = "EVALUATOR_SOFTWARE_ERROR"

    ALL = (CORRECT, INCORRECT, EMPTY_OUTPUT, INVALID_OUTPUT,
           SOFTWARE_ERROR)


@dataclass(frozen=True)
class EvaluationRecordC:
    verdict: str
    matched_alternative: bool = False
    reasons: tuple = ()


def _cmp(op: str, lhs, rhs) -> bool:
    return {"==": lambda: lhs == rhs, "!=": lambda: lhs != rhs,
            "<=": lambda: lhs <= rhs, ">=": lambda: lhs >= rhs,
            "<": lambda: lhs < rhs, ">": lambda: lhs > rhs}[op]()


def _holds(cond: dict, state: dict) -> bool:
    slot = cond.get("slot")
    return slot in state and _cmp(cond.get("op", "=="), state[slot],
                                  cond.get("value"))


def _simulate(plan, start_state: dict, actions: dict):
    state = dict(start_state)
    for i, step in enumerate(plan):
        spec = actions.get(step)
        if spec is None:
            return False, f"step {i}: undeclared action {step!r}"
        for k, v in (spec.get("preconditions") or {}).items():
            if state.get(k) != v:
                return False, (f"step {i} ({step}): precondition "
                               f"{k}={v!r} fails")
        state.update(spec.get("effects") or {})
    return True, ""


def _eval_c17(value, exp: dict, alts: list) -> EvaluationRecordC:
    want = list(exp.get("truth") or [])
    got = list(value or [])
    if got == want:
        return EvaluationRecordC(ProductionVerdictC.CORRECT)
    return EvaluationRecordC(
        ProductionVerdictC.INCORRECT,
        reasons=(f"truth vector {got!r} != stored {want!r}",))


def _eval_c18(value, exp: dict, alts: list) -> EvaluationRecordC:
    want = {tuple(e) for e in (exp.get("edges") or [])}
    got = {tuple(e) for e in (value or [])}
    if got == want:
        return EvaluationRecordC(ProductionVerdictC.CORRECT,
                                 matched_alternative=bool(got),
                                 reasons=("edge order differs; ordering "
                                          "freedom declared",)
                                 if got and list(got) != list(want) else ())
    return EvaluationRecordC(
        ProductionVerdictC.INCORRECT,
        reasons=(f"edge set {sorted(got)} != stored {sorted(want)}",))


def _eval_plan(payload: dict, value, exp: dict, alts: list,
               current_state: dict, prefix=None) -> EvaluationRecordC:
    goal = payload.get("goal") or {}
    actions = payload.get("actions") or {}
    plan = [str(x) for x in (value or [])]
    if prefix and len(plan) >= len(prefix) + 1 and \
            plan[:len(prefix)] == list(prefix):
        return EvaluationRecordC(
            ProductionVerdictC.INCORRECT,
            reasons=("continuation re-executes the interrupted prefix",))
    ok, reason = _simulate(plan, current_state, actions)
    if not ok:
        return EvaluationRecordC(ProductionVerdictC.INCORRECT,
                                 reasons=(f"plan does not simulate: "
                                          f"{reason}",))
    final = dict(current_state)
    for step in plan:
        final.update((actions.get(step) or {}).get("effects") or {})
    if not all(final.get(k) == v for k, v in goal.items()):
        return EvaluationRecordC(
            ProductionVerdictC.INCORRECT,
            reasons=("plan does not reach the goal predicate",))
    return EvaluationRecordC(
        ProductionVerdictC.CORRECT,
        matched_alternative=bool(plan) and plan !=
        (exp.get("reference_plan") or exp.get("continuation")),
        reasons=("alternative simulated-valid plan accepted",))


class ProductionEvaluatorC:
    identity = "eval_assurance.production.evaluator_c@1"

    def evaluate(self, case: dict, expectation: dict,
                 parsed: ParsedAnswerC) -> EvaluationRecordC:
        prim = case.get("primitive", "")
        if parsed.parse_class == PARSE_EMPTY:
            return EvaluationRecordC(ProductionVerdictC.EMPTY_OUTPUT)
        if parsed.parse_class == PARSE_SOFTWARE:
            return EvaluationRecordC(ProductionVerdictC.SOFTWARE_ERROR,
                                     reasons=("parser software fault",))
        if parsed.parse_class == PARSE_MALFORMED:
            return EvaluationRecordC(ProductionVerdictC.INVALID_OUTPUT,
                                     reasons=parsed.violations)
        exp = (expectation or {}).get("expected") or {}
        alts = [str(a).lower() for a in
                (expectation or {}).get("alternatives") or [] if a]
        payload = case.get("public_payload") or {}
        if prim == "C17":
            return _eval_c17(parsed.value, exp, alts)
        if prim == "C18":
            return _eval_c18(parsed.value, exp, alts)
        if prim == "C19":
            return _eval_plan(payload, parsed.value, exp, alts,
                              payload.get("initial_state") or {})
        if prim == "C20":
            want = list(exp.get("holding") or [])
            got = [str(x) for x in (parsed.value or [])]
            if sorted(got) == sorted(want):
                return EvaluationRecordC(ProductionVerdictC.CORRECT)
            return EvaluationRecordC(
                ProductionVerdictC.INCORRECT,
                reasons=(f"holding set {sorted(got)} != stored "
                         f"{sorted(want)}",))
        if prim == "C21":
            return _eval_plan(payload, parsed.value, exp, alts,
                              payload.get("current_state") or
                              exp.get("current_state") or {},
                              prefix=payload.get("executed_prefix"))
        if prim == "C22":
            want_is = exp.get("is_error")
            want_code = exp.get("code") or ""
            got = parsed.value or {}
            why = []
            if got.get("is_error") != want_is:
                why.append(f"is_error {got.get('is_error')!r} != "
                           f"{want_is!r}")
            if (got.get("code") or "") != want_code:
                why.append(f"code {got.get('code')!r} != {want_code!r}")
            if why:
                return EvaluationRecordC(ProductionVerdictC.INCORRECT,
                                         reasons=tuple(why))
            return EvaluationRecordC(ProductionVerdictC.CORRECT)
        if prim == "C23":
            want = exp.get("arguments") or {}
            if parsed.value == want:
                return EvaluationRecordC(ProductionVerdictC.CORRECT)
            diff = {k: ((parsed.value or {}).get(k), want.get(k))
                    for k in set(parsed.value or {}) | set(want)
                    if (parsed.value or {}).get(k) != want.get(k)}
            return EvaluationRecordC(
                ProductionVerdictC.INCORRECT,
                reasons=(f"corrected arguments differ: {diff}",))
        if prim == "C24":
            state = payload.get("state") or {}
            fallbacks = payload.get("fallbacks") or []
            first = next((f for f in fallbacks
                          if _holds(f.get("condition") or {}, state)),
                         None)
            if first is None:
                return EvaluationRecordC(
                    ProductionVerdictC.SOFTWARE_ERROR,
                    reasons=("no fallback condition holds in the public "
                             "state; stored answer cannot be "
                             "reproduced"))
            got = parsed.value or {}
            why = []
            if got.get("fallback_id") != first.get("id"):
                why.append(f"fallback_id {got.get('fallback_id')!r} != "
                           f"{first.get('id')!r}")
            if got.get("action") != first.get("action"):
                why.append(f"action {got.get('action')!r} != "
                           f"{first.get('action')!r}")
            if got.get("arguments") != dict(
                    first.get("args_template") or {}):
                why.append("arguments differ from the args_template")
            if why:
                return EvaluationRecordC(ProductionVerdictC.INCORRECT,
                                         reasons=tuple(why))
            return EvaluationRecordC(ProductionVerdictC.CORRECT)
        return EvaluationRecordC(ProductionVerdictC.SOFTWARE_ERROR,
                                 reasons=(f"primitive {prim} outside "
                                          "Batch C evaluator scope",))
