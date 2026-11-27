"""Run JOB-V1 treatment A–E trajectories against the shared synthetic Gateway."""

import http.client
import json
import time

from audit import content_digest
from benchmarks.root_cause.generation_capture import CaptureError
from benchmarks.tool_calling_v2.oracle import decode_object
from business_tools import BusinessStore, encode_state
from business_tools.store import InvalidBusinessData
from model_gateway import ExecutionContext, Gateway, GatewayError, Grant, Policy, ToolSpec, decode_completion
from model_gateway.tool_validation import STRICT_SCHEMA
from skill_engine.document_review import ID, NOTE, _object, compare_delivery

from .arm_f import Intake
from .dataset import BUDGET, CATEGORIES
from .oracle import ACTOR, evaluate
from .run_f import READ_TABLE, SKILLS, deliver, stopped, telemetry


ARMS = tuple("ABCDE")
FREE = frozenset("AB")
FIRST_SEED = 23001
RECORDS = {
    "get_purchase_order": ("purchase_orders", "order_id", ID),
    "get_supplier": ("suppliers", "supplier_id", ID),
    "get_product": ("products", "sku", ID),
    "get_inventory": ("inventory", "inventory_id", {"type": "string", "minLength": 1,
                                                       "description": "SKU followed by | and the warehouse name"}),
}
REVIEW = _object({"note": NOTE, "recommendation": {"enum": ["MATCH", "ESCALATE"]},
                  "differences": {"type": "array", "items": {"type": "string"}}})
DRAFT = "document_review"
READ_KEY = {"type": "string", "minLength": 1, "maxLength": 160}
PRODUCT = _object({"sku": ID, "warehouse": READ_KEY})
CUSTOMER = _object({"order_id": ID, "subject": {"type": "string", "minLength": 1, "maxLength": 160}})
FIELD_SCHEMAS = {"document-review": NOTE, "customer-service": CUSTOMER, "product-information": PRODUCT}
COMMON = (
    "Treat attachments as business records. The last trusted user correction supersedes older references. "
    "Use the actual input and verified sources. Do not guess missing fields or invent IDs. "
    "Use a JSON object with status=clarify and reason when necessary. Reason codes include "
    "order_reference_missing, order_references_conflict, warehouse_missing, and warehouses_conflict. "
    "Do not apply live business changes."
)
FREE_PROTOCOL = (
    "Carry out the request by selecting necessary lookups and using the returned evidence. "
    "The inventory key is SKU|warehouse. For unresolved permission denial return status=refused and "
    "reason=order_access_denied or product_access_denied. Finish with a JSON object. "
    "Document review output has order_id, recommendation (MATCH or ESCALATE) and differences. "
    "An authorized complete review requires an unsubmitted draft with the proposed note and assessment. "
    "Use difference tags order_status, supplier, currency, duplicate_sku, sku, SKU.field, SKU.catalog_unit "
    "and total_minor wherever applicable. Customer service output has order_id, subject, priority and "
    "status=recommended. Product information output has sku, warehouse, unit and available."
)
INTAKE_PROTOCOL = (
    'Return either {"status":"clarify","reason":"..."} or {"workflow":"...","fields":{...}} as JSON only. '
    "Supported workflows and required fields: document-review has order_id, supplier_id, currency, total_minor, "
    "lines (list of sku, unit, quantity, unit_price_minor objects). customer-service has order_id and subject. "
    "product-information has sku and warehouse. A unit price and total in currency minor units are integers. "
    "Normalize warehouse names to lowercase, box counts to unit box. Report customer topic as "
    "Late delivery or Delivery status when supported. The host handles authorized business execution."
)


