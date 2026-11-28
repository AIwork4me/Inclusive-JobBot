"""Batch B task families, C09-C16 (IJ-NANO-1.3S N03-B2).

Output-representation diversity is the point of this batch: flat JSON,
nested JSON, a compact DSL, typed slot records, mention/id pairs, numeric
records, unit/currency conversions and grounded queries over tool output.
Ground truth is public-recomputable wherever arithmetic or documents allow
(C09/C10/C11/C14/C15/C16); construction semantics with independent rule
tables cover the authored cases (C12/C13).
"""
from __future__ import annotations

from .core import Family, WORLDS

# ---------------------------------------------------------------- C09 ----
def _c09_json(fam_id, world, split, kind):
    """Flat JSON structural generation: the expected record is recomputable
    from the public payload alone."""
    def build(rng, language, seq):
        difficulty = 1 + (seq % 3)
        if kind == "profile":
            names = {"en": ["Ada", "Bram", "Cleo"], "zh": ["小艾达", "小布拉姆", "小克利奥"]}
            payload = {"full_name": names[language][seq % 3],
                       "seat_count": 1 + seq % 9, "active": seq % 2 == 0}
            schema = {"full_name": "string", "seat_count": "integer",
                      "active": "boolean"}
            record = dict(payload)
        elif kind == "order":
            payload = {"order_ref": f"ORD-{4100 + seq}",
                       "item_count": 2 + seq % 5,
                       "total_minor": 1000 + seq * 137,
                       "paid": seq % 3 != 0}
            schema = {"order_ref": "string", "item_count": "integer",
                      "total_minor": "integer", "paid": "boolean"}
            record = dict(payload)
        else:  # timesheet (confirmation)
            payload = {"worker_id": f"W-{200 + seq}",
                       "hours": round(1.5 + (seq % 7) * 0.5, 1),
                       "break_minutes": [0, 15, 30][seq % 3],
                       "remote": seq % 2 == 1}
            schema = {"worker_id": "string", "hours": "number",
                      "break_minutes": "integer", "remote": "boolean"}
            record = dict(payload)
        if language == "en":
            instr = ("Emit a single JSON object conforming exactly to this "
                     "schema, populated from the details.")
        else:
            instr = "根据以下信息，输出一个严格符合该结构定义的JSON对象。"
        return {"public": {"schema": schema, "details": payload,
                           "instruction": instr},
                "difficulty": difficulty,
                "expected": {"record": record},
                "alternatives": ["key order irrelevant (canonicalized "
                                 "before comparison)"]}
    return Family(family_id=fam_id, primitive="C09", world=world,
                  split=split,
                  protocols=["chat", "chat_json_schema",
                             "chat_bounded_reasoning_t2",
                             "completion_negative_transfer"],
                  build=build,
                  witnesses={"positive": ['{"full_name": "Ada", '
                                          '"seat_count": 4, "active": true}'],
                             "negative": ['{"full_name": "Ada", "seat_count": "4"}',
                                          '{"full_name": "Ada"}   # field dropped']})


C09_FAMILIES = [
    _c09_json("profile", "smart_home", "development", "profile"),
    _c09_json("order", "retail_ops", "development", "order"),
    _c09_json("timesheet", "finance_backoffice", "confirmation", "timesheet"),
]

