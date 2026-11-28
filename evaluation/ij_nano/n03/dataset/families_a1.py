"""Batch A task families, C01-C04 (IJ-NANO-1.3S N03-B2).

Per primitive: two development families + one confirmation family, disjoint
worlds and entity pools. Ground truth is construction-semantics based: each
case's ``expected`` records the machine-checkable construction attributes,
and the independent verifier (dataset/verify.py) re-derives truth from a
separately implemented truth table or computation over the PUBLIC payload -
never by importing the builders in this module.
"""
from __future__ import annotations

from .core import Family, WORLDS

# ---------------------------------------------------------------- C01 ----
_C01_HELPDESK = {
    "refund_request": {"payment": 1, "reversal": 1},
    "exchange_request": {"payment": 1, "reversal": 0, "swap_item": 1},
    "shipping_status": {"asks_where": 1},
    "account_lock": {"locked_out": 1},
    "incident_report": {"reports_outage": 1},
    "feature_request": {"suggests_feature": 1},
    "billing_query": {"asks_charge_explanation": 1},
    "escalation_demand": {"demands_manager": 1},
}
_C01_HELPDESK_TEXT = {
    "en": {
        "refund_request": ["I want my money back for the last charge",
                           "Please refund the payment I made on Monday"],
        "exchange_request": ["I'd like to swap this for the other size",
                             "Can I exchange the item I bought?"],
        "shipping_status": ["where is my package right now",
                            "has my order shipped yet"],
        "account_lock": ["I'm locked out of my account",
                         "my login keeps saying account locked"],
        "incident_report": ["the dashboard has been down all morning",
                            "nothing loads, looks like an outage"],
        "feature_request": ["it would be great if you added dark mode",
                            "please consider adding a search bar"],
        "billing_query": ["can you explain this charge on my invoice",
                          "what is the 49 euro fee for"],
        "escalation_demand": ["get me your manager immediately",
                              "I want to speak to a supervisor now"]},
    "zh": {
        "refund_request": ["我想退回上次的付款", "请把我周一付的钱退给我"],
        "exchange_request": ["我想换一个尺码", "这个能换货吗"],
        "shipping_status": ["我的包裹现在到哪里了", "我的订单发货了吗"],
        "account_lock": ["我的账号被锁了", "登录一直提示账户锁定"],
        "incident_report": ["控制台整个上午都打不开", "什么都加载不出来，像是故障了"],
        "feature_request": ["如果能加个深色模式就好了", "建议增加搜索栏"],
        "billing_query": ["能解释一下账单里的这笔费用吗", "这49欧的费用是什么"],
        "escalation_demand": ["马上让你们经理来", "我现在就要找主管"]},
}
_C01_SMARTHOME = {
    "set_device": {"wants_state_change": 1},
    "query_state": {"asks_current_state": 1},
    "schedule_action": {"wants_later_execution": 1},
    "cancel_schedule": {"cancels_previous": 1},
    "group_control": {"targets_multiple": 1},
    "energy_report": {"asks_usage_summary": 1},
}
_C01_SMARTHOME_TEXT = {
    "en": {
        "set_device": ["turn the air purifier to level two",
                       "set the study lights to 40 percent"],
        "query_state": ["is the towel warmer on right now",
                        "what's the blind position in the sunroom"],
        "schedule_action": ["start the purifier at seven tomorrow",
                            "close the blinds at sunset"],
        "cancel_schedule": ["cancel tomorrow morning's purifier run",
                            "remove the scheduled blind closing"],
        "group_control": ["turn off everything in the study and hallway",
                          "set all lights downstairs to night mode"],
        "energy_report": ["how much power did the sunroom use this week",
                          "show me this month's energy summary"]},
    "zh": {
        "set_device": ["把空气净化器调到二档", "书房灯光调到百分之四十"],
        "query_state": ["毛巾加热架现在开着吗", "阳光房的窗帘现在在什么位置"],
        "schedule_action": ["明天七点启动净化器", "日落时关窗帘"],
        "cancel_schedule": ["取消明天早上的净化器运行", "把已定的关窗帘任务取消"],
        "group_control": ["把书房和走廊的设备全部关掉", "楼下所有灯调成夜间模式"],
        "energy_report": ["阳光房这周用了多少电", "给我看本月的能耗汇总"]},
}
_C01_BANKING = {
    "balance_inquiry": {"asks_balance": 1},
    "transfer_request": {"instructs_move_money": 1},
    "card_freeze": {"blocks_card": 1},
    "loan_question": {"asks_credit_product": 1},
    "statement_request": {"asks_document": 1},
    "fraud_alert": {"reports_unknown_tx": 1},
    "branch_hours": {"asks_office_info": 1},
    "currency_exchange": {"asks_fx_rate": 1},
}
_C01_BANKING_TEXT = {
    "en": {
        "balance_inquiry": ["what's my current balance",
                            "how much is left in account 2210"],
        "transfer_request": ["move 200 to account 3308",
                             "send 50 to my savings account"],
        "card_freeze": ["freeze my card, I can't find it",
                        "block the card ending 4471"],
        "loan_question": ["do you offer renovation loans",
                          "what are the mortgage rates"],
        "statement_request": ["send me last month's statement",
                              "I need a PDF of my transactions"],
        "fraud_alert": ["there's a charge I never made",
                        "someone used my card abroad"],
        "branch_hours": ["is the midtown branch open on Saturdays",
                         "what time does the harbor branch close"],
        "currency_exchange": ["what's the rate for USD to JPY",
                              "how much is 1000 euros in yen"]},
    "zh": {
        "balance_inquiry": ["我账户2210还有多少余额", "查一下当前余额"],
        "transfer_request": ["转200到账户3308", "往储蓄账户转50"],
        "card_freeze": ["卡丢了，帮我冻结", "冻结尾号4471的卡"],
        "loan_question": ["你们有装修贷款吗", "房贷利率是多少"],
        "statement_request": ["把上个月的账单发给我", "我需要交易流水PDF"],
        "fraud_alert": ["有一笔不是我刷的消费", "有人在国外刷了我的卡"],
        "branch_hours": ["城中支行周六营业吗", "海港支行几点关门"],
        "currency_exchange": ["美元兑日元的汇率是多少", "1000欧能换多少日元"]},
}


