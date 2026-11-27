"""Build bounded V2 software witness graphs from the visible bilingual contract."""
import re

from benchmarks.agentic_planning_v1.contract import TOOLS
from benchmarks.atlas_validity.planning_intent_witness import REFERENCE, understand
from .contract import references


def ref(source, field):
    return {"from": source, "field": field}


def first(sources, field):
    return {"first": [ref(s, field) for s in sources]}


def eq(left, right):
    return {"op": "eq", "left": left, "right": right}


def present(source, field):
    return {"op": "exists", "ref": ref(source, field)}


def build(wire):
    prompt = wire["messages"][-1]["content"]
    names = {t["function"]["name"] for t in wire["tools"]}
    subject = ref("public", "subject")
    public = {"subject": REFERENCE.search(prompt)[0]}
    nodes, stops = [], []

    def add(name, tool, args, when=True):
        if tool not in names:
            return None
        uses = sorted({s for s, _ in references([*args.values(), when])} - {"public", "event"})
        nodes.append({"id": name, "tool": tool, "arguments": args, "when": when, "depends_on": [], "observes": uses})
        return name

    def stop(when, disposition="completed", **facts):
        stops.append({"when": when, "disposition": disposition, "facts": {"subject": subject, **facts}})

    def chain(prefix, tool, initial, count=10):
        ids = []
        for i in range(count):
            source = ref(ids[-1], "linked_id") if ids else initial
            ids.append(add(prefix + str(i), tool, {"id": source}))
        return ids

    if not names:
        answer = understand(prompt)
        facts = {k: v for k, v in answer["facts"].items() if k != "subject"}
        goal = facts.get("objective", "review")
        stop(True, answer["disposition"], **facts)
    elif not ({"read_record", "check_policy"} & names):
        if "status" not in prompt and "classification" not in prompt:
            goal = "verified_delivery"
            stop(True, "clarify", reason="delivery_scope_required")
        else:
            facts, guards = {}, []
            for key, tool in (("status", "status"), ("classification", "archive")):
                if key in prompt:
                    add(tool, tool, {"reference": subject})
                    facts[key] = ref(tool, key)
                    guards.append(present(tool, key))
            goal = "status_and_history" if len(guards) == 2 else "current_status" if "status" in facts else "record_classification"
            stop({"op": "and", "args": guards}, **facts)
    elif "check_policy" in names and "classification" in prompt and "status" not in prompt:
        goal = "record_classification"
        add("find", "lookup", {"reference": subject})
        options = []
        if "read_record" in names:
            add("primary", "read_record", {"id": ref("find", "id")}, eq(ref("find", "kind"), "primary"))
            options = ["primary"] + chain("next", "read_record", ref("primary", "linked_id"), 5)
        add("direct", "check_policy", {"id": ref("find", "id")}, eq(ref("find", "kind"), "policy"))
        if options:
            add("linked", "check_policy", {"id": first(options, "policy_id")})
        sources = ["direct"] + (["linked"] if options else [])
        stop({"op": "or", "args": [present(s, "classification") for s in sources]},
             classification=first(sources, "classification"))
    else:
        add("find", "lookup", {"reference": subject})
        add("primary", "read_record", {"id": ref("find", "id")})
        add("revised", "lookup", {"reference": ref("event", "revised_reference")})
        add("active", "read_record", {"id": ref("revised", "id")})
        primary = ["active", "primary"]
        if add("backup", "read_backup", {"id": {"first": [ref("primary", "backup_id"), ref("find", "id")]}},
               eq(ref("primary", "permitted_source"), "replica")):
            primary.insert(0, "backup")
        for source in primary:
            stop(eq(ref(source, "code"), "permission_denied"), "escalate", reason="permission_denied")
        if "audit_read" not in names:
            goal = "verified_status"
            if add("mirror", "status_mirror", {"reference": subject},
                   eq(ref("primary", "permitted_source"), "independent_status_service")):
                primary.insert(0, "mirror")
            add("history", "archive", {"reference": subject}, {"op": "or", "args": [present(s, "status") for s in primary]})
            stop(present("history", "classification"), status=first(primary, "status"), classification=ref("history", "classification"))
        else:
            main = primary + chain("next", "read_record", first([s for s in primary if s != "backup"], "linked_id"), 3)
            endpoints = [ref(s, "audit_primary_id") for s in main if s != "backup"]
            if "check_policy" in names:
                policy = chain("policy", "check_policy", first(main, "policy_id"))
                endpoints += [ref(s, "audit_id") for s in policy]
            peers = chain("peer", "inspect_partner", first(main, "partner_id"))
            add("audit", "audit_read", {"id": {"first": endpoints}, "peer_id": first(peers, "audit_id")})
            threshold = re.search(r"(at most|at least|最多|至少)\s*(\d+)", wire["messages"][0]["content"])
            assessment = ref("audit", "assessment")
            if threshold:
                upper = threshold[1] in ("at most", "最多")
                assessment = {"if": {"op": "le" if upper else "ge", "left": ref("audit", "observed_metric"),
                                     "right": int(threshold[2])}, "then": "meets_policy", "else": "outside_policy"}
            goal = "verified_assessment"
            if "draft_id" not in prompt and "audit_ref" not in prompt:
                stop(eq(ref("audit", "code"), "ok"), assessment=assessment)
            else:
                goal = "verified_delivery"
                action = re.search(r"(?:filed as |reviewable |按 |将 )([a-z]+(?:_[a-z]+)+)", prompt)[1]
                add("draft", "stage", {"reference": subject, "action": action, "assessment": assessment})
                if "draft_id" in prompt:
                    add("verify", "verify_draft", {"draft_id": ref("draft", "draft_id")})
                    stop(present("verify", "outcome"), assessment=assessment, outcome=ref("verify", "outcome"),
                         draft_id=ref("draft", "draft_id"))
                else:
                    add("ask", "request_confirmation", {"draft_id": ref("draft", "draft_id")})
                    stop(eq(ref("event", "decision"), "declined"), "escalate", reason="approval_declined")
                    add("send", "commit", {"draft_id": ref("draft", "draft_id"), "approval": ref("event", "approval")},
                        eq(ref("event", "decision"), "approved"))
                    if add("verify", "verify_delivery", {"audit_ref": ref("send", "audit_ref")}):
                        stop(present("verify", "outcome"), assessment=assessment, outcome=ref("verify", "outcome"),
                             audit_ref=ref("send", "audit_ref"))
    tools = {name: {"inputs": list(TOOLS[name][1]), "outputs": [*TOOLS[name][2], "code"]} for name in names}
    if "read_record" in tools:
        tools["read_record"]["outputs"].extend(["backup_id", "permitted_source"])
    contract = {"goal": goal, "public_fields": ["subject"], "event_fields": ["revised_reference", "draft_id", "decision", "approval"],
                "tools": tools}
    return {"version": 2, "goal": goal, "actions": nodes, "stops": stops}, contract, public
