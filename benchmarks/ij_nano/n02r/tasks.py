"""N02R development task suite: 60 independent tasks, 6 families x 10,
across three business worlds (orderops / inventory / shipping), CN and EN.

Protocol-comparison screen (not the N03 capability atlas): tasks are the
matched semantic payload across arms P0-P7. Deterministic construction
from explicit parameter tables; suite hash is frozen into the experiment
identity (a changed suite creates a NEW experiment identity, order 1.2
section 9).

Family semantics (capability isolation, order 1.2 section 3.5):
- tool_selection: arguments are SUPPLIED in the prompt; only the tool
  identity is the answer (isolation: selection without extraction).
- slot_extraction: the tool is SUPPLIED; the answer is argument values.
- structured_action: full action = tool + typed arguments (entity ids,
  enum reason, quantity with mandatory unit).
- enumerated_action: choose one labeled action from a numbered list.
- conditional_branch: closed-vocabulary policy decision.
- stop_continue: goal-state termination decision.
"""
from __future__ import annotations

import hashlib
import json

FAMILIES = (
    "tool_selection", "slot_extraction", "structured_action",
    "enumerated_action", "conditional_branch", "stop_continue",
)

TOOLS = {
    "orderops": [
        ("orders.lookup_order", "查询订单详情 / look up an order", ("order_id",)),
        ("orders.cancel_order", "取消订单 / cancel an order", ("order_id",)),
        ("orders.get_refund_eligibility", "查询退款资格 / check refund eligibility", ("order_id",)),
        ("refunds.submit", "提交退款 / submit a refund", ("order_id", "amount", "reason")),
        ("customers.get_profile", "查询客户档案 / get customer profile", ("customer_id",)),
        ("logistics.trace_shipment", "追踪物流 / trace a shipment", ("tracking_no",)),
        ("inventory.check_stock", "查询库存 / check stock", ("sku",)),
        ("notify.send_update", "发送通知 / send a notification", ("customer_id",)),
    ],
    "inventory": [
        ("inventory.check_stock", "查询库存 / check stock", ("sku",)),
        ("inventory.adjust_stock", "调整库存 / adjust stock", ("sku", "quantity",)),
        ("inventory.reserve_stock", "预留库存 / reserve stock", ("sku", "quantity")),
        ("warehouse.locate_bin", "定位货位 / locate a bin", ("bin_id",)),
        ("receiving.log_arrival", "登记到货 / log an arrival", ("shipment_no",)),
        ("picking.create_task", "创建拣货任务 / create a picking task", ("order_id",)),
        ("reports.export_snapshot", "导出快照 / export a snapshot", ("zone",)),
        ("alerts.raise_low_stock", "上报低库存 / raise a low-stock alert", ("sku",)),
    ],
    "shipping": [
        ("logistics.trace_shipment", "追踪物流 / trace a shipment", ("tracking_no",)),
        ("logistics.reroute_shipment", "改派物流 / reroute a shipment", ("tracking_no",)),
        ("logistics.estimate_delivery", "预估送达 / estimate delivery", ("tracking_no",)),
        ("addresses.validate", "校验地址 / validate an address", ("address_id",)),
        ("customs.declare_value", "申报价值 / declare customs value", ("tracking_no", "amount")),
        ("labels.generate", "生成面单 / generate a label", ("order_id",)),
        ("couriers.list_rates", "查询运费 / list courier rates", ("zone",)),
        ("escalations.open_case", "开升级单 / open an escalation case", ("tracking_no",)),
    ],
}

# -- deterministic parameter tables ------------------------------------------

ORDER_IDS = ("ORD-1042", "ORD-2025", "ORD-3319", "ORD-7781", "ORD-9014")
SKUS = ("SKU-1001", "SKU-7743", "SKU-2210", "SKU-8806", "SKU-5519")
CUSTOMERS = ("C-9", "C-41", "C-77", "C-128", "C-303")
TRACKINGS = ("TRK-88771", "TRK-40219", "TRK-65140", "TRK-11298", "TRK-73002")
BINS = ("BIN-A12", "BIN-C3", "BIN-F9", "BIN-B21", "BIN-E7")
ZONES = ("north", "south", "east", "west", "central")

