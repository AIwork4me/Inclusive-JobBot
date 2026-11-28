"""EA03-D — independent reference Oracle for N03 Batch D (C25-C32).

Obligation A (``validate_ground_truth``): every stored expected answer
derived from the PUBLIC payload:

- C25: goal-predicate evaluation over the state — STOP iff every goal
  key holds with the goal value, else CONTINUE.
- C26: sufficiency vs the required schema — a slot is missing iff it
  is ABSENT from the available information OR present-but-INVALID
  under the declared ``field_validity`` ("one of a|b|c" membership);
  ACT iff nothing is missing, ASK + the missing set otherwise. Fields
  not declared required never trigger ASK.
- C27: threshold predicate evaluation over the policy — a rule
  triggers iff its condition holds over the facts, where (per the
  PUBLIC instruction) a ``>=`` threshold value ITSELF does not trigger
  unless a rule states otherwise (strict-greater boundary semantics);
  ESCALATE + the complete triggered rule set, or PROCEED.
- C28: the target is the value introduced by the ACTIVE-marker
  sentence (bilingual); values flagged superseded / older-reference /
  sibling-account are decoys and never the answer.
- C29: candidate duplication rule — when the request phrase matches
  multiple candidate descriptions (exact normalized equality) with no
  distinguishing rule, the truth is AMBIGUOUS + the conflicting ids;
  a unique match resolves to its id.
- C30: the canonical operation string is derived from the PUBLIC
  request via an independently authored bilingual op table (op lexicon
  + entity/id/number/date extraction, zh dates normalized to ISO); the
  declared canonical_format pins the surface ``op:entity[:extra]``.
- C31: required citations are derived per CLAIM (question clauses
  split bilingually) by topical keyword agreement with the evidence
  texts; supersets of the required minimum restricted to existing ids
  are acceptable (declared alternative).
- C32: declared sufficiency — the fact is answerable iff the evidence
  text (in the case's language) actually contains the asked fact type
  (time-of-day for "what time / 几点" questions); otherwise ABSTAIN.
  The answer value is extracted from the evidence, never guessed.

Obligation B (``evaluate_response``): only VALID ground truth supports
qualified evaluation; software errors are never model failures. No
IJ-NANO imports.
"""
from __future__ import annotations

import re

from .interpreter_d import parse_response as _interp_parse
from .oracle import (GroundTruthResult, GroundTruthVerdict, ResponseResult,
                     ResponseVerdict)

BATCH_D = tuple(f"C{i:02d}" for i in range(25, 33))

_TIME_RE = re.compile(r"\d{1,2}:\d{2}")


def _cmp(op: str, lhs, rhs) -> bool:
    if op == "==":
        return lhs == rhs
    if op == "!=":
        return lhs != rhs
    if op == ">=":
        # public C27 instruction: the threshold value itself does NOT
        # trigger '>=' unless the rule states otherwise -> strict
        return lhs > rhs
    if op == "<=":
        return lhs <= rhs
    if op == ">":
        return lhs > rhs
    if op == "<":
        return lhs < rhs
    return False


# ---------------------------------------------------------------------------
# per-primitive derivations
# ---------------------------------------------------------------------------
def _c25(payload: dict, expected: dict) -> GroundTruthResult:
    goal = payload.get("goal") or {}
    state = payload.get("state") or {}
    if not goal or not isinstance(state, dict):
        return GroundTruthResult("", "", GroundTruthVerdict.NOT_ESTABLISHED,
                                 reasons=("missing goal/state",))
    met = all(state.get(k) == v for k, v in goal.items())
    decision = "STOP" if met else "CONTINUE"
    stored = expected.get("decision")
    if stored == decision:
        return GroundTruthResult("", "", GroundTruthVerdict.VALID,
                                 {"decision": decision},
                                 verified_fields=("decision",))
    return GroundTruthResult("", "", GroundTruthVerdict.INVALID,
                             {"decision": decision},
                             reasons=(f"stored {stored!r} != derived "
                                      f"{decision!r}",))


