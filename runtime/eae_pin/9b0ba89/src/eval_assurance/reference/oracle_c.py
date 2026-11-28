"""EA03-C — independent reference Oracle for N03 Batch C (C17-C24).

Obligation A (``validate_ground_truth``): every stored expected answer
is derived from the PUBLIC payload under the Batch C handoff rules:

- C17: each queried predicate is evaluated over the typed state
  (``state[slot] op value``); the truth vector is the per-predicate
  evaluation in declared order. A queried slot absent from the state
  is NOT_ESTABLISHED (never a silent false).
- C18: dependency edges by pre/eff intersection algebra — an edge
  (a, b) exists iff some EFFECT KEY of a is a PRECONDITION KEY of b
  (a != b); compared as a SET (stored alternative: edge order within
  the list is irrelevant).
- C19: plan validity by SIMULATION against the published
  preconditions/effects: every step's preconditions hold in the state
  reached so far, effects apply, and the goal predicate holds at the
  end. ANY simulated-valid goal-reaching plan is CORRECT; the stored
  reference_plan is a WITNESS, never the answer key (handoff
  plan-scoring rule).
- C20: holding branches are those whose condition evaluates true over
  the state, in declared order; mutual exclusion is structural (two
  contradictory conditions on the same slot cannot both hold).
- C21: the continuation is simulated FROM THE CURRENT STATE (the
  executed prefix is never re-simulated); validity = per-step
  preconditions + goal at the end + prefix actions naturally fail if
  re-executed (their preconditions no longer hold).
- C22: error-envelope rule — an error object inside the body IS an
  error regardless of an HTTP 200 wrapper (the public instruction
  says so); the code must be a catalog member.
- C23: the corrected record is the failed call's arguments with
  EXACTLY the diagnosed field fixed from the public facts ("case" ->
  the uppercase member of the allowed set; "format" -> the canonical
  value supplied in facts); any other mutation is a defect.
- C24: the applicable fallbacks are those whose condition holds; the
  answer is the FIRST in declared order; arguments come from the
  args_template verbatim.

Obligation B (``evaluate_response``): only VALID ground truth supports
qualified evaluation; plans are SIMULATED, never string-matched
against the reference witness. Software errors are never model
failures. No IJ-NANO imports.
"""
from __future__ import annotations

from .interpreter_c import parse_response as _interp_parse
from .oracle import (GroundTruthResult, GroundTruthVerdict, ResponseResult,
                     ResponseVerdict)

BATCH_C = tuple(f"C{i:02d}" for i in range(17, 25))


def _cmp(op: str, lhs, rhs) -> bool:
    return {"==": lambda: lhs == rhs,
            "!=": lambda: lhs != rhs,
            "<=": lambda: lhs <= rhs,
            ">=": lambda: lhs >= rhs,
            "<": lambda: lhs < rhs,
            ">": lambda: lhs > rhs}[op]()


# ---------------------------------------------------------------------------
# plan simulation (C19 / C21) — the pinned plan-scoring rule
# ---------------------------------------------------------------------------
def simulate_plan(plan, start_state: dict, actions: dict):
    """Simulate ``plan`` from ``start_state``.

    Returns ``(ok, reason, final_state)``; ``ok`` is False at the
    first step whose preconditions do not hold or whose action is not
    declared.
    """
    state = dict(start_state)
    for i, step in enumerate(plan):
        spec = actions.get(step)
        if spec is None:
            return False, f"step {i}: undeclared action {step!r}", state
        pre = spec.get("preconditions") or {}
        for k, v in pre.items():
            if state.get(k) != v:
                return False, (f"step {i} ({step}): precondition {k}="
                               f"{v!r} does not hold "
                               f"(state {k}={state.get(k)!r})"), state
        state.update(spec.get("effects") or {})
    return True, "", state


def _goal_holds(goal: dict, state: dict) -> bool:
    return all(state.get(k) == v for k, v in (goal or {}).items())


# ---------------------------------------------------------------------------
# per-primitive truth derivation
# ---------------------------------------------------------------------------
def _c17(payload: dict, expected: dict) -> GroundTruthResult:
    state = payload.get("state") or {}
    preds = payload.get("predicates") or []
    if not state or not preds:
        return GroundTruthResult("", "", GroundTruthVerdict.NOT_ESTABLISHED,
                                 reasons=("missing state/predicates",))
    truth, why = [], []
    for p in preds:
        slot = p.get("slot")
        if slot not in state:
            why.append(f"queried slot {slot!r} absent from state")
            continue
        truth.append(_cmp(p.get("op", "=="), state[slot], p.get("value")))
    if why:
        return GroundTruthResult("", "", GroundTruthVerdict.NOT_ESTABLISHED,
                                 None, reasons=tuple(why))
    stored = expected.get("truth")
    if stored == truth:
        return GroundTruthResult("", "", GroundTruthVerdict.VALID,
                                 {"truth": truth},
                                 verified_fields=("truth",))
    return GroundTruthResult("", "", GroundTruthVerdict.INVALID,
                             {"truth": truth},
                             reasons=(f"stored truth {stored!r} != derived "
                                      f"{truth!r}",))