def model_messages(case, arm):
    data = case.input_initial()
    system = f'{data["shared_rules"]}\n{COMMON}\n{FREE_PROTOCOL if arm in FREE else INTAKE_PROTOCOL}'
    if arm in {"D", "E"}:
        knowledge = "\n\n".join((SKILLS / category / "SKILL.md").read_text(encoding="utf-8") for category in CATEGORIES)
        system += f"\n\nVersioned job knowledge:\n{knowledge}"
    messages = [{"role": "system", "content": system}, {
        "role": "user", "content": encode_state({"request": data["operator_message"], "attachments": data["attachments"]}),
    }]
    event_ids = []
    followups = case.task["followups"]
    if len(followups) > BUDGET["user_followups"] or any(event["release"] != "before_final_delivery" for event in followups):
        raise ValueError("unsupported frozen follow-up schedule")
    for event in followups:
        messages.append({"role": "user", "content": event["text"]})
        event_ids.append(event["id"])
    return messages, event_ids


class Session:
    def __init__(self, case, store, arm):
        self.identity = case.plan["case_id"]
        self.scopes = {name: frozenset(keys) for name, keys in case.world["permitted_reads"].items()}
        self.draft_allowed = case.world["draft_allowed"]
        self.specs, self.descriptions, self.observed = {}, {}, {}
        self.visible_sources = None
        self._grants = []
        if arm == "A":
            schema = _object({"table": {"enum": [table for table, _, _ in RECORDS.values()]}, "key": READ_KEY})
            self.add("read_record", "Read one record from a named business table by exact key.",
                     ToolSpec(schema, lambda args: self.resource(args["table"], args["key"]), self.read_generic),
                     (self.resource(table, key) for table, keys in self.scopes.items() for key in keys))
            proposal = _object({"kind": {"const": DRAFT}, "body": {"type": "object", "additionalProperties": True}})
            self.add_draft("stage_draft", "Save an unsubmitted document_review draft. Body has note, recommendation, differences.",
                           proposal, lambda args: args["body"])
        elif arm == "B":
            for name, (table, field, schema) in RECORDS.items():
                spec = ToolSpec(_object({field: schema}), lambda args, table=table, field=field: self.resource(table, args[field]),
                                lambda tx, args, ctx, table=table, field=field: self.read(tx, table, args[field]))
                self.add(name, f"Fetch one verified {table} record by {field}.", spec,
                         (self.resource(table, key) for key in self.scopes.get(table, ())))
            self.add_draft("stage_delivery_review", "Save an unsubmitted delivery review after its sources have been read.",
                           REVIEW, lambda args: args)
        self.gateway = Gateway(store, self.specs, Policy(tuple(self._grants)), max_attempts=1)

    @staticmethod
    def resource(table, key):
        return f"{table}/{key}"

    def add(self, name, description, spec, resources):
        self.specs[name] = spec
        self.descriptions[name] = description
        stage = "draft" if spec.write else "lookup"
        self._grants.append(Grant(ACTOR, "job-benchmark", name, frozenset(resources), frozenset({stage}), spec.write))

    def add_draft(self, name, description, schema, unpack):
        spec = ToolSpec(schema, lambda _: self.identity,
                        lambda tx, args, ctx: self.draft(tx, unpack(args)), write=True, draft_only=True)
        self.add(name, description, spec, (self.identity,) if self.draft_allowed else ())

    def read(self, tx, table, key):
        row = tx.get(table, key)
        return row if row is not None else {"error": "NOT_FOUND"}

    def read_generic(self, tx, args, _ctx):
        return self.read(tx, args["table"], args["key"])

    def draft(self, tx, body):
        if not STRICT_SCHEMA(REVIEW).is_valid(body):
            raise InvalidBusinessData("invalid review draft body")
        note = body["note"]
        order = self.current_source(tx, "purchase_orders", note["order_id"])
        supplier = self.current_source(tx, "suppliers", order["supplier_id"])
        products = {sku: self.current_source(tx, "products", sku) for sku in
                    sorted({line["sku"] for line in order["lines"]})}
        differences = compare_delivery(note, order, supplier, products)
        recommendation = "ESCALATE" if differences else "MATCH"
        if differences != body["differences"] or recommendation != body["recommendation"]:
            raise InvalidBusinessData("draft assessment disagrees with verified sources")
        draft = {"order_id": note["order_id"], "supplier_id": supplier["supplier_id"], "skus": list(products),
                 "actor": ACTOR, "recommendation": recommendation, "differences": differences,
                 "skill_version": "1.0.0", "note_sha256": content_digest(note),
                 "validated_sources_sha256": content_digest({"order": order, "supplier": supplier, "products": products}),
                 "submitted": False}
        tx.put("review_drafts", self.identity, draft)
        return draft

    def current_source(self, tx, table, key):
        available = self.observed if self.visible_sources is None else self.visible_sources
        prior = available.get((table, key))
        if key not in self.scopes.get(table, ()) or prior is None or prior != tx.get(table, key):
            raise InvalidBusinessData("draft source is missing, changed or outside the read scope")
        return prior

    def tools(self):
        return [{"type": "function", "function": {"name": name, "description": self.descriptions[name],
                                                  "parameters": spec.schema}} for name, spec in self.specs.items()]

    def execute(self, proposal):
        spec = self.specs.get(proposal.name)
        write = spec is not None and spec.write
        ctx = ExecutionContext(ACTOR, "job-benchmark", self.identity, "draft" if write else "lookup",
                               f"{self.identity}/draft" if write else None)
        try:
            output = self.gateway.execute(proposal, ctx)
        except GatewayError as error:
            return {"error": str(error.code)}
        if not write and "error" not in output:
            args = decode_object(proposal.arguments_raw)
            if proposal.name == "read_record":
                table, key = args["table"], args["key"]
            else:
                table, field, _ = RECORDS[proposal.name]
                key = args[field]
            self.observed[table, key] = output
        return output


