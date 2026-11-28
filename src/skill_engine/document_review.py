"""Document review workflow with scoped lookups and explicit review submission."""

from __future__ import annotations

import json
import uuid

from audit import content_digest
from model_gateway import ExecutionContext, Gateway, Grant, Policy, Proposal, ToolSpec
from model_gateway.tool_validation import STRICT_SCHEMA

from . import Skill

ID = {"type": "string", "pattern": "^[A-Z0-9][A-Z0-9-]{0,63}$"}
ROW = {
    "type": "object", "additionalProperties": False,
    "required": ["sku", "unit", "quantity", "unit_price_minor"],
    "properties": {
        "sku": ID, "unit": {"type": "string", "minLength": 1, "maxLength": 20},
        "quantity": {"type": "integer", "minimum": 1, "maximum": 10**7},
        "unit_price_minor": {"type": "integer", "minimum": 0, "maximum": 10**10},
    },
}
NOTE = {
    "type": "object", "additionalProperties": False,
    "required": ["order_id", "supplier_id", "currency", "total_minor", "lines"],
    "properties": {
        "order_id": ID, "supplier_id": ID, "currency": {"enum": ["CNY", "USD", "EUR"]},
        "total_minor": {"type": "integer", "minimum": 0, "maximum": 10**16},
        "lines": {"type": "array", "minItems": 1, "maxItems": 100, "items": ROW},
    },
}


def _object(properties):
    return {
        "type": "object", "additionalProperties": False,
        "required": list(properties), "properties": properties,
    }


REVIEW = _object({
    "order_id": ID,
    "supplier_id": ID,
    "skus": {"type": "array", "items": ID, "minItems": 1, "uniqueItems": True},
    "actor": {"type": "string", "minLength": 1},
    "recommendation": {"enum": ["MATCH", "ESCALATE"]},
    "differences": {"type": "array", "items": {"type": "string"}},
    "skill_version": {"const": "1.0.0"},
    "note_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    "validated_sources_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    "submitted": {"const": False},
})


def compare_delivery(note, order, supplier, products):
    differences = []
    if order["order_id"] != note["order_id"]:
        raise ValueError("Purchase order returned a different identity")
    if supplier["supplier_id"] != order["supplier_id"]:
        raise ValueError("Supplier lookup returned a different identity")
    if any(product["sku"] != sku for sku, product in products.items()):
        raise ValueError("Catalog lookup returned a different identity")
    if order["status"] != "receivable":
        differences.append("order_status")
    if note["supplier_id"] != order["supplier_id"] or supplier.get("qualified") is not True:
        differences.append("supplier")
    if note["currency"] != order["currency"]:
        differences.append("currency")
    observed = {row["sku"]: row for row in note["lines"]}
    expected = {row["sku"]: row for row in order["lines"]}
    if len(observed) != len(note["lines"]) or len(expected) != len(order["lines"]):
        differences.append("duplicate_sku")
    if observed.keys() != expected.keys():
        differences.append("sku")
    for sku in sorted(observed.keys() & expected.keys()):
        for field in ("quantity", "unit", "unit_price_minor"):
            if observed[sku][field] != expected[sku][field]:
                differences.append(f"{sku}.{field}")
        if observed[sku]["unit"] != products[sku]["unit"]:
            differences.append(f"{sku}.catalog_unit")
    amount = lambda rows: sum(row["quantity"] * row["unit_price_minor"] for row in rows)
    if not note["total_minor"] == amount(note["lines"]) == amount(order["lines"]) == order["total_minor"]:
        differences.append("total_minor")
    return differences


