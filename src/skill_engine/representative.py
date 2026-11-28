"""Representative product-information and customer-service skill paths."""

import json
import uuid

from audit import content_digest
from model_gateway import ExecutionContext, Gateway, Grant, Policy, Proposal, ToolSpec

from . import Skill
from .document_review import ID, _object


def run_representative(skill_path, store, actor, session_id, scopes, request):
    skill = Skill.load(skill_path)
    context = ExecutionContext(actor, skill.name, session_id, "lookup")
    definitions = {
        "get_product": ("products", "sku", ID),
        "get_inventory": ("inventory", "inventory_id", {"type": "string", "minLength": 1}),
        "get_order": ("purchase_orders", "order_id", ID),
    }
    tools, grants = {}, []
    for operation, (table, field, schema) in definitions.items():
        def read(unit, arguments, _context, table=table, field=field):
            record = unit.get(table, arguments[field])
            if record is None:
                raise ValueError(f"Missing {table} row")
            return record

        tools[operation] = ToolSpec(_object({field: schema}), lambda args, field=field: args[field], read)
        grants.append(Grant(actor, context.role, operation, frozenset(scopes.get(table, ())), frozenset({"lookup"})))
    gateway = Gateway(store, tools, Policy(tuple(grants)))

    def lookup(tool, **arguments):
        proposal = Proposal(uuid.uuid4().hex, tool, json.dumps(arguments))
        return gateway.execute(proposal, context)

    operations = {
        "get_product": lambda inputs, _: lookup("get_product", sku=inputs["sku"]),
        "get_inventory": lambda inputs, parents: lookup(
            "get_inventory", inventory_id=f'{parents["product"]["sku"]}|{inputs["warehouse"]}',
        ),
        "summarize_inventory": lambda _, parents: {
            "sku": parents["product"]["sku"], "unit": parents["product"]["unit"],
            "available": parents["inventory"]["available"],
            "source_sha256": content_digest(parents),
        },
        "get_order": lambda inputs, _: lookup("get_order", order_id=inputs["order_id"]),
        "recommend_ticket": lambda inputs, parents: {
            "order_id": parents["order"]["order_id"], "subject": inputs["subject"],
            "priority": "high" if parents["order"].get("delivery_status") == "overdue" else "normal",
            "source_sha256": content_digest(parents), "status": "recommended",
        },
    }
    return skill.workflow.execute(request, operations)["assessment"]