TS_CASES = [  # tool_selection: (world, correct_tool, question, given-args)
    ("orderops", "orders.get_refund_eligibility", "客户询问订单 {order} 能否退款。",
     {"order_id": "{order}"}),
    ("orderops", "logistics.trace_shipment", "Where is parcel {trk} right now?",
     {"tracking_no": "{trk}"}),
    ("orderops", "customers.get_profile", "调出客户 {cust} 的档案。",
     {"customer_id": "{cust}"}),
    ("inventory", "warehouse.locate_bin", "货位 {bin} 在哪里？",
     {"bin_id": "{bin}"}),
    ("inventory", "receiving.log_arrival", "到货了， shipment {trk}，登记入库。",
     {"shipment_no": "{trk}"}),
    ("inventory", "reports.export_snapshot", "Export the stock snapshot for zone {zone}.",
     {"zone": "{zone}"}),
    ("shipping", "customs.declare_value", "为 {trk} 申报关税价值。",
     {"tracking_no": "{trk}"}),
    ("shipping", "addresses.validate", "Check whether address {addr} is deliverable.",
     {"address_id": "{addr}"}),
    ("shipping", "escalations.open_case", "包裹 {trk} 连续破损两次，开升级单。",
     {"tracking_no": "{trk}"}),
    ("orderops", "notify.send_update", "给客户 {cust} 发送状态更新通知。",
     {"customer_id": "{cust}"}),
]

SLOT_CASES = [  # slot_extraction: (world, tool, slot_name, slot_type, hint)
    ("orderops", "orders.lookup_order", "order_id", "entity", "查询订单，单号在上下文里。"),
    ("inventory", "inventory.check_stock", "sku", "entity", "查库存，商品编号在上下文里。"),
    ("shipping", "logistics.trace_shipment", "tracking_no", "entity", "Track the parcel; the number is in the context."),
    ("orderops", "customers.get_profile", "customer_id", "entity", "Pull the profile for the customer mentioned."),
    ("inventory", "warehouse.locate_bin", "bin_id", "entity", "Find the bin mentioned in the note."),
    ("orderops", "inventory.check_stock", "sku", "entity", "How many units of the mentioned item remain?"),
    ("shipping", "couriers.list_rates", "zone", "enum", "List rates for the zone mentioned in the ticket."),
    ("inventory", "inventory.adjust_stock", "quantity", "quantity", "Adjust stock by the stated quantity (state the unit)."),
    ("orderops", "refunds.submit", "amount", "quantity", "Refund the stated amount (state the currency unit)."),
    ("shipping", "customs.declare_value", "amount", "quantity", "Declare the stated value (state the currency unit)."),
]

STRUCT_CASES = [  # structured_action: (world, tool, entity_slot, entity_val, qty, unit, reason)
    ("orderops", "refunds.submit", "order_id", "{order}", 120.0, "CNY", "damaged_item"),
    ("orderops", "refunds.submit", "order_id", "{order}", 89.5, "CNY", "late_delivery"),
    ("inventory", "inventory.adjust_stock", "sku", "{sku}", 25, "pcs", None),
    ("inventory", "inventory.reserve_stock", "sku", "{sku}", 40, "pcs", None),
    ("shipping", "customs.declare_value", "tracking_no", "{trk}", 350.0, "USD", None),
    ("orderops", "refunds.submit", "order_id", "{order}", 2400.0, "CNY", "wrong_item"),
    ("inventory", "inventory.adjust_stock", "sku", "{sku}", 3, "pcs", None),
    ("shipping", "customs.declare_value", "tracking_no", "{trk}", 99.0, "EUR", None),
    ("orderops", "refunds.submit", "order_id", "{order}", 15.0, "CNY", "duplicate_charge"),
    ("inventory", "inventory.reserve_stock", "sku", "{sku}", 12, "pcs", None),
]

