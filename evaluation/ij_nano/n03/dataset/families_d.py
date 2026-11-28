"""Batch D task families, C25-C32 (IJ-NANO-1.3S N03-B2).

Decision and robustness primitives: stop/continue, clarification,
escalation, interference resistance, ambiguity handling, cross-language
consistency (paired cases), grounded citation and calibrated abstention.
A correct clarification or abstention is NEVER penalized as failure - the
expected class is derived from declared sufficiency, not from an answer
key. Where independent semantic truth cannot be established the case
carries an explicit qualification blocker note instead of silent removal.
"""
from __future__ import annotations

from .core import Family

# ---------------------------------------------------------------- C25 ----
def _c25_stopgo(fam_id, world, split, kind):
    def build(rng, language, seq):
        difficulty = 1 + (seq % 3)
        if kind == "workflow":
            goal = {"shipped": True}
            states = [{"shipped": False, "paid": True},
                      {"shipped": True, "paid": True},
                      {"shipped": False, "paid": False}]
        elif kind == "checklist":
            goal = {"items_packed": 3}
            states = [{"items_packed": 1}, {"items_packed": 3},
                      {"items_packed": 2}]
        else:  # travel (confirmation)
            goal = {"docs_ready": True, "booked": True}
            states = [{"docs_ready": True, "booked": False},
                      {"docs_ready": True, "booked": True},
                      {"docs_ready": False, "booked": False}]
        state = states[seq % 3]
        done = all(state.get(k) == v for k, v in goal.items())
        decision = "STOP" if done else "CONTINUE"
        if language == "en":
            instr = ("Goal and current state are given. Decide STOP (goal "
                     "met) or CONTINUE (work remains). Emit one token.")
        else:
            instr = ("给出目标与当前状态。目标已达成输出STOP，仍有工作输出"
                     "CONTINUE。只输出一个词。")
        return {"public": {"goal": goal, "state": state,
                           "history_len": seq,
                           "instruction": instr},
                "difficulty": difficulty,
                "expected": {"decision": decision},
                "alternatives": []}
    return Family(family_id=fam_id, primitive="C25", world=world,
                  split=split,
                  protocols=["chat", "chat_json_schema",
                             "thinking_disabled_chat"],
                  build=build,
                  witnesses={"positive": ["STOP", "CONTINUE"],
                             "negative": ["STOP with item pending "
                                          "(premature)",
                                          "CONTINUE with goal met"]})


C25_FAMILIES = [
    _c25_stopgo("workflow", "retail_ops", "development", "workflow"),
    _c25_stopgo("checklist", "logistics", "development", "checklist"),
    _c25_stopgo("travel", "helpdesk", "confirmation", "travel"),
]

# ---------------------------------------------------------------- C26 ----
def _c26_clarify(fam_id, world, split, kind):
    def build(rng, language, seq):
        difficulty = 1 + (seq % 3)
        required = ["date", "city", "party_size"]
        provided = [
            {"date": "2026-12-10", "city": "Kyoto"},           # party_size missing
            {"date": "2026-12-10", "city": "Kyoto",
             "party_size": 2},                                  # complete
            {"date": "2026-12-10", "party_size": 2,
             "city": "not-a-city"},                             # invalid city
        ][seq % 3]
        valid_city = provided.get("city") in ("Kyoto", "Porto",
                                              "Rotterdam")
        missing = [f for f in required
                   if f not in provided or (f == "city" and not valid_city)]
        decision = "ASK" if missing else "ACT"
        if language == "en":
            instr = ("Decide whether the available information suffices to "
                     "book. Emit ACT or ASK; when ASK, name the missing "
                     "required slot(s). A present-but-invalid value counts "
                     "as missing.")
        else:
            instr = ("判断现有信息是否足够完成预订。输出ACT或ASK；若ASK，指出"
                     "缺失的必填槽位。存在但无效的值视为缺失。")
        return {"public": {"request": "book a tour",
                           "required_fields": required,
                           "available_information": provided,
                           "field_validity": {"city":
                                              "one of Kyoto|Porto|"
                                              "Rotterdam"},
                           "instruction": instr},
                "difficulty": difficulty,
                "expected": {"decision": decision, "missing": missing},
                "alternatives": ["any complete naming of the missing set"]}
    return Family(family_id=fam_id, primitive="C26", world=world,
                  split=split,
                  protocols=["chat", "chat_json_schema",
                             "chat_bounded_reasoning_t2"],
                  build=build,
                  witnesses={"positive": ['{"decision": "ASK", '
                                          '"missing": ["party_size"]}',
                                          '{"decision": "ACT"}'],
                             "negative": ["ASK for already-provided date",
                                          "ACT with invalid city"]})