def _valid_under(value, constraint: str) -> bool:
    """"one of a|b|c" membership (the only declared validity form)."""
    m = re.match(r"^one of (.+)$", constraint or "")
    if not m:
        return True                       # unknown constraint: not
        #                                    derivable as invalid
    allowed = [x.strip() for x in m.group(1).split("|")]
    return str(value) in allowed


def _c26(payload: dict, expected: dict) -> GroundTruthResult:
    required = payload.get("required_fields") or []
    avail = payload.get("available_information") or {}
    validity = payload.get("field_validity") or {}
    if not required or not isinstance(avail, dict):
        return GroundTruthResult("", "", GroundTruthVerdict.NOT_ESTABLISHED,
                                 reasons=("missing required/available",))
    missing = []
    for slot in required:
        if slot not in avail:
            missing.append(slot)
        elif slot in validity and not _valid_under(avail[slot],
                                                   validity[slot]):
            missing.append(slot)          # present-but-invalid counts
            #                              as missing (public rule)
    derived = {"decision": "ASK" if missing else "ACT",
               "missing": missing}
    stored_d = expected.get("decision")
    stored_m = expected.get("missing")
    why = []
    if stored_d != derived["decision"]:
        why.append(f"decision {stored_d!r} != {derived['decision']!r}")
    if sorted(stored_m or []) != sorted(missing):
        why.append(f"missing {stored_m!r} != {missing!r}")
    if why:
        return GroundTruthResult("", "", GroundTruthVerdict.INVALID,
                                 derived, reasons=tuple(why))
    return GroundTruthResult("", "", GroundTruthVerdict.VALID, derived,
                             verified_fields=("decision", "missing"))


def _c27(payload: dict, expected: dict) -> GroundTruthResult:
    policy = payload.get("policy") or []
    facts = payload.get("facts") or {}
    if not policy or not isinstance(facts, dict):
        return GroundTruthResult("", "", GroundTruthVerdict.NOT_ESTABLISHED,
                                 reasons=("missing policy/facts",))
    triggered = []
    for rule in policy:
        c = rule.get("condition") or {}
        slot = c.get("slot")
        if slot not in facts:
            continue                      # condition slot unknown: the
            #                                 rule cannot trigger
        if _cmp(c.get("op", "=="), facts[slot], c.get("value")):
            triggered.append(rule.get("rule"))
    derived = {"decision": "ESCALATE" if triggered else "PROCEED",
               "rules": triggered}
    stored_d = expected.get("decision")
    stored_r = expected.get("rules")
    why = []
    if stored_d != derived["decision"]:
        why.append(f"decision {stored_d!r} != "
                   f"{derived['decision']!r}")
    if sorted(stored_r or []) != sorted(triggered):
        why.append(f"rules {stored_r!r} != {triggered!r}")
    if why:
        return GroundTruthResult("", "", GroundTruthVerdict.INVALID,
                                 derived, reasons=tuple(why))
    return GroundTruthResult("", "", GroundTruthVerdict.VALID, derived,
                             verified_fields=("decision", "rules"))


def _c28(payload: dict, expected: dict) -> GroundTruthResult:
    doc = payload.get("document") or ""
    if not doc:
        return GroundTruthResult("", "", GroundTruthVerdict.NOT_ESTABLISHED,
                                 reasons=("missing document",))
    active = re.findall(
        r"(?:The active policy number is|(?:本账户)?当前生效的保单号是)"
        r"\s*(POL-\d+)", doc)
    if len(active) != 1:
        return GroundTruthResult(
            "", "", GroundTruthVerdict.NOT_ESTABLISHED, None,
            reasons=(f"active-policy sentence not uniquely derivable "
                     f"({len(active)} candidates)",))
    target = active[0]
    decoys = [v for v in re.findall(r"POL-\d+", doc) if v != target]
    derived = {"answer": target, "decoys": decoys}
    stored = expected.get("answer")
    con = expected.get("construction") or {}
    why = []
    if stored != target:
        why.append(f"stored answer {stored!r} != derived {target!r}")
    if con.get("target") is not None and con["target"] != target:
        why.append("construction target mismatch")
    if sorted(con.get("decoys") or []) != sorted(decoys):
        why.append("construction decoys mismatch")
    if why:
        return GroundTruthResult("", "", GroundTruthVerdict.INVALID,
                                 derived, reasons=tuple(why))
    return GroundTruthResult("", "", GroundTruthVerdict.VALID, derived,
                             verified_fields=("answer",))