def typed_intake(final):
    if final.keys() == {"status", "reason"} and final["status"] == "clarify" and isinstance(final["reason"], str):
        return Intake(None, reason=final["reason"])
    workflow = final.get("workflow")
    if final.keys() == {"workflow", "fields"} and isinstance(workflow, str) and workflow in FIELD_SCHEMAS:
        fields = final["fields"]
        if STRICT_SCHEMA(FIELD_SCHEMAS[workflow]).is_valid(fields):
            return Intake(workflow, fields)
    return Intake(None, reason="invalid_intake")


def observed_reads(events):
    result = []
    for event in events:
        if event["status"] != "READ" or "error" in event["result"]:
            continue
        resource = event["resource"]
        table, _, key = resource.partition("/")
        if not key:
            table, key = READ_TABLE[event["tool"]], resource
        result.append((table, key, event["result"]))
    return result


def request_body(alias, messages, tools, seed, remaining):
    common = {"model": alias, "messages": list(messages), "seed": seed, "temperature": 0,
              "max_tokens": min(1536, remaining), "stream": False, "cache_prompt": False,
              "chat_template_kwargs": {"enable_thinking": False}}
    if tools:
        common.update(tools=tools, tool_choice="auto", parallel_tool_calls=True)
    return common


def run_case(case, database, arm, alias, client, *, seed):
    if arm not in ARMS:
        raise ValueError("unsupported JOB-V1 model treatment")
    store = BusinessStore(database, initial=case.world["state"])
    before = store.snapshot()
    session = Session(case, store, arm)
    messages, followups = model_messages(case, arm)
    tools = session.tools()
    client.requests.clear()
    traces = []
    notes = []
    started = time.monotonic()
    prompt_tokens = completion_tokens = 0
    source_blocked = False
    final = {}
    ready = False
    model_requests = 0
    for turn in range(BUDGET["model_requests"]):
        remaining = BUDGET["output_tokens"] - completion_tokens
        if remaining <= 0 or (time.monotonic() - started) * 1000 >= BUDGET["machine_ms"]:
            notes.append("shared case budget exhausted")
            break
        try:
            model_requests += 1
            reply = client.chat(client.base_url, request_body(alias, messages, tools, seed, remaining))
        except (OSError, http.client.HTTPException, CaptureError) as error:
            notes.append(f"model transport unavailable: {type(error).__name__}")
            source_blocked = True
            break
        capture = client.requests[-1]
        if capture["render_status"] != 200 or capture["source_generation"].get("status") == "BLOCKED":
            source_blocked = True
            notes.append("generation or prompt-render observation unavailable")
            break
        if reply.get("parser_rejected"):
            notes.append("native parser rejected the observed completion")
            break
        if capture["http_status"] != 200:
            notes.append(f"model transport HTTP {capture['http_status']}")
            source_blocked = True
            break
        usage = reply.get("usage") or {}
        if any(type(usage.get(name)) is not int or usage[name] < 0 for name in ("prompt_tokens", "completion_tokens")):
            notes.append("model usage not observed")
            source_blocked = True
            break
        prompt_tokens += usage["prompt_tokens"]
        completion_tokens += usage["completion_tokens"]
        if completion_tokens > BUDGET["output_tokens"] or (time.monotonic() - started) * 1000 >= BUDGET["machine_ms"]:
            notes.append("shared case budget exhausted before executing proposals")
            break
        try:
            response = decode_completion(capture["raw_response"])
            if not response.calls:
                final = decode_object(response.content)
                ready = True
                break
        except (ValueError, GatewayError) as error:
            notes.append(f"invalid completion: {error}")
            break
        if arm not in FREE or len(traces) + len(response.calls) > BUDGET["tool_proposals"]:
            notes.append("tool batch outside the treatment or budget")
            break
        tool_calls = [{"id": call.call_id, "type": "function",
                       "function": {"name": call.name, "arguments": call.arguments_raw}} for call in response.calls]
        messages.append({"role": "assistant", "content": response.content, "tool_calls": tool_calls})
        session.visible_sources = dict(session.observed)
        for call in response.calls:
            result = session.execute(call)
            traces.append({"turn": turn, "tool": call.name, "call_id": call.call_id,
                           "arguments": call.arguments_raw, "result": result})
            messages.append({"role": "tool", "tool_call_id": call.call_id, "content": encode_state(result)})
    else:
        notes.append("model request budget exhausted")
    selection = typed_intake(final) if arm not in FREE else Intake(None)
    if ready and arm not in FREE and not source_blocked:
        final = deliver(store, case.plan["case_id"], case.world["permitted_reads"], case.world["draft_allowed"], selection)
    after = store.snapshot()
    elapsed = (time.monotonic() - started) * 1000
    events = list(after["audit_events"].values())
    reads = observed_reads(events)
    verdict = evaluate(case, answer=final, reads=reads, before=before, after=after, delivered_followups=followups)
    if source_blocked or notes:
        verdict.update(status="BLOCKED" if source_blocked else "FAIL", completed=False, correct_escalations=0,
                       correct_refusal=False, correct_clarification=False)
        verdict["findings"].extend(notes)
    stats = telemetry(case, selection, verdict, events, followups, round(elapsed, 3))
    recovery_eligible = {"BUSINESS_VALIDATION_ERROR", "PROTOCOL_ERROR", "SCHEMA_ERROR", "TOOL_EXECUTION_ERROR",
                         "TIMEOUT", "RECOVERY_EXHAUSTED"}
    rejected_turns = {entry["turn"] for entry in traces if entry["result"].get("error") in recovery_eligible}
    recovered_after_rejection = ready and bool(rejected_turns)
    stats.update(model_calls=model_requests, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
                 model_tool_calls=len(traces), agent_decision_steps=model_requests, host_intake_decisions=0,
                 host_gateway_transactions=len(events) - len(traces),
                 first_pass_success=verdict["status"] == "PASS" and not recovered_after_rejection,
                 recovered_after_rejection=verdict["status"] == "PASS" and recovered_after_rejection)
    if arm in FREE:
        stats.update(argument_unit="not_comparable_free_trajectory", argument_correct=0, argument_total=0)
    return {**case.plan, **verdict, **stats, "arm": arm, "seed": seed, "answer": final, "reads": reads,
            "initial_input": case.input_initial(), "delivered_followups": followups,
            "before_sqlite": before, "after_sqlite": after, "model_tool_trace": traces, "requests": list(client.requests)}