# ---------------------------------------------------------------- C10 ----
def _c10_nested(fam_id, world, split, kind):
    def build(rng, language, seq):
        difficulty = 1 + (seq % 3)
        groups = 1 + seq % 3
        if kind == "shipment":
            outer, inner = "shipment", "line_items"
            g = [{"sku": f"SKU-{900 + i}", "qty": 1 + (seq + i) % 4,
                  "unit_price_minor": 500 + (seq * 31 + i * 97) % 9000}
                 for i in range(groups)]
            doc = {"carrier": WORLDS["logistics"][language]["modes"][seq % 3],
                   inner: g}
        elif kind == "orgchart":
            outer, inner = "department", "teams"
            g = [{"team": f"team-{i}", "lead": WORLDS["helpdesk"][language]
                  ["agents"][i % 3], "headcount": 2 + (seq + i) % 6}
                 for i in range(groups)]
            doc = {"department": "operations", inner: g}
        else:  # menu (confirmation)
            outer, inner = "category", "items"
            g = [{"dish": WORLDS["retail_ops"][language]["items"][i % 3],
                  "price_minor": 800 + (seq * 53 + i * 211) % 4000,
                  "spicy": (seq + i) % 2 == 0}
                 for i in range(groups)]
            doc = {"category": "seasonal", inner: g}
        schema = {"type": "object", "fields": {
            outer if kind != "shipment" else "carrier": "string",
            inner: {"type": "array", "min": groups, "item": {
                "type": "object", "fields": {
                    k: ("string" if isinstance(v, str) else
                        "integer" if isinstance(v, int) else "boolean")
                    for k, v in g[0].items()}}}}}
        if language == "en":
            instr = ("Emit one JSON object matching the nested schema: the "
                     f"array must contain exactly {groups} item(s) built "
                     "from the details.")
        else:
            instr = (f"输出符合嵌套结构的JSON对象：数组须恰好包含{groups}个"
                     "条目，内容来自所给信息。")
        return {"public": {"schema": schema, "details": doc,
                           "instruction": instr},
                "difficulty": difficulty,
                "expected": {"document": doc, "array_size": groups},
                "alternatives": ["array order follows the details order; "
                                 "no other freedom"]}
    return Family(family_id=fam_id, primitive="C10", world=world,
                  split=split,
                  protocols=["chat", "chat_json_schema",
                             "chat_bounded_reasoning_t2"],
                  build=build,
                  witnesses={"positive": ['{"carrier":"rail","line_items":'
                                          '[{"sku":"SKU-900","qty":2,'
                                          '"unit_price_minor":627}]}'],
                             "negative": ["line item flattened into the "
                                          "outer object",
                                          "array with one entry where schema "
                                          "demands 2"]})


C10_FAMILIES = [
    _c10_nested("shipment", "logistics", "development", "shipment"),
    _c10_nested("orgchart", "helpdesk", "development", "orgchart"),
    _c10_nested("menu", "retail_ops", "confirmation", "menu"),
]

# ---------------------------------------------------------------- C11 ----
_DSL_ACTIONS = {
    "MOVE": 2, "PICK": 1, "DROP": 1, "SCAN": 1, "CHARGE": 1}
_DSL_DESC = {"en": {"MOVE": "MOVE <from> <to> - travel between locations",
                    "PICK": "PICK <object> - pick an object up",
                    "DROP": "DROP <object> - put an object down",
                    "SCAN": "SCAN <area> - scan an area for items",
                    "CHARGE": "CHARGE <dock> - dock and recharge"},
             "zh": {"MOVE": "MOVE <起点> <终点> - 在位置间移动",
                    "PICK": "PICK <对象> - 拾取对象",
                    "DROP": "DROP <对象> - 放下对象",
                    "SCAN": "SCAN <区域> - 扫描区域寻找物品",
                    "CHARGE": "CHARGE <dock> - 对接充电"}}
_DSL_LOCS = {"en": ["dock", "aisle3", "packzone"], "zh": ["dock", "aisle3", "packzone"]}
_DSL_OBJS = {"en": ["tote7", "crate2", "pallet9"], "zh": ["tote7", "crate2", "pallet9"]}