def _c29(payload: dict, expected: dict) -> GroundTruthResult:
    request = (payload.get("request") or "").strip()
    rooms = payload.get("rooms") or []
    if not request or not rooms:
        return GroundTruthResult("", "", GroundTruthVerdict.NOT_ESTABLISHED,
                                 reasons=("missing request/rooms",))
    matches = [r.get("id") for r in rooms
               if str(r.get("desc", "")).strip() == request]
    if len(matches) == 0:
        return GroundTruthResult(
            "", "", GroundTruthVerdict.NOT_ESTABLISHED,
            {"matches": []},
            reasons=("no room description matches the request phrase",))
    if len(matches) > 1:
        derived = {"class": "AMBIGUOUS", "readings": matches}
    else:
        derived = {"class": "ANSWER", "answer": matches[0]}
    stored_c = expected.get("class")
    why = []
    if stored_c != derived["class"]:
        why.append(f"class {stored_c!r} != {derived['class']!r}")
    elif stored_c == "AMBIGUOUS" and \
            sorted(expected.get("readings") or []) != sorted(matches):
        why.append("ambiguous readings mismatch")
    elif stored_c == "ANSWER" and expected.get("answer") != matches[0]:
        why.append("answer id mismatch")
    if why:
        return GroundTruthResult("", "", GroundTruthVerdict.INVALID,
                                 derived, reasons=tuple(why))
    return GroundTruthResult("", "", GroundTruthVerdict.VALID, derived,
                             verified_fields=("class",))


# -- C30: bilingual canonical-operation derivation --------------------------
_C30_OPS = [
    # (EN pattern, ZH pattern, op name, extra builder)
    (re.compile(r"cancel order (\d+)", re.I),
     re.compile(r"取消订单(\d+)"), "cancel_order", None),
    (re.compile(r"move drawing ([A-Z]+-\d+) to (.+?)\.?$", re.I),
     re.compile(r"把图纸([A-Z]+-\d+)改到(.+?)。?$"), "reschedule", "_date"),
    (re.compile(r"raise the limit of account ([A-Z]+-\d+) to (\d+)",
                re.I),
     re.compile(r"把账户([A-Z]+-\d+)的限额提高到(\d+)"), "increase_limit",
     "_num"),
    (re.compile(r"flag parcel ([A-Z]+-\d+) as (\w+)", re.I),
     re.compile(r"将包裹([A-Z]+-\d+)标记为(\S+)。?$"), "flag", "_raw"),
    (re.compile(r"assign ticket ([A-Z]+-\d+) to the (\w+) queue", re.I),
     re.compile(r"把工单([A-Z]+-\d+)分到(\w+)队列。?$"), "assign",
     "_queue"),
]
_MONTHS = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"])}

#: canonical (EN) tokens for zh attribute words — the canonical_format
#: pins ids/numbers exact and the canonical vocabulary is English
_ZH_ATTR = {"易碎": "fragile"}
_ZH_QUEUE = {"计费": "billing"}


def _iso_date(text: str):
    t = text.strip().rstrip(".。")
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", t)
    if m:
        return m.group(0)
    m = re.match(r"(\w+) (\d{1,2}), (\d{4})$", t)
    if m and m.group(1).lower() in _MONTHS:
        return (f"{m.group(3)}-{_MONTHS[m.group(1).lower()]:02d}-"
                f"{int(m.group(2)):02d}")
    m = re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})日$", t)
    if m:
        return (f"{m.group(1)}-{int(m.group(2)):02d}-"
                f"{int(m.group(3)):02d}")
    return None