def _c01_family(fam_id, world, split, catalog, texts, base_catalog_size):
    def build(rng, language, seq):
        label = rng.choice(sorted(catalog))
        variant = texts[language][label][seq % len(texts[language][label])]
        difficulty = 1 + (seq % 3)
        if difficulty == 1:                      # smaller, easier menu
            others = rng.sample([k for k in sorted(catalog) if k != label], 3)
            shown = sorted([label] + others)
        else:
            shown = sorted(catalog)
        payload = {"utterance": variant,
                   "intent_catalog": {k: _c01_desc(k) for k in shown},
                   "instruction": {
                       "en": "Choose exactly one intent label from the "
                             "catalog for this utterance.",
                       "zh": "从目录中为这句话选择恰好一个意图标签。"}[language]}
        return {"public": payload, "difficulty": difficulty,
                "expected": {"label": label,
                             "construction": dict(catalog[label])}}
    return Family(family_id=fam_id, primitive="C01", world=world,
                  split=split,
                  protocols=["chat", "chat_json_schema",
                             "chat_bounded_reasoning_t2", "thinking_disabled_chat"],
                  build=build,
                  witnesses={
                      "positive": [
                          '{"intent": "shipping_status"}',
                          "shipping_status"],
                      "negative": [
                          '{"intent": "refund_request"}',
                          "I think maybe shipping, not sure"]})