def _c11_dsl(fam_id, world, split):
    def build(rng, language, seq):
        difficulty = 1 + (seq % 3)
        n_ops = 1 + seq % 3
        ops = []
        for i in range(n_ops):
            act = ["MOVE", "PICK", "SCAN", "DROP", "CHARGE"][i % 5]
            if act == "MOVE":
                a = _DSL_LOCS[language][i % 3]
                b = _DSL_LOCS[language][(i + 1) % 3]
                if a == b:
                    b = _DSL_LOCS[language][(i + 2) % 3]
                ops.append(f"MOVE {a} {b}")
            elif act in ("PICK", "DROP"):
                ops.append(f"{act} {_DSL_OBJS[language][i % 3]}")
            elif act == "SCAN":
                ops.append(f"SCAN {_DSL_LOCS[language][i % 3]}")
            else:
                ops.append("CHARGE dock")
        program = "\n".join(ops)
        vocab = {k: _DSL_DESC[language][k] for k in sorted(_DSL_ACTIONS)}
        if language == "en":
            instr = ("Write the robot program for this task using ONLY the "
                     "declared statements, one per line, in the given "
                     "order.")
        else:
            instr = "仅使用声明的语句，按给定顺序每行一条，写出机器人程序。"
        # task steps render the INSTANTIATED operations (the exact
        # locations/objects), so the program is fully determined
        def _step(op):
            t = op.split()
            if t[0] == "MOVE":
                return {"en": f"move from {t[1]} to {t[2]}",
                        "zh": f"从{t[1]}移动到{t[2]}"}[language]
            if t[0] == "PICK":
                return {"en": f"pick up {t[1]}", "zh": f"拾取{t[1]}"}[
                    language]
            if t[0] == "DROP":
                return {"en": f"put down {t[1]}", "zh": f"放下{t[1]}"}[
                    language]
            if t[0] == "SCAN":
                return {"en": f"scan {t[1]}", "zh": f"扫描{t[1]}"}[language]
            return {"en": "dock and recharge", "zh": "对接充电"}[language]
        task_steps = [f"step {i + 1}: {_step(o)}"
                      for i, o in enumerate(ops)]
        return {"public": {"grammar": vocab, "task_steps": task_steps,
                           "instruction": instr},
                "difficulty": difficulty,
                "expected": {"program": program, "op_count": n_ops},
                "alternatives": []}
    return Family(family_id=fam_id, primitive="C11", world=world,
                  split=split,
                  protocols=["chat", "chat_json_schema"],
                  build=build,
                  witnesses={"positive": ["MOVE dock aisle3\nPICK tote7"],
                             "negative": ["move dock aisle3   # lowercase "
                                          "action token",
                                          "MOVE dock   # missing argument"]})


C11_FAMILIES = [
    _c11_dsl("robot", "logistics", "development"),
    _c11_dsl("batchops", "retail_ops", "development"),
    _c11_dsl("drone", "smart_home", "confirmation"),
]

# ---------------------------------------------------------------- C12 ----
def _c12_slots(fam_id, world, split, kind):
    def build(rng, language, seq):
        difficulty = 1 + (seq % 3)
        if kind == "booking":
            names = WORLDS["clinic"][language]["patients"]
            slots = {"patient": names[seq % 3],
                     "department": WORLDS["clinic"][language]["departments"]
                     [seq % 3],
                     "time": WORLDS["clinic"][language]["slots"][seq % 3],
                     "date": f"2026-12-{4 + seq % 20:02d}"}
            schema = {"patient": "string", "department": "string",
                      "time": "hh:mm", "date": "iso-date"}
            if language == "en":
                msg = (f"Please book {slots['patient']} in "
                       f"{slots['department']} on {slots['date']} at "
                       f"{slots['time']}.")
            else:
                msg = (f"请为{slots['patient']}预约{slots['department']}，"
                       f"日期{slots['date']}，时间{slots['time']}。")
        elif kind == "shipping":
            cities = {"en": ["Rotterdam", "Kyoto", "Porto"],
                      "zh": ["鹿特丹", "京都", "波尔图"]}
            slots = {"city": cities[language][seq % 3],
                     "weight_kg": round(0.5 + (seq % 9) * 0.5, 1),
                     "service": ["standard", "express", "economy"][seq % 3],
                     "insured": seq % 2 == 0}
            schema = {"city": "string", "weight_kg": "number",
                      "service": "enum", "insured": "boolean"}
            if language == "en":
                msg = (f"Ship my parcel to {slots['city']}, it weighs "
                       f"{slots['weight_kg']} kg, use "
                       f"{slots['service']} service"
                       + (", insured." if slots["insured"] else
                          ", not insured."))
            else:
                svc_zh = {"standard": "标准", "express": "特快",
                          "economy": "经济"}[slots["service"]]
                msg = (f"包裹寄往{slots['city']}，重{slots['weight_kg']}公斤，"
                       f"用{svc_zh}（{slots['service']}）服务"
                       + ("，需要保价。" if slots["insured"] else "，不保价。"))
        else:  # meeting (confirmation)
            slots = {"room": WORLDS["smart_home"][language]["rooms"][seq % 3],
                     "duration_min": 30 * (1 + seq % 3),
                     "attendees": 2 + seq % 5,
                     "recording": seq % 2 == 1}
            schema = {"room": "string", "duration_min": "integer",
                      "attendees": "integer", "recording": "boolean"}
            if language == "en":
                msg = (f"Reserve {slots['room']} for "
                       f"{slots['duration_min']} minutes for "
                       f"{slots['attendees']} people"
                       + (", with recording." if slots["recording"] else
                          ", no recording."))
            else:
                msg = (f"预订{slots['room']}，时长{slots['duration_min']}分钟，"
                       f"{slots['attendees']}人参加"
                       + ("，需要录制。" if slots["recording"] else "，不录制。"))
        if language == "en":
            instr = ("Fill every declared slot from the message; use null "
                     "only when the message does not state it.")
        else:
            instr = "从消息中填写所有声明的槽位；消息未提及的才用null。"
        return {"public": {"schema": schema, "message": msg,
                           "instruction": instr},
                "difficulty": difficulty,
                "expected": {"slots": slots},
                "alternatives": []}
    return Family(family_id=fam_id, primitive="C12", world=world,
                  split=split,
                  protocols=["chat", "chat_json_schema",
                             "native_function_calling"],
                  build=build,
                  witnesses={"positive": ['{"patient":"H. Tanaka",'
                                          '"department":"cardiology",'
                                          '"time":"14:10",'
                                          '"date":"2026-12-13"}'],
                             "negative": ["slot filled from a distractor "
                                          "entity",
                                          "missing slot without null"]})