def _c18(payload: dict, expected: dict) -> GroundTruthResult:
    actions = payload.get("actions") or {}
    if not actions:
        return GroundTruthResult("", "", GroundTruthVerdict.NOT_ESTABLISHED,
                                 reasons=("missing actions",))
    derived = set()
    for a, sa in actions.items():
        eff = (sa.get("effects") or {}).keys()
        for b, sb in actions.items():
            if a == b:
                continue
            pre = (sb.get("preconditions") or {}).keys()
            if eff & pre:
                derived.add((a, b))
    stored = {tuple(e) for e in (expected.get("edges") or [])}
    if stored == derived:
        return GroundTruthResult("", "", GroundTruthVerdict.VALID,
                                 {"edges": sorted(derived)},
                                 verified_fields=("edges",))
    missing = sorted(derived - stored)
    spurious = sorted(stored - derived)
    return GroundTruthResult("", "", GroundTruthVerdict.INVALID,
                             {"edges": sorted(derived)},
                             reasons=(f"stored edges miss {missing}, "
                                      f"add spurious {spurious}",))


def _c19(payload: dict, expected: dict) -> GroundTruthResult:
    init = payload.get("initial_state") or {}
    goal = payload.get("goal") or {}
    actions = payload.get("actions") or {}
    plan = expected.get("reference_plan")
    if not init or not goal or not actions or plan is None:
        return GroundTruthResult("", "", GroundTruthVerdict.NOT_ESTABLISHED,
                                 reasons=("missing plan task components",))
    ok, reason, final = simulate_plan(plan, init, actions)
    if not ok:
        return GroundTruthResult("", "", GroundTruthVerdict.INVALID,
                                 None, reasons=(f"reference plan does not "
                                                f"simulate: {reason}",))
    if expected.get("must_reach_goal", True) and not _goal_holds(goal,
                                                                 final):
        return GroundTruthResult("", "", GroundTruthVerdict.INVALID,
                                 None, reasons=("reference plan does not "
                                                "reach the goal",))
    return GroundTruthResult(
        "", "", GroundTruthVerdict.VALID,
        {"goal": goal, "initial_state": init, "actions": actions,
         "reference_plan": plan,
         "scoring_rule": "ANY simulated-valid goal-reaching plan is "
                         "CORRECT; the reference plan is one witness"},
        verified_fields=("reference_plan",))


def _c20(payload: dict, expected: dict) -> GroundTruthResult:
    state = payload.get("state") or {}
    branches = payload.get("branches") or []
    if not state or not branches:
        return GroundTruthResult("", "", GroundTruthVerdict.NOT_ESTABLISHED,
                                 reasons=("missing state/branches",))
    holding = []
    for b in branches:
        c = b.get("condition") or {}
        slot = c.get("slot")
        # a condition over a slot ABSENT from the state does not hold
        # (typed-state semantics; e.g. a payment branch in a service
        # state without a paid slot simply never selects)
        if slot in state and _cmp(c.get("op", "=="), state[slot],
                                  c.get("value")):
            holding.append(b.get("id"))
    stored = expected.get("holding")
    if stored == holding:
        return GroundTruthResult("", "", GroundTruthVerdict.VALID,
                                 {"holding": holding},
                                 verified_fields=("holding",))
    return GroundTruthResult("", "", GroundTruthVerdict.INVALID,
                             {"holding": holding},
                             reasons=(f"stored holding {stored!r} != "
                                      f"derived {holding!r}",))