def _c01_desc(label: str) -> str:
    d = {"refund_request": "customer wants money returned for a payment",
         "exchange_request": "customer wants to swap an item, not money back",
         "shipping_status": "customer asks where a package or order is",
         "account_lock": "customer cannot log in, account locked",
         "incident_report": "customer reports a service outage or fault",
         "feature_request": "customer suggests a new product feature",
         "billing_query": "customer asks to explain a charge",
         "escalation_demand": "customer demands a human supervisor",
         "set_device": "change a device state or setting now",
         "query_state": "ask the current state of a device",
         "schedule_action": "run something at a later time",
         "cancel_schedule": "remove a previously scheduled run",
         "group_control": "control several devices together",
         "energy_report": "summarize energy usage",
         "balance_inquiry": "ask how much money is in the account",
         "transfer_request": "move money between accounts",
         "card_freeze": "temporarily block a payment card",
         "loan_question": "ask about credit or loan products",
         "statement_request": "ask for a document of transactions",
         "fraud_alert": "report a transaction not made by the customer",
         "branch_hours": "ask branch opening information",
         "currency_exchange": "ask exchange rates"}
    return d[label]


C01_FAMILIES = [
    _c01_family("helpdesk", "helpdesk", "development",
                _C01_HELPDESK, _C01_HELPDESK_TEXT, 8),
    _c01_family("smarthome", "smart_home", "development",
                _C01_SMARTHOME, _C01_SMARTHOME_TEXT, 6),
    _c01_family("banking", "finance_backoffice", "confirmation",
                _C01_BANKING, _C01_BANKING_TEXT, 8),
]

# ---------------------------------------------------------------- C02 ----
_C02_ACTIONS = {"submit": {"en": "submit", "zh": "提交"},
                "review": {"en": "review", "zh": "评审"},
                "approve": {"en": "approve", "zh": "审批"},
                "migrate": {"en": "migrate", "zh": "迁移"},
                "archive": {"en": "archive", "zh": "归档"}}
_C02_OBJECTS = {"quarterly_report": {"en": "the quarterly report",
                                     "zh": "季度报告"},
                "onboarding_guide": {"en": "the onboarding guide",
                                     "zh": "入职指南"},
                "pricing_sheet": {"en": "the pricing sheet", "zh": "价格表"},
                "data_export": {"en": "the data export", "zh": "数据导出"},
                "audit_trail": {"en": "the audit trail", "zh": "审计记录"}}
_C02_DEADLINES = {"2026-12-04", "2026-12-11", "2027-01-08", None}


def _c02_family(fam_id, world, split, voice):
    def build(rng, language, seq):
        action = rng.choice(sorted(_C02_ACTIONS))
        obj = rng.choice(sorted(_C02_OBJECTS))
        deadline = rng.choice(sorted(d for d in _C02_DEADLINES if d))
        has_deadline = (seq % 2 == 0)
        has_criterion = (seq % 3 != 0)
        difficulty = 1 + (seq % 3)
        a = _C02_ACTIONS[action][language]
        o = _C02_OBJECTS[obj][language]
        if voice == "manager":
            core = (f"Please {a} {o}"
                    if language == "en" else f"请{a}{o}")
        else:
            core = (f"Could you {a} {o} when you get a chance"
                    if language == "en" else f"有空的话帮我{a}一下{o}")
        if language == "en":
            dl = f" by {deadline}" if has_deadline else ""
            crit = (f" Completion means it is visible in the system."
                    if has_criterion else "")
        else:
            dl = f"，截止{deadline}" if has_deadline else ""
            crit = " 完成标准是能在系统里看到。" if has_criterion else ""
        msg = core + dl + ("。" if language == "zh" else ".") + crit
        expected = {"action": action, "object": obj,
                    "deadline": deadline if has_deadline else None,
                    "completion_criterion": (
                        "visible_in_system" if has_criterion else None),
                    "unknown_flags": {
                        "deadline": not has_deadline,
                        "completion_criterion": not has_criterion}}
        return {"public": {"message": msg, "schema_fields": [
                    "action", "object", "deadline", "completion_criterion",
                    "unknown_flags"],
                "instruction": {
                    "en": "Extract the goal record. Use null plus a true "
                          "unknown flag when a field is not stated.",
                    "zh": "提取目标记录。未说明的字段用null并将unknown标记为true。"
                }[language]},
                "difficulty": difficulty,
                "expected": expected,
                "alternatives": []}
    return Family(family_id=fam_id, primitive="C02", world=world,
                  split=split,
                  protocols=["chat", "chat_json_schema",
                             "chat_bounded_reasoning_t2"],
                  build=build,
                  witnesses={
                      "positive": [
                          '{"action":"submit","object":"quarterly_report",'
                          '"deadline":"2026-12-04",'
                          '"completion_criterion":"visible_in_system",'
                          '"unknown_flags":{"deadline":false,'
                          '"completion_criterion":false}}'],
                      "negative": [
                          '{"action":"submit","object":"quarterly_report",'
                          '"deadline":"2026-12-04"}   # fields dropped',
                          "deadline invented for a no-deadline message"]})


