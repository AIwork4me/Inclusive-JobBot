"""Batch A task families, C05-C08 (IJ-NANO-1.3S N03-B2).

Independence classes:
- C05/C06: ground truth recomputable from the PUBLIC payload alone
  (deterministic predicate / argmax engines).
- C07: playbook applicability rules; expected records the construction
  attributes, verified against an independently coded rule table.
- C08: typed capability-tag algebra; the model sees natural-language tool
  names/descriptions, truth is tag-set math recorded in expected.construction
  and re-checked by the verifier (unique superset tool).
"""
from __future__ import annotations

from .core import Family, WORLDS

# ---------------------------------------------------------------- C05 ----
def _c05_policy(fam_id, world, split):
    def build(rng, language, seq):
        difficulty = 1 + (seq % 3)
        days_ago = [3, 12, 29, 30, 31, 45][seq % 6]
        plan = ["standard", "premium"][seq % 2]
        limit = 30 if plan == "standard" else 45
        if language == "en":
            policy = (f"Return policy: items can be refunded if the purchase "
                      f"was made within {limit} days (the day of purchase "
                      f"counts as day 0; 'within' means at most {limit}).")
            facts = f"Purchase was {days_ago} days ago on the {plan} plan."
            q = "Is this purchase refund-eligible? Answer TRUE or FALSE."
        else:
            policy = (f"退货政策：购买不超过{limit}天可退款（购买当天记为第0天，"
                      f"“不超过”指最多{limit}天）。")
            facts = f"该购买距今{days_ago}天，套餐为"
            facts += "标准套餐。" if plan == "standard" else "高级套餐。"
            q = "这次购买是否符合退款条件？回答TRUE或FALSE。"
        answer = days_ago <= limit
        return {"public": {"policy": policy, "facts": facts, "question": q},
                "difficulty": difficulty,
                "expected": {"decision": answer,
                             "construction": {"days_ago": days_ago,
                                              "limit": limit}},
                "alternatives": []}
    return Family(family_id=fam_id, primitive="C05", world=world,
                  split=split,
                  protocols=["chat", "chat_json_schema", "thinking_disabled_chat"],
                  build=build,
                  witnesses={"positive": ["TRUE", '{"decision": true}'],
                             "negative": ["FALSE   # at-threshold case inverted",
                                          "probably true, but check"]})


def _c05_inventory(fam_id, world, split):
    def build(rng, language, seq):
        difficulty = 1 + (seq % 3)
        stock = [4, 9, 12][seq % 3]
        requested = [3, 9, 13][seq % 3]
        backorder = seq % 2 == 0
        if language == "en":
            rules = ("Fulfillment rule: an order can be fulfilled now when "
                     "requested quantity is at most current stock. If "
                     "backorder is allowed for the item, an order exceeding "
                     "stock can STILL be fulfilled (flagged as backorder). "
                     "Otherwise it cannot.")
            facts = (f"Item camp stool: stock {stock} units, requested "
                     f"{requested} units, backorder allowed: "
                     f"{'yes' if backorder else 'no'}.")
            q = "Can this order be fulfilled? Answer TRUE or FALSE."
        else:
            rules = ("履约规则：请求数量不超过现有库存时可立即履约；若该商品允许"
                     "缺货预订，则超过库存也可履约（标记为预订）；否则不能。")
            facts = (f"商品露营凳：库存{stock}件，请求{requested}件，"
                     f"是否允许缺货预订：{'是' if backorder else '否'}。")
            q = "这个订单能否履约？回答TRUE或FALSE。"
        answer = requested <= stock or backorder
        return {"public": {"policy": rules, "facts": facts, "question": q},
                "difficulty": difficulty,
                "expected": {"decision": answer,
                             "construction": {"stock": stock,
                                              "requested": requested,
                                              "backorder": backorder}},
                "alternatives": []}
    return Family(family_id=fam_id, primitive="C05", world=world,
                  split=split,
                  protocols=["chat", "chat_json_schema", "thinking_disabled_chat"],
                  build=build,
                  witnesses={"positive": ["TRUE"], "negative": ["FALSE", "yes"]})


