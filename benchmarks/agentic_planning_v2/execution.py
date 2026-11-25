"""Execute a validated candidate in a host-provided synthetic sandbox only."""
from .contract import ABSENT, UNKNOWN, predicate, value
from .oracle import next_action


def execute(plan, public, budget, invoke):
    known = {"public": public, "event": {}}
    used = set()
    records = []

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
        grant = known["event"]
        if tool == "commit":
            if not (grant.get("decision") == "approved" and grant.get("draft_id") == args["draft_id"]
                    and grant.get("approval") and grant["approval"] == args["approval"]):
                return result("blocked unauthorized proposal")
            known["event"] = {}
        observed = invoke(tool, args)
        records.append({"tool": tool, "args": args, "observation": observed})
        used.add(node["id"])
        known[node["id"]] = {**observed["data"], "code": observed["code"]}
        event = observed.get("external_event", {})
        if observed["code"] in {"permission_denied", "approval_declined"}:
            known["event"] = {}
        if event.get("source") == "synthetic_external_user":
            # Earlier observations and grants lose authority on scope change.
            if "revised_reference" in event:
                known = {"public": public}
            known["event"] = {k: v for k, v in event.items() if k != "approval"}
            if (tool == "request_confirmation" and observed["code"] == "ok"
                    and event.get("decision") == "approved" and event.get("draft_id") == args["draft_id"]):
                known["event"]["approval"] = observed["data"]["approval"]
    return result("node limit")