def _c21(payload: dict, expected: dict) -> GroundTruthResult:
    current = payload.get("current_state") or {}
    goal = payload.get("goal") or {}
    actions = payload.get("actions") or {}
    cont = expected.get("continuation")
    prefix = payload.get("executed_prefix") or []
    if not current or not goal or not actions or cont is None:
        return GroundTruthResult("", "", GroundTruthVerdict.NOT_ESTABLISHED,
                                 reasons=("missing replan components",))
    ok, reason, final = simulate_plan(cont, current, actions)
    if not ok:
        return GroundTruthResult("", "", GroundTruthVerdict.INVALID,
                                 None, reasons=(
                                     f"continuation does not simulate "
                                     f"from the current state: {reason}",))
    if not _goal_holds(goal, final):
        return GroundTruthResult("", "", GroundTruthVerdict.INVALID,
                                 None, reasons=("continuation does not "
                                                "reach the goal",))
    if len(cont) >= len(prefix) + 1 and cont[:len(prefix)] == \
            list(prefix):
        return GroundTruthResult("", "", GroundTruthVerdict.INVALID,
                                 None, reasons=("continuation re-executes "
                                                "the prefix",))
    return GroundTruthResult(
        "", "", GroundTruthVerdict.VALID,
        {"goal": goal, "current_state": current, "actions": actions,
         "reference_continuation": cont,
         "scoring_rule": "any simulated-valid continuation from the "
                         "current state reaching the goal is CORRECT"},
        verified_fields=("continuation",))


def _c22(payload: dict, expected: dict) -> GroundTruthResult:
    resp = payload.get("response") or {}
    catalog = payload.get("error_catalog") or {}
    if not resp or not catalog:
        return GroundTruthResult("", "", GroundTruthVerdict.NOT_ESTABLISHED,
                                 reasons=("missing response/catalog",))
    body = resp.get("body") if isinstance(resp.get("body"), dict) \
        else resp                     # wrapped vs bare envelope
    err = body.get("error")
    wrapper = "http_status" in resp
    derived = {"is_error": isinstance(err, dict),
               "wrapper": wrapper}
    if derived["is_error"]:
        code = err.get("code")
        derived["code"] = code
        if code not in catalog:
            return GroundTruthResult(
                "", "", GroundTruthVerdict.NOT_ESTABLISHED, derived,
                reasons=(f"error code {code!r} not in the public "
                         "catalog",))
    else:
        derived["code"] = ""
    stored_is = expected.get("is_error")
    stored_code = expected.get("code")
    why = []
    if stored_is is not derived["is_error"]:
        why.append(f"is_error stored {stored_is!r} != derived "
                   f"{derived['is_error']!r}")
    if (stored_code or "") != (derived["code"] or ""):
        why.append(f"code stored {stored_code!r} != derived "
                   f"{derived['code']!r}")
    if why:
        return GroundTruthResult("", "", GroundTruthVerdict.INVALID,
                                 derived, reasons=tuple(why))
    # construction.wrapper records the BUILDER's generation variant
    # (bare vs wrapped family) — the two families share envelope
    # shapes, so it is NOT public-derivable truth: cross-checked as
    # metadata only when the shape is unambiguous
    return GroundTruthResult(
        "", "", GroundTruthVerdict.VALID, derived,
        verified_fields=("is_error", "code"),
        unverified_fields=("construction.wrapper",)
        if "construction" in expected else ())


def _c23(payload: dict, expected: dict) -> GroundTruthResult:
    call = payload.get("failed_call") or {}
    args = dict(call.get("arguments") or {})
    diag = payload.get("diagnosis") or {}
    facts = payload.get("facts") or {}
    field, problem = diag.get("field"), diag.get("problem")
    if not args or field not in args:
        return GroundTruthResult("", "", GroundTruthVerdict.NOT_ESTABLISHED,
                                 reasons=(f"diagnosed field {field!r} not "
                                          "in the failed call",))
    corrected = dict(args)
    if problem == "case":
        allowed = None
        for v in facts.values():
            if isinstance(v, list) and all(isinstance(x, str) for x in v) \
                    and str(args[field]).upper() in [str(x).upper()
                                                     for x in v]:
                allowed = v
                break
        if allowed is None:
            return GroundTruthResult(
                "", "", GroundTruthVerdict.NOT_ESTABLISHED, None,
                reasons=(f"no allowed set in facts contains "
                         f"{args[field]!r} case-insensitively",))
        corrected[field] = next(x for x in allowed
                                if str(x).upper() ==
                                str(args[field]).upper())
    elif problem == "format":
        canon = facts.get(f"canonical_{field}")
        if canon is None:
            return GroundTruthResult(
                "", "", GroundTruthVerdict.NOT_ESTABLISHED, None,
                reasons=(f"facts carry no canonical_{field}",))
        corrected[field] = canon
    else:
        return GroundTruthResult(
            "", "", GroundTruthVerdict.NOT_ESTABLISHED, None,
            reasons=(f"problem kind {problem!r} not derivable",))
    stored = expected.get("arguments")
    if stored == corrected:
        return GroundTruthResult("", "", GroundTruthVerdict.VALID,
                                 {"arguments": corrected},
                                 verified_fields=("arguments",))
    return GroundTruthResult("", "", GroundTruthVerdict.INVALID,
                             {"arguments": corrected},
                             reasons=(f"stored arguments {stored!r} != "
                                      f"derived {corrected!r}",))