def _c30(payload: dict, expected: dict) -> GroundTruthResult:
    request = (payload.get("request") or "").strip()
    if not request:
        return GroundTruthResult("", "", GroundTruthVerdict.NOT_ESTABLISHED,
                                 reasons=("missing request",))
    canonical = None
    for en, zh, op, extra in _C30_OPS:
        m = en.search(request) or zh.search(request)
        if not m:
            continue
        groups = m.groups()
        if extra is None:
            canonical = f"{op}:{groups[0]}"
        elif extra == "_date":
            d = _iso_date(groups[1])
            if d is None:
                break
            canonical = f"{op}:{groups[0]}:{d}"
        elif extra == "_num":
            canonical = f"{op}:{groups[0]}:{int(groups[1])}"
        elif extra == "_raw":
            attr = groups[1].rstrip("。.")
            canonical = f"{op}:{groups[0]}:{_ZH_ATTR.get(attr, attr.lower())}"
        elif extra == "_queue":
            q = groups[1]
            canonical = f"{op}:{groups[0]}:queue-{_ZH_QUEUE.get(q, q.lower())}"
        break
    if canonical is None:
        return GroundTruthResult(
            "", "", GroundTruthVerdict.NOT_ESTABLISHED, None,
            reasons=(f"canonical operation not derivable from "
                     f"{request!r}",))
    stored = expected.get("canonical")
    if stored == canonical:
        return GroundTruthResult("", "", GroundTruthVerdict.VALID,
                                 {"canonical": canonical},
                                 verified_fields=("canonical",))
    return GroundTruthResult("", "", GroundTruthVerdict.INVALID,
                             {"canonical": canonical},
                             reasons=(f"stored {stored!r} != derived "
                                      f"{canonical!r}",))


# -- C31: per-claim required citations ---------------------------------------
_C31_CLAIM_TOPICS = [
    # claim keyword (bilingual) -> topic tag
    (("return", "退货"), "returns"),
    (("gift card", "礼品卡"), "giftcards"),
    (("warranty", "保修"), "warranty"),
    (("refund", "退款"), "refunds"),
    (("ship", "配送"), "shipping"),
    (("cancel", "取消"), "cancellation"),
]


def _c31_claims(question: str):
    parts = re.split(r"(?:, and |，|？|\? | and )", question)
    return [p.strip(" ，,?？.") for p in parts if p.strip(" ，,?？.")]


def _c31(payload: dict, expected: dict) -> GroundTruthResult:
    evid = payload.get("evidence") or []
    question = payload.get("question") or ""
    if not evid or not question:
        return GroundTruthResult("", "", GroundTruthVerdict.NOT_ESTABLISHED,
                                 reasons=("missing evidence/question",))
    q = question.lower()
    required = []
    for kws, _tag in _C31_CLAIM_TOPICS:
        if any(kw.lower() in q for kw in kws):
            for ev in evid:
                text = str(ev.get("text", "")).lower()
                if any(kw.lower() in text for kw in kws):
                    required.append(ev.get("id"))
    required = sorted(set(required))
    ids = [ev.get("id") for ev in evid]
    derived = {"required_citations": required, "evidence_ids": ids}
    stored = expected.get("required_citations") or []
    if sorted(stored) == required and set(required) <= set(ids):
        return GroundTruthResult("", "", GroundTruthVerdict.VALID,
                                 derived,
                                 verified_fields=("required_citations",))
    return GroundTruthResult(
        "", "", GroundTruthVerdict.INVALID, derived,
        reasons=(f"stored required citations {stored!r} != derived "
                 f"{required!r}",))


# -- C32: declared sufficiency ----------------------------------------------
def _c32(payload: dict, expected: dict) -> GroundTruthResult:
    evid = payload.get("evidence") or ""
    question = payload.get("question") or {}
    if not evid or not question:
        return GroundTruthResult("", "", GroundTruthVerdict.NOT_ESTABLISHED,
                                 reasons=("missing evidence/question",))
    q = question.get("en", "") + " " + str(question.get("zh", ""))
    ql = q.lower()
    asks_time = "what time" in ql or "几点" in q
    if asks_time:
        m = _TIME_RE.search(evid)
        if m:
            derived = {"output_class": "ANSWER", "answer": m.group(0)}
        else:
            derived = {"output_class": "ABSTAIN", "answer": None}
    else:
        return GroundTruthResult(
            "", "", GroundTruthVerdict.NOT_ESTABLISHED, None,
            reasons=(f"question fact type not derivable: {q[:40]!r}",))
    stored_c = expected.get("output_class")
    stored_a = expected.get("answer")
    why = []
    if stored_c != derived["output_class"]:
        why.append(f"output_class {stored_c!r} != "
                   f"{derived['output_class']!r}")
    if derived["output_class"] == "ANSWER" and stored_a != \
            derived["answer"]:
        why.append(f"answer {stored_a!r} != {derived['answer']!r}")
    if why:
        return GroundTruthResult("", "", GroundTruthVerdict.INVALID,
                                 derived, reasons=tuple(why))
    return GroundTruthResult("", "", GroundTruthVerdict.VALID, derived,
                             verified_fields=("output_class", "answer"))