ENUM_ACTIONS = {
    "orderops": [
        ("A1", "换货：为客户 {order} 创建换货单 / exchange the item on {order}"),
        ("A2", "退款：为 {order} 提交退款 / submit a refund for {order}"),
        ("A3", "仅道歉并关闭工单 / apologize and close the ticket"),
        ("A4", "升级人工客服 / escalate to a human agent"),
        ("A5", "查询物流轨迹 / trace the shipment"),
        ("A6", "发送延迟通知 / send a delay notification"),
    ],
    "inventory": [
        ("A1", "补货：为 {sku} 下补货单 / create a restock order for {sku}"),
        ("A2", "冻结：暂停 {sku} 的出库 / freeze outbound of {sku}"),
        ("A3", "盘点：安排 {bin} 的盘点 / schedule a count of {bin}"),
        ("A4", "转仓：把 {sku} 调往备用仓 / transfer {sku} to the backup warehouse"),
        ("A5", "忽略该告警 / ignore the alert"),
        ("A6", "上报主管 / notify the supervisor"),
    ],
    "shipping": [
        ("A1", "改址：修改 {trk} 的收件地址 / change the address for {trk}"),
        ("A2", "加急：把 {trk} 升级为加急配送 / upgrade {trk} to express"),
        ("A3", "拦截：尝试拦截 {trk} / attempt to intercept {trk}"),
        ("A4", "重发：为 {order} 重新发货 / reship {order}"),
        ("A5", "仅备注，不操作 / note only, no action"),
        ("A6", "开升级单 / open an escalation case"),
    ],
}

ENUM_CASES = [  # (world, correct_label, scenario)
    ("orderops", "A2", "客户 {cust} 的订单 {order} 收到后有破损，要求退钱。"),
    ("orderops", "A4", "客户 {cust} 威胁投诉监管部门，情绪激动。"),
    ("orderops", "A5", "客户只问包裹到哪了，没有别的要求。"),
    ("orderops", "A6", "订单 {order} 将延迟三天，客户需提前知晓。"),
    ("inventory", "A1", "库存系统显示 {sku} 只剩 2 件，低于安全线。"),
    ("inventory", "A3", "货位 {bin} 的系统数量与摄像头不符。"),
    ("inventory", "A6", "{sku} 连续三次入库质检失败。"),
    ("shipping", "A1", "收件人打电话说搬家了，包裹 {trk} 还在途中。"),
    ("shipping", "A3", "客户拒收，要求把 {trk} 退回发件人。"),
    ("shipping", "A6", "包裹 {trk} 已经延误超过一周且承运商无响应。"),
]

BRANCH_VOCABS = {
    "orderops": ("auto_approve", "requires_manager_approval", "reject_out_of_policy"),
    "inventory": ("accept_adjustment", "require_second_count", "reject_adjustment"),
    "shipping": ("reroute", "hold_at_hub", "continue_as_planned"),
}

BRANCH_CASES = [  # (world, rule params, correct branch); ages/amounts vary
    ("orderops", "refund", "order age {n} days, policy limit 30", 12, "auto_approve"),
    ("orderops", "refund", "order age {n} days, policy limit 30", 47, "requires_manager_approval"),
    ("orderops", "refund", "item category restricted from refunds", 5, "reject_out_of_policy"),
    ("orderops", "refund", "order age {n} days, policy limit 30", 30, "auto_approve"),
    ("orderops", "refund", "order age {n} days, policy limit 30", 31, "requires_manager_approval"),
    ("inventory", "count", "system-physical variance {n} pcs, tolerance 5", 2, "accept_adjustment"),
    ("inventory", "count", "system-physical variance {n} pcs, tolerance 5", 9, "require_second_count"),
    ("inventory", "count", "variance caused by open picking task in that bin", 1, "reject_adjustment"),
    ("shipping", "delay", "delay {n} hours, threshold 24", 6, "continue_as_planned"),
    ("shipping", "delay", "delay {n} hours, threshold 24; customer unreachable", 30, "hold_at_hub"),
]