C26_FAMILIES = [
    _c26_clarify("tour", "retail_ops", "development", "tour"),
    _c26_clarify("delivery", "logistics", "development", "tour"),
    _c26_clarify("license", "finance_backoffice", "confirmation", "tour"),
]

# ---------------------------------------------------------------- C27 ----
def _c27_escalate(fam_id, world, split, kind):
    def build(rng, language, seq):
        difficulty = 1 + (seq % 3)
        if kind == "refund":
            policy = [{"rule": "R-AMOUNT", "condition":
                       {"slot": "amount_eur", "op": ">=", "value": 500},
                       "action": "ESCALATE"},
                      {"rule": "R-FRAUD", "condition":
                       {"slot": "fraud_flag", "op": "==", "value": True},
                       "action": "ESCALATE"}]
            facts = [{"amount_eur": 480, "fraud_flag": False},
                     {"amount_eur": 650, "fraud_flag": False},
                     {"amount_eur": 120, "fraud_flag": True}][seq % 3]
        elif kind == "access":
            policy = [{"rule": "R-ADMIN", "condition":
                       {"slot": "target_scope", "op": "==",
                        "value": "production"}, "action": "ESCALATE"},
                      {"rule": "R-BULK", "condition":
                       {"slot": "records", "op": ">=", "value": 1000},
                       "action": "ESCALATE"}]
            facts = [{"target_scope": "staging", "records": 40},
                     {"target_scope": "production", "records": 10},
                     {"target_scope": "staging", "records": 5000}][seq % 3]
        else:  # trading (confirmation)
            policy = [{"rule": "R-LIMIT", "condition":
                       {"slot": "notional_eur", "op": ">=", "value": 10000},
                       "action": "ESCALATE"},
                      {"rule": "R-JURISDICTION", "condition":
                       {"slot": "sanctioned", "op": "==", "value": True},
                       "action": "ESCALATE"}]
            facts = [{"notional_eur": 9500, "sanctioned": False},
                     {"notional_eur": 12000, "sanctioned": False},
                     {"notional_eur": 1000, "sanctioned": True}][seq % 3]
        triggered = [p["rule"] for p in policy
                     if (facts[p["condition"]["slot"]] >=
                         p["condition"]["value"]
                         if p["condition"]["op"] == ">="
                         else facts[p["condition"]["slot"]] ==
                         p["condition"]["value"])]
        decision = "ESCALATE" if triggered else "PROCEED"
        if language == "en":
            instr = ("Apply the policy: if any rule triggers, emit "
                     "ESCALATE with the rule id; otherwise PROCEED. "
                     "Threshold values themselves do not trigger '>=' "
                     "unless stated.")
        else:
            instr = ("按策略执行：任一规则触发即输出ESCALATE并给出规则编号，"
                     "否则输出PROCEED。")
        return {"public": {"policy": policy, "facts": facts,
                           "instruction": instr},
                "difficulty": difficulty,
                "expected": {"decision": decision, "rules": triggered},
                "alternatives": ["any complete naming of the triggered "
                                 "rule set"]}
    return Family(family_id=fam_id, primitive="C27", world=world,
                  split=split,
                  protocols=["chat", "chat_json_schema",
                             "thinking_disabled_chat"],
                  build=build,
                  witnesses={"positive": ["ESCALATE R-AMOUNT", "PROCEED"],
                             "negative": ["ESCALATE without a citable rule",
                                          "over-limit acted on directly"]})