C02_FAMILIES = [
    _c02_family("project", "finance_backoffice", "development", "manager"),
    _c02_family("personal", "smart_home", "development", "casual"),
    _c02_family("logcoord", "logistics", "confirmation", "manager"),
]

# ---------------------------------------------------------------- C03 ----
_C03_ITEMS = {"trail_jacket": {"en": "trail jacket", "zh": "冲锋衣",
                               "stock": 1, "tag": "apparel"},
              "insulated_bottle": {"en": "insulated bottle", "zh": "保温壶",
                                   "stock": 0, "tag": "gear"},
              "camp_stool": {"en": "camp stool", "zh": "露营凳",
                             "stock": 1, "tag": "gear"},
              "wool_scarf": {"en": "wool scarf", "zh": "羊毛围巾",
                             "stock": 0, "tag": "apparel"},
              "headlamp": {"en": "headlamp", "zh": "头灯",
                           "stock": 1, "tag": "electronics"},
              "map_case": {"en": "map case", "zh": "地图包",
                           "stock": 1, "tag": "gear"}}


def _c03_formatting(fam_id, world, split):
    def build(rng, language, seq):
        keys = sorted(_C03_ITEMS)
        chosen = [k for i, k in enumerate(keys) if i != seq % len(keys)][:4]
        difficulty = 1 + (seq % 3)
        mode = seq % 3
        # uppercase is undefined for Chinese surfaces: zh cases use the
        # in-stock / not-in-stock semantics without the case requirement
        # (design constraint, not a verifier concession)
        upper = language == "en" and mode in (1, 2)
        if language == "zh":
            mode = 0 if mode == 1 else mode
        items = {k: dict(_C03_ITEMS[k],
                         name=_C03_ITEMS[k][language]) for k in chosen}
        if language == "en":
            if mode == 0:
                instr = "List only the in-stock items, one per line."
                rule = "in_stock"
            elif mode == 1:
                instr = "List only the in-stock items, one per line, in " \
                        "uppercase."
                rule = "in_stock_upper"
            else:
                instr = "List the items that are NOT in stock, one per " \
                        "line, in uppercase."
                rule = "not_in_stock_upper"
        else:
            if mode == 0:
                instr = "只列出有库存的物品，每行一个。"
                rule = "in_stock"
            elif mode == 1:
                instr = "只列出有库存的物品，每行一个。"
                rule = "in_stock"
            else:
                instr = "列出没有库存的物品，每行一个。"
                rule = "not_in_stock"
        upper = "upper" in rule
        in_stock = rule.startswith("in_stock")
        expected_lines = []
        for k in chosen:
            if (_C03_ITEMS[k]["stock"] == 1) == in_stock:
                nm = _C03_ITEMS[k]["en"] if upper else _C03_ITEMS[k][language]
                # uppercase applies to the latin name regardless of surface
                expected_lines.append(nm.upper() if upper else nm)
        item_list = [{"name": it["name"], "stock": it["stock"],
                      "tag": it["tag"]} for it in items.values()]
        return {"public": {"items": item_list, "instruction": instr},
                "difficulty": difficulty,
                "expected": {"lines": expected_lines, "rule": rule},
                "alternatives": []}
    return Family(family_id=fam_id, primitive="C03", world=world,
                  split=split,
                  protocols=["chat", "chat_json_schema", "thinking_disabled_chat"],
                  build=build,
                  witnesses={"positive": ["TRAIL JACKET\nCAMP STOOL\nHEADLAMP",
                                          "trail jacket\ncamp stool\nheadlamp"],
                             "negative": ["trail jacket, camp stool, headlamp, map case",   # includes out-of-stock wool_scarf missing but extra item
                                          "TRAIL JACKET CAMP STOOL"]})  # separator dropped


