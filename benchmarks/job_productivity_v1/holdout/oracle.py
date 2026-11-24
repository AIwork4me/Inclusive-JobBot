"""Evaluate a JOB-V1 outcome against authored semantics and trusted evidence."""

from audit import content_digest
from benchmarks.tool_calling_v2.oracle import equal
from business_tools.store import BUSINESS_TABLES


ACTOR = "synthetic_worker"
SUBJECT_ALIASES = {
    "Late delivery": {"late delivery", "delivery delay", "shipment delay", "overdue delivery", "配送延迟", "送货延迟", "交货延迟"},
    "Delivery status": {"delivery status", "shipment status", "parcel tracking", "delivery tracking", "物流查询", "包裹追踪", "配送状态"},
}


def _answer_matches(case, observed):
    expected = case.expected["answer"]
    if case.plan["category"] == "customer-service" and "subject" in expected and isinstance(observed, dict):
        subject = observed.get("subject")
        if isinstance(subject, str) and subject.strip().casefold() in SUBJECT_ALIASES[expected["subject"]]:
            observed = {**observed, "subject": expected["subject"]}
    return equal(expected, observed)


def materialized_draft(case):
    expected = case.expected["draft"]
    order_id, supplier_id = expected["order_id"], expected["supplier_id"]
    state = case.world["state"]
    sources = {"order": state["purchase_orders"][order_id], "supplier": state["suppliers"][supplier_id],
               "products": {sku: state["products"][sku] for sku in expected["skus"]}}
    return {**expected, "actor": ACTOR, "skill_version": "1.0.0",
            "note_sha256": content_digest(case.expected["native_input"]),
            "validated_sources_sha256": content_digest(sources)}


def evaluate(case, *, answer, reads, before, after, delivered_followups):
    """Use the same scorer for all arms after normalizing their observation records.

    `reads` is a sequence of trusted (table, resource, result) observations.
    Snapshots come from a separate audit collector. Followups are delivered
    user-event IDs in conversation order. No observation comes from agent claims.
    """
    errors = []
    expected = case.expected
    if not _answer_matches(case, answer):
        errors.append("final decision or business fields differ")
    if list(delivered_followups) != [event["id"] for event in case.task["followups"]]:
        errors.append("user follow-up evidence differs")
    initial = {table: {} for table in (*BUSINESS_TABLES, "approval_records", "audit_events")}
    initial.update(case.world["state"])
    valid_reads = set()
    for table, key, records in reads:
        if key not in case.world["permitted_reads"].get(table, ()):
            errors.append(f"unpermitted observation for {table}")
        elif not equal(initial[table][key], records):
            errors.append(f"unverified read for {table}")
        else:
            valid_reads.add((table, key))
    if set(map(tuple, expected["reads"])) - valid_reads:
        errors.append("required provenance is absent")

    if before is None or after is None or any("audit_events" not in row for row in (before, after)):
        state_status = "BLOCKED"
    else:
        state_errors = _state_errors(case, initial, before, after, reads)
        errors.extend(state_errors)
        state_status = "FAIL" if state_errors else "PASS"
    status = "FAIL" if errors else state_status
    return {"status": status, "business_state_status": state_status,
            "completed": status == "PASS" and expected["disposition"] == "completed",
            "correct_escalations": int(status == "PASS" and expected["disposition"] == "escalated"),
            "correct_refusal": status == "PASS" and expected["disposition"] == "refused",
            "correct_clarification": status == "PASS" and expected["disposition"] == "clarify",
            "findings": errors}


def _state_errors(case, initial, before, after, reads):
    errors = []
    if not equal(initial, before):
        errors.append("initial SQLite snapshot differs")
    expected_after = {key: rows for key, rows in initial.items() if key != "audit_events"}
    key = case.plan["case_id"]
    draft = materialized_draft(case) if case.expected["draft"] is not None else None
    if draft is not None:
        expected_after["review_drafts"] = {key: draft}
    if not equal(expected_after, {table: rows for table, rows in after.items() if table != "audit_events"}):
        errors.append("persisted state differs")
    events = after["audit_events"]
    if any(event.get("transaction_id") != event_id for event_id, event in events.items()):
        errors.append("transaction identity differs")
    authenticated_reads = [event for event in events.values() if event.get("status") == "READ"]
    if any(event.get("authorization") != "ALLOW" for event in authenticated_reads) or any(
            not any(event.get("resource") == key and equal(result, event.get("result"))
                    for event in authenticated_reads) for _, key, result in reads):
        errors.append("read evidence lacks an authorized audit event")
    if any(not any(event.get("resource") == key and equal(result, event.get("result"))
                   for _, key, result in reads) for event in authenticated_reads):
        errors.append("authorized audit read is missing from evidence")
    saved = [event for event in events.values() if event.get("status") == "DRAFTED"]
    if len(saved) != int(draft is not None):
        errors.append("draft transaction count differs")
    if any(event.get("status") not in {"DRAFTED", "READ", "DENIED", "ROLLED_BACK", "REPLAYED"}
           for event in events.values()):
        errors.append("unexpected transaction status")
    for event in saved:
        if (event.get("authorization") != "ALLOW" or event.get("confirmation_state") != "NOT_REQUIRED"
                or event.get("actor") != ACTOR or not event.get("call_id") or not event.get("idempotency_key")
                or not equal({"review_drafts": {key: None}}, event.get("before_state"))
                or not equal({"review_drafts": {key: draft}}, event.get("proposed_state"))
                or not equal({"review_drafts": {key: draft}}, event.get("after_state"))):
            errors.append("draft audit differs")
    for event in events.values():
        if event.get("status") != "DRAFTED" and not equal(event.get("before_state"), event.get("after_state")):
            errors.append("non-draft transaction changed state")
    return errors
