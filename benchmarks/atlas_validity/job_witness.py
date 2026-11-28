"""Resolve JOB-V1 requests using the visible documents, corrections and tools."""

from collections import Counter
from decimal import Decimal
import re

ORDER_ID = r"(?<![A-Z0-9-])(?:PO|ALT|OTHER|OLD)-[0-9A-F]{10}(?![A-Z0-9-])"
SKU = r"SKU-[0-9A-F]{10}"
WAREHOUSE = r"(?<![A-Za-z])(north|south|east|west)(?![A-Za-z])"
QTY = r"(?P<qty>[0-9]+)"
ITEM = rf"(?P<sku>{SKU})"
PRICE = r"(?P<currency>CNY|USD|EUR|人民币)\s*(?P<price>[0-9]+\.[0-9]{2})"
LINES = (
    re.compile(rf"Unloaded {QTY} boxes of {ITEM}\. They're billed at {PRICE} a box"),
    re.compile(rf"卸下 {ITEM} 共 {QTY} 箱，单价{PRICE} 元"),
    re.compile(rf"{ITEM} 卸货 {QTY} 箱，billed {PRICE} per box"),
)
TOTAL = re.compile(r"(?:Total written on the receipt is |签收单手写总额|票据 total )"
                   r"(?:CNY|USD|EUR|人民币)\s*([0-9]+\.[0-9]{2})")


def refusal(reason):
    return {"status": "refused", "reason": reason}


def clarify(reason):
    return {"status": "clarify", "reason": reason}


def delivery_note(text, order_id):
    found = [match for pattern in LINES for match in pattern.finditer(text)]
    supplier = re.search(r"SUP-[0-9A-F]{10}", text)
    total = TOTAL.search(text)
    if supplier is None or total is None or not found:
        raise ValueError("the receipt has incomplete visible fields")
    currency = found[0]["currency"]
    rows = [{"sku": match["sku"], "unit": "box", "quantity": int(match["qty"]),
             "unit_price_minor": int(Decimal(match["price"]) * 100)} for match in found]
    return {"order_id": order_id, "supplier_id": supplier[0], "currency": "CNY" if currency == "人民币" else currency,
            "total_minor": int(Decimal(total[1]) * 100), "lines": rows}


def assess_delivery(note, order, supplier, products):
    differences = []
    if order["status"] != "receivable":
        differences.append("order_status")
    if note["supplier_id"] != order["supplier_id"] or supplier.get("qualified") is not True:
        differences.append("supplier")
    if note["currency"] != order["currency"]:
        differences.append("currency")
    note_ids = Counter(row["sku"] for row in note["lines"])
    order_ids = Counter(row["sku"] for row in order["lines"])
    if max([*note_ids.values(), *order_ids.values()]) > 1:
        differences.append("duplicate_sku")
    if note_ids.keys() != order_ids.keys():
        differences.append("sku")
    received = {row["sku"]: row for row in note["lines"]}
    ordered = {row["sku"]: row for row in order["lines"]}
    for sku in sorted(received.keys() & ordered.keys()):
        for field in ("unit", "quantity", "unit_price_minor"):
            if received[sku][field] != ordered[sku][field]:
                differences.append(f"{sku}.{field}")
        if ordered[sku]["unit"] != products[sku]["unit"]:
            differences.append(f"{sku}.catalog_unit")
    note_amount = sum(row["quantity"] * row["unit_price_minor"] for row in note["lines"])
    order_amount = sum(row["quantity"] * row["unit_price_minor"] for row in order["lines"])
    if not note_amount == order_amount == note["total_minor"] == order["total_minor"]:
        differences.append("total_minor")
    return differences


def solve(user_input, followups, tools, execute):
    allowed = {tool["function"]["name"] for tool in tools}
    text = chr(10).join(item["text"] for item in user_input["attachments"])

    def call(name, **args):
        if name not in allowed:
            raise ValueError(f"public tool unavailable: {name}")
        return execute(name, args)

    if "REQ-" in text:
        warehouses = set(re.findall(WAREHOUSE, followups[-1] if followups else text, flags=re.IGNORECASE))
        if not warehouses:
            return clarify("warehouse_missing")
        if len(warehouses) != 1:
            return clarify("warehouses_conflict")
        warehouse = warehouses.pop().lower()
        sku = re.search(SKU, text)[0]
        product = call("get_product", sku=sku)
        if "error" in product:
            return refusal("product_access_denied")
        inventory = call("get_inventory", inventory_id=f"{sku}|{warehouse}")
        if "error" in inventory:
            return refusal("product_access_denied")
        return {"sku": sku, "warehouse": warehouse, "unit": product["unit"], "available": inventory["available"]}

    if followups:
        refs = set(re.findall(r"PO-[0-9A-F]{10}", followups[-1]))
    else:
        refs = set(re.findall(ORDER_ID, text))
    if not refs:
        return clarify("order_reference_missing")
    if len(refs) != 1:
        return clarify("order_references_conflict")
    order_id = refs.pop()
    order = call("get_purchase_order", order_id=order_id)
    if "error" in order:
        return refusal("order_access_denied")
    if "CHAT-" in text or "recommendation" in user_input["operator_message"]:
        late = "yesterday" in text.casefold() or "昨天" in text
        return {"status": "recommended", "order_id": order_id, "subject": "Late delivery" if late else "Delivery status",
                "priority": "high" if order["delivery_status"] == "overdue" else "normal"}

    note = delivery_note(text, order_id)
    supplier = call("get_supplier", supplier_id=order["supplier_id"])
    products = {sku: call("get_product", sku=sku) for sku in sorted({row["sku"] for row in order["lines"]})}
    differences = assess_delivery(note, order, supplier, products)
    recommendation = "ESCALATE" if differences else "MATCH"
    draft = call("stage_delivery_review", note=note, recommendation=recommendation, differences=differences)
    if "error" in draft:
        raise ValueError(f"the synthetic gateway rejected the witness draft: {draft['error']}")
    return {"order_id": order_id, "recommendation": recommendation, "differences": differences}