def _c03_formfill(fam_id, world, split):
    fields = {"full_name": {"en": "full name", "zh": "姓名"},
              "delivery_city": {"en": "delivery city", "zh": "送达城市"},
              "contact_phone": {"en": "contact phone", "zh": "联系电话"}}

    def build(rng, language, seq):
        difficulty = 1 + (seq % 3)
        member = WORLDS["retail_ops"][language]["members"][seq % 3]
        city = {"en": ["Rotterdam", "Kyoto", "Porto"],
                "zh": ["鹿特丹", "京都", "波尔图"]}[language][seq % 3]
        phone = f"+31-10-{555000 + seq * 7}"
        stated = {"full_name": member, "delivery_city": city,
                  "contact_phone": phone}
        target = sorted(fields)[seq % 3]
        if language == "en":
            msg = (f"My name is {stated['full_name']}, the delivery city "
                   f"is {stated['delivery_city']}, and my phone is "
                   f"{stated['contact_phone']}. Fill in ONLY the "
                   f"{fields[target]['en']} field.")
        else:
            msg = (f"我叫{stated['full_name']}，送达城市是"
                   f"{stated['delivery_city']}，电话是"
                   f"{stated['contact_phone']}。只填写"
                   f"{fields[target]['zh']}字段。")
        return {"public": {"message": msg, "form_fields": sorted(fields)},
                "difficulty": difficulty,
                "expected": {"field": target, "value": stated[target]},
                "alternatives": []}
    return Family(family_id=fam_id, primitive="C03", world=world,
                  split=split,
                  protocols=["chat", "chat_json_schema", "thinking_disabled_chat"],
                  build=build,
                  witnesses={"positive": ['{"delivery_city": "Rotterdam"}'],
                             "negative": ['{"full_name": "Dana", "delivery_city": "Rotterdam"}',   # extra field filled
                                          '{"delivery_city": "dam"}']})  # value corrupted


def _c03_one_edit(fam_id, world, split):
    """Confirmation family: apply exactly ONE edit instruction to a short
    record line. Different semantic operation from the dev families
    (formatting/filtering vs single-edit transformation)."""
    def build(rng, language, seq):
        difficulty = 1 + (seq % 3)
        mode = seq % 3
        hub = WORLDS["logistics"][language]["hubs"][seq % 3]
        parcel = WORLDS["logistics"][language]["parcels"][seq % 3]
        mode_name = WORLDS["logistics"][language]["modes"][seq % 3]
        if language == "en":
            line = f"{parcel} | route via {hub} | {mode_name} | PRIORITY LOW"
        else:
            line = f"{parcel} | 途经{hub} | {mode_name} | 优先级低"
        if mode == 0:
            new = "2026-12-04"
            if language == "en":
                instr = (f"Change the priority to HIGH and keep everything "
                         f"else exactly as is. Output only the updated line.")
                expect = (f"{parcel} | route via {hub} | {mode_name} | "
                          f"PRIORITY HIGH")
            else:
                instr = "把优先级改为高，其余保持不变。只输出更新后的这一行。"
                expect = f"{parcel} | 途经{hub} | {mode_name} | 优先级高"
            rule = "set_priority_high"
        elif mode == 1:
            if language == "en":
                instr = ("Remove the transport mode segment and keep "
                         "everything else exactly as is. Output only the "
                         "updated line.")
                expect = f"{parcel} | route via {hub} | PRIORITY LOW"
            else:
                instr = "删去运输方式这一段，其余保持不变。只输出更新后的这一行。"
                expect = f"{parcel} | 途经{hub} | 优先级低"
            rule = "drop_segment_mode"
        else:
            hub2 = WORLDS["logistics"][language]["hubs"][(seq + 1) % 3]
            if language == "en":
                instr = (f"Replace the routing hub with {hub2} and keep "
                         f"everything else exactly as is. Output only the "
                         f"updated line.")
                expect = (f"{parcel} | route via {hub2} | {mode_name} | "
                          f"PRIORITY LOW")
            else:
                instr = f"把途经仓改为{hub2}，其余保持不变。只输出更新后的这一行。"
                expect = f"{parcel} | 途经{hub2} | {mode_name} | 优先级低"
            rule = "replace_hub"
        return {"public": {"line": line, "instruction": instr},
                "difficulty": difficulty,
                "expected": {"line": expect, "rule": rule},
                "alternatives": []}
    return Family(family_id=fam_id, primitive="C03", world=world,
                  split=split,
                  protocols=["chat", "chat_json_schema", "thinking_disabled_chat"],
                  build=build,
                  witnesses={"positive": ["PKG-77120 | route via KRK-2 | "
                                          "rail | PRIORITY HIGH"],
                             "negative": ["PKG-77120 | route via KRK-2 | "
                                          "rail | PRIORITY HIGH | edited",
                                          "priority changed but mode dropped"]})


