"""Conservative deterministic intake over the shared operator text and extracts."""

from dataclasses import dataclass
import re
import unicodedata


ROUTES = {
    "document-review": re.compile(r"\b(?:review|sign-off|draft queue)\b|审核|收货|签收", re.I),
    "customer-service": re.compile(r"\b(?:ticket|support|follow[- ]up)\b|客服|客户|工单|对话", re.I),
    "product-information": re.compile(r"\b(?:stock|availability|warehouse|ready to pick)\b|库存|排产|仓点|可用数", re.I),
}
ORDER = re.compile(r"\b(?:PO|ALT|OTHER|OLD)-[A-Z0-9]{2,60}\b")
PRODUCT = re.compile(r"\bSKU-[A-Z0-9]{2,60}\b")
SUPPLIER = re.compile(r"\bSUP-[A-Z0-9]{2,60}\b")
WAREHOUSE = re.compile(r"\b(east|west|north|south)\b", re.I)
CORRECTION = re.compile(r"\b(?:correction|corrected|instead|switched|void|replace)\b|更正|改用|改到|改查|作废", re.I)
ORDER_TARGET = re.compile(r"(?:\b(?:link to|use|corrected (?:the )?order reference to)\b|改用|按)\s*"
                          r"((?:PO|ALT|OTHER|OLD)-[A-Z0-9]{2,60})\b", re.I)
AMOUNT = r"([0-9]{1,12}(?:\.[0-9]{1,2})?)(?![0-9]|\.[0-9])"
QUANTITIES = (
    re.compile(r"\b(?:unloaded|received|delivered)\s+([0-9]+)\s+(box(?:es)?)\s+of\s+(SKU-[A-Z0-9]+)\b", re.I),
    re.compile(r"\b(SKU-[A-Z0-9]+)\s*卸货\s*([0-9]+)\s*(箱)"),
    re.compile(r"\b(SKU-[A-Z0-9]+)\s*共\s*([0-9]+)\s*(箱)"),
)
PRICE = re.compile(r"(?:\b(?:billed(?: at)?|unit price)\s+CNY\s+|单价人民币\s*)" + AMOUNT, re.I)
TOTAL = re.compile(r"(?:\b(?:total written on the receipt is|total)\s+CNY\s+|手写总额人民币\s*)" + AMOUNT, re.I)
LATE = re.compile(r"\b(?:promised|overdue|late|delay|yesterday|ETA)\b|昨天|延期|逾期|延迟", re.I)
DELIVERY = re.compile(r"\b(?:parcel|package|shipment|delivery)\b|包裹|快递|配送", re.I)


class Unresolved(ValueError):
    pass


@dataclass(frozen=True)
class Intake:
    workflow: str | None
    fields: dict | None = None
    reason: str | None = None


def pick(values, missing, conflict):
    candidates = set(values)
    if not candidates:
        raise Unresolved(missing)
    if len(candidates) != 1:
        raise Unresolved(conflict)
    return next(iter(candidates))


def corrected_field(text, revisions, observed_pattern, correction_pattern, missing, conflict):
    if revisions:
        latest = revisions[-1]
        if not CORRECTION.search(latest):
            raise Unresolved("followup_unsupported")
        return pick(correction_pattern.findall(latest), "followup_ambiguous", "followup_ambiguous")
    return pick(observed_pattern.findall(text), missing, conflict)


def minor_units(text):
    whole, _, cents = text.partition(".")
    return 100 * int(whole) + int(cents.ljust(2, "0"))


def document(text, order):
    if re.search(r"\b(?:USD|EUR)\b", text, re.I):
        raise Unresolved("currency_unsupported")
    candidates = []
    for quantity, _, sku in QUANTITIES[0].findall(text):
        candidates.append((sku.upper(), quantity))
    for pattern in QUANTITIES[1:]:
        candidates.extend((sku, quantity) for sku, quantity, _ in pattern.findall(text))
    sku, quantity = pick(candidates, "delivery_quantity_missing", "delivery_quantities_conflict")
    supplier = pick(SUPPLIER.findall(text), "supplier_reference_missing", "supplier_references_conflict")
    amount = pick(map(minor_units, TOTAL.findall(text)), "delivery_total_missing", "delivery_totals_conflict")
    price = pick(map(minor_units, PRICE.findall(text)), "unit_price_missing", "unit_prices_conflict")
    return {"order_id": order, "supplier_id": supplier, "currency": "CNY", "total_minor": amount,
            "lines": [{"sku": sku, "unit": "box", "quantity": int(quantity), "unit_price_minor": price}]}


def intake(request, followups):
    """Resolve only planned grammar from the same previously delivered input to all arms."""
    operator = unicodedata.normalize("NFKC", request["operator_message"])
    routed = [name for name, pattern in ROUTES.items() if pattern.search(operator)]
    if len(routed) != 1:
        return Intake(None, reason="intent_missing" if not routed else "intents_conflict")
    workflow = routed[0]
    text = unicodedata.normalize("NFKC", "\n".join(item["text"] for item in request["attachments"]))
    revisions = [unicodedata.normalize("NFKC", message) for message in followups]
    try:
        if workflow == "product-information":
            sku = pick(PRODUCT.findall(text), "product_reference_missing", "product_references_conflict")
            warehouse = corrected_field(text.lower(), [item.lower() for item in revisions], WAREHOUSE, WAREHOUSE,
                                        "warehouse_missing", "warehouses_conflict").lower()
            return Intake(workflow, {"sku": sku, "warehouse": warehouse})
        order = corrected_field(text, revisions, ORDER, ORDER_TARGET,
                                "order_reference_missing", "order_references_conflict").upper()
        if workflow == "document-review":
            return Intake(workflow, document(text, order))
        if not DELIVERY.search(text):
            raise Unresolved("customer_issue_missing")
        return Intake(workflow, {"order_id": order, "subject": "Late delivery" if LATE.search(text) else "Delivery status"})
    except Unresolved as failure:
        return Intake(workflow, reason=str(failure))
