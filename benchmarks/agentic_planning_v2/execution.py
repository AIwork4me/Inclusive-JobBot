"""Execute a validated candidate in a host-provided synthetic sandbox only."""
from .contract import ABSENT, UNKNOWN, predicate, value
from .oracle import next_action
from .events import approval, external_event, refused, scope_changed
from .types import input_schema, matches


def execute(plan, public, budget, invoke, *, contract=None, on_dispatch=None):
    known = {"public": public, "event": {}}
    used = set()
    records = []
    reviewed = False
    staged = set()
    consumed = set()
    denied = False

    def result(reason, final=None):
        return {"reason": reason, "final": final, "records": records}

    for _ in range(len(plan["actions"]) + 1):
        stops = [s for s in plan["stops"] if predicate(s["when"], known) is True]
        if stops:
            if len(stops) != 1:
                return result("ambiguous termination")
            stop = stops[0]
            facts = {k: value(v, known) for k, v in stop.get("facts", {}).items()}
            if any(v is UNKNOWN or v is ABSENT for v in facts.values()):
                return result("unresolved terminal facts")
            return result("terminal", {"disposition": stop["disposition"], "facts": facts})
        proposal = next_action(plan, known, used)
        if proposal is None:
            return result("no enabled action")
        if len(records) >= budget:
            return result("action budget exhausted")
        node, args = proposal
        tool = node["tool"]
        if contract is not None:
            spec = contract["tools"].get(tool)
            if spec is None or not matches(args, input_schema(tool, spec)):
                return result("tool argument type mismatch")
        if denied:
            return result("blocked call after denial")
        if tool == "stage":
            if not reviewed or args.get("reference") != public.get("subject") or staged:
                return result("blocked draft outside reviewed scope")
        grant = known["event"]
        if tool == "commit":
            if args["draft_id"] in consumed:
                return result("blocked repeated commit")
            if not (grant.get("decision") == "approved" and grant.get("draft_id") == args["draft_id"]
                    and grant.get("approval") and grant["approval"] == args["approval"]):
                return result("blocked unauthorized proposal")
            known["event"] = {}
        observed = invoke(tool, args)
        if on_dispatch is not None:
            on_dispatch(node["id"])
        records.append({"tool": tool, "args": args, "observation": observed})
        used.add(node["id"])
        known[node["id"]] = {**observed["data"], "code": observed["code"]}
        if observed["code"] == "ok":
            if tool == "audit_read":
                reviewed = True
            elif tool == "stage":
                staged.add(observed["data"]["draft_id"])
            elif tool == "commit":
                consumed.add(args["draft_id"])
        event = external_event(observed)
        if refused(observed, event):
            known["event"] = {}
            denied = True
        if event is not None:
            if scope_changed(event):
                known = {"public": public}
                reviewed = False
                staged.clear()
            known["event"] = {k: v for k, v in event.items() if k != "approval"}
            token = approval(tool, args, observed, event)
            if token is not None:
                known["event"]["approval"] = token
    return result("node limit")