def _c24(payload: dict, expected: dict) -> GroundTruthResult:
    state = payload.get("state") or {}
    fallbacks = payload.get("fallbacks") or []
    if not state or not fallbacks:
        return GroundTruthResult("", "", GroundTruthVerdict.NOT_ESTABLISHED,
                                 reasons=("missing state/fallbacks",))
    applicable = []
    for f in fallbacks:
        c = f.get("condition") or {}
        slot = c.get("slot")
        if slot not in state:
            return GroundTruthResult(
                "", "", GroundTruthVerdict.NOT_ESTABLISHED, None,
                reasons=(f"fallback {f.get('id')} queries absent slot "
                         f"{slot!r}",))
        if _cmp(c.get("op", "=="), state[slot], c.get("value")):
            applicable.append(f)
    if not applicable:
        return GroundTruthResult(
            "", "", GroundTruthVerdict.NOT_ESTABLISHED,
            {"applicable": []},
            reasons=("no fallback condition holds in the state",))
    first = applicable[0]
    derived = {"fallback_id": first.get("id"),
               "action": first.get("action"),
               "arguments": dict(first.get("args_template") or {}),
               "applicable": [f.get("id") for f in applicable]}
    why = []
    if expected.get("fallback_id") != derived["fallback_id"]:
        why.append(f"fallback_id {expected.get('fallback_id')!r} != "
                   f"{derived['fallback_id']!r}")
    if expected.get("action") is not None and \
            expected.get("action") != derived["action"]:
        why.append("action mismatch")
    if expected.get("arguments") is not None and \
            expected.get("arguments") != derived["arguments"]:
        why.append("arguments mismatch")
    if expected.get("applicable") is not None and \
            list(expected.get("applicable")) != derived["applicable"]:
        why.append(f"applicable {expected.get('applicable')} != "
                   f"{derived['applicable']}")
    if why:
        return GroundTruthResult("", "", GroundTruthVerdict.INVALID,
                                 derived, reasons=tuple(why))
    return GroundTruthResult("", "", GroundTruthVerdict.VALID, derived,
                             verified_fields=("fallback_id", "action",
                                              "arguments"))


_HANDLERS = {"C17": _c17, "C18": _c18, "C19": _c19, "C20": _c20,
             "C21": _c21, "C22": _c22, "C23": _c23, "C24": _c24}


def validate_ground_truth(case: dict, expectation: dict) -> GroundTruthResult:
    payload = case.get("public_payload") or {}
    expected = (expectation or {}).get("expected")
    prim = case.get("primitive")
    if expected is None:
        return GroundTruthResult(case.get("case_id", ""), prim,
                                 GroundTruthVerdict.NOT_ESTABLISHED,
                                 reasons=("no stored expectation",))
    handler = _HANDLERS.get(prim)
    if handler is None:
        return GroundTruthResult(case.get("case_id", ""), prim,
                                 GroundTruthVerdict.NOT_ESTABLISHED,
                                 reasons=(f"primitive {prim} outside Batch C "
                                          "oracle scope",))
    r = handler(payload, expected)
    return GroundTruthResult(case.get("case_id", ""), prim, r.verdict,
                             r.recomputed, r.reasons, r.verified_fields,
                             r.unverified_fields)