C12_FAMILIES = [
    _c12_slots("booking", "clinic", "development", "booking"),
    _c12_slots("shipping", "logistics", "development", "shipping"),
    _c12_slots("meeting", "smart_home", "confirmation", "meeting"),
]

# ---------------------------------------------------------------- C13 ----
def _c13_coref(fam_id, world, split, kind):
    """Mention -> entity id. The target rotates per case; same-name (or
    same-kind) collisions are resolved by declared attribute agreement,
    which the construction records for the independent verifier."""
    CANDS = {
        "contacts": [
            {"id": "CT-1", "name": "Wei Zhang", "name_zh": "张伟",
             "attrs": {"role": "accountant", "city": "Porto"}},
            {"id": "CT-2", "name": "Wei Zhang", "name_zh": "张伟",
             "attrs": {"role": "engineer", "city": "Kyoto"}},
            {"id": "CT-3", "name": "Ana Reis", "name_zh": "安娜·雷斯",
             "attrs": {"role": "engineer", "city": "Porto"}}],
        "devices": [
            {"id": "DV-1", "name": "purifier", "name_zh": "净化器",
             "attrs": {"room": "study", "state": "on"}},
            {"id": "DV-2", "name": "purifier", "name_zh": "净化器",
             "attrs": {"room": "sunroom", "state": "off"}},
            {"id": "DV-3", "name": "blind", "name_zh": "窗帘",
             "attrs": {"room": "study", "state": "half"}}],
        "accounts": [
            {"id": "AC-7", "name": "Ines", "name_zh": "伊内斯",
             "attrs": {"currency": "EUR", "type": "savings"}},
            {"id": "AC-8", "name": "Ines", "name_zh": "伊内斯",
             "attrs": {"currency": "EUR", "type": "checking"}},
            {"id": "AC-9", "name": "Paul", "name_zh": "保罗",
             "attrs": {"currency": "USD", "type": "savings"}}]}

    def build(rng, language, seq):
        difficulty = 1 + (seq % 3)
        cand = CANDS[kind]
        target = cand[seq % 3]
        name_key = "name_zh" if language == "zh" else "name"
        same_name = [c for c in cand if c[name_key] == target[name_key]]
        if len(same_name) > 1:
            # collision: the mention must carry the distinguishing attrs
            dis = {k: v for k, v in target["attrs"].items()
                   if any(c["attrs"].get(k) != v for c in same_name)}
            attr_txt = ", ".join(f"{k} {v}" for k, v in sorted(dis.items()))
            if language == "en":
                passage = (f"{sorted(c['id'] for c in cand)[0]} and others "
                           f"are listed. The {target[name_key]} with "
                           f"({attr_txt}) sent today's file; a different "
                           f"{target[name_key]} replied earlier. Forward "
                           f"the file to the {target[name_key]} with "
                           f"({attr_txt}).")
                mention = f"the {target[name_key]} with ({attr_txt})"
            else:
                attr_txt_zh = "、".join(f"{k}为{v}" for k, v in
                                        sorted(dis.items()))
                passage = (f"候选名单已列出。属性{attr_txt_zh}的"
                           f"{target[name_key]}发来了今天的文件；另一位"
                           f"{target[name_key]}早些时候回复过。请把文件转"
                           f"发给属性{attr_txt_zh}的那位{target[name_key]}。")
                mention = f"属性{attr_txt_zh}的那位{target[name_key]}"
            match = {"name": target[name_key], "attrs": dis}
        else:
            # unique surface name resolves by itself
            others = ", ".join(c[name_key] for c in cand
                               if c["id"] != target["id"])
            if language == "en":
                passage = (f"Among {others} and {target[name_key]}, only "
                           f"{target[name_key]} handles this matter. Send "
                           f"the request to {target[name_key]}.")
                mention = target[name_key]
            else:
                passage = (f"在{others}与{target[name_key]}之中，只有"
                           f"{target[name_key]}负责此事。请把请求发给"
                           f"{target[name_key]}。")
                mention = target[name_key]
            match = {"name": target[name_key], "attrs": {}}
        cands_pub = [{"id": c["id"], "name": c[name_key],
                      "attrs": dict(c["attrs"])} for c in cand]
        if language == "en":
            instr = ("Resolve the marked mention to exactly one candidate "
                     "id. Attribute agreement beats recency.")
        else:
            instr = "将标记的指称解析到唯一候选编号；属性一致优先于就近原则。"
        return {"public": {"passage": passage, "mention": mention,
                           "candidates": cands_pub,
                           "instruction": instr},
                "difficulty": difficulty,
                "expected": {"resolution": target["id"],
                             "construction": {"kind": kind,
                                              "match": match}},
                "alternatives": []}
    return Family(family_id=fam_id, primitive="C13", world=world,
                  split=split,
                  protocols=["chat", "chat_json_schema",
                             "chat_bounded_reasoning_t2"],
                  build=build,
                  witnesses={"positive": ["CT-2", "DV-1"],
                             "negative": ["CT-1   # same name, wrong "
                                          "attribute",
                                          "AC-9   # recency/name trap"]})


