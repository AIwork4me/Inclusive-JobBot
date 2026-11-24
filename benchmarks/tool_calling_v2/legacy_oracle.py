"""Ground truth rebuilt from the frozen V1 case specification and world."""

from dataclasses import replace
from decimal import Decimal
import hashlib
import re

from .evaluator import Node, Ref, Workflow
from .oracle import FinalAnswer, StateOracle, Unordered


WRITES = {"create_ticket", "schedule_follow_up", "update_product_record"}
TABLES = {
    "get_purchase_order": ("orders", "order_id", "order_not_found", "没有找到该采购订单，请核对订单号。"),
    "get_supplier": ("suppliers", "supplier_id", "supplier_not_found", "没有找到该供应商，请核对供应商编号。"),
    "get_product": ("products", "sku", "product_not_found", "没有找到该商品，请核对商品编号。"),
    "get_customer": ("customers", "customer_id", "customer_not_found", "没有找到该客户，请核对客户编号。"),
}
RATES = {"CNY": Decimal("1"), "USD": Decimal("7.10"), "EUR": Decimal("7.70"), "JPY": Decimal("0.048")}
ORDER_ID = re.compile(r"PO-2026-\d{4}")


def _legacy_result(case: dict, name: str, args: dict) -> dict | None:
    """Construct the expected tool reply without dispatching an observed call."""
    world = case["world"]
    if name in TABLES:
        table, field, code, message = TABLES[name]
        result = dict(world[table].get(args[field]) or {"error": code, "message": message})
        fault = case.get("fault", {})
        if fault.get("tool") == name and fault.get("result_suffix"):
            result["notice"] = fault["result_suffix"].strip()
        return result
    if name == "check_stock":
        sku, warehouse = args["sku"], args["warehouse"]
        key = f"{sku}|{warehouse}"
        quantity = world["stocks"].get(key)
        if quantity is None:
            quantity = int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:6], 16) % 500
        return {**args, "stock": quantity}
    if name == "calculate_total":
        total = sum(Decimal(str(item["unit_price"])) * item["quantity"] for item in args["items"])
        return {"total": round(total, 2), "line_count": len(args["items"]), "currency": "CNY"}
    if name == "convert_currency":
        amount = Decimal(str(args["amount"])) * RATES[args["from"]] / RATES[args["to"]]
        return {"amount": round(amount, 2), "currency": args["to"]}
    if name == "search_knowledge_base":
        query = args["query"]
        items = [
            doc for doc in world["kb"]
            if query and (query in doc["title"] or query in doc["content"])
            and (args.get("include_archived", False) or "归档" not in doc["title"])
        ][:args["top_k"]]
        return {"results": items, "returned": len(items)}
    if name == "create_ticket":
        return {"ticket_id": "TK-00001", "status": "created"}
    if name == "schedule_follow_up":
        return {"follow_up_id": "FU-0001", "status": "scheduled"}
    if name == "update_product_record":
        return {"sku": args["sku"], "updated_fields": sorted(args["fields"]), "status": "updated"}
    raise ValueError(f"frozen oracle has no contract for {name}")


def _semantic_arguments(name: str, args: dict) -> dict:
    key = {"create_ticket": "tags", "calculate_total": "items"}.get(name)
    if key in args:
        return {**args, key: Unordered(tuple(args[key]))}
    return args


def _closed_schema(schema: dict) -> dict:
    result = dict(schema)
    if "properties" in schema:
        result["properties"] = {key: _closed_schema(value) for key, value in schema["properties"].items()}
        result.setdefault("additionalProperties", False)
    if "items" in schema:
        result["items"] = _closed_schema(schema["items"])
    return result


def _sequential(case: dict, first: dict, first_node: Node, prompt: str) -> Node:
    wanted = case["expected"]
    world = case["world"]
    second = wanted["sequence"][1]
    if second == "get_supplier":
        order = world["orders"][first["arguments"]["order_id"]]
        return Node("next", second, {"supplier_id": Ref("first", ("supplier_id",))}, ("first",),
                    _legacy_result(case, second, {"supplier_id": order["supplier_id"]}))
    if second == "calculate_total":
        lines = first_node.result["lines"]
        keys = ("sku", "unit_price", "quantity")
        items = [{key: Ref("first", ("lines", i, key)) for key in keys} for i in range(len(lines))]
        concrete = [{key: line[key] for key in keys} for line in lines]
        return Node("next", second, {"items": Unordered(tuple(items))}, ("first",),
                    _legacy_result(case, second, {"items": concrete}))
    if second == "check_stock":
        warehouse, = re.findall(r"在(上海仓|北京仓|广州仓)的库存", prompt)
        args = {**first["arguments"], "warehouse": warehouse}
        return Node("next", second, args, result=_legacy_result(case, second, args))
    if second == "create_ticket":
        priority, = re.findall(r"优先级为“([低中高])”", prompt)
        args = {"subject": "回访预约", "priority": priority, "tags": ["回访", f"{priority}优先级"]}
        return Node("next", second, _semantic_arguments(second, args), ("first",),
                    _legacy_result(case, second, args))
    if second == "get_purchase_order":
        orders = ORDER_ID.findall(prompt)
        if len(orders) != 2 or first["arguments"]["order_id"] not in orders:
            raise ValueError(f"unexpected frozen order comparison prompt: {case['id']}")
        orders.remove(first["arguments"]["order_id"])
        args = {"order_id": orders[0]}
        return Node("next", second, args, result=_legacy_result(case, second, args))
    raise ValueError(f"unexpected sequential node: {second}")


def make_workflow(case: dict, *, observed_write: bool = False) -> Workflow:
    wanted = case["expected"]
    prompt = case["messages"][0]["content"]
    first = wanted.get("first_call")
    calls = wanted.get("calls") or ([first] if first else [])
    nodes = [
        Node("first" if i == 0 else f"first-{i}", row["name"],
             _semantic_arguments(row["name"], row["arguments"]),
             result=_legacy_result(case, row["name"], row["arguments"]), sop_turn=0)
        for i, row in enumerate(calls)
    ]
    if case["category"] == "sequential_multi_tool":
        nodes.append(_sequential(case, first, nodes[0], prompt))
    elif case.get("fault", {}).get("fail_first_calls") == 1:
        fault = case["fault"]
        initial, = nodes
        nodes = [
            replace(initial, result={"error": fault["error"], "message": fault["message"]}),
            replace(initial, node_id="retry", depends_on=("first",), sop_turn=1),
        ]

    required = [tuple(group) for group in wanted.get("final_contains_any", [])]
    forbidden = list(wanted.get("final_not_contains", []))
    for node in nodes:
        receipt = node.result or {}
        for key in ("ticket_id", "follow_up_id"):
            if key in receipt:
                required.append((receipt[key],))
        if node.tool == "calculate_total" and case["category"] == "sequential_multi_tool":
            initial_total = Decimal(str(nodes[0].result["total"]))
            if receipt["total"] == initial_total:
                forbidden.extend(("不一致", "不相符", "不相同", "存在差异"))
    schemas = {tool["function"]["name"]: _closed_schema(tool["function"]["parameters"]) for tool in case["tools"]}
    # A V1 simulated write does not expose database or transaction state.
    state = StateOracle(None, None) if observed_write or any(node.tool in WRITES for node in nodes) else None
    return Workflow(tuple(nodes), schemas, frozenset(wanted.get("forbidden_attempts", [])),
                    FinalAnswer(required=tuple(required), forbidden=tuple(forbidden)), state)
