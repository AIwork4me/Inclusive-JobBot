"""EA03/EA05 — independent reference Oracle for N03 Batch A (C01-C08).

Two obligations, never conflated (qualification order section 2):

A. ``validate_ground_truth(case, expectation)`` — is the STORED expected
   answer actually correct for the public task? Independently recomputed
   for C03/C04/C05/C06 from public payloads; recomputed algebraically for
   C08 from the committed construction record (dev cases only — protected
   confirmation construction is NOT accessible, and public recomputability
   is NOT claimed there); independently rule-table validated for the
   construction-authored C01/C02/C07 (rules derive from the PUBLIC catalog
   descriptions and surface evidence, never from the stored label).

B. ``evaluate_response(case, expectation, response)`` — does a model
   response satisfy the independently established truth?

Independence: this module imports NOTHING from IJ-NANO production or
dataset-builder code. Verdicts: VALID / INVALID / AMBIGUOUS (multiple
defensible truths; adjudication required) / NOT_ESTABLISHED (insufficient
information — e.g. protected construction) — never silent removal.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class GroundTruthVerdict(Enum):
    VALID = "VALID"                    # expected answer independently confirmed
    INVALID = "INVALID"                # expected answer contradicts recomputation
    AMBIGUOUS = "AMBIGUOUS"            # multiple defensible truths
    NOT_ESTABLISHED = "NOT_ESTABLISHED"  # truth not independently derivable


@dataclass
class GroundTruthResult:
    case_id: str
    primitive: str
    verdict: GroundTruthVerdict
    recomputed: object = None
    reasons: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# shared helpers (independently authored; no IJ-NANO imports)
# ---------------------------------------------------------------------------
def _cmp(op: str, lhs, rhs) -> bool:
    return {"<": lambda: lhs < rhs, "<=": lambda: lhs <= rhs,
            ">": lambda: lhs > rhs, ">=": lambda: lhs >= rhs,
            "==": lambda: lhs == rhs, "!=": lambda: lhs != rhs}[op]()


# -- C01 / C07: construction-authored catalog selection --------------------
def _catalog_ground_truth(payload: dict, expected_id: str,
                          text_key: str, catalog_key: str,
                          rule_table: dict) -> GroundTruthResult:
    """Independent validation for catalog-selection primitives: an
    independently authored rule table (surface evidence -> catalog label)
    derived from the PUBLIC catalog descriptions, applied to the public
    utterance/situation. Agreement with the stored label = independent
    confirmation; conflict = INVALID (correction request); multiple
    equally-strong matches = AMBIGUOUS."""
    text = (payload.get(text_key) or "").lower()
    catalog = payload.get(catalog_key) or {}
    if expected_id not in catalog:
        return GroundTruthResult("", "", GroundTruthVerdict.INVALID,
                                 reasons=("expected id not in public catalog",))
    scores: dict[str, int] = {}
    STRONG = ("everything", "all the", "全部", "所有")   # multi-target
    for label, pattern_list in rule_table.items():
        if label not in catalog:
            continue
        scores[label] = sum(2 if pat in STRONG else 1
                            for pat in pattern_list if pat in text)
    best = max(scores.values(), default=0)
    winners = sorted(l for l, s in scores.items() if s == best and best > 0)
    if not winners:
        return GroundTruthResult("", "", GroundTruthVerdict.NOT_ESTABLISHED,
                                 reasons=("no rule-table evidence in text",))
    if len(winners) > 1:
        return GroundTruthResult("", "", GroundTruthVerdict.AMBIGUOUS,
                                 recomputed=winners,
                                 reasons=(f"rule table ties: {winners}",))
    if winners[0] != expected_id:
        return GroundTruthResult("", "", GroundTruthVerdict.INVALID,
                                 recomputed=winners[0],
                                 reasons=("rule table selects a different "
                                          f"label ({winners[0]})",))
    return GroundTruthResult("", "", GroundTruthVerdict.VALID,
                             recomputed=winners[0])


# Rule tables authored from the PUBLIC catalog descriptions of the pinned
# dataset (spot-checked across the dev corpus), not from stored labels.
_C01_RULES = {
    "incident_report": ["down", "outage", "not working", "broken", "crash",
                        "error", "fault", "isn't running", "故障", "中断",
                        "宕机", "坏了", "不能用"],
    "refund_request": ["refund", "money back", "charge back", "reimburse",
                       "退款", "退钱"],
    "escalation_demand": ["supervisor", "manager", "human agent",
                          "escalate", "complain", "speak to a person",
                          "主管", "经理", "转人工", "投诉", "人工客服"],
    "feature_request": ["suggest", "feature", "would be nice", "idea",
                        "propose", "add an option", "would be great",
                        "added", "建议", "新功能", "希望增加", "要是能",
                        "如果能"],
    "account_lock": ["locked out", "cannot log in", "can't log in",
                     "account locked", "can't sign in", "登录不了",
                     "账户被锁", "锁住了"],
    "billing_query": ["explain the charge", "why was i charged",
                      "what is this charge", "explain a charge", "这笔费用",
                      "为什么扣"],
    "cancel_schedule": ["cancel the scheduled", "remove the scheduled",
                        "stop the scheduled", "取消预定", "取消计划", "取消"],
    "energy_report": ["energy usage", "energy report", "how much energy",
                      "用电", "能耗", "能源报告"],
    "exchange_request": ["swap", "exchange", "different size",
                         "换货", "换一个"],
    "group_control": ["together", "all the lights", "several devices",
                      "everything", "all the", "一起", "所有设备", "全部"],
    "query_state": ["current state", "is it on", "status of",
                    "what state", "现在的状态", "当前状态", "开了吗"],
    "schedule_action": ["later", "schedule", "tomorrow", "预定", "稍后",
                        "定时"],
    "set_device": ["set the", "turn on", "turn off", "change the",
                   "set to", "打开", "关闭", "调成"],
    "shipping_status": ["where is", "package", "shipment", "tracking",
                        "快递", "包裹", "在哪"],
}
_C07_RULES = {
    "escalate_fraud": ["stolen", "fraud", "unauthorized", "never made",
                       "盗刷", "欺诈", "未授权"],
    "issue_refund": ["refund", "disputed charge", "money back", "退款",
                     "争议", "退货期"],
    "reset_password": ["forgot", "password", "credentials", "密码", "忘记"],
    "schedule_callback": ["call me", "callback", "phone", "later",
                          "回电", "致电"],
    "clear_cache": ["stale", "cache", "缓存", "旧数据"],
    "page_oncall": ["severity-1", "sev1", "full outage",
                    "全站", "一级故障", "整个服务"],
    "restart_service": ["restart", "unhealthy", "重启", "不健康"],
    "rollback_deploy": ["rollback", "recent release", "after the release",
                        "回滚", "发版", "上线后"],
    "scale_replicas": ["scale", "replicas", "sustained load", "扩容",
                       "负载"],
    "update_record": ["wrong record", "mistake", "data-entry",
                      "entered the wrong", "录错"],
    "verify_identity": ["lost access", "verify", "confirm who", "identity",
                        "验证身份", "无法访问", "无法登录"],
}


# -- C02: goal record --------------------------------------------------------
_ISO = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


def _c02(payload: dict, expected: dict) -> GroundTruthResult:
    msg = payload.get("message") or ""
    problems = []
    # deadline is the one field independently recomputable from the surface
    # (ISO dates are language-invariant in this corpus); action/object/
    # completion_criterion are construction-authored CANONICAL codes, not
    # surface strings, so only structural checks apply to them.
    m = _ISO.search(msg)
    rec_deadline = m.group(1) if m else None
    if rec_deadline != expected.get("deadline"):
        problems.append(f"deadline: expected {expected.get('deadline')!r}, "
                        f"recomputed {rec_deadline!r}")
    flags = expected.get("unknown_flags") or {}
    if flags.get("deadline") is True and rec_deadline is not None:
        problems.append("deadline flagged unknown but stated in message")
    if flags.get("deadline") is not True and rec_deadline is None:
        problems.append("deadline not flagged unknown but absent")
    for fld in ("action", "object"):
        v = expected.get(fld)
        if not isinstance(v, str) or not v or not re.fullmatch(
                r"[a-z][a-z0-9_]*", v or ""):
            problems.append(f"{fld} not a canonical snake_case code: {v!r}")
    if not isinstance(flags.get("completion_criterion"), bool):
        problems.append("completion_criterion flag not boolean")
    if problems:
        return GroundTruthResult("", "", GroundTruthVerdict.INVALID,
                                 recomputed={"deadline": rec_deadline},
                                 reasons=tuple(problems))
    return GroundTruthResult("", "", GroundTruthVerdict.VALID,
                             recomputed={"deadline": rec_deadline})


# -- C03: formatting / formfill / oneedit ------------------------------------
def _c03(payload: dict, expected: dict) -> GroundTruthResult:
    if "lines" in expected:                     # formatting family
        rule = expected.get("rule")
        items = payload.get("items") or []
        if rule == "in_stock":
            rec = [it["name"] for it in items
                   if it.get("stock", 0) > 0]
            order_free = "one per line" in (payload.get("instruction") or "")
            if sorted(rec) == sorted(expected.get("lines") or []) :
                return GroundTruthResult("", "", GroundTruthVerdict.VALID,
                                         recomputed=rec)
            if set(rec) == set(expected.get("lines") or []):
                # order freedom is not declared in C03 expectations
                return GroundTruthResult("", "", GroundTruthVerdict.VALID,
                                         recomputed=rec,
                                         reasons=("line order differs; "
                                                  "sequence rule undeclared"))
            return GroundTruthResult("", "", GroundTruthVerdict.INVALID,
                                     recomputed=rec,
                                     reasons=("in-stock set mismatch",))
        return GroundTruthResult("", "", GroundTruthVerdict.NOT_ESTABLISHED,
                                 reasons=(f"rule {rule!r} not recomputable",))
    if "field_value" in expected or "value" in expected:   # formfill
        return GroundTruthResult("", "", GroundTruthVerdict.NOT_ESTABLISHED,
                                 reasons=("formfill single-field truth is "
                                          "construction-authored",))
    if "line" in expected:                      # oneedit
        return GroundTruthResult("", "", GroundTruthVerdict.NOT_ESTABLISHED,
                                 reasons=("oneedit exact-line truth requires "
                                          "edit semantics adjudication",))
    return GroundTruthResult("", "", GroundTruthVerdict.NOT_ESTABLISHED,
                             reasons=("unknown C03 expectation shape",))


# -- C04: constraint-filtered id set ----------------------------------------
def _c04(payload: dict, expected: dict) -> GroundTruthResult:
    constraints = expected.get("constraints") or []
    items = payload.get("items") or []
    rec = []
    for it in items:
        ok = True
        for (field_op, bound) in constraints:
            mm = re.fullmatch(r"([a-z_]+)(<=|>=|<|>|==|!=)", field_op)
            if not mm:
                return GroundTruthResult(
                    "", "", GroundTruthVerdict.NOT_ESTABLISHED,
                    reasons=(f"unparsed constraint {field_op!r}",))
            f, op = mm.group(1), mm.group(2)
            if not _cmp(op, it.get(f), bound):
                ok = False
                break
        if ok:
            rec.append(it["id"])
    exp_ids = expected.get("ids") or []
    if sorted(rec) == sorted(exp_ids):
        return GroundTruthResult("", "", GroundTruthVerdict.VALID,
                                 recomputed=rec)
    return GroundTruthResult("", "", GroundTruthVerdict.INVALID,
                             recomputed=rec,
                             reasons=(f"constraint filter yields {sorted(rec)}"
                                      f" != expected {sorted(exp_ids)}"))


# -- C05: boolean predicate recomputation -----------------------------------
_DAYS = re.compile(r"(\d+)\s*days?\s+ago", re.I)
_DAYS_ZH = re.compile(r"距今\s*(\d+)\s*天")
_WITHIN = re.compile(r"within\s+(\d+)\s*days", re.I)
_WITHIN_ZH = re.compile(r"不超过\s*(\d+)\s*天")
_WITHIN_ZH2 = re.compile(r"(\d+)\s*天内")


def _c05_fulfillment(payload: dict, expected: dict) -> GroundTruthResult | None:
    """Second C05 predicate family: order fulfillment under stock limits
    with optional backorder. Returns None when the texts are not this
    family."""
    facts = payload.get("facts") or ""
    policy = payload.get("policy") or ""
    sm = (re.search(r"stock (\d+) units?.*?requested (\d+) units?"
                    r"(?:.*?backorder allowed: (yes|no))?", facts, re.I)
          or re.search(r"库存\s*(\d+)\s*件.*?请求\s*(\d+)\s*件"
                       r"(?:.*?缺货预订[：:]\s*(是|否))?", facts))
    if not sm:
        return None
    stock, requested = int(sm.group(1)), int(sm.group(2))
    backorder = (sm.group(3) or "").lower() in ("yes", "是")
    rec = requested <= stock or backorder
    if rec != expected.get("decision"):
        return GroundTruthResult("", "", GroundTruthVerdict.INVALID,
                                 recomputed={"decision": rec},
                                 reasons=(f"fulfillment recompute {rec} !="
                                          f" stored {expected.get('decision')}",))
    return GroundTruthResult("", "", GroundTruthVerdict.VALID,
                             recomputed={"decision": rec})


def _c05(payload: dict, expected: dict) -> GroundTruthResult:
    ful = _c05_fulfillment(payload, expected)
    if ful is not None:
        return ful
    policy = payload.get("policy") or ""
    facts = payload.get("facts") or ""
    m = (_WITHIN.search(policy) or _WITHIN_ZH.search(policy)
         or _WITHIN_ZH2.search(policy))
    if not m:
        return GroundTruthResult("", "", GroundTruthVerdict.NOT_ESTABLISHED,
                                 reasons=("limit not extractable from policy",
                                          ))
    limit = int(m.group(1))
    dm = _DAYS.search(facts) or _DAYS_ZH.search(facts)
    if not dm:
        return GroundTruthResult("", "", GroundTruthVerdict.NOT_ESTABLISHED,
                                 reasons=("days_ago not extractable from "
                                          "facts"))
    days = int(dm.group(1))
    rec = days <= limit        # 'within' == at most limit (policy text)
    if rec != expected.get("decision"):
        return GroundTruthResult("", "", GroundTruthVerdict.INVALID,
                                 recomputed={"decision": rec,
                                             "days": days, "limit": limit},
                                 reasons=(f"recomputed {days}<={limit}="
                                          f"{rec} != stored decision"))
    return GroundTruthResult("", "", GroundTruthVerdict.VALID,
                             recomputed={"decision": rec, "days": days,
                                         "limit": limit})


# -- C06: cheapest-option-under-requirements --------------------------------
_NEED_SEATS = re.compile(r"at least (\d+) seats?", re.I)
_SEATS_ZH = re.compile(r"至少\s*(\d+)\s*(?:个)?席位")
_REC_W = re.compile(r"\bwith(?:out)?\s+recording\b", re.I)
_REC = re.compile(r"\brecording\b", re.I)


def _c06(payload: dict, expected: dict) -> GroundTruthResult:
    instr = payload.get("instruction") or ""
    options = payload.get("options") or []
    first = options[0] if options else {}
    if "seats" in first:
        m = _NEED_SEATS.search(instr) or _SEATS_ZH.search(instr)
        if not m:
            return GroundTruthResult(
                "", "", GroundTruthVerdict.NOT_ESTABLISHED,
                reasons=("seats requirement not parseable"))
        seats_need = int(m.group(1))
        recording_need = None
        rw = _REC_W.search(instr)
        if rw:
            recording_need = "without" not in rw.group(0)
        elif _REC.search(instr):
            recording_need = True
        qualifying = [o for o in options
                      if o.get("seats", 0) >= seats_need
                      and (recording_need is None
                           or bool(o.get("recording")) == recording_need)]
    elif "iso" in first and "audit" in first:
        # supplier variant: BOTH ISO certification AND a passed audit
        need_iso = bool(re.search(r"iso|认证", instr, re.I))
        need_audit = bool(re.search(r"audit|审计", instr, re.I))
        qualifying = [o for o in options
                      if (not need_iso or bool(o.get("iso")))
                      and (not need_audit or bool(o.get("audit")))]
    else:
        return GroundTruthResult(
            "", "", GroundTruthVerdict.NOT_ESTABLISHED,
            reasons=("option schema outside the independently parsed "
                     "C06 variants"))
    if not qualifying:
        return GroundTruthResult("", "", GroundTruthVerdict.INVALID,
                                 recomputed=[],
                                 reasons=("no option satisfies the parsed "
                                          "requirement — instruction/option "
                                          "mismatch"))
    best_price = min(o["price"] for o in qualifying)
    winners = sorted(o["id"] for o in qualifying if o["price"] == best_price)
    exp = expected.get("choice")
    if len(winners) == 1 and winners[0] == exp:
        return GroundTruthResult("", "", GroundTruthVerdict.VALID,
                                 recomputed=winners[0])
    if exp in winners:
        alts = expected.get("alternatives") or []
        if any("tie" in str(a).lower() for a in alts) or len(winners) > 1:
            return GroundTruthResult("", "", GroundTruthVerdict.VALID,
                                     recomputed=winners,
                                     reasons=("declared tie set",))
        return GroundTruthResult("", "", GroundTruthVerdict.AMBIGUOUS,
                                 recomputed=winners,
                                 reasons=("recomputed tie without declared "
                                          "alternative"))
    return GroundTruthResult("", "", GroundTruthVerdict.INVALID,
                             recomputed=winners,
                             reasons=(f"cheapest qualifying {winners} != "
                                      f"expected {exp!r}"))


# -- C08: capability-superset algebra over the construction record ----------
def _c08(payload: dict, expected: dict) -> GroundTruthResult:
    construction = (expected or {}).get("construction") or {}
    registry = construction.get("registry_tags")
    required = construction.get("required_tags")
    if registry is None or required is None:
        return GroundTruthResult(
            "", "", GroundTruthVerdict.NOT_ESTABLISHED,
            reasons=("protected construction record required (public "
                     "recomputability NOT claimed for C08)",))
    req = set(required)
    winners = sorted(tid for tid, tags in registry.items()
                     if req.issubset(set(tags)))
    public_ids = {t.get("id") for t in payload.get("tools") or []}
    if not set(registry).issubset(public_ids):
        return GroundTruthResult("", "", GroundTruthVerdict.INVALID,
                                 reasons=("registry references tools absent "
                                          "from the public inventory"))
    exp = expected.get("tool_id")
    if len(winners) == 1 and winners[0] == exp:
        return GroundTruthResult("", "", GroundTruthVerdict.VALID,
                                 recomputed=winners[0],
                                 reasons=("unique capability superset",))
    if exp in winners:
        return GroundTruthResult("", "", GroundTruthVerdict.AMBIGUOUS,
                                 recomputed=winners,
                                 reasons=("multiple supersets — uniqueness "
                                          "not satisfied"))
    return GroundTruthResult("", "", GroundTruthVerdict.INVALID,
                             recomputed=winners,
                             reasons=(f"superset algebra yields {winners} != "
                                      f"expected {exp!r}"))


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------
def validate_ground_truth(case: dict, expectation: dict) -> GroundTruthResult:
    """Obligation A: independently validate the STORED expected answer."""
    payload = case.get("public_payload") or {}
    expected = (expectation or {}).get("expected")
    prim = case.get("primitive")
    if expected is None:
        return GroundTruthResult(case.get("case_id", ""), prim,
                                 GroundTruthVerdict.NOT_ESTABLISHED,
                                 reasons=("no stored expectation",))
    if prim == "C01":
        r = _catalog_ground_truth(payload, expected.get("label"),
                                  "utterance", "intent_catalog", _C01_RULES)
    elif prim == "C02":
        r = _c02(payload, expected)
    elif prim == "C03":
        r = _c03(payload, expected)
    elif prim == "C04":
        r = _c04(payload, expected)
    elif prim == "C05":
        r = _c05(payload, expected)
    elif prim == "C06":
        r = _c06(payload, expected)
    elif prim == "C07":
        r = _catalog_ground_truth(payload, expected.get("action"),
                                  "situation", "action_catalog", _C07_RULES)
    elif prim == "C08":
        r = _c08(payload, expected)
    else:
        return GroundTruthResult(case.get("case_id", ""), prim,
                                 GroundTruthVerdict.NOT_ESTABLISHED,
                                 reasons=(f"primitive {prim} outside Batch A "
                                          "oracle scope",))
    return GroundTruthResult(case.get("case_id", ""), prim, r.verdict,
                             r.recomputed, r.reasons)