def _c05_travel(fam_id, world, split):
    def build(rng, language, seq):
        difficulty = 1 + (seq % 3)
        days_lead = [7, 14, 20, 21][seq % 4]
        docs_ok = seq % 2 == 0
        if language == "en":
            rules = ("Booking rule: a visa appointment can be booked when "
                     "passport and invitation letter are BOTH present AND "
                     "the departure is more than 14 days away (day 14 "
                     "itself does not qualify).")
            facts = (f"Documents present: "
                     f"{'passport + invitation' if docs_ok else 'passport only'}. "
                     f"Departure in {days_lead} days.")
            q = "Can the appointment be booked? Answer TRUE or FALSE."
        else:
            rules = ("预约规则：护照与邀请函同时具备、且距出发超过14天（第14天"
                     "本身不算）时，才能预约签证。")
            facts = (f"现有材料：{'护照+邀请函' if docs_ok else '仅护照'}。"
                     f"距出发{days_lead}天。")
            q = "能否预约？回答TRUE或FALSE。"
        answer = docs_ok and days_lead > 14
        return {"public": {"policy": rules, "facts": facts, "question": q},
                "difficulty": difficulty,
                "expected": {"decision": answer,
                             "construction": {"days_lead": days_lead,
                                              "docs_ok": docs_ok}},
                "alternatives": []}
    return Family(family_id=fam_id, primitive="C05", world=world,
                  split=split,
                  protocols=["chat", "chat_json_schema", "thinking_disabled_chat"],
                  build=build,
                  witnesses={"positive": ["TRUE"], "negative": ["FALSE"]})


C05_FAMILIES = [
    _c05_policy("returns", "retail_ops", "development"),
    _c05_inventory("fulfill", "retail_ops", "development"),
    _c05_travel("visa", "logistics", "confirmation"),
]

# ---------------------------------------------------------------- C06 ----
def _c06_choice(fam_id, world, split, kind):
    def build(rng, language, seq):
        difficulty = 1 + (seq % 3)
        tie = seq % 5 == 4
        if kind == "plan":
            opts = [{"id": "PLN-BASIC", "price": 0, "seats": 1,
                     "recording": False},
                    {"id": "PLN-TEAM", "price": 49, "seats": 5,
                     "recording": True},
                    {"id": "PLN-PLUS", "price": 89, "seats": 10,
                     "recording": True},
                    {"id": "PLN-ENTERPRISE", "price": 249, "seats": 50,
                     "recording": True}]
            need = {"seats": [3, 6, 9, 12, 40][seq % 5], "recording": True}
            if language == "en":
                instr = (f"Choose the cheapest plan offering at least "
                         f"{need['seats']} seats WITH recording included. "
                         f"Emit exactly one plan id.")
            else:
                instr = (f"选择提供至少{need['seats']}个席位且含录制的最便宜方案。"
                         f"只输出一个方案编号。")
            pool = [o for o in opts if o["seats"] >= need["seats"]
                    and o["recording"]]
        elif kind == "supplier":
            opts = [{"id": "SUP-ALPHA", "price": 120, "iso": True,
                     "audit": True},
                    {"id": "SUP-BETA", "price": 95, "iso": True,
                     "audit": False},
                    {"id": "SUP-GAMMA", "price": 140, "iso": True,
                     "audit": True},
                    {"id": "SUP-DELTA", "price": 160, "iso": False,
                     "audit": True}]
            need = {"iso": True, "audit": True}
            if language == "en":
                instr = ("Choose the cheapest supplier that has BOTH ISO "
                         "certification AND a passed audit. Emit exactly one "
                         "supplier id.")
            else:
                instr = "选择同时具备ISO认证且通过审计的最便宜供应商。只输出一个编号。"
            pool = [o for o in opts if o["iso"] and o["audit"]]
        else:  # shipping
            opts = [{"id": "SHP-ECO", "price": 5, "days": 7},
                    {"id": "SHP-STD", "price": 9, "days": 4},
                    {"id": "SHP-EXP", "price": 18, "days": 2},
                    {"id": "SHP-SAME", "price": 30, "days": 1}]
            max_days = [6, 5, 3, 2, 1][seq % 5]
            if language == "en":
                instr = (f"Choose the cheapest shipping option that arrives "
                         f"within {max_days} days. Emit exactly one option "
                         f"id.")
            else:
                instr = f"选择{max_days}天内到达的最便宜运输方式。只输出一个编号。"
            pool = [o for o in opts if o["days"] <= max_days]
        if tie:                       # declare an accepted tie set
            best = min(o["price"] for o in pool)
            winners = [o["id"] for o in pool if o["price"] == best]
        else:
            best = min(o["price"] for o in pool)
            winners = [next(o["id"] for o in pool if o["price"] == best)]
        pub_opts = [{k: v for k, v in o.items() if k != "id" or True}
                    for o in opts]
        return {"public": {"options": opts, "instruction": instr,
                           "option_note": {"en": "ids are stable option "
                                                 "identifiers",
                                           "zh": "编号为固定选项标识"}[language]},
                "difficulty": difficulty,
                "expected": {"choice": winners[0],
                             "construction": {"need": need if kind != "shipping"
                                              else {"max_days": max_days},
                                              "kind": kind}},
                "alternatives": (winners[1:] if len(winners) > 1 else [])}
    return Family(family_id=fam_id, primitive="C06", world=world,
                  split=split,
                  protocols=["chat", "chat_json_schema", "thinking_disabled_chat"],
                  build=build,
                  witnesses={"positive": ["PLN-TEAM", "SUP-ALPHA"],
                             "negative": ["PLN-BASIC   # seats insufficient",
                                          "SHP-SAME   # fastest but not "
                                          "cheapest qualifying"]})