# ---------------------------------------------------------------------------
# Obligation B — reference evaluation (plans SIMULATED, never matched)
# ---------------------------------------------------------------------------
def _compare(prim: str, payload: dict, parsed, truth: dict) -> tuple:
    if prim == "C17":
        want = truth.get("truth") or []
        got = parsed if isinstance(parsed, list) else None
        if got is None or len(got) != len(want):
            return False, (f"truth vector arity {len(got or [])} != "
                           f"{len(want)}",)
        if [bool(x) for x in got] != [bool(x) for x in want]:
            return False, (f"truth vector {got!r} != {want!r}",)
        if any(not isinstance(x, bool) for x in got):
            return False, ("non-boolean truth entries",)
        return True, ()
    if prim == "C18":
        want = {tuple(e) for e in (truth.get("edges") or [])}
        got = {tuple(e) for e in (parsed or [])}
        if got != want:
            return False, (f"edge set {sorted(got)} != {sorted(want)}",)
        return True, ()
    if prim == "C19":
        ok, reason, final = simulate_plan(
            parsed or [], truth.get("initial_state") or {},
            truth.get("actions") or {})
        if not ok:
            return False, (f"plan does not simulate: {reason}",)
        if not _goal_holds(truth.get("goal") or {}, final):
            return False, ("plan does not reach the goal predicate",)
        return True, ("alternative simulated-valid plan",)
    if prim == "C20":
        want = list(truth.get("holding") or [])
        got = [str(x) for x in (parsed or [])]
        if sorted(got) != sorted(want):
            return False, (f"holding set {sorted(got)} != {sorted(want)}",)
        if [x for x in got if x not in want]:
            return False, ("selected branch whose condition does not "
                           "hold",)
        return True, ()
    if prim == "C21":
        prefix = (payload.get("executed_prefix") or [])
        if len(parsed or []) >= len(prefix) + 1 and \
                list((parsed or [])[:len(prefix)]) == list(prefix):
            return False, ("continuation re-executes the interrupted "
                           "prefix",)
        ok, reason, final = simulate_plan(
            parsed or [], truth.get("current_state") or {},
            truth.get("actions") or {})
        if not ok:
            return False, (f"continuation does not simulate from the "
                           f"current state: {reason}",)
        if not _goal_holds(truth.get("goal") or {}, final):
            return False, ("continuation does not reach the goal",)
        return True, ("alternative simulated-valid continuation",)
    if prim == "C22":
        want_is = truth.get("is_error")
        want_code = truth.get("code") or ""
        if parsed.get("is_error") != want_is:
            return False, (f"is_error {parsed.get('is_error')!r} != "
                           f"{want_is!r}",)
        if (parsed.get("code") or "") != want_code:
            return False, (f"code {parsed.get('code')!r} != "
                           f"{want_code!r}",)
        return True, ()
    if prim == "C23":
        want = truth.get("arguments") or {}
        if parsed != want:
            diff = {k: (parsed.get(k), want.get(k))
                    for k in set(parsed) | set(want)
                    if parsed.get(k) != want.get(k)}
            return False, (f"corrected arguments differ: {diff}",)
        return True, ()
    if prim == "C24":
        want_id = truth.get("fallback_id")
        want_action = truth.get("action")
        want_args = truth.get("arguments") or {}
        why = []
        if parsed.get("fallback_id") != want_id:
            why.append(f"fallback_id {parsed.get('fallback_id')!r} != "
                       f"{want_id!r}")
        if parsed.get("action") != want_action:
            why.append(f"action {parsed.get('action')!r} != "
                       f"{want_action!r}")
        if parsed.get("arguments") != want_args:
            why.append("arguments differ from the args_template")
        if why:
            return False, tuple(why)
        return True, ()
    return False, (f"primitive {prim} outside Batch C comparison scope",)


def evaluate_response(case: dict, expectation: dict,
                      response) -> ResponseResult:
    prim = case.get("primitive", "")
    case_id = case.get("case_id", "")
    try:
        parsed, parse_class, parse_reasons = _interp_parse(
            prim, case.get("public_payload") or {}, response)
    except Exception as exc:
        return ResponseResult(
            case_id, prim, ResponseVerdict.NOT_EVALUABLE,
            reasons=(f"interpreter software error: {type(exc).__name__}: "
                     f"{exc}",))
    if parse_class == "EMPTY_OUTPUT":
        return ResponseResult(case_id, prim, ResponseVerdict.EMPTY_OUTPUT,
                              reasons=parse_reasons or ("empty output",))
    try:
        gt = validate_ground_truth(case, expectation)
        if gt.verdict is not GroundTruthVerdict.VALID:
            return ResponseResult(
                case_id, prim, ResponseVerdict.NOT_EVALUABLE, parsed=parsed,
                truth=gt.recomputed,
                reasons=(f"ground truth not independently established "
                         f"({gt.verdict.value}); qualified response "
                         f"evaluation refused",))
        truth = gt.recomputed
        if parse_class != "OK":
            return ResponseResult(case_id, prim, ResponseVerdict.INCORRECT,
                                  parsed=parsed, truth=truth,
                                  reasons=parse_reasons or
                                  ("malformed output",))
        ok, why = _compare(prim, case.get("public_payload") or {},
                           parsed, truth)
        if ok:
            return ResponseResult(case_id, prim, ResponseVerdict.CORRECT,
                                  parsed=parsed, truth=truth)
        return ResponseResult(case_id, prim, ResponseVerdict.INCORRECT,
                              parsed=parsed, truth=truth, reasons=why)
    except Exception as exc:
        return ResponseResult(
            case_id, prim, ResponseVerdict.NOT_EVALUABLE, parsed=parsed,
            reasons=(f"reference-path software error: "
                     f"{type(exc).__name__}: {exc}",))