class ReviewSession:
    def __init__(self, store, skill_path, actor, session_id, task_id, orders, suppliers, products):
        self.skill = Skill.load(skill_path)
        if self.skill.name != "document-review":
            raise ValueError("Expected the document-review skill")
        self.task_id = task_id
        self.context = ExecutionContext(actor, "document-reviewer", session_id, "review")
        self.proposal = None
        self.draft = None
        specs = {}
        grants = []

        for tool, table, field, resources in (
            ("get_purchase_order", "purchase_orders", "order_id", orders),
            ("get_supplier", "suppliers", "supplier_id", suppliers),
            ("get_product", "products", "sku", products),
        ):
            def handler(unit, arguments, _context, table=table, field=field):
                result = unit.get(table, arguments[field])
                if result is None:
                    raise ValueError(f"{table} row does not exist")
                return result

            specs[tool] = ToolSpec(_object({field: ID}), lambda args, field=field: args[field], handler)
            grants.append(Grant(actor, self.context.role, tool, frozenset(resources), frozenset({"review"})))

        persisted = _object({"id": {"type": "string"}, "review": REVIEW})
        for tool, stage, handler in (
            ("save_review_draft", "draft", self._persist_draft),
            ("submit_review", "confirm", self._persist_submission),
        ):
            specs[tool] = ToolSpec(persisted, lambda args: args["id"], handler,
                                   write=True, draft_only=stage == "draft")
            grants.append(Grant(actor, self.context.role, tool, frozenset({task_id}), frozenset({stage}), write=True))
        self.gateway = Gateway(store, specs, Policy(tuple(grants)))

    def _read(self, name, arguments):
        proposal = Proposal(uuid.uuid4().hex, name, json.dumps(arguments))
        return self.gateway.execute(proposal, self.context)

    def _purchase_order(self, note, _parents):
        return self._read("get_purchase_order", {"order_id": note["order_id"]})

    def _supplier(self, _note, parents):
        return self._read("get_supplier", {"supplier_id": parents["order"]["supplier_id"]})

    def _products(self, _note, parents):
        return {sku: self._read("get_product", {"sku": sku}) for sku in
                sorted({line["sku"] for line in parents["order"]["lines"]})}

    def _assess(self, note, parents):
        differences = compare_delivery(note, parents["order"], parents["supplier"], parents["products"])
        return {
            "order_id": note["order_id"], "supplier_id": parents["supplier"]["supplier_id"],
            "skus": sorted(parents["products"]), "actor": self.context.actor,
            "recommendation": "ESCALATE" if differences else "MATCH", "differences": differences,
            "skill_version": self.skill.version, "note_sha256": content_digest(note),
            "validated_sources_sha256": content_digest(parents), "submitted": False,
        }

    @staticmethod
    def _persist_draft(unit, arguments, _context):
        if unit.get("review_drafts", arguments["id"]) is not None:
            raise ValueError("Review already has a persisted draft")
        unit.put("review_drafts", arguments["id"], arguments["review"])
        return arguments["review"]

    @staticmethod
    def _persist_submission(unit, arguments, context):
        review = arguments["review"]
        current = unit.get("review_drafts", arguments["id"])
        if (current != review or review["actor"] != context.actor
                or review["recommendation"] != "MATCH" or review["submitted"]):
            raise ValueError("Review changed or is ineligible for submission")
        sources = {
            "order": unit.get("purchase_orders", review["order_id"]),
            "supplier": unit.get("suppliers", review["supplier_id"]),
            "products": {sku: unit.get("products", sku) for sku in review["skus"]},
        }
        if content_digest(sources) != review["validated_sources_sha256"]:
            raise ValueError("Source evidence changed after review")
        submitted = {**review, "submitted": True}
        unit.put("review_drafts", arguments["id"], submitted)
        return submitted

    def propose(self, note):
        """Accept a submitted note from the operator and save its review draft."""
        STRICT_SCHEMA(NOTE).validate(note)
        result = self.skill.workflow.execute(note, {
            "order_lookup": self._purchase_order, "supplier_lookup": self._supplier,
            "product_lookups": self._products, "assess": self._assess,
        })
        self.draft = result["assessment"]
        self._persist("save_review_draft", "draft", self.draft)
        return self.draft

    def _persist(self, tool, stage, review):
        context = ExecutionContext(self.context.actor, self.context.role, self.context.session_id,
                                   stage, f"{self.task_id}/{stage}")
        proposal = Proposal(uuid.uuid4().hex, tool, json.dumps({"id": self.task_id, "review": review}))
        if stage == "draft":
            return self.gateway.execute(proposal, context)
        confirmation = self.gateway.confirm(proposal, context)
        return self.gateway.execute(proposal, context, confirmation=confirmation)

    def submit_confirmed(self):
        """Call only from the host's trusted employee confirmation action."""
        if self.draft is None or self.draft["recommendation"] != "MATCH":
            raise ValueError("Only a matched review can be submitted")
        return self._persist("submit_review", "confirm", self.draft)