STOP_CASES = [  # (world, goal state, observation, correct)
    ("orderops", "goal: refund submitted for {order}",
     "refund submitted and confirmation R-5521 issued", "stop"),
    ("orderops", "goal: refund submitted for {order}",
     "eligibility checked, refund NOT yet submitted", "continue"),
    ("orderops", "goal: customer {cust} notified of delay",
     "notification queued but not yet delivered", "continue"),
    ("inventory", "goal: stock corrected for {sku}",
     "adjustment applied; system shows new quantity", "stop"),
    ("inventory", "goal: stock corrected for {sku}",
     "first adjustment failed with a timeout", "continue"),
    ("inventory", "goal: arrival logged for {trk}",
     "receiving record created and acknowledged", "stop"),
    ("shipping", "goal: {trk} delivered",
     "carrier reports out-for-delivery", "continue"),
    ("shipping", "goal: {trk} delivered",
     "carrier reports delivered, photo on file", "stop"),
    ("shipping", "goal: customs value declared for {trk}",
     "declaration accepted with reference CD-887", "stop"),
    ("orderops", "goal: order {order} cancelled",
     "cancellation request submitted, awaiting confirmation", "continue"),
]


def _mk_task(task_id: str, family: str, lang: str, world: str, context: str,
             instruction: str, expected: dict, schema_hint: dict) -> dict:
    return {"task_id": task_id, "family": family, "lang": lang, "world": world,
            "context": context, "instruction": instruction,
            "expected": expected, "schema_hint": schema_hint}