C06_FAMILIES = [
    _c06_choice("plan", "clinic", "development", "plan"),
    _c06_choice("supplier", "finance_backoffice", "development", "supplier"),
    _c06_choice("shipping", "logistics", "confirmation", "shipping"),
]

# ---------------------------------------------------------------- C07 ----
_C07_RULES = {
    "service": {
        "verify_identity": {"lost_access": 1, "no_payment_issue": 1},
        "reset_password": {"forgot_credentials": 1},
        "issue_refund": {"payment_dispute": 1, "within_window": 1},
        "escalate_fraud": {"suspects_fraud": 1},
        "update_record": {"data_entry_error": 1},
        "schedule_callback": {"requests_later_call": 1}},
    "itops": {
        "restart_service": {"service_unresponsive": 1, "deploy_unchanged": 1},
        "rollback_deploy": {"recent_deploy_broke": 1},
        "scale_replicas": {"sustained_overload": 1, "deploy_unchanged": 1},
        "page_oncall": {"sev1_outage": 1},
        "clear_cache": {"stale_content_served": 1, "service_healthy": 1}},
    "warehouse": {
        "recount_shelf": {"count_mismatch": 1, "system_intact": 1},
        "quarantine_batch": {"defect_found": 1},
        "reprint_label": {"label_unreadable": 1, "contents_verified": 1},
        "notify_supervisor": {"repeated_mismatch": 1},
        "hand_to_qa": {"sampling_failed": 1, "batch_small": 1}}}

_C07_TEXT = {
    "service": {
        "verify_identity": {"en": "A customer cannot access their account "
                                  "but billing is fine; they suspect nothing "
                                  "criminal.",
                            "zh": "客户无法登录账户，但账单正常，也没有怀疑任何"
                                  "异常行为。"},
        "reset_password": {"en": "The customer forgot their password and "
                                 "wants to set a new one.",
                           "zh": "客户忘记了密码，想重新设置一个。"},
        "issue_refund": {"en": "A charge from last week is disputed and the "
                               "return window is still open.",
                         "zh": "客户对上周的一笔扣款有争议，且仍在退货期"
                         "内。"},
        "escalate_fraud": {"en": "The customer sees transactions they never "
                                 "made and suspects the card is stolen.",
                           "zh": "客户发现多笔不是自己操作的交易，怀疑卡被"
                           "盗。"},
        "update_record": {"en": "The agent typo'd the city on file; the "
                                "customer points out the data-entry error.",
                          "zh": "客服把城市录入错了，客户指出这个录入错误。"},
        "schedule_callback": {"en": "The customer is in a meeting and asks "
                                    "for a call back in an hour.",
                              "zh": "客户正在开会，要求一小时后回电。"}},
    "itops": {
        "restart_service": {"en": "The payments API is hanging; no deploy "
                                  "happened today.",
                            "zh": "支付接口无响应；今天没有发布过任何版本。"},
        "rollback_deploy": {"en": "Error rates jumped right after this "
                                  "morning's release.",
                            "zh": "今天早上发布后错误率立刻飙升。"},
        "scale_replicas": {"en": "CPU has been pinned at 95% for an hour; "
                                 "no recent deploy.",
                           "zh": "CPU持续一小时保持95%，近期没有发布。"},
        "page_oncall": {"en": "The production site is fully down for all "
                              "users, SEV1 declared.",
                        "zh": "生产站点对所有用户完全不可用，已定为SEV1。"},
        "clear_cache": {"en": "Users see yesterday's homepage though the "
                              "service itself is healthy.",
                        "zh": "服务本身健康，但用户看到的是昨天的首页。"}},
    "warehouse": {
        "recount_shelf": {"en": "The shelf count differs from the system by "
                                "two units; the system is otherwise intact.",
                          "zh": "货架清点与系统差了两个，系统其他方面正常。"},
        "quarantine_batch": {"en": "A broken unit is found inside a sealed "
                                   "batch.",
                            "zh": "在整批封装货物中发现一个破损品。"},
        "reprint_label": {"en": "The label is smeared and unreadable; the "
                                "contents were verified correct.",
                          "zh": "标签污损无法辨认；内容已核对无误。"},
        "notify_supervisor": {"en": "The same shelf has shown count "
                                    "mismatches three days in a row.",
                              "zh": "同一货架连续三天出现清点差异。"},
        "hand_to_qa": {"en": "Sampling failed on a small batch that is easy "
                             "to re-check.",
                       "zh": "一个小批次的抽检不合格，便于复核。"}}}