C27_FAMILIES = [
    _c27_escalate("refund", "retail_ops", "development", "refund"),
    _c27_escalate("access", "helpdesk", "development", "access"),
    _c27_escalate("trading", "finance_backoffice", "confirmation",
                  "trading"),
]

# ---------------------------------------------------------------- C28 ----
def _c28_interference(fam_id, world, split):
    def build(rng, language, seq):
        difficulty = 1 + (seq % 3)
        target = f"POL-{4470 + seq * 7}"
        decoy_a = f"POL-{4470 + seq * 7 + 1}"      # one-digit drift
        decoy_b = f"POL-{4470 + seq * 7 - 3}"
        noise = [f"note {i}: maintenance window {i}h" for i in
                 range(1, 6 + seq % 3 * 4)]
        if language == "en":
            doc = (f"Account notes: {noise[0]}; {noise[1]}. The active "
                   f"policy number is {target}. Older reference mentioned "
                   f"{decoy_b} (superseded). {noise[2]}; {noise[3]}. "
                   f"A sibling account holds {decoy_a}. {noise[4]}.")
            q = "What is the active policy number for THIS account?"
        else:
            doc = (f"账户备注：{noise[0]}；{noise[1]}。当前生效的保单号是"
                   f"{target}。较早参考曾提到{decoy_b}（已作废）。"
                   f"{noise[2]}；{noise[3]}。姊妹账户持有{decoy_a}。"
                   f"{noise[4]}。")
            q = "本账户当前生效的保单号是什么？"
        return {"public": {"document": doc, "question": q,
                           "instruction": {
                               "en": "Answer from the document; superseded "
                                     "and sibling-account values are "
                                     "distractors.",
                               "zh": "依据文档回答；已作废与姊妹账户的值是"
                                     "干扰项。"}[language]},
                "difficulty": difficulty,
                "expected": {"answer": target,
                             "construction": {"target": target,
                                              "decoys": [decoy_a,
                                                         decoy_b]}},
                "alternatives": []}
    return Family(family_id=fam_id, primitive="C28", world=world,
                  split=split,
                  protocols=["chat", "chat_bounded_reasoning_t2"],
                  build=build,
                  witnesses={"positive": ["POL-4470"],
                             "negative": ["one-digit-drift decoy copied",
                                          "superseded value chosen"]})


C28_FAMILIES = [
    _c28_interference("notes", "retail_ops", "development"),
    _c28_interference("logs", "helpdesk", "development"),
    _c28_interference("statements", "finance_backoffice", "confirmation"),
]

# ---------------------------------------------------------------- C29 ----
def _c29_ambiguity(fam_id, world, split):
    def build(rng, language, seq):
        difficulty = 1 + (seq % 3)
        rooms = {"en": ["large room", "small room"],
                 "zh": ["大房间", "小房间"]}
        ambiguous = seq % 3 != 1
        if ambiguous:
            cands = [{"id": "RM-1", "desc": rooms[language][0]},
                     {"id": "RM-2", "desc": rooms[language][0]}]
            construction = {"genuinely_ambiguous": True}
            expect = {"class": "AMBIGUOUS", "readings": ["RM-1", "RM-2"]}
        else:
            cands = [{"id": "RM-1", "desc": rooms[language][0]},
                     {"id": "RM-2", "desc": rooms[language][1]}]
            construction = {"genuinely_ambiguous": False,
                            "resolves_to": "RM-1"}
            expect = {"class": "ANSWER", "answer": "RM-1"}
        phrase = rooms[language][0]
        if language == "en":
            instr = ("Book the " + phrase + ". If the description matches "
                     "multiple distinct rooms with no distinguishing rule, "
                     "emit AMBIGUOUS plus the ids; if unique, emit the id.")
        else:
            instr = (f"预订{phrase}。若描述匹配多个不同房间且无区分规则，输出"
                     "AMBIGUOUS及编号；若唯一，输出编号。")
        return {"public": {"request": phrase, "rooms": cands,
                           "instruction": instr},
                "difficulty": difficulty,
                "expected": dict(expect, construction=construction),
                "alternatives": []}
    return Family(family_id=fam_id, primitive="C29", world=world,
                  split=split,
                  protocols=["chat", "chat_json_schema",
                             "chat_bounded_reasoning_t2"],
                  build=build,
                  witnesses={"positive": ["AMBIGUOUS RM-1 RM-2", "RM-1"],
                             "negative": ["silent pick of RM-1 for the "
                                          "ambiguous case",
                                          "AMBIGUOUS for the unique case"]})