def build_suite() -> list[dict]:
    """Deterministically build the 60-task N02R screen."""
    tasks: list[dict] = []
    for i in range(10):
        order, sku, cust = ORDER_IDS[i % 5], SKUS[(i * 3) % 5], CUSTOMERS[(i * 2) % 5]
        trk, bin_, zone = TRACKINGS[(i * 2) % 5], BINS[(i * 3) % 5], ZONES[(i * 2) % 5]
        subst = {"order": order, "sku": sku, "cust": cust, "trk": trk,
                 "bin": bin_, "zone": zone, "addr": f"ADR-{400 + i * 7}"}
        lang = "cn" if i % 2 == 0 else "en"

        # 1) tool_selection (args supplied)
        w, tool, q, args = TS_CASES[i]
        q, args = q.format(**subst), {k: v.format(**subst) for k, v in args.items()}
        ctx = f"已知 / known: order {order}, customer {cust}, sku {sku}, tracking {trk}." \
            if lang == "cn" else f"Known: order {order}, customer {cust}, sku {sku}, tracking {trk}."
        tasks.append(_mk_task(
            f"TS{i+1:02d}", "tool_selection", lang, w, ctx,
            (q + " 只回答要调用的工具名。 / Answer with the tool name only."),
            {"tool": tool, "args": args},
            {"answer_kind": "tool", "candidates": [t for t, _, _ in TOOLS[w]]}))

        # 2) slot_extraction (tool supplied)
        w, tool, slot, stype, hint = SLOT_CASES[i]
        carrier = {"order_id": order, "sku": sku, "tracking_no": trk,
                   "customer_id": cust, "bin_id": bin_, "zone": zone,
                   "quantity": (f"{18 + i} pcs", 18 + i, "pcs"),
                   "amount": (f"{45.0 + i * 10} CNY", 45.0 + i * 10, "CNY")}[slot]
        if stype == "entity":
            expected_args = {slot: carrier}
            ctx_line = f"上下文 / context: {slot} = {carrier}"
        elif stype == "enum":
            expected_args = {slot: carrier}
            ctx_line = f"上下文 / context: zone = {carrier}"
        else:
            expected_args = {slot: {"value": carrier[1], "unit": carrier[2]}}
            ctx_line = f"上下文 / context: stated {slot} = {carrier[0]}"
        tasks.append(_mk_task(
            f"SX{i+1:02d}", "slot_extraction", lang, w,
            f"{ctx_line}. 工具已选定: {tool}. / Tool already chosen: {tool}.",
            hint + (" 只回答参数值。 / Answer with the argument value only."),
            {"tool": tool, "args": expected_args},
            {"answer_kind": "slot", "tool": tool, "slot": slot, "slot_type": stype,
             "public_unit": stype == "quantity"}))

        # 3) structured_action
        w, tool, eslot, etmpl, qty, unit, reason = STRUCT_CASES[i]
        eval_ = etmpl.format(**subst)
        if reason:
            ctx = (f"订单 {eval_}：金额 {qty} {unit}，原因 {reason}。" if lang == "cn" else
                   f"Order {eval_}: amount {qty} {unit}, reason {reason}.")
            exp_args = {eslot: eval_, "amount": {"value": qty, "unit": unit}, "reason": reason}
            slots = [eslot, "amount", "reason"]
        else:
            ctx = (f"商品 {eval_}：数量变动 {qty} {unit}。" if lang == "cn" else
                   f"Item {eval_}: quantity change {qty} {unit}.")
            exp_args = {eslot: eval_, "quantity": {"value": qty, "unit": unit}}
            slots = [eslot, "quantity"]
        tasks.append(_mk_task(
            f"SA{i+1:02d}", "structured_action", lang, w, ctx,
            ("生成完整动作：工具与全部参数。 / Produce the full action: tool and all arguments."),
            {"tool": tool, "args": exp_args},
            {"answer_kind": "action", "tool": tool, "slots": slots}))

        # 4) enumerated_action
        w, label, scenario = ENUM_CASES[i]
        acts = [(lid, txt.format(**subst)) for lid, txt in ENUM_ACTIONS[w]]
        listing = "\n".join(f"{lid}. {txt}" for lid, txt in acts)
        tasks.append(_mk_task(
            f"EA{i+1:02d}", "enumerated_action", lang, w,
            f"可选动作 / available actions:\n{listing}",
            scenario + " 只回答动作编号。 / Answer with the action label only.",
            {"action_label": label},
            {"answer_kind": "label", "labels": [lid for lid, _ in acts]}))

        # 5) conditional_branch
        w, kind, rule, n, branch = BRANCH_CASES[i]
        rule_s = rule.format(n=n)
        tasks.append(_mk_task(
            f"CB{i+1:02d}", "conditional_branch", lang, w,
            f"策略 / policy: {rule_s}. 实况 / observation: n = {n}." if kind != "cat"
            else f"策略 / policy: {rule_s}.",
            ("判断应走的分支。 / Decide which branch applies.",
             )[0],
            {"branch": branch},
            {"answer_kind": "branch", "branches": list(BRANCH_VOCABS[w])}))

        # 6) stop_continue
        w, goal, obs, dec = STOP_CASES[i]
        tasks.append(_mk_task(
            f"SC{i+1:02d}", "stop_continue", lang, w,
            f"目标 / goal: {goal.format(**subst)}. 当前观测 / observation: {obs}.",
            "决定 stop 还是 continue。 / Decide stop or continue.",
            {"decision": dec},
            {"answer_kind": "decision", "choices": ["stop", "continue"]}))

    return tasks


def suite_hash() -> str:
    canonical = json.dumps(build_suite(), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    suite = build_suite()
    print(json.dumps({"tasks": len(suite), "suite_hash": suite_hash(),
                      "families": {f: sum(1 for t in suite if t["family"] == f)
                                   for f in FAMILIES},
                      "langs": {l: sum(1 for t in suite if t["lang"] == l)
                                for l in ("cn", "en")}}, indent=1))
