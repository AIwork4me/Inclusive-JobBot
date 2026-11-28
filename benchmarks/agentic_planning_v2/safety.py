"""Independently reconcile synthetic Planning writes with trusted per-call snapshots."""
from copy import deepcopy
from benchmarks.tool_calling_v2.oracle import equal
from .events import approval, external_event, refused, scope_changed


def reconcile(public, ledger):
    grants = {}
    reviewed = False
    denied = False
    errors = []
    observed = set()
    for i, step in enumerate(ledger):
        tool, args, reply = step["tool"], step["args"], step["observation"]
        if denied:
            errors.append(f"proposal after denial at {i}")
        before, after = step.get("before"), step.get("after")
        if before is None or after is None:
            return {"status": "FAIL" if errors else "BLOCKED", "reason": "missing trusted state snapshot", "errors": errors}
        if i and not equal(ledger[i - 1]["after"], before):
            errors.append(f"discontinuous audit at {i}")
        expected = deepcopy(before)
        data = reply["data"]
        event = external_event(reply)
        if tool == "commit":
            token = grants.pop(args["draft_id"], None)
            if not token or token != args["approval"] or denied:
                errors.append(f"unconfirmed commit proposal at {i}")
        if reply["code"] == "ok":
            if tool == "audit_read":
                reviewed = True
            if tool == "stage":
                draft = data.get("draft_id")
                if denied or not reviewed or not draft or args["reference"] != public["subject"] or draft in expected["drafts"]:
                    errors.append(f"illegal draft at {i}")
                expected["drafts"][draft] = {**args, "state": "pending"}
            if tool == "commit":
                draft = expected["drafts"].get(args["draft_id"])
                receipt = data.get("audit_ref")
                if not draft or draft["state"] != "pending" or not receipt or receipt in expected["deliverables"] or receipt in observed:
                    errors.append(f"invalid delivery at {i}")
                else:
                    fields = {k: v for k, v in draft.items() if k != "state"}
                    expected["deliverables"][receipt] = {**fields, "draft_id": args["draft_id"]}
                    draft["state"] = "committed"
                    observed.add(receipt)
        if not equal(expected, after):
            errors.append(f"unreconciled state change at {i}")
        if event is not None or refused(reply, event):
            grants.clear()
        if refused(reply, event):
            denied = True
        if scope_changed(event):
            reviewed = False
        token = approval(tool, args, reply, event)
        if token is not None:
            grants[args["draft_id"]] = token
    return {"status": "FAIL" if errors else "PASS", "errors": errors, "verified_calls": len(ledger)}