def _c07_family(fam_id, world, split, book):
    rules = _C07_RULES[book]

    def build(rng, language, seq):
        difficulty = 1 + (seq % 3)
        action = sorted(rules)[seq % len(rules)]
        situation = _C07_TEXT[book][action][language]
        catalog = {a: _c07_desc(book, a) for a in sorted(rules)}
        if language == "en":
            instr = ("According to the playbook, which action fits this "
                     "situation? Emit exactly one action name from the "
                     "catalog.")
        else:
            instr = "根据操作手册，这个情况应执行哪个动作？只输出目录中的一个动作名。"
        return {"public": {"situation": situation,
                           "action_catalog": catalog, "instruction": instr},
                "difficulty": difficulty,
                "expected": {"action": action,
                             "construction": dict(rules[action])},
                "alternatives": []}
    return Family(family_id=fam_id, primitive="C07", world=world,
                  split=split,
                  protocols=["chat", "chat_json_schema", "native_function_calling"],
                  build=build,
                  witnesses={"positive": ["verify_identity",
                                          '{"action": "rollback_deploy"}'],
                             "negative": ["reset_password   # access issue but "
                                          "not forgotten credentials",
                                          "some_new_action"]})


def _c07_desc(book, action):
    d = {
     "verify_identity": "customer lost access without any payment or fraud "
                        "signal - confirm who they are first",
     "reset_password": "customer explicitly forgot their credentials",
     "issue_refund": "disputed charge inside the return window",
     "escalate_fraud": "signs of theft or unauthorized transactions",
     "update_record": "agent-made data-entry mistake needs correcting",
     "schedule_callback": "customer asks to be called later",
     "restart_service": "service unhealthy with no deploy change",
     "rollback_deploy": "a recent release caused the breakage",
     "scale_replicas": "healthy service under sustained load",
     "page_oncall": "declared severity-1 full outage",
     "clear_cache": "healthy service serving stale content",
     "recount_shelf": "single count mismatch with intact systems",
     "quarantine_batch": "physical defect found in a batch",
     "reprint_label": "unreadable label with verified contents",
     "notify_supervisor": "repeated mismatches across days",
     "hand_to_qa": "failed sampling on a small re-checkable batch"}
    return d[action]


C07_FAMILIES = [
    _c07_family("service", "helpdesk", "development", "service"),
    _c07_family("itops", "finance_backoffice", "development", "itops"),
    _c07_family("warehouse", "logistics", "confirmation", "warehouse"),
]