C03_FAMILIES = [
    _c03_formatting("formatting", "retail_ops", "development"),
    _c03_formfill("formfill", "retail_ops", "development"),
    _c03_one_edit("oneedit", "logistics", "confirmation"),
]

# ---------------------------------------------------------------- C04 ----
def _c04_filter_family(fam_id, world, split, domain):
    """Deterministic multi-constraint filtering: truth recomputable from the
    PUBLIC item table alone (strongest independence class)."""
    def build(rng, language, seq):
        difficulty = 1 + (seq % 3)
        n_items = 4 + (seq % 3) * 2
        if domain == "retail":
            names = {"en": ["trail jacket", "insulated bottle", "camp stool",
                            "wool scarf", "headlamp", "map case", "rain poncho",
                            "stash bag"],
                     "zh": ["冲锋衣", "保温壶", "露营凳", "羊毛围巾", "头灯",
                            "地图包", "雨披", "收纳袋"]}
            base = [{"id": f"SKU-{i:03d}", "name_en": names["en"][i % 8],
                     "name_zh": names["zh"][i % 8],
                     "price": 15 + ((i * 37) % 180),
                     "stock": (i * 7) % 3, "rating": 2 + ((i * 11) % 40) / 10,
                     "vendor": ["alpine-co", "trailworks", "north-depot"][i % 3]}
                    for i in range(n_items)]
        else:  # archive / guestlist share the numeric engine
            base = [{"id": f"DOC-{i:03d}",
                     "name_en": f"report-{i}",
                     "name_zh": f"报告{i}",
                     "price": 2 + ((i * 13) % 40),
                     "stock": (i * 5) % 3, "rating": 1 + ((i * 17) % 50) / 10,
                     "vendor": ["team-a", "team-b", "team-c"][i % 3]}
                    for i in range(n_items)]
        constraints = []
        if seq % 3 == 0:
            constraints = [("price<=", 60), ("stock>", 0)]
        elif seq % 3 == 1:
            constraints = [("stock>", 0), ("rating>=", 3.0),
                           ("vendor!=", "north-depot")]
        else:
            constraints = [("price<=", 100), ("rating>=", 3.5)]
        order = "rating" if difficulty >= 2 else None
        label = {"en": {"price<=": "price at or under", "stock>": "in stock",
                        "rating>=": "rating at least", "vendor!=":
                        "not from vendor", "sort_by": "sort by"},
                 "zh": {"price<=": "价格不高于", "stock>": "有库存",
                        "rating>=": "评分不低于", "vendor!=": "供应商不是",
                        "sort_by": "排序方式"}}[language]
        if language == "en":
            cs = "; ".join(
                f"{label[k]} {v}" if k != "stock>" else f"{label[k]}"
                for k, v in constraints)
            instr = f"List the matching item ids. Requirements: {cs}."
            if order:
                instr += f" Sort by {order} descending."
        else:
            cs = "；".join(
                f"{label[k]}{v}" if k != "stock>" else label[k]
                for k, v in constraints)
            instr = f"列出满足条件的物品编号。条件：{cs}。"
            if order:
                instr += f"按{order}降序排列。"
        items = [{"id": b["id"], "name": b[f"name_{language}"],
                  "price": b["price"], "stock": b["stock"],
                  "rating": b["rating"], "vendor": b["vendor"]}
                 for b in base]
        survivors = [b for b in base if all(
            (b["price"] <= v if k == "price<=" else
             b["stock"] > v if k == "stock>" else
             b["rating"] >= v if k == "rating>=" else
             b["vendor"] != v) for k, v in constraints)]
        if order:
            survivors.sort(key=lambda b: (-b[order], b["id"]))
        expected = [b["id"] for b in survivors]
        return {"public": {"items": items, "instruction": instr},
                "difficulty": difficulty,
                "expected": {"ids": expected, "constraints": [
                    [k, v] for k, v in constraints], "order": order},
                "alternatives": ["ties in unspecified keys may differ"
                                 if not order else "no alternatives"]}
    return Family(family_id=fam_id, primitive="C04", world=world,
                  split=split,
                  protocols=["chat", "chat_json_schema",
                             "chat_bounded_reasoning_t2"],
                  build=build,
                  witnesses={"positive": ["SKU-001, SKU-005", "[]   # empty "
                                          "result is a correct answer"],
                             "negative": ["SKU-001\n\nSKU-002\n\n...all ids...",
                                          "SKU-999   # id not in the table"]})