_HANDLERS = {"C25": _c25, "C26": _c26, "C27": _c27, "C28": _c28,
             "C29": _c29, "C30": _c30, "C31": _c31, "C32": _c32}


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
                                 reasons=(f"primitive {prim} outside Batch D "
                                          "oracle scope",))
    r = handler(payload, expected)
    return GroundTruthResult(case.get("case_id", ""), prim, r.verdict,
                             r.recomputed, r.reasons, r.verified_fields,
                             r.unverified_fields)


# ---------------------------------------------------------------------------
# Obligation B
# ---------------------------------------------------------------------------
def _compare(prim: str, payload: dict, parsed, truth: dict) -> tuple:
    if prim == "C25":
        return (parsed == truth.get("decision")), (
            f"decision {parsed!r} != {truth.get('decision')!r}",)
    if prim == "C26":
        want_m = sorted(truth.get("missing") or [])
        got_m = sorted(parsed.get("missing") or [])
        if parsed.get("decision") != truth.get("decision"):
            return False, (f"decision {parsed.get('decision')!r} != "
                           f"{truth.get('decision')!r}",)
        if got_m != want_m:
            return False, (f"missing {got_m} != {want_m}",)
        return True, ()
    if prim == "C27":
        want_r = sorted(truth.get("rules") or [])
        got_r = sorted(parsed.get("rules") or [])
        if parsed.get("decision") != truth.get("decision"):
            return False, (f"decision {parsed.get('decision')!r} != "
                           f"{truth.get('decision')!r}",)
        if got_r != want_r:
            return False, (f"rules {got_r} != {want_r}",)
        return True, ()
    if prim == "C28":
        return (parsed == truth.get("answer")), (
            f"answer {parsed!r} != {truth.get('answer')!r}",)
    if prim == "C29":
        if truth.get("class") == "AMBIGUOUS":
            if parsed.get("class") != "AMBIGUOUS":
                return False, ("genuinely ambiguous request silently "
                               "disambiguated",)
            want = sorted(truth.get("readings") or [])
            got = sorted(parsed.get("readings") or [])
            return (got == want), (f"conflicting ids {got} != {want}",)
        if parsed.get("class") == "AMBIGUOUS":
            return False, ("over-flagging: the request resolves uniquely",)
        return (parsed.get("answer") == truth.get("answer")), (
            f"answer {parsed.get('answer')!r} != "
            f"{truth.get('answer')!r}",)
    if prim == "C30":
        return (parsed == truth.get("canonical")), (
            f"canonical {parsed!r} != {truth.get('canonical')!r}",)
    if prim == "C31":
        ids = set(truth.get("evidence_ids") or [])
        required = set(truth.get("required_citations") or [])
        cited = set(parsed.get("citations") or [])
        phantom = cited - ids
        if phantom:
            return False, (f"phantom citations {sorted(phantom)}",)
        missing = required - cited
        if missing:
            return False, (f"claims left uncited: {sorted(missing)}",)
        return True, ()
    if prim == "C32":
        if truth.get("output_class") == "ABSTAIN":
            if parsed.get("class") == "ABSTAIN":
                return True, ()
            return False, ("confident answer where the evidence lacks "
                           "the fact (must ABSTAIN)",)
        if parsed.get("class") == "ABSTAIN":
            return False, ("over-abstention: the evidence contains the "
                           "fact",)
        return (parsed.get("answer") == truth.get("answer")), (
            f"answer {parsed.get('answer')!r} != "
            f"{truth.get('answer')!r}",)
    return False, (f"primitive {prim} outside Batch D comparison scope",)


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
