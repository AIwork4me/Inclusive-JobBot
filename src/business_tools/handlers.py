"""Reference handlers for the isolated business simulator."""

from __future__ import annotations

import hashlib
import json

from .store import InvalidBusinessData


def create_ticket(unit, arguments: dict, context) -> dict:
    """Create a ticket bound to existing customer and optional order records."""
    customer_id, order_id = arguments["customer_id"], arguments.get("order_id")
    if unit.get("customers", customer_id) is None:
        raise InvalidBusinessData("ticket customer does not exist")
    evidence = [{"table": "customers", "id": customer_id}]
    if order_id is not None:
        order = unit.get("purchase_orders", order_id)
        if order is None or order.get("customer_id") != customer_id:
            raise InvalidBusinessData("ticket order does not belong to the customer")
        evidence.append({"table": "purchase_orders", "id": order_id})
    operation = json.dumps([context.actor, context.operation_id]).encode("utf-8")
    ticket_id = "TK-" + hashlib.sha256(operation).hexdigest()[:24]
    if unit.get("tickets", ticket_id) is not None:
        raise InvalidBusinessData("ticket already exists")
    unit.put("tickets", ticket_id, {
        "subject": arguments["subject"], "priority": arguments["priority"], "tags": arguments["tags"],
        "customer_id": customer_id, "order_id": order_id, "source_evidence": evidence,
        "actor": context.actor, "status": "created",
    })
    return {"ticket_id": ticket_id, "status": "created"}