C13_FAMILIES = [
    _c13_coref("contacts", "finance_backoffice", "development", "contacts"),
    _c13_coref("devices", "smart_home", "development", "devices"),
    _c13_coref("accounts", "finance_backoffice", "confirmation", "accounts"),
]

# ---------------------------------------------------------------- C14 ----
def _c14_numbers(fam_id, world, split, kind):
    def build(rng, language, seq):
        difficulty = 1 + (seq % 3)
        if kind == "finance":
            a = 1200 + seq * 91
            b = round(49.5 + seq * 3.25, 2)
            neg = -(50 + seq * 7)
            if language == "en":
                text = (f"Ledger shows a credit of {a:,} USD, a fee of "
                        f"{b} EUR and an adjustment of {neg} GBP.")
                schema = {"credit_usd": "number", "fee_eur": "number",
                          "adjustment_gbp": "number"}
                vals = {"credit_usd": a, "fee_eur": b,
                        "adjustment_gbp": neg}
            else:
                text = (f"账本显示入账{a:,}美元、手续费{b}欧元、调整项"
                        f"{neg}英镑。")
                schema = {"credit_usd": "number", "fee_eur": "number",
                          "adjustment_gbp": "number"}
                vals = {"credit_usd": a, "fee_eur": b,
                        "adjustment_gbp": neg}
        elif kind == "metrics":
            p = round(3.1 + seq * 1.7, 1)
            n = -(2 + seq)
            count = 1000 + seq * 37
            if language == "en":
                text = (f"Uptime ratio changed by {p} percent; error count "
                        f"delta {n}; sessions today {count:,}.")
                schema = {"uptime_delta_pct": "number",
                          "error_delta": "integer", "sessions": "integer"}
                vals = {"uptime_delta_pct": p, "error_delta": n,
                        "sessions": count}
            else:
                text = f"可用率变化{p}个百分点；错误数变化{n}；今日会话数{count:,}。"
                schema = {"uptime_delta_pct": "number",
                          "error_delta": "integer", "sessions": "integer"}
                vals = {"uptime_delta_pct": p, "error_delta": n,
                        "sessions": count}
        else:  # inventory (confirmation)
            lo, hi = 3 + seq, 12 + seq
            exact = 250 + seq * 13
            if language == "en":
                text = (f"Between {lo} and {hi} boxes per pallet are "
                        f"acceptable; today's count is exactly {exact}.")
                schema = {"pallet_min": "integer", "pallet_max": "integer",
                          "today_count": "integer"}
                vals = {"pallet_min": lo, "pallet_max": hi,
                        "today_count": exact}
            else:
                text = f"每托盘{lo}到{hi}箱为合格；今日清点恰好为{exact}箱。"
                schema = {"pallet_min": "integer", "pallet_max": "integer",
                          "today_count": "integer"}
                vals = {"pallet_min": lo, "pallet_max": hi,
                        "today_count": exact}
        if language == "en":
            instr = ("Extract the numeric fields exactly as stated - no "
                     "rounding, keep the sign, numbers not strings.")
        else:
            instr = "精确提取数值字段：不舍入、保留符号、用数字而非字符串。"
        return {"public": {"text": text, "schema": schema,
                           "instruction": instr},
                "difficulty": difficulty,
                "expected": {"values": vals},
                "alternatives": ["1200.50 == 1200.5 trailing-zero forms"]}
    return Family(family_id=fam_id, primitive="C14", world=world,
                  split=split,
                  protocols=["chat", "chat_json_schema"],
                  build=build,
                  witnesses={"positive": ['{"credit_usd": 1383, "fee_eur": '
                                          '52.75, "adjustment_gbp": -78}'],
                             "negative": ['{"credit_usd": "1383"}',
                                          "rounded fee 52.8"]})


