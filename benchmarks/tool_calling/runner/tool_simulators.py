"""Deterministic stand-ins for the tool-calling benchmark.

Every tool answers from the ``world`` rows stored in its case. There is no I/O
and no side effect. A tool that the case did not declare, or that is on the
forbidden list, is never executed: the host answers with a policy denial and
records the attempt.
"""

from __future__ import annotations

import hashlib

RATES = {"CNY": 1.0, "USD": 7.10, "EUR": 7.70, "JPY": 0.048}
WAREHOUSES = ("上海仓", "北京仓", "广州仓")
DENIED = {"error": "policy_denied", "message": "该工具未获授权，操作已被拒绝。"}


def _text(value) -> str:
  return str(value).strip() if value is not None else ""


class ToolHost:
  def __init__(self, case: dict):
    self.case = case
    self.world = case["world"]
    self.declared = {tool["function"]["name"] for tool in case["tools"]}
    self.fault = case.get("fault")
    self.counts: dict[str, int] = {}
    self.sequence = 0
    self.executed: list[str] = []
    self.denied: list[str] = []

  def dispatch(self, name: str, arguments) -> dict:
    if name not in self.declared:
      self.denied.append(name)
      return dict(DENIED)
    count = self.counts.get(name, 0) + 1
    self.counts[name] = count
    self.executed.append(name)
    if self.fault and self.fault.get("tool") == name and self.fault.get("fail_first_calls", 0) >= count:
      return {"error": self.fault["error"], "message": self.fault["message"]}
    handler = getattr(self, f"tool_{name}", None)
    result = handler(arguments) if handler else {"error": "not_implemented", "message": "工具尚未实现"}
    if self.fault and self.fault.get("tool") == name and self.fault.get("result_suffix"):
      result = dict(result)
      result["notice"] = self.fault["result_suffix"].strip()
    return result

  def _stock(self, sku: str, warehouse: str) -> int:
    stored = self.world.get("stocks", {}).get(f"{sku}|{warehouse}")
    if stored is not None:
      return stored
    # Stable fallback for a warehouse the case did not draw a number for.
    return int(hashlib.sha256(f"{sku}|{warehouse}".encode("utf-8")).hexdigest()[:6], 16) % 500

  def tool_get_purchase_order(self, arguments) -> dict:
    order = self.world["orders"].get(_text(arguments.get("order_id")))
    if not order:
      return {"error": "order_not_found", "message": "没有找到该采购订单，请核对订单号。"}
    return dict(order)

  def tool_get_supplier(self, arguments) -> dict:
    supplier = self.world["suppliers"].get(_text(arguments.get("supplier_id")))
    if not supplier:
      return {"error": "supplier_not_found", "message": "没有找到该供应商，请核对供应商编号。"}
    return dict(supplier)

  def tool_get_product(self, arguments) -> dict:
    product = self.world["products"].get(_text(arguments.get("sku")))
    if not product:
      return {"error": "product_not_found", "message": "没有找到该商品，请核对商品编号。"}
    return dict(product)

  def tool_check_stock(self, arguments) -> dict:
    sku, warehouse = _text(arguments.get("sku")), _text(arguments.get("warehouse"))
    if warehouse not in WAREHOUSES:
      return {"error": "invalid_warehouse", "message": f"仓库不存在，可选仓库：{'、'.join(WAREHOUSES)}。"}
    if sku not in self.world["products"]:
      return {"error": "product_not_found", "message": "没有找到该商品，请核对商品编号。"}
    return {"sku": sku, "warehouse": warehouse, "stock": self._stock(sku, warehouse)}

  def tool_calculate_total(self, arguments) -> dict:
    items = arguments.get("items")
    if not isinstance(items, list) or not items:
      return {"error": "invalid_arguments", "message": "items 必须是非空数组。"}
    try:
      total = round(sum(float(item["unit_price"]) * int(item["quantity"]) for item in items), 2)
    except (KeyError, TypeError, ValueError):
      return {"error": "invalid_arguments", "message": "明细行缺少 sku、unit_price 或 quantity，或类型不正确。"}
    return {"total": total, "line_count": len(items), "currency": "CNY"}

  def tool_convert_currency(self, arguments) -> dict:
    try:
      source, target = _text(arguments.get("from")), _text(arguments.get("to"))
      amount = float(arguments.get("amount"))
    except (TypeError, ValueError):
      return {"error": "invalid_arguments", "message": "amount 必须是数字。"}
    if source not in RATES or target not in RATES:
      return {"error": "invalid_arguments", "message": "不支持的币种。"}
    return {"amount": round(amount * RATES[source] / RATES[target], 2), "currency": target}

  def tool_search_knowledge_base(self, arguments) -> dict:
    query, top_k = _text(arguments.get("query")), arguments.get("top_k")
    if not isinstance(top_k, int) or isinstance(top_k, bool) or not 1 <= top_k <= 5:
      return {"error": "invalid_arguments", "message": "top_k 必须是 1 到 5 之间的整数。"}
    archived = bool(arguments.get("include_archived", False))
    hits = [doc for doc in self.world["kb"] if query and (query in doc["title"] or query in doc["content"])]
    if not archived:
      hits = [doc for doc in hits if "归档" not in doc["title"]]
    return {"results": hits[:top_k], "returned": len(hits[:top_k])}

  def tool_create_ticket(self, arguments) -> dict:
    subject, priority, tags = _text(arguments.get("subject")), _text(arguments.get("priority")), arguments.get("tags")
    if not subject or priority not in ("低", "中", "高") or not isinstance(tags, list):
      return {"error": "invalid_arguments", "message": "subject 不能为空，priority 必须是 低、中、高 之一，tags 必须是数组。"}
    self.sequence += 1
    return {"ticket_id": f"TK-{self.sequence:05d}", "status": "created"}

  def tool_get_customer(self, arguments) -> dict:
    customer = self.world["customers"].get(_text(arguments.get("customer_id")))
    if not customer:
      return {"error": "customer_not_found", "message": "没有找到该客户，请核对客户编号。"}
    return dict(customer)

  def tool_schedule_follow_up(self, arguments) -> dict:
    customer_id = _text(arguments.get("customer_id"))
    if customer_id not in self.world["customers"]:
      return {"error": "customer_not_found", "message": "没有找到该客户，请核对客户编号。"}
    if not _text(arguments.get("date")) or not _text(arguments.get("note")):
      return {"error": "invalid_arguments", "message": "date 和 note 不能为空。"}
    self.sequence += 1
    return {"follow_up_id": f"FU-{self.sequence:04d}", "status": "scheduled"}

  def tool_update_product_record(self, arguments) -> dict:
    sku, fields = _text(arguments.get("sku")), arguments.get("fields")
    if sku not in self.world["products"]:
      return {"error": "product_not_found", "message": "没有找到该商品，请核对商品编号。"}
    if not isinstance(fields, dict) or not fields:
      return {"error": "invalid_arguments", "message": "fields 必须是非空对象。"}
    return {"sku": sku, "updated_fields": sorted(fields), "status": "updated"}

  def tool_compare_documents(self, arguments) -> dict:
    first = self.world["documents"].get(_text(arguments.get("doc_a_id")))
    second = self.world["documents"].get(_text(arguments.get("doc_b_id")))
    if not first or not second:
      return {"error": "document_not_found", "message": "没有找到单据，请核对单据编号。"}
    mismatches = [key for key in ("supplier_id", "total", "quantity") if first[key] != second[key]]
    return {"doc_a_id": first["doc_id"], "doc_b_id": second["doc_id"], "mismatched_fields": mismatches, "consistent": not mismatches}