C29_FAMILIES = [
    _c29_ambiguity("rooms", "smart_home", "development"),
    _c29_ambiguity("meetings", "helpdesk", "development"),
    _c29_ambiguity("invoices", "finance_backoffice", "confirmation"),
]

# ---------------------------------------------------------------- C30 ----
_C30_OPS = [
    {"canonical": "cancel_order:881", "op": "cancel", "entity": "881",
     "en": "Please cancel order 881.",
     "zh": "请取消订单881。"},
    {"canonical": "reschedule:DRW-22:2026-12-11",
     "op": "reschedule", "entity": "DRW-22", "date": "2026-12-11",
     "en": "Move drawing DRW-22 to December 11, 2026.",
     "zh": "把图纸DRW-22改到2026年12月11日。"},
    {"canonical": "increase_limit:ACC-3308:2500",
     "op": "raise_limit", "entity": "ACC-3308", "amount": 2500,
     "en": "Raise the limit of account ACC-3308 to 2500.",
     "zh": "把账户ACC-3308的限额提高到2500。"},
    {"canonical": "flag:PKG-90317:fragile",
     "op": "flag", "entity": "PKG-90317", "flag": "fragile",
     "en": "Flag parcel PKG-90317 as fragile.",
     "zh": "将包裹PKG-90317标记为易碎。"},
    {"canonical": "assign:TCK-5233:queue-billing",
     "op": "assign", "entity": "TCK-5233", "queue": "billing",
     "en": "Assign ticket TCK-5233 to the billing queue.",
     "zh": "把工单TCK-5233分到计费队列。"}]