C14_FAMILIES = [
    _c14_numbers("finance", "finance_backoffice", "development", "finance"),
    _c14_numbers("metrics", "helpdesk", "development", "metrics"),
    _c14_numbers("inventory", "retail_ops", "confirmation", "inventory"),
]

# ---------------------------------------------------------------- C15 ----
def _c15_units(fam_id, world, split, kind):
    def build(rng, language, seq):
        difficulty = 1 + (seq % 3)
        if kind == "currency":
            amount = 100 + seq * 350
            rate = [150.0, 0.92, 6.8][seq % 3]
            src, dst = [("JPY", "USD"), ("EUR", "USD"),
                        ("CNY", "USD")][seq % 3]
            if language == "en":
                text = (f"Convert {amount:,} {src} to {dst} using the "
                        f"supplied rate 1 {dst} = {rate} {src}.")
                instr = "Emit value and unit fields."
            else:
                text = f"按所给汇率1{dst}={rate}{src}，将{amount:,}{src}兑换为{dst}。"
                instr = "输出数值和单位字段。"
            value = round(amount / rate, 2)
            expected = {"value": value, "unit": dst}
            surface = {"amount": amount, "rate": rate}
        elif kind == "units":
            amount = 2 + seq * 0.5
            if seq % 2 == 0:
                src, dst, factor = "kg", "g", 1000
            else:
                src, dst, factor = "km", "m", 1000
            value = round(amount * factor, 2)
            if language == "en":
                text = (f"Express {amount} {src} in {dst} "
                        f"(1 {src} = {factor} {dst}).")
                instr = "Emit value and unit fields."
            else:
                text = f"将{amount}{src}换算为{dst}（1{src}={factor}{dst}）。"
                instr = "输出数值和单位字段。"
            expected = {"value": value, "unit": dst}
            surface = {"amount": amount, "factor": factor}
        else:  # affine (confirmation)
            c = 18 + seq
            f = round(c * 9 / 5 + 32, 1)
            if language == "en":
                text = (f"Convert {c} degrees Celsius to Fahrenheit "
                        f"(F = C * 9/5 + 32).")
                instr = "Emit value and unit fields."
            else:
                text = f"将{c}摄氏度换算为华氏度（F = C * 9/5 + 32）。"
                instr = "输出数值和单位字段。"
            expected = {"value": f, "unit": "F"}
            surface = {"celsius": c}
        return {"public": {"text": text, "instruction": instr},
                "difficulty": difficulty,
                "expected": {"conversion": expected, "surface": surface,
                             "kind": kind},
                "alternatives": ["declared rounding tolerance: exact for "
                                 "integers, 2dp for division"]}
    return Family(family_id=fam_id, primitive="C15", world=world,
                  split=split,
                  protocols=["chat", "chat_json_schema",
                             "chat_bounded_reasoning_t2"],
                  build=build,
                  witnesses={"positive": ['{"value": 8.0, "unit": "USD"}',
                                          '{"value": 64.4, "unit": "F"}'],
                             "negative": ["factor inverted (rate "
                                          "multiplied instead of divided)",
                                          "unit code mutated to source"]})


