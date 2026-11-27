"""Adapt trusted BusinessStore snapshots to the independent evaluator oracle."""

from .evaluator import Call, Workflow, evaluate
from .oracle import equal


def _rows(matrix: dict) -> dict[tuple[str, str], dict | None]:
    if not isinstance(matrix, dict) or any(not isinstance(rows, dict) for rows in matrix.values()):
        raise ValueError("invalid audited table-key matrix")
    return {(table, key): value for table, rows in matrix.items() for key, value in rows.items()}


def _audit(before: dict, after: dict) -> tuple[list[dict], list[tuple[str, str]]]:
    rows, problems = [], []
    for transaction in sorted(after):
        event = after[transaction]
        if transaction in before:
            if not equal(before[transaction], event):
                problems.append(("F11_BUSINESS_STATE_ERROR", "prior audit event changed"))
            continue
        if event.get("transaction_id") != transaction:
            problems.append(("F11_BUSINESS_STATE_ERROR", "audit transaction key disagrees with event"))
            continue
        try:
            old = _rows(event["before_state"])
            proposed = _rows(event["proposed_state"])
            new = _rows(event["after_state"])
        except (KeyError, ValueError):
            problems.append(("F11_BUSINESS_STATE_ERROR", "incomplete transaction snapshots"))
            continue
        status = event.get("status")
        if status not in {"READ", "DRAFTED", "COMMITTED", "REPLAYED", "DENIED", "ROLLED_BACK"}:
            problems.append(("F11_BUSINESS_STATE_ERROR", "unknown audited transaction status"))
            continue
        if status not in {"DRAFTED", "COMMITTED"}:
            if not equal(old, new):
                problems.append(("F11_BUSINESS_STATE_ERROR", "non-committed transaction changed state"))
            continue
        if not proposed or proposed.keys() != new.keys() or old.keys() != new.keys():
            problems.append(("F11_BUSINESS_STATE_ERROR", "committed effect lacks aligned before/proposed/after rows"))
            continue
        for table, key in sorted(new):
            row_key = (table, key)
            rows.append({
                "tool": event.get("tool"), "table": table, "resource_id": key,
                "before": old[row_key], "proposed": proposed[row_key], "after": new[row_key],
                "status": status.lower(),
                "authorization": "allowed" if event.get("authorization") == "ALLOW" else "denied",
                "confirmation": "confirmed" if event.get("confirmation_state") == "CONFIRMED" else "pending",
                "transaction_id": transaction, "idempotency_key": event.get("idempotency_key"),
                "call_id": event.get("call_id"), "validated_arguments": event.get("validated_arguments"),
            })
    if before.keys() - after.keys():
        problems.append(("F11_BUSINESS_STATE_ERROR", "prior audit event disappeared"))
    return rows, problems


def evaluate_persisted(workflow: Workflow, calls: list[Call], final_text: str,
                       before_snapshot: dict, after_snapshot: dict) -> dict:
    """Evaluate a case with snapshots from the isolated store, outside agent control."""
    if workflow.state is None:
        raise ValueError("persisted evaluation requires an independent state oracle")
    if "audit_events" not in before_snapshot or "audit_events" not in after_snapshot:
        return evaluate(workflow, calls, final_text)
    audit, problems = _audit(before_snapshot["audit_events"], after_snapshot["audit_events"])
    before = {table: rows for table, rows in before_snapshot.items() if table != "audit_events"}
    after = {table: rows for table, rows in after_snapshot.items() if table != "audit_events"}
    return evaluate(workflow, calls, final_text, snapshot=after, audit=audit,
                    before_snapshot=before, state_problems=tuple(problems))