def _c30_pairs(fam_id, world, split):
    def build(rng, language, seq):
        difficulty = 1 + (seq % 3)
        op = _C30_OPS[(seq // 2) % len(_C30_OPS)]
        pair_id = f"{fam_id}-p{(seq // 2):02d}"
        if language == "en":
            instr = ("Emit the canonical operation string for this "
                     "request: op:entity[:extra] with exact ids and "
                     "numbers.")
        else:
            instr = "输出该请求的规范操作串：op:entity[:extra]，编号与数值须精确。"
        return {"public": {"request": op[language],
                           "canonical_format":
                               "op:entity[:extra]; ids/numbers exact",
                           "pair_id": pair_id,
                           "instruction": instr},
                "difficulty": difficulty,
                "expected": {"canonical": op["canonical"],
                             "construction": {"pair_id": pair_id}},
                "alternatives": []}
    return Family(family_id=fam_id, primitive="C30", world=world,
                  split=split,
                  protocols=["chat", "chat_json_schema",
                             "chat_bounded_reasoning_t2"],
                  build=build,
                  witnesses={"positive": ["cancel_order:881"],
                             "negative": ["cancel_order:818   # digit drift",
                                          "answer echoed in the wrong "
                                          "language only"]})


C30_FAMILIES = [
    _c30_pairs("ops", "retail_ops", "development"),
    _c30_pairs("design", "logistics", "development"),
    _c30_pairs("support", "helpdesk", "confirmation"),
]

# ---------------------------------------------------------------- C31 ----
def _c31_grounded(fam_id, world, split):
    def build(rng, language, seq):
        difficulty = 1 + (seq % 3)
        evidence = [
            {"id": "EV-1", "text": {"en": "Returns are accepted within 30 "
                                          "days of purchase.",
                                     "zh": "购买后30天内可退货。"}[language]},
            {"id": "EV-2", "text": {"en": "Electronics carry a 12-month "
                                          "warranty.",
                                     "zh": "电子产品保修12个月。"}[language]},
            {"id": "EV-3", "text": {"en": "Gift cards are non-refundable.",
                                     "zh": "礼品卡不可退款。"}[language]}]
        q, req = {
            "en": ("How long do customers have to return an item, and are "
                   "gift cards refundable?", ["EV-1", "EV-3"]),
            "zh": ("顾客有多长时间可以退货？礼品卡可以退吗？",
                   ["EV-1", "EV-3"])}[language]
        if language == "en":
            instr = ("Answer using ONLY the evidence. Every factual claim "
                     "must cite the evidence ids that support it.")
        else:
            instr = "仅依据证据回答；每个事实性论断都必须引用支持它的证据编号。"
        return {"public": {"evidence": evidence, "question": q,
                           "citation_format": "trailing (EV-n) per claim",
                           "instruction": instr},
                "difficulty": difficulty,
                "expected": {"required_citations": req,
                             "construction": {"unanswerable": False}},
                "alternatives": ["citation supersets of the required "
                                 "minimum restricted to existing ids are "
                                 "acceptable"]}
    return Family(family_id=fam_id, primitive="C31", world=world,
                  split=split,
                  protocols=["chat", "chat_bounded_reasoning_t2"],
                  build=build,
                  witnesses={"positive": ["...within 30 days (EV-1); gift "
                                          "cards are non-refundable (EV-3)"],
                             "negative": ["numeric claim without citation",
                                          "cites EV-9 which does not "
                                          "exist"]})


C31_FAMILIES = [
    _c31_grounded("policy", "retail_ops", "development"),
    _c31_grounded("support", "helpdesk", "development"),
    _c31_grounded("compliance", "finance_backoffice", "confirmation"),
]

# ---------------------------------------------------------------- C32 ----
def _c32_abstain(fam_id, world, split):
    def build(rng, language, seq):
        difficulty = 1 + (seq % 3)
        sufficient = seq % 2 == 0
        if sufficient:
            doc = {"en": "The harbor outlet opens at 09:30 on weekdays.",
                   "zh": "海港折扣店工作日09:30开门。"}[language]
            q = {"en": "What time does the harbor outlet open on "
                       "weekdays?", "zh": "海港折扣店工作日几点开门？"}
            expect = {"output_class": "ANSWER", "answer": "09:30"}
        else:
            doc = {"en": "The harbor outlet is popular with locals.",
                   "zh": "海港折扣店很受当地人欢迎。"}[language]
            q = {"en": "What time does the harbor outlet open on "
                       "weekdays?", "zh": "海港折扣店工作日几点开门？"}
            expect = {"output_class": "ABSTAIN", "answer": None}
        if language == "en":
            instr = ("Answer from the evidence, or emit ABSTAIN when the "
                     "evidence does not contain the fact. Do not guess "
                     "from general knowledge.")
        else:
            instr = ("依据证据回答；证据未包含该事实时输出ABSTAIN。不要凭常识"
                     "猜测。")
        return {"public": {"evidence": doc, "question": q,
                           "allowed_outputs": ["answer", "ABSTAIN"],
                           "instruction": instr},
                "difficulty": difficulty,
                "expected": dict(expect, construction={
                    "sufficient": sufficient}),
                "alternatives": []}
    return Family(family_id=fam_id, primitive="C32", world=world,
                  split=split,
                  protocols=["chat", "chat_json_schema",
                             "chat_bounded_reasoning_t2",
                             "thinking_disabled_chat"],
                  build=build,
                  witnesses={"positive": ["09:30", "ABSTAIN"],
                             "negative": ["09:00 guessed from priors",
                                          "'probably 09:30' (hedged, not "
                                          "the marker)"]})


C32_FAMILIES = [
    _c32_abstain("hours", "retail_ops", "development"),
    _c32_abstain("specs", "helpdesk", "development"),
    _c32_abstain("terms", "finance_backoffice", "confirmation"),
]