def _c04_guest(fam_id, world, split):
    """Confirmation family: guest filtering over its own schema
    (rsvp / plus_ones / vip) - a distinct constraint engine from the dev
    price/stock/rating families."""
    def build(rng, language, seq):
        difficulty = 1 + (seq % 3)
        n = 5 + (seq % 3)
        names = {"en": ["Ana", "Bo", "Cai", "Dov", "Elif", "Fum", "Gus"],
                 "zh": ["小安", "小博", "小蔡", "小多", "小埃", "小福", "小古"]}
        guests = [{"id": f"GST-{i:02d}", "name": names[language][i % 7],
                   "rsvp": ["yes", "no", "maybe"][i % 3],
                   "plus_ones": i % 4, "vip": (i % 2 == 0)}
                  for i in range(n)]
        constraints = [("rsvp==", "yes"), ("plus_ones<=", 2)]
        if difficulty >= 2:
            constraints.append(("vip==", True))
        if language == "en":
            cs = ("replied yes; bringing at most 2 extra people"
                  + ("; VIP guests only" if difficulty >= 2 else ""))
            instr = (f"List the guest ids matching ALL conditions: {cs}. "
                     f"Sort by plus_ones descending.")
        else:
            cs = ("已回复参加；额外人数不超过2"
                  + ("；仅限VIP客人" if difficulty >= 2 else ""))
            instr = f"列出同时满足以下条件的客人编号：{cs}。按额外人数降序排列。"
        survivors = [g for g in guests if all(
            (g["rsvp"] == v if k == "rsvp==" else
             g["plus_ones"] <= v if k == "plus_ones<=" else
             g["vip"] is v) for k, v in constraints)]
        survivors.sort(key=lambda g: (-g["plus_ones"], g["id"]))
        return {"public": {"items": guests, "instruction": instr},
                "difficulty": difficulty,
                "expected": {"ids": [g["id"] for g in survivors],
                             "constraints": [[k, v] for k, v in constraints],
                             "order": "plus_ones"},
                "alternatives": ["ties in ids may appear in any order when "
                                 "plus_ones is equal"]}
    return Family(family_id=fam_id, primitive="C04", world=world,
                  split=split,
                  protocols=["chat", "chat_json_schema",
                             "chat_bounded_reasoning_t2"],
                  build=build,
                  witnesses={"positive": ["GST-00, GST-04",
                                          "[]   # nobody qualifies is valid"],
                             "negative": ["GST-00, GST-01, GST-02, GST-03",
                                          "GST-01   # rsvp != yes included"]})


C04_FAMILIES = [
    _c04_filter_family("retail", "retail_ops", "development", "retail"),
    _c04_filter_family("docs", "finance_backoffice", "development", "docs"),
    _c04_guest("guestlist", "clinic", "confirmation"),
]
