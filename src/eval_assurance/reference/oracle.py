"""EA03/EA05 — independent reference Oracle for N03 Batch A (C01-C08).

Two obligations, never conflated (qualification order section 2):

A. ``validate_ground_truth(case, expectation)`` — is the STORED expected
   answer actually correct for the public task? Every field is derived from
   the PUBLIC payload (message / instruction / items / options / tool
   descriptions) under the parser-semantics contract; stored construction
   metadata is CROSS-CHECKED, never used as the truth authority:

   - C02: action / object / deadline / completion_criterion / unknown_flags
     all independently derived from the public message; required-field
     presence (exactly the declared ``schema_fields``) enforced; partial
     derivation is reported as NOT_ESTABLISHED (field-level), never
     promoted to VALID (GT-D01).
   - C03: formatting rules (in_stock / not_in_stock / *_upper) parsed from
     the public instruction, lines recomputed in payload order, sequence
     vs set semantics distinguished; formfill field+value derived from the
     public instruction and message (GT-D05).
   - C04: constraints AND sort order parsed from the public instruction
     (operators, thresholds, stock conditions, vendor exclusions, sort key
     and direction, both languages); stored ``constraints``/``order`` are
     cross-checked metadata, and the id set/sequence is recomputed from the
     parsed constraints — a coupled corruption of stored constraints+ids
     cannot validate (GT-D02).
   - C05: boolean predicates recomputed from public policy+facts, stored
     construction record cross-checked.
   - C06: seats / recording / ISO / audit requirements parsed from the
     public instruction (explicit inclusion AND exclusion, both languages);
     cheapest qualifying recomputed; undeclared ties are AMBIGUOUS, never
     automatically VALID (GT-D03).
   - C07: independently authored rule table over the public utterance and
     catalog (surface evidence -> catalog label), never the stored label.
   - C08: required capability tags derived from the PUBLIC objective and
     per-tool tags from the PUBLIC tool descriptions (bilingual capability
     lexicon with negation guards); the stored construction record must
     match the public derivation exactly — coupled mutations of required
     tags / registry tags / expected tool id are detected (GT-D04).
   - C01: independently authored rule table over the public utterance and
     catalog.

B. ``evaluate_response(case, expectation, response)`` — does a model
   response satisfy the independently established truth? Only VALID ground
   truth supports qualified response evaluation; anything else is
   NOT_EVALUABLE. Software errors are never model failures.

Independence: this module imports NOTHING from IJ-NANO production or
dataset-builder code. Verdicts: VALID / INVALID / AMBIGUOUS (multiple
defensible truths; adjudication required) / NOT_ESTABLISHED (insufficient
information) — never silent removal.
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
    verified_fields: tuple[str, ...] = ()    # fields independently derived+compared
    unverified_fields: tuple[str, ...] = ()  # fields not independently derivable


# ---------------------------------------------------------------------------
# shared helpers (independently authored; no IJ-NANO imports)
# ---------------------------------------------------------------------------
def _cmp(op: str, lhs, rhs) -> bool:
    return {"<": lambda: lhs < rhs, "<=": lambda: lhs <= rhs,
            ">": lambda: lhs > rhs, ">=": lambda: lhs >= rhs,
            "==": lambda: lhs == rhs, "!=": lambda: lhs != rhs}[op]()


def _snake(text: str) -> str:
    """Canonical snake_case normalization declared by the C02 contract."""
    return re.sub(r"[\s\-]+", "_", text.strip().lower()).strip("_")


# -- C01 / C07: construction-authored catalog selection --------------------
def _catalog_ground_truth(payload: dict, expected_id: str,
                          text_key: str, catalog_key: str,
                          rule_table: dict,
                          veto_table: dict | None = None) -> GroundTruthResult:
    """Independent validation for catalog-selection primitives: an
    independently authored rule table (surface evidence -> catalog label)
    derived from the PUBLIC catalog descriptions, applied to the public
    utterance/situation. A NEGATION VETO table removes labels whose
    evidence is explicitly negated by the surface (e.g. "no deploy
    happened" vetoes rollback). Agreement with the stored label =
    independent confirmation; conflict = INVALID (correction request);
    multiple equally-strong matches = AMBIGUOUS."""
    text = (payload.get(text_key) or "").lower()
    catalog = payload.get(catalog_key) or {}
    veto_table = veto_table or {}
    if expected_id not in catalog:
        return GroundTruthResult("", "", GroundTruthVerdict.INVALID,
                                 reasons=("expected id not in public catalog",))
    scores: dict[str, int] = {}
    STRONG = ("everything", "all the", "all the lights", "全部", "所有",
              "所有灯", "several devices", "together")   # multi-target
    for label, pattern_list in rule_table.items():
        if label not in catalog:
            continue
        if any(neg in text for neg in veto_table.get(label, ())):
            scores[label] = -1               # negated evidence: cannot win
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
                      "how much power", "用电", "能耗", "能源报告", "电量",
                      "耗电"],
    "exchange_request": ["swap", "exchange", "different size",
                         "换货", "换一个"],
    "group_control": ["together", "all the lights", "several devices",
                      "everything", "all the", "一起", "所有设备", "全部",
                      "所有灯"],
    "query_state": ["current state", "is it on", "on right now",
                    "status of", "what state", "现在的状态", "当前状态",
                    "开了吗", "现在开着"],
    "schedule_action": ["later", "schedule", "tomorrow", "预定", "稍后",
                        "定时"],
    "set_device": ["set the", "turn on", "turn off", "change the",
                   "set to", "打开", "关闭", "调成", "调到", "调至"],
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
    "clear_cache": ["stale", "cache", "see yesterday", "yesterday's homepage",
                    "看到的是昨天", "昨天的首页", "缓存", "旧数据"],
    "page_oncall": ["severity-1", "sev1", "full outage",
                    "全站", "一级故障", "整个服务"],
    "restart_service": ["restart", "unhealthy", "hanging", "hangs",
                        "无响应", "不响应", "卡死", "重启", "不健康"],
    "rollback_deploy": ["rollback", "release", "deploy", "发版", "上线后",
                        "发布", "发布后", "回滚", "error rates", "错误率",
                        "飙升"],
    "scale_replicas": ["scale", "replicas", "sustained load", "扩容",
                       "负载", "pinned at", "cpu", "95%", "持续一小时",
                       "for an hour"],
    "update_record": ["wrong record", "mistake", "data-entry",
                      "entered the wrong", "录错"],
    "verify_identity": ["lost access", "verify", "confirm who", "identity",
                        "验证身份", "无法访问", "无法登录"],
}
# explicit surface negation -> label veto (the distractor guard)
_C07_VETOES = {
    "rollback_deploy": ["no deploy", "no recent deploy", "no release",
                        "没有发布", "未发布", "没有发版", "没有上线"],
    "restart_service": ["healthy", "本身健康", "服务正常"],
}


# -- C02: goal record (GT-D01: FULL field-level semantic derivation) --------
_ISO = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_C02_EN_VERB = re.compile(r"(?:please|could you)\s+([a-z]+)\b", re.I)
_C02_EN_OBJECT = re.compile(
    r"\bthe\s+(.+?)(?=\s+by\b|\s+when\b|[.,。]|$)", re.I)
_C02_CC_SPLIT = re.compile(r"Completion means|完成标准是", re.I)
# zh surface lexicons are scoped to the public corpus vocabulary; an
# unknown zh phrase is honestly reported as not independently derivable.
_C02_ZH_ACTIONS = {"迁移": "migrate", "提交": "submit", "审批": "approve",
                   "评审": "review", "归档": "archive"}
_C02_ZH_OBJECTS = {"季度报告": "quarterly_report", "入职指南": "onboarding_guide",
                   "审计记录": "audit_trail", "数据导出": "data_export",
                   "价格表": "pricing_sheet"}
_C02_CC_PHRASES = {  # completion-criterion surface -> canonical code
    "visible in the system": "visible_in_system",
    "能在系统里看到": "visible_in_system",
}


def _c02_derive(msg: str) -> dict:
    """Derive every C02 goal field from the public message alone."""
    derived: dict = {}
    unverified: list[str] = []
    # goal clause = message before the completion-criterion sentence
    goal_clause = _C02_CC_SPLIT.split(msg, maxsplit=1)[0]
    # deadline: ISO dates are language-invariant surfaces.
    iso = _ISO.findall(goal_clause)
    if len(iso) == 1:
        derived["deadline"] = iso[0]
    elif len(iso) > 1:
        unverified.append("deadline")        # ambiguous surface
    else:
        derived["deadline"] = None
    # action
    en_v = _C02_EN_VERB.findall(goal_clause)
    zh_v = sorted({code for pat, code in _C02_ZH_ACTIONS.items()
                   if pat in goal_clause})
    if len(en_v) == 1 and not zh_v:
        derived["action"] = _snake(en_v[0])
    elif len(zh_v) == 1 and not en_v:
        derived["action"] = zh_v[0]
    else:
        unverified.append("action")
    # object (en: mechanical phrase normalization; zh: corpus lexicon)
    en_o = _C02_EN_OBJECT.findall(goal_clause)
    zh_o = sorted({code for pat, code in _C02_ZH_OBJECTS.items()
                   if pat in goal_clause})
    if len(en_o) == 1 and not zh_o:
        derived["object"] = _snake(en_o[0])
    elif len(zh_o) == 1 and not en_o:
        derived["object"] = zh_o[0]
    else:
        unverified.append("object")
    # completion criterion
    cc = [code for pat, code in _C02_CC_PHRASES.items() if pat in msg.lower()]
    if len(cc) == 1:
        derived["completion_criterion"] = cc[0]
    elif len(cc) > 1:
        unverified.append("completion_criterion")
    else:
        derived["completion_criterion"] = None
    # unknown flags follow nullness by the declared contract
    derived["unknown_flags"] = {
        "deadline": derived.get("deadline") is None
        if "deadline" in derived else None,
        "completion_criterion":
            derived.get("completion_criterion") is None
            if "completion_criterion" in derived else None,
    }
    if unverified:
        for f in ("deadline", "completion_criterion"):
            if f in unverified:
                derived["unknown_flags"][f] = None
    return {"derived": derived, "unverified": unverified}


def _c02(payload: dict, expected: dict) -> GroundTruthResult:
    msg = payload.get("message") or ""
    problems = []
    schema_fields = payload.get("schema_fields") or [
        "action", "object", "deadline", "completion_criterion",
        "unknown_flags"]
    # required field presence / unexpected additional fields (GT-D01)
    exp_keys = set(expected or {})
    for req in schema_fields:
        if req not in exp_keys:
            problems.append(f"required field missing: {req}")
    for extra in sorted(exp_keys - set(schema_fields)):
        problems.append(f"unexpected additional field: {extra}")
    der = _c02_derive(msg)
    derived, unverified = der["derived"], der["unverified"]
    verified: list[str] = []
    for fld in ("action", "object", "deadline", "completion_criterion"):
        if fld in derived:
            got = expected.get(fld)
            want = derived[fld]
            if got != want:
                problems.append(f"{fld}: expected {got!r}, independently "
                                f"derived {want!r}")
            else:
                verified.append(fld)
        elif fld not in problems:
            unverified.append(fld) if fld not in unverified else None
    # unknown flags (compared only when the paired field was derived)
    exp_flags = expected.get("unknown_flags")
    if not isinstance(exp_flags, dict):
        problems.append("unknown_flags not an object")
    else:
        flag_keys = set(exp_flags)
        for f in sorted(flag_keys - {"deadline", "completion_criterion"}):
            problems.append(f"unexpected unknown_flag key: {f}")
        for f in ("deadline", "completion_criterion"):
            if f in derived and derived["unknown_flags"].get(f) is not None:
                want = derived["unknown_flags"][f]
                if exp_flags.get(f) != want:
                    problems.append(
                        f"unknown_flags.{f}: expected "
                        f"{exp_flags.get(f)!r}, derived {want!r} "
                        f"(field is {'absent' if want else 'stated'})")
                else:
                    verified.append(f"unknown_flags.{f}")
    if problems:
        return GroundTruthResult(
            "", "", GroundTruthVerdict.INVALID, recomputed=derived,
            reasons=tuple(problems), verified_fields=tuple(verified),
            unverified_fields=tuple(unverified))
    if unverified:
        # partial semantic validation is NOT complete truth (GT-D01)
        return GroundTruthResult(
            "", "", GroundTruthVerdict.NOT_ESTABLISHED, recomputed=derived,
            reasons=(f"field-level partial validation only; not "
                     f"independently derivable: {sorted(set(unverified))}",),
            verified_fields=tuple(verified),
            unverified_fields=tuple(sorted(set(unverified))))
    return GroundTruthResult("", "", GroundTruthVerdict.VALID,
                             recomputed=derived,
                             verified_fields=tuple(verified))


# -- C03: formatting / formfill / oneedit (GT-D05) ---------------------------
_C03_IN_STOCK_EN = re.compile(r"\bin[- ]stock\b", re.I)
_C03_NOT_STOCK_EN = re.compile(r"\bnot in[- ]stock\b|\bout of stock\b", re.I)
_C03_NOT_STOCK_ZH = re.compile(r"没有库存|不在库存|无库存")
_C03_IN_STOCK_ZH = re.compile(r"有库存")
_C03_UPPER = re.compile(r"uppercase|全大写|大写", re.I)


def _c03_formatting(payload: dict, expected: dict) -> GroundTruthResult:
    instr = payload.get("instruction") or ""
    items = payload.get("items") or []
    problems = []
    # polarity from the PUBLIC instruction
    if _C03_NOT_STOCK_EN.search(instr) or _C03_NOT_STOCK_ZH.search(instr):
        want_in_stock = False
    elif _C03_IN_STOCK_EN.search(instr) or _C03_IN_STOCK_ZH.search(instr):
        want_in_stock = True
    else:
        return GroundTruthResult(
            "", "", GroundTruthVerdict.NOT_ESTABLISHED,
            reasons=("stock predicate not parseable from instruction",))
    upper = bool(_C03_UPPER.search(instr))
    rule = ("not_in_stock" if not want_in_stock else "in_stock")
    if upper:
        rule += "_upper"
    if expected.get("rule") != rule:
        problems.append(f"stored rule {expected.get('rule')!r} contradicts "
                        f"instruction-derived rule {rule!r}")
    lines = [it["name"].upper() if upper else it["name"]
             for it in items if bool(it.get("stock", 0) > 0) == want_in_stock]
    exp_lines = expected.get("lines") or []
    if lines == exp_lines:
        verdict = GroundTruthVerdict.VALID
    elif sorted(lines) == sorted(exp_lines):
        # sequence equality is not set equality when ordering matters
        # (GT-D05): order freedom is not declared in C03 expectations.
        verdict = GroundTruthVerdict.AMBIGUOUS
        problems.append("line set matches but sequence differs; ordering "
                        "freedom not declared by the expectation contract")
    else:
        verdict = GroundTruthVerdict.INVALID
        problems.append(f"recomputed lines {lines} != expected {exp_lines}")
    if problems and verdict == GroundTruthVerdict.VALID:
        verdict = GroundTruthVerdict.INVALID
    return GroundTruthResult("", "", verdict, recomputed=lines,
                             reasons=tuple(problems))


_C03_FIELD_PHRASES = {  # instruction phrase -> form field id
    "contact phone": "contact_phone", "联系电话": "contact_phone",
    "delivery city": "delivery_city", "送达城市": "delivery_city",
    "full name": "full_name", "姓名": "full_name",
}
_C03_FILL_EN = re.compile(r"fill in only the ([a-z ]+?) field", re.I)
_C03_FILL_ZH = re.compile(r"只填写([^，。]+?)字段")
_C03_VALUE_PATTERNS = (
    (re.compile(r"my phone is\s*([+\d][\d\- ]+?)\s*[.,]", re.I),
     "contact_phone"),
    (re.compile(r"电话是\s*([+\d][\d\- ]+?)\s*[。，.,]"), "contact_phone"),
    (re.compile(r"delivery city is\s*([^.,，。]+?)\s*[.,，。]", re.I),
     "delivery_city"),
    (re.compile(r"送达城市是\s*([^.,，。]+?)\s*[.,，。]"), "delivery_city"),
    (re.compile(r"my name is\s*([^.,，。]+?)\s*[.,，。]", re.I), "full_name"),
    (re.compile(r"我叫\s*([^.,，。]+?)\s*[.,，。]"), "full_name"),
)


def _c03_formfill(payload: dict, expected: dict) -> GroundTruthResult:
    msg = payload.get("message") or ""
    instr = payload.get("instruction") or ""
    # the directive may live in the message itself (public surface)
    directive = f"{instr} {msg}".lower()
    form_fields = payload.get("form_fields") or []
    problems = []
    verified: list[str] = []
    # requested field from the PUBLIC directive sentence (the message value
    # sentences mention the OTHER fields too — only the directive names the
    # requested one)
    requested = None
    m = _C03_FILL_EN.search(directive) or _C03_FILL_ZH.search(directive)
    if m:
        phrase = m.group(1).strip().lower()
        requested = _C03_FIELD_PHRASES.get(phrase, "__unknown__")
    hits = [requested] if requested else []
    field_ok = None
    if len(hits) == 1:
        if hits[0] not in form_fields:
            problems.append(f"instruction requests {hits[0]!r} which is not "
                            "in the public form_fields")
        elif expected.get("field") != hits[0]:
            problems.append(f"field: expected {expected.get('field')!r}, "
                            f"instruction-derived {hits[0]!r}")
        else:
            field_ok = hits[0]
            verified.append("field")
    # value from the PUBLIC message, for the REQUESTED field (messages
    # carry all three values; only the requested one is the answer)
    value = None
    value_field = None
    if requested:
        for pat, fld in _C03_VALUE_PATTERNS:
            if fld != requested:
                continue
            m = pat.search(msg)
            if m:
                value, value_field = m.group(1).strip(), fld
                break
    if value is not None and field_ok is not None:
        if value_field != field_ok:
            problems.append(f"message supplies {value_field} but "
                            f"instruction requests {field_ok}")
        elif expected.get("value") != value:
            problems.append(f"value: expected {expected.get('value')!r}, "
                            f"message-derived {value!r}")
        else:
            verified.append("value")
    if problems:
        return GroundTruthResult(
            "", "", GroundTruthVerdict.INVALID,
            recomputed={"field": hits[0] if len(hits) == 1 else None,
                        "value": value},
            reasons=tuple(problems), verified_fields=tuple(verified))
    if field_ok is None or value is None:
        return GroundTruthResult(
            "", "", GroundTruthVerdict.NOT_ESTABLISHED,
            recomputed={"field": hits[0] if len(hits) == 1 else None,
                        "value": value},
            reasons=("field-level partial validation only; "
                     + ("requested field not derivable from instruction"
                        if field_ok is None else
                        "value not derivable from message"),),
            verified_fields=tuple(verified),
            unverified_fields=tuple(
                f for f in ("field", "value")
                if (field_ok is None if f == "field" else value is None)))
    return GroundTruthResult("", "", GroundTruthVerdict.VALID,
                             recomputed={"field": field_ok, "value": value},
                             verified_fields=("field", "value"))


_C03_QUOTED = re.compile(r"['\"]([^'\"]+)['\"]")


def _c03_oneedit(payload: dict, expected: dict) -> GroundTruthResult:
    """Exact-line edit semantics. Only derivable when the public payload
    carries the source line and the instruction states one unambiguous
    quoted substitution; otherwise honestly NOT_ESTABLISHED."""
    instr = payload.get("instruction") or ""
    source = (payload.get("source_line") or payload.get("record_line")
              or payload.get("line_to_edit"))
    if source is None:
        return GroundTruthResult(
            "", "", GroundTruthVerdict.NOT_ESTABLISHED,
            reasons=("oneedit source line not exposed in the public "
                     "payload; exact edit semantics not independently "
                     "derivable",))
    if not re.search(r"replace|change|substitute|替换|改为|修改", instr, re.I):
        return GroundTruthResult(
            "", "", GroundTruthVerdict.NOT_ESTABLISHED,
            reasons=("oneedit edit operation not parseable from "
                     "instruction",))
    quotes = _C03_QUOTED.findall(instr)
    if len(quotes) != 2:
        return GroundTruthResult(
            "", "", GroundTruthVerdict.NOT_ESTABLISHED,
            reasons=("oneedit substitution operands ambiguous",))
    old, new = quotes
    if source.count(old) != 1:
        return GroundTruthResult(
            "", "", GroundTruthVerdict.NOT_ESTABLISHED,
            reasons=("oneedit target occurs != once in source line",))
    edited = source.replace(old, new)
    if expected.get("line") == edited:
        return GroundTruthResult("", "", GroundTruthVerdict.VALID,
                                 recomputed=edited)
    return GroundTruthResult(
        "", "", GroundTruthVerdict.INVALID, recomputed=edited,
        reasons=(f"edited line {edited!r} != expected "
                 f"{expected.get('line')!r}",))


def _c03(payload: dict, expected: dict) -> GroundTruthResult:
    if "lines" in expected:                     # formatting family
        return _c03_formatting(payload, expected)
    if "field" in expected or "value" in expected:   # formfill family
        return _c03_formfill(payload, expected)
    if "line" in expected:                      # oneedit family
        return _c03_oneedit(payload, expected)
    return GroundTruthResult("", "", GroundTruthVerdict.NOT_ESTABLISHED,
                             reasons=("unknown C03 expectation shape",))


# -- C04: constraint-filtered id set (GT-D02: instruction is the authority) --
_C04_ZH_FIELD = {"价格": "price", "评分": "rating", "库存": "stock",
                 "页数": "pages", "重量": "weight"}
_C04_ZH_CONSTR = re.compile(
    r"(价格|评分|库存|页数|重量)(不低于|不高于|高于|低于|等于)"
    r"(\d+(?:\.\d+)?)")
_C04_EN_CONSTR = re.compile(
    r"\b(price|rating|stock|pages|weight)\s+"
    r"(at or under|at most|no more than|under|below|at least|no less than|"
    r"over|above|more than|exactly)\s+(\d+(?:\.\d+)?)", re.I)
_C04_EN_OPMAP = {"at or under": "<=", "at most": "<=", "no more than": "<=",
                 "under": "<", "below": "<", "at least": ">=",
                 "no less than": ">=", "over": ">", "above": ">",
                 "more than": ">", "exactly": "=="}
_C04_ZH_OPMAP = {"不低于": ">=", "不高于": "<=", "高于": ">", "低于": "<",
                 "等于": "=="}
_C04_VENDOR_EN = re.compile(r"not from vendor\s+([^\s.;]+)", re.I)
_C04_VENDOR_EN_EQ = re.compile(r"from vendor\s+([^\s.;]+)", re.I)
_C4_VENDOR_ZH_NE = re.compile(r"供应商不是([^\s。.;；]+)")
_C4_VENDOR_ZH_EQ = re.compile(r"供应商是([^\s。.;；]+)")
_C04_SORT_EN = re.compile(
    r"sort by\s+(\w+)\s+(ascending|descending)", re.I)
_C04_SORT_ZH = re.compile(r"按(\w+)(升序|降序)排列")


def _c04_parse_instruction(instr: str) -> tuple[list, tuple | None]:
    """Parse constraints + sort from the PUBLIC instruction (GT-D02)."""
    constraints: list[tuple[str, str, object]] = []
    for zh_f, op, bound in _C04_ZH_CONSTR.findall(instr):
        constraints.append((_C04_ZH_FIELD[zh_f], _C04_ZH_OPMAP[op],
                            float(bound) if "." in bound else int(bound)))
    for f, op, bound in _C04_EN_CONSTR.findall(instr):
        constraints.append((f.lower(), _C04_EN_OPMAP[op.lower()],
                            float(bound) if "." in bound else int(bound)))
    if re.search(r"\bin stock\b", instr, re.I) or "有库存" in instr:
        constraints.append(("stock", ">", 0))
    if (re.search(r"\bout of stock\b|\bnot in stock\b", instr, re.I)
            or re.search(r"没有库存|无库存", instr)):
        constraints.append(("stock", "==", 0))
    for v in _C04_VENDOR_EN.findall(instr):
        constraints.append(("vendor", "!=", v))
    for v in _C4_VENDOR_ZH_NE.findall(instr):
        constraints.append(("vendor", "!=", v))
    for v in _C04_VENDOR_EN_EQ.findall(instr):
        if ("vendor", "!=", v) not in constraints:
            constraints.append(("vendor", "==", v))
    for v in _C4_VENDOR_ZH_EQ.findall(instr):
        if ("vendor", "!=", v) not in constraints:
            constraints.append(("vendor", "==", v))
    sort = None
    m = _C04_SORT_EN.search(instr)
    if m:
        sort = (m.group(1).lower(), m.group(2).lower())
    else:
        m = _C04_SORT_ZH.search(instr)
        if m:
            sort = (m.group(1), "descending" if m.group(2) == "降序"
                    else "ascending")
    return constraints, sort


def _c04(payload: dict, expected: dict, alternatives=()) -> GroundTruthResult:
    instr = payload.get("instruction") or ""
    items = payload.get("items") or []
    constraints, sort = _c04_parse_instruction(instr)
    if not constraints:
        return GroundTruthResult(
            "", "", GroundTruthVerdict.NOT_ESTABLISHED,
            reasons=("no constraints parseable from the public "
                     "instruction",))
    problems = []
    # GT-D02: the instruction — NOT the stored record — is the authority.
    # Recompute the id set/sequence from the instruction-derived constraints.
    rec_ids = []
    for it in items:
        ok = True
        for (f, op, bound) in constraints:
            if not _cmp(op, it.get(f), bound):
                ok = False
                break
        if ok:
            rec_ids.append(it["id"])
    if sort:
        key, direction = sort
        rec_ids.sort(key=lambda i: next(
            it.get(key) for it in items if it["id"] == i),
            reverse=(direction == "descending"))
    # stored metadata cross-check (contradiction with the public text)
    norm_exp = sorted((c[0], c[1]) if isinstance(c, list) else tuple(c)
                      for c in (expected.get("constraints") or []))
    norm_rec = sorted((f"{f}{op}", b) for f, op, b in constraints)
    if norm_exp != norm_rec:
        problems.append(f"stored constraints {norm_exp} contradict the "
                        f"instruction-derived constraints {norm_rec}")
    exp_order = expected.get("order")
    if (exp_order or None) != (sort[0] if sort else None):
        problems.append(f"stored order {exp_order!r} contradicts the "
                        f"instruction-derived sort {sort}")
    exp_ids = expected.get("ids") or []
    alts = [str(a).lower() for a in (alternatives or [])]
    tie_free = any("tie" in a or "order" in a or "unspecified" in a
                   for a in alts)
    if sort:
        if rec_ids != exp_ids:
            problems.append(f"sorted filter yields {rec_ids} != expected "
                            f"sequence {exp_ids} (sort {sort[0]} "
                            f"{sort[1]})")
    else:
        if sorted(rec_ids) != sorted(exp_ids):
            problems.append(f"constraint filter yields {sorted(rec_ids)} "
                            f"!= expected {sorted(exp_ids)}")
        elif rec_ids != exp_ids and not tie_free:
            problems.append("sequence differs with no sort declared and "
                            "no tie freedom declared")
    if problems:
        return GroundTruthResult("", "", GroundTruthVerdict.INVALID,
                                 recomputed=rec_ids,
                                 reasons=tuple(problems))
    reasons = ()
    if not sort and rec_ids != exp_ids:
        reasons = ("order differs; tie freedom declared by the "
                   "expectation",)
    return GroundTruthResult("", "", GroundTruthVerdict.VALID,
                             recomputed=rec_ids, reasons=reasons)


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
    sm = (re.search(r"stock (\d+) units?.*?requested (\d+) units?"
                    r"(?:.*?backorder allowed: (yes|no))?", facts, re.I)
          or re.search(r"库存\s*(\d+)\s*件.*?请求\s*(\d+)\s*件"
                       r"(?:.*?(?:是否允许)?缺货预订[：:]\s*(是|否))?", facts))
    if not sm:
        return None
    stock, requested = int(sm.group(1)), int(sm.group(2))
    backorder = (sm.group(3) or "").lower() in ("yes", "是")
    rec = requested <= stock or backorder
    construction = expected.get("construction") or {}
    problems = []
    if construction:
        for k, v in (("stock", stock), ("requested", requested),
                     ("backorder", backorder)):
            if k in construction and construction[k] != v:
                problems.append(f"construction.{k}: stored "
                                f"{construction[k]!r} != derived {v!r}")
    if rec != expected.get("decision"):
        problems.append(f"fulfillment recompute {rec} != stored "
                        f"{expected.get('decision')}")
    if problems:
        return GroundTruthResult("", "", GroundTruthVerdict.INVALID,
                                 recomputed={"decision": rec, "stock": stock,
                                             "requested": requested,
                                             "backorder": backorder},
                                 reasons=tuple(problems))
    return GroundTruthResult("", "", GroundTruthVerdict.VALID,
                             recomputed={"decision": rec, "stock": stock,
                                         "requested": requested,
                                         "backorder": backorder})


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
    problems = []
    construction = expected.get("construction") or {}
    if construction:
        if "limit" in construction and construction["limit"] != limit:
            problems.append(f"construction.limit: stored "
                            f"{construction['limit']!r} != derived {limit!r}")
        if "days_ago" in construction and construction["days_ago"] != days:
            problems.append(f"construction.days_ago: stored "
                            f"{construction['days_ago']!r} != derived "
                            f"{days!r}")
    if rec != expected.get("decision"):
        problems.append(f"recomputed {days}<={limit}={rec} != stored "
                        "decision")
    if problems:
        return GroundTruthResult("", "", GroundTruthVerdict.INVALID,
                                 recomputed={"decision": rec, "days": days,
                                             "limit": limit},
                                 reasons=tuple(problems))
    return GroundTruthResult("", "", GroundTruthVerdict.VALID,
                             recomputed={"decision": rec, "days": days,
                                         "limit": limit})


# -- C06: cheapest-option-under-requirements (GT-D03) ------------------------
_NEED_SEATS = re.compile(r"at least (\d+) seats?", re.I)
_SEATS_ZH = re.compile(r"至少\s*(\d+)\s*(?:个)?席位")
_REC_W = re.compile(r"\bwith(?:out)?\s+recording\b", re.I)
_REC_EN_YES = re.compile(r"\bwith\s+recording|recording\s+included\b", re.I)
_REC_EN_NO = re.compile(r"\bwithout\s+recording|no\s+recording\b", re.I)
_REC_ZH_YES = re.compile(r"含录制|包含录制|需要录制|带录制")
_REC_ZH_NO = re.compile(r"不含录制|无需录制|不带录制|不要求录制")
_ISO_YES = re.compile(r"\biso\b|iso认证|具备iso", re.I)
_ISO_NO = re.compile(r"without\s+iso|no\s+iso|iso\s+not|无iso|不需要iso",
                     re.I)
_AUDIT_YES = re.compile(r"passed\s+(?:an?\s+)?audit|通过审计|审计通过",
                        re.I)
_AUDIT_NO = re.compile(r"failed\s+(?:an?\s+)?audit|audit\s+failed|"
                       r"未通过审计|审计未通过|无需审计", re.I)


def _c06_need(instr: str, option_keys: set) -> dict:
    """Parse every requirement from the PUBLIC instruction (GT-D03):
    explicit inclusion AND exclusion, both languages."""
    need: dict = {}
    m = _NEED_SEATS.search(instr) or _SEATS_ZH.search(instr)
    if m:
        need["seats"] = int(m.group(1))
    if "recording" in option_keys:
        if _REC_EN_YES.search(instr) or _REC_ZH_YES.search(instr):
            need["recording"] = True
        elif _REC_EN_NO.search(instr) or _REC_ZH_NO.search(instr):
            need["recording"] = False
    if "iso" in option_keys or "audit" in option_keys:
        if _ISO_NO.search(instr):
            need["iso"] = False
        elif _ISO_YES.search(instr):
            need["iso"] = True
        if _AUDIT_NO.search(instr):
            need["audit"] = False
        elif _AUDIT_YES.search(instr):
            need["audit"] = True
    return need


def _c06(payload: dict, expected: dict, alternatives=()) -> GroundTruthResult:
    instr = payload.get("instruction") or ""
    options = payload.get("options") or []
    if not options:
        return GroundTruthResult("", "", GroundTruthVerdict.NOT_ESTABLISHED,
                                 reasons=("no public options",))
    keys = set(options[0])
    need = _c06_need(instr, keys)
    if not need:
        return GroundTruthResult(
            "", "", GroundTruthVerdict.NOT_ESTABLISHED,
            reasons=("no requirement parseable from the instruction for "
                     f"option schema {sorted(keys)}"))
    problems = []
    construction = expected.get("construction") or {}
    stored_need = construction.get("need")
    if stored_need is not None and stored_need != need:
        problems.append(f"stored construction.need {stored_need!r} "
                        f"contradicts the instruction-derived need {need!r}")
    qualifying = [o for o in options
                  if all(o.get(k) == v if isinstance(v, bool)
                         else o.get(k, 0) >= v for k, v in need.items())]
    if not qualifying:
        return GroundTruthResult(
            "", "", GroundTruthVerdict.INVALID, recomputed={"need": need},
            reasons=("no option satisfies the instruction-derived "
                     f"requirement {need} — instruction/option mismatch"))
    best_price = min(o["price"] for o in qualifying)
    winners = sorted(o["id"] for o in qualifying if o["price"] == best_price)
    exp = expected.get("choice")
    alts = [str(a).lower() for a in (alternatives or [])]
    tie_declared = any("tie" in a for a in alts)
    if problems:
        return GroundTruthResult("", "", GroundTruthVerdict.INVALID,
                                 recomputed={"need": need, "winners": winners},
                                 reasons=tuple(problems))
    if len(winners) == 1 and winners[0] == exp:
        return GroundTruthResult("", "", GroundTruthVerdict.VALID,
                                 recomputed={"need": need,
                                             "choice": winners[0]})
    if exp in winners:
        if tie_declared:
            return GroundTruthResult(
                "", "", GroundTruthVerdict.VALID,
                recomputed={"need": need, "winners": winners},
                reasons=("declared tie set",))
        # GT-D03: an undeclared tie is NOT automatically valid.
        return GroundTruthResult(
            "", "", GroundTruthVerdict.AMBIGUOUS,
            recomputed={"need": need, "winners": winners},
            reasons=("recomputed tie without a declared alternative"))
    return GroundTruthResult("", "", GroundTruthVerdict.INVALID,
                             recomputed={"need": need, "winners": winners},
                             reasons=(f"cheapest qualifying {winners} != "
                                      f"expected {exp!r}"))


# -- C08: public-objective / tool-description derivation (GT-D04) -----------
_C08_OBJ_EN = re.compile(
    r"i need to\s+(.+?)(?=\s+for our customers\b|[.,。]|$)", re.I)
_C08_OBJ_TOKEN_EN = {"send out": "send", "look up": "lookup",
                     "support ticket": "ticket"}
_C08_OBJ_TOKEN_ZH = {"邮件": "email", "发送": "send", "起草": "draft",
                     "生成": "generate", "发票": "invoice", "查询": "lookup",
                     "工单": "ticket", "数据集": "dataset", "校验": "validate",
                     "导出": "export", "日历": "calendar", "排期": "schedule",
                     "报表": "report", "关闭": "close", "预订": "schedule"}
# zh objective tokens, longest first so 发票 is not eaten by 发送-style
# prefixes and 安排周期生成 is consumed whole.
_C08_ZH_PHRASES = [("安排周期生成", {"schedule"})]
_C08_AUX_EN = re.compile(r"^handles\s+(.+?)\s+only$", re.I)
_C08_AUX_ZH = re.compile(r"^只处理(.+)$")
_C08_AUX_TOKEN = {"look up": "lookup", "support ticket": "ticket",
                  "发送": "send", "发票": "invoice", "报表": "report",
                  "排期": "schedule", "数据集": "dataset", "校验": "validate",
                  "生成": "generate", "邮件": "email", "工单": "ticket",
                  "查询": "lookup", "起草": "draft", "关闭": "close",
                  "日历": "calendar", "消息": "message", "发布": "post",
                  "导出": "export", "预订": "schedule", "提醒": "message"}
# EN description lemma scan -> tags (multiword phrases first)
_C08_EN_PATTERNS = [
    (re.compile(r"\blooks?\s+up\b", re.I), "lookup"),
    (re.compile(r"\bsupport\s+ticket|\btickets?\b", re.I), "ticket"),
    (re.compile(r"\bsends?\b|\bsending\b", re.I), "send"),
    (re.compile(r"\bemails?\b", re.I), "email"),
    (re.compile(r"\bdrafts?\b", re.I), "draft"),
    (re.compile(r"\bgenerates?\b|\bgenerating\b", re.I), "generate"),
    (re.compile(r"\binvoices?\b", re.I), "invoice"),
    (re.compile(r"\bdatasets?\b", re.I), "dataset"),
    (re.compile(r"\bvalidates?\b", re.I), "validate"),
    (re.compile(r"\bexports?\b", re.I), "export"),
    (re.compile(r"\bcalendars?\b", re.I), "calendar"),
    (re.compile(r"\bbooks?\b|\bschedules?\b", re.I), "schedule"),
    (re.compile(r"\bmessages?\b|\breminders?\b", re.I), "message"),
    (re.compile(r"\bposts?\b", re.I), "post"),
    (re.compile(r"\breports?\b", re.I), "report"),
    (re.compile(r"\bcloses?\b", re.I), "close"),
]
# zh description phrases, longest-first span consumption
_C08_ZH_DESC_PHRASES = [
    ("安排周期生成", {"schedule"}), ("预订", {"schedule"}), ("排期", {"schedule"}),
    ("关闭", {"close"}), ("发票", {"invoice"}), ("发送", {"send"}),
    ("邮件", {"email"}), ("起草", {"draft"}), ("生成", {"generate"}),
    ("查询", {"lookup"}), ("工单", {"ticket"}), ("数据集", {"dataset"}),
    ("校验", {"validate"}), ("导出", {"export"}), ("日历", {"calendar"}),
    ("提醒", {"message"}), ("消息", {"message"}), ("发布", {"post"}),
    ("报表", {"report"}),
]
_C08_NEGATIONS = ["without sending", "并不发送", "但不发送", "无需发送"]


def _c08_objective_tags(objective: str) -> tuple[set, bool]:
    """Derive required capability tags from the PUBLIC objective."""
    if not objective:
        return set(), False
    m = _C08_OBJ_EN.search(objective)
    if m:
        tags = set()
        for tok in re.split(r"\s+and\s+", m.group(1).strip().lower()):
            tok = tok.strip()
            if not tok:
                continue
            tags.add(_C08_OBJ_TOKEN_EN.get(tok, tok.replace(" ", "_")))
        return tags, True
    if objective.startswith("我需要"):
        body = objective[len("我需要"):].rstrip("。.，,")
        tags = set()
        rest = body
        for phrase, add in _C08_ZH_PHRASES:
            if phrase in rest:
                tags |= add
                rest = rest.replace(phrase, "")
        for tok in re.split(r"并", rest):
            tok = tok.strip()
            if tok:
                tags.add(_C08_OBJ_TOKEN_ZH[tok])
        return tags, True
    return set(), False


def _c08_description_tags(desc: str) -> tuple[set, bool]:
    """Derive capability tags from a PUBLIC tool description."""
    if not desc:
        return set(), False
    aux_en = _C08_AUX_EN.match(desc.strip())
    if aux_en:
        tok = aux_en.group(1).strip().lower()
        return {_C08_AUX_TOKEN.get(tok, tok.replace(" ", "_"))}, True
    aux_zh = _C08_AUX_ZH.match(desc.strip())
    if aux_zh:
        tok = aux_zh.group(1).strip()
        if tok in _C08_AUX_TOKEN:
            return {_C08_AUX_TOKEN[tok]}, True
        return set(), False
    text = desc
    for neg in _C08_NEGATIONS:
        text = text.replace(neg, "")
    if re.search(r"[一-龥]", text):       # zh description
        tags = set()
        rest = text
        for phrase, add in _C08_ZH_DESC_PHRASES:
            if phrase in rest:
                tags |= add
                rest = rest.replace(phrase, "")
        return tags, bool(tags)
    tags = set()
    for pat, tag in _C08_EN_PATTERNS:
        if pat.search(text):
            tags.add(tag)
    return tags, bool(tags)


def _c08(payload: dict, expected: dict) -> GroundTruthResult:
    tools = payload.get("tools") or []
    construction = (expected or {}).get("construction") or {}
    registry = construction.get("registry_tags")
    required = construction.get("required_tags")
    if registry is None or required is None:
        return GroundTruthResult(
            "", "", GroundTruthVerdict.NOT_ESTABLISHED,
            reasons=("protected construction record required (public "
                     "recomputability NOT claimed for C08)",))
    # GT-D04: derive everything from the PUBLIC objective + descriptions.
    obj_tags, obj_ok = _c08_objective_tags(payload.get("objective") or "")
    derived_registry: dict[str, set] = {}
    underived: list[str] = []
    for t in tools:
        tags, ok = _c08_description_tags(t.get("description") or "")
        derived_registry[t.get("id")] = tags
        if not ok:
            underived.append(t.get("id"))
    problems = []
    if obj_ok and set(required) != obj_tags:
        problems.append(f"stored required_tags {sorted(required)} contradict "
                        f"the objective-derived tags {sorted(obj_tags)}")
    public_ids = {t.get("id") for t in tools}
    if set(registry) != public_ids:
        missing = sorted(set(registry) - public_ids)
        extra = sorted(public_ids - set(registry))
        problems.append(f"registry does not correspond to the public "
                        f"inventory (registry-only: {missing}, "
                        f"public-only: {extra})")
    for tid, tags in sorted(derived_registry.items()):
        if tid in registry and registry[tid] is not None:
            if set(registry[tid]) != tags:
                problems.append(
                    f"registry tags for {tid}: stored "
                    f"{sorted(registry[tid])} != description-derived "
                    f"{sorted(tags)}")
    if underived:
        return GroundTruthResult(
            "", "", GroundTruthVerdict.NOT_ESTABLISHED,
            recomputed={"required": sorted(obj_tags) if obj_ok else None,
                        "registry": {k: sorted(v)
                                     for k, v in derived_registry.items()}},
            reasons=(f"tool descriptions not independently derivable: "
                     f"{sorted(underived)}",),
            verified_fields=("registry correspondence",) if not problems else ())
    if not obj_ok:
        return GroundTruthResult(
            "", "", GroundTruthVerdict.NOT_ESTABLISHED,
            recomputed={"registry": {k: sorted(v)
                                     for k, v in derived_registry.items()}},
            reasons=("objective not independently parseable",),
            verified_fields=("registry",))
    winners = sorted(tid for tid, tags in derived_registry.items()
                     if obj_tags.issubset(tags))
    exp = expected.get("tool_id")
    if problems:
        return GroundTruthResult("", "", GroundTruthVerdict.INVALID,
                                 recomputed={"required": sorted(obj_tags),
                                             "winners": winners},
                                 reasons=tuple(problems),
                                 verified_fields=("objective", "registry"))
    if len(winners) == 1 and winners[0] == exp:
        return GroundTruthResult("", "", GroundTruthVerdict.VALID,
                                 recomputed={"required": sorted(obj_tags),
                                             "choice": winners[0]},
                                 reasons=("unique capability superset",),
                                 verified_fields=("objective", "registry"))
    if exp in winners:
        return GroundTruthResult("", "", GroundTruthVerdict.AMBIGUOUS,
                                 recomputed={"required": sorted(obj_tags),
                                             "winners": winners},
                                 reasons=("multiple supersets — uniqueness "
                                          "not satisfied"),
                                 verified_fields=("objective", "registry"))
    return GroundTruthResult("", "", GroundTruthVerdict.INVALID,
                             recomputed={"required": sorted(obj_tags),
                                         "winners": winners},
                             reasons=(f"public derivation yields {winners} != "
                                      f"expected {exp!r}"),
                             verified_fields=("objective", "registry"))


# ---------------------------------------------------------------------------
# public API — Obligation A
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
        r = _c04(payload, expected,
                 (expectation or {}).get("alternatives") or [])
    elif prim == "C05":
        r = _c05(payload, expected)
    elif prim == "C06":
        r = _c06(payload, expected,
                 (expectation or {}).get("alternatives") or [])
    elif prim == "C07":
        r = _catalog_ground_truth(payload, expected.get("action"),
                                  "situation", "action_catalog", _C07_RULES,
                                  _C07_VETOES)
    elif prim == "C08":
        r = _c08(payload, expected)
    else:
        return GroundTruthResult(case.get("case_id", ""), prim,
                                 GroundTruthVerdict.NOT_ESTABLISHED,
                                 reasons=(f"primitive {prim} outside Batch A "
                                          "oracle scope",))
    return GroundTruthResult(case.get("case_id", ""), prim, r.verdict,
                             r.recomputed, r.reasons, r.verified_fields,
                             r.unverified_fields)


# ---------------------------------------------------------------------------
# public API — Obligation B (reference path)
# ---------------------------------------------------------------------------
class ResponseVerdict(Enum):
    CORRECT = "CORRECT"
    INCORRECT = "INCORRECT"
    EMPTY_OUTPUT = "EMPTY_OUTPUT"          # its own class, never INCORRECT
    NOT_EVALUABLE = "NOT_EVALUABLE"        # software error / no established GT


@dataclass
class ResponseResult:
    case_id: str
    primitive: str
    verdict: ResponseVerdict
    parsed: object = None                  # typed semantics from the interpreter
    truth: object = None                   # independently established truth
    reasons: tuple[str, ...] = ()


def evaluate_response(case: dict, expectation: dict,
                      response, interpreter=None) -> ResponseResult:
    """Obligation B: evaluate a RAW model response against independently
    established task truth (never against unestablished stored answers).

    ``interpreter`` defaults to the independent interpreter module; a
    production parser may be injected for dual-path comparison, but the
    truth side is always the reference derivation above.
    """
    from eval_assurance.reference import interpreter as _default_interp
    interp = interpreter or _default_interp
    prim = case.get("primitive", "")
    case_id = case.get("case_id", "")
    try:
        parsed, parse_class, parse_reasons = interp.parse_response(
            prim, case.get("public_payload") or {}, response)
    except Exception as exc:                     # software error, never model
        return ResponseResult(
            case_id, prim, ResponseVerdict.NOT_EVALUABLE,
            reasons=(f"interpreter software error: {type(exc).__name__}: "
                     f"{exc}",))
    if parse_class == "EMPTY_OUTPUT":
        return ResponseResult(case_id, prim, ResponseVerdict.EMPTY_OUTPUT,
                              reasons=parse_reasons or ("empty output",))
    try:
        return _evaluate_parsed(case, expectation, prim, case_id,
                                parsed, parse_class, parse_reasons, interp)
    except Exception as exc:                     # software error, never model
        return ResponseResult(
            case_id, prim, ResponseVerdict.NOT_EVALUABLE, parsed=parsed,
            reasons=(f"reference-path software error: "
                     f"{type(exc).__name__}: {exc}",))


def _evaluate_parsed(case, expectation, prim, case_id,
                     parsed, parse_class, parse_reasons, interp):
    gt = validate_ground_truth(case, expectation)
    if gt.verdict is not GroundTruthVerdict.VALID:
        return ResponseResult(
            case_id, prim, ResponseVerdict.NOT_EVALUABLE, parsed=parsed,
            truth=gt.recomputed,
            reasons=(f"ground truth not independently established "
                     f"({gt.verdict.value}); qualified response evaluation "
                     f"refused",))
    truth = gt.recomputed
    if parse_class != "OK":
        # malformed surface (non-JSON, hedges, multiple labels, markers…)
        return ResponseResult(case_id, prim, ResponseVerdict.INCORRECT,
                              parsed=parsed, truth=truth,
                              reasons=parse_reasons or ("malformed output",))
    ok, why = _compare_typed(prim, case.get("public_payload") or {},
                             parsed, truth, expectation or {})
    if ok:
        return ResponseResult(case_id, prim, ResponseVerdict.CORRECT,
                              parsed=parsed, truth=truth)
    return ResponseResult(case_id, prim, ResponseVerdict.INCORRECT,
                          parsed=parsed, truth=truth, reasons=why)


def _compare_typed(prim: str, payload: dict, parsed, truth,
                   expectation: dict) -> tuple[bool, tuple]:
    """Complete typed-semantic comparison against established truth."""
    if prim == "C01":
        catalog = payload.get("intent_catalog") or {}
        if parsed not in catalog:
            return False, (f"label {parsed!r} not in public catalog",)
        return (parsed == truth), (f"label {parsed!r} != {truth!r}",)
    if prim == "C02":
        if not isinstance(parsed, dict):
            return False, ("parsed goal record is not an object",)
        why = []
        for fld in ("action", "object", "deadline", "completion_criterion"):
            if parsed.get(fld) != truth.get(fld):
                why.append(f"{fld}: {parsed.get(fld)!r} != {truth.get(fld)!r}")
        pf = parsed.get("unknown_flags") or {}
        tf = truth.get("unknown_flags") or {}
        for k in ("deadline", "completion_criterion"):
            if pf.get(k) != tf.get(k):
                why.append(f"unknown_flags.{k}: {pf.get(k)!r} != {tf.get(k)!r}")
        extra = set(parsed) - {"action", "object", "deadline",
                               "completion_criterion", "unknown_flags"}
        if extra:
            why.append(f"unexpected fields: {sorted(extra)}")
        return (not why), tuple(why)
    if prim == "C03":
        if isinstance(truth, dict) and "field" in truth:      # formfill
            return (parsed == truth), (
                f"formfill {parsed!r} != {truth!r}",)
        if isinstance(truth, dict) and "need" in truth:
            return (parsed == truth), (f"{parsed!r} != {truth!r}",)
        # formatting / oneedit: line sequence equality
        return (parsed == truth), (f"lines {parsed!r} != {truth!r}",)
    if prim == "C04":
        norm = lambda xs: [str(x).strip().lower() for x in (xs or [])]
        order = ((expectation.get("expected") or {}).get("order"))
        if order:
            return (norm(parsed) == norm(truth)), (
                f"sorted ids {parsed!r} != {truth!r}",)
        if sorted(norm(parsed)) != sorted(norm(truth)):
            return False, (f"id set {sorted(parsed)} != {sorted(truth)}",)
        if norm(parsed) != norm(truth):
            return True, ("order differs; tie freedom declared",)
        return True, ()
    if prim == "C05":
        return (parsed is truth["decision"]), (
            f"decision {parsed!r} != {truth['decision']!r}",)
    if prim == "C06":
        if isinstance(truth, dict):
            target = truth.get("choice")
            alts = [str(a).lower() for a in (expectation.get("alternatives")
                                             or [])]
            if str(parsed).lower() != str(target).lower() and alts \
                    and "tie" in alts[0]:
                winners = [str(w).lower() for w in (truth.get("winners")
                                                    or [])]
                return (parsed in winners), (
                    f"choice {parsed!r} not in declared tie set {winners}",)
            truth = target
        return (str(parsed).lower() == str(truth).lower()), (
            f"choice {parsed!r} != {truth!r}",)
    if prim == "C07":
        catalog = payload.get("action_catalog") or {}
        if parsed not in catalog:
            return False, (f"action {parsed!r} not in public catalog",)
        return (parsed == truth), (f"action {parsed!r} != {truth!r}",)
    if prim == "C08":
        ids = {str(t.get("id")).lower() for t in payload.get("tools") or []}
        if str(parsed).lower() not in ids:
            return False, (f"tool id {parsed!r} not in candidate list",)
        return (str(parsed).lower() == str(truth if not isinstance(
            truth, dict) else truth.get("choice")).lower()), (
            f"tool id {parsed!r} != {truth!r}",)
    return False, (f"primitive {prim} outside Batch A scope",)