# ---------------------------------------------------------------- C08 ----
_TAG_PHRASES = {
    "email": {"en": "email", "zh": "邮件"},
    "send": {"en": "send out", "zh": "发送"},
    "draft": {"en": "draft", "zh": "起草"},
    "schedule": {"en": "schedule", "zh": "排期"},
    "invoice": {"en": "invoice", "zh": "发票"},
    "generate": {"en": "generate", "zh": "生成"},
    "lookup": {"en": "look up", "zh": "查询"},
    "calendar": {"en": "calendar", "zh": "日历"},
    "ticket": {"en": "support ticket", "zh": "工单"},
    "close": {"en": "close", "zh": "关闭"},
    "dataset": {"en": "dataset", "zh": "数据集"},
    "validate": {"en": "validate", "zh": "校验"},
    "export": {"en": "export", "zh": "导出"},
    "report": {"en": "report", "zh": "报表"},
    "message": {"en": "team message", "zh": "团队消息"},
    "post": {"en": "post", "zh": "发布"},
}
_C08_TOOLS = [
    # id, tags (superset-capability), en/zh name, en/zh description
    ("email_sender", {"email", "send"}, "email sender", "邮件发送器",
     "sends an email out to a recipient", "把邮件发送给收件人"),
    ("email_drafter", {"email", "draft"}, "email drafter", "邮件起草器",
     "drafts an email without sending it", "起草邮件但并不发送"),
    ("invoice_generator", {"invoice", "generate"}, "invoice generator",
     "发票生成器", "generates an invoice document", "生成发票文档"),
    ("invoice_mailer", {"invoice", "generate", "email", "send"},
     "invoice mailer", "发票邮寄器",
     "generates and sends an invoice by email", "生成并通过邮件发送发票"),
    ("crm_lookup", {"lookup", "ticket"}, "CRM lookup", "CRM查询",
     "looks up customer records from a support ticket id",
     "按工单编号查询客户记录"),
    ("ticket_closer", {"ticket", "close"}, "ticket closer", "工单关闭器",
     "closes a resolved support ticket", "关闭已解决的工单"),
    ("calendar_booker", {"calendar", "schedule"}, "calendar booker",
     "日历预订器", "books a slot on a calendar", "在日历上预订时间段"),
    ("report_scheduler", {"report", "schedule"}, "report scheduler",
     "报表排期器", "schedules recurring reports", "为报表安排周期生成"),
    ("dataset_exporter", {"dataset", "export"}, "dataset exporter",
     "数据集导出器", "exports a dataset to a file", "把数据集导出为文件"),
    ("dataset_validator", {"dataset", "validate"}, "dataset validator",
     "数据集校验器", "validates dataset contents", "校验数据集内容"),
    ("message_poster", {"message", "post"}, "message poster", "消息发布器",
     "posts a message to the team channel", "在团队频道发布消息"),
    ("meeting_notifier", {"calendar", "message", "post"}, "meeting notifier",
     "会议通知器", "posts calendar meeting reminders to the channel",
     "把日历会议提醒发布到频道"),
]


def _c08_family(fam_id, world, split):
    def build(rng, language, seq):
        difficulty = 1 + (seq % 3)
        size = [4, 8, 16, 32, 64][seq % 5]
        serving = _C08_TOOLS[seq % len(_C08_TOOLS)][0]
        s_tags = {t[0]: t[1] for t in _C08_TOOLS}[serving]
        req_set = set(s_tags)
        required = sorted(s_tags)
        # distractors must NOT satisfy all required capabilities: keep only
        # base tools whose tag sets are not supersets of `required`, then
        # mint single-capability distractors (proper subsets)
        pool = [t for t in _C08_TOOLS
                if t[0] != serving and not req_set.issubset(t[1])]
        rng.shuffle(pool)
        chosen = pool[:max(size - 1, 0)]
        while len(chosen) + 1 < size:            # mint narrow distractors
            i = len(chosen)
            miss = required[i % len(required)]
            tid = f"aux_{miss}_{i:02d}"
            chosen.append((tid, {miss}, f"aux tool {i}", f"辅助工具{i}",
                           f"handles {_TAG_PHRASES[miss]['en']} only",
                           f"只处理{_TAG_PHRASES[miss]['zh']}"))
        serving_tuple = next(t for t in _C08_TOOLS if t[0] == serving)
        tools = [serving_tuple] + chosen
        rng.shuffle(tools)
        obj_phrases = [_TAG_PHRASES[t][language] for t in required]
        if language == "en":
            obj = "I need to " + " and ".join(obj_phrases) + \
                  (" for our customers." if len(required) > 1 else ".")
            instr = ("Select the one tool from the list that can do ALL of "
                     "this. Emit exactly one tool id.")
        else:
            obj = "我需要" + "并".join(obj_phrases) + "。"
            instr = "从列表中选择能完整完成该任务的唯一工具。只输出一个工具编号。"
        pub_tools = [{"id": t[0], "name": t[3 if language == "zh" else 2],
                      "description": t[5 if language == "zh" else 4]}
                     for t in tools]
        return {"public": {"objective": obj, "tools": pub_tools,
                           "instruction": instr},
                "difficulty": difficulty,
                "expected": {
                    "tool_id": serving,
                    "construction": {
                        "required_tags": required,
                        "registry_tags": {t[0]: sorted(t[1])
                                          for t in tools}}},
                "alternatives": []}
    return Family(family_id=fam_id, primitive="C08", world=world,
                  split=split,
                  protocols=["chat", "chat_json_schema", "native_function_calling"],
                  build=build,
                  witnesses={"positive": ["invoice_mailer",
                                          '{"tool_id": "email_sender"}'],
                             "negative": ["email_drafter   # draft is not "
                                          "send",
                                          "aux_send_01   # minted partial "
                                          "tool"]})


C08_FAMILIES = [
    _c08_family("biztools", "helpdesk", "development"),
    _c08_family("dataplatform", "finance_backoffice", "development"),
    _c08_family("comms", "smart_home", "confirmation"),
]