C15_FAMILIES = [
    _c15_units("currency", "retail_ops", "development", "currency"),
    _c15_units("units", "logistics", "development", "units"),
    _c15_units("affine", "clinic", "confirmation", "affine"),
]

# ---------------------------------------------------------------- C16 ----
def _c16_toolresult(fam_id, world, split, kind):
    def build(rng, language, seq):
        difficulty = 1 + (seq % 3)
        if kind == "orderstatus":
            doc = {"order_ref": "ORD-7741", "status": "SHIPPED",
                   "shipments": [{"carrier": "rail", "eta": "2026-12-09"},
                                 {"carrier": "air freight",
                                  "eta": "2026-12-05"}],
                   "stale_note": {"status": "PENDING"}}
            if seq % 2 == 0:
                q = {"en": "Has the order shipped?",
                     "zh": "订单已发货了吗？"}
                ans = "yes"
            else:
                q = {"en": "What is the earliest ETA across shipments?",
                     "zh": "所有运单中最早的到达时间是？"}
                ans = "2026-12-05"
        elif kind == "ledger":
            entries = [{"id": f"TX-{i}", "amount": 100 * (i + 1),
                        "flag": "CLEARED" if i != seq % 4 else "PENDING"}
                       for i in range(4)]
            doc = {"ledger": "AP", "entries": entries}
            if seq % 2 == 0:
                q = {"en": "Which transaction id is PENDING?",
                     "zh": "哪一笔交易是PENDING？"}
                ans = f"TX-{seq % 4}"
            else:
                q = {"en": "What is the total of CLEARED entries?",
                     "zh": "已清算条目的总额是多少？"}
                ans = str(sum(e["amount"] for i, e in enumerate(entries)
                              if i != seq % 4))
        else:  # shipment (confirmation)
            doc = {"parcel": "PKG-88401", "events": [
                {"ts": "12-01", "code": "ARRIVED", "hub": "LIS-1"},
                {"ts": "12-02", "code": "DEPARTED", "hub": "LIS-1"},
                {"ts": "12-03", "code": "ARRIVED", "hub": "OSA-4"}]}
            if seq % 2 == 0:
                q = {"en": "Which hub did the parcel LAST arrive at?",
                     "zh": "包裹最后到达哪个仓？"}
                ans = "OSA-4"
            else:
                q = {"en": "How many DEPARTED events are listed?",
                     "zh": "列出了几个DEPARTED事件？"}
                ans = "1"
        if language == "en":
            instr = ("Answer strictly from this tool output. The field "
                     "'stale_note', when present, is outdated context and "
                     "must not override the live fields.")
        else:
            instr = ("仅根据该工具输出回答。如存在'stale_note'字段，它是过期"
                     "上下文，不得覆盖实时字段。")
        return {"public": {"tool_output": doc, "question": q[language],
                           "instruction": instr},
                "difficulty": difficulty,
                "expected": {"answer": ans, "kind": kind,
                             "construction": {"variant": seq % 2}},
                "alternatives": []}
    return Family(family_id=fam_id, primitive="C16", world=world,
                  split=split,
                  protocols=["chat", "chat_bounded_reasoning_t2"],
                  build=build,
                  witnesses={"positive": ["yes", "2026-12-05"],
                             "negative": ["no   # read the stale PENDING "
                                          "note",
                                          "answers not derivable from the "
                                          "document"]})


C16_FAMILIES = [
    _c16_toolresult("orderstatus", "retail_ops", "development",
                    "orderstatus"),
    _c16_toolresult("ledger", "finance_backoffice", "development", "ledger"),
    _c16_toolresult("shipment", "logistics", "confirmation", "shipment"),
]
