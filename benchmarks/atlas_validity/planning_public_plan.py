"""Construct conditional initial plans using the public Planning contract."""

import re

from .planning_intent_witness import REFERENCE, understand


def initial_plan(wire):
    prompt = wire["messages"][-1]["content"]
    ref = REFERENCE.search(prompt)[0]
    names = {tool["function"]["name"] for tool in wire["tools"]}
    actions = []

    def action(name, tool, arguments, sources=(), condition=None):
        actions.append({"id": name, "tool": tool, "arguments": arguments, "depends_on": list(sources),
                        "preconditions": [condition] if condition else []})
        return name

    def field(source, key):
        return {"from": source, "field": key}

    if not names:
        goal = understand(prompt)
        objective = goal["facts"].get("objective", "review")
        subgoals = ["Resolve the stated request or identify the missing input"]
    elif "check_policy" in names and "classification" in prompt:
        objective = "record_classification"
        subgoals = ["Locate the underlying record", "Read the active classification"]
        action("discover", "lookup", {"reference": ref})
        action("direct-policy", "check_policy", {"id": field("discover", "id")}, ("discover",),
               "Use a direct policy reference when lookup identifies one")
        if "read_record" in names:
            action("primary", "read_record", {"id": field("discover", "id")}, ("discover",),
                   "Use a primary record reference when lookup identifies one")
            action("primary-policy", "check_policy", {"id": field("primary", "policy_id")}, ("primary",),
                   "Use a policy ID directly supplied by the primary")
            action("linked", "read_record", {"id": field("primary", "linked_id")}, ("primary",),
                   "Follow an active primary link when present")
            action("linked-policy", "check_policy", {"id": field("linked", "policy_id")}, ("linked",))
            action("linked-next", "read_record", {"id": field("linked", "linked_id")}, ("linked",),
                   "Follow the next active primary link if necessary")
            action("linked-next-policy", "check_policy", {"id": field("linked-next", "policy_id")},
                   ("linked-next",))
    elif "audit_read" in names:
        objective = "verified_delivery" if "audit_ref" in prompt or "draft_id" in prompt else "verified_assessment"
        subgoals = ["Locate the primary", "Cross-check the independent linked records"]
        action("discover", "lookup", {"reference": ref})
        action("primary", "read_record", {"id": field("discover", "id")}, ("discover",))
        action("primary-link", "read_record", {"id": field("primary", "linked_id")}, ("primary",),
               "Follow linked_id if the primary record delegates the assessment")
        policy_sources = []
        peer_sources = []
        records = ("primary", "primary-link")
        for record in records:
            if "check_policy" in names:
                policy = action(f"{record}-policy", "check_policy", {"id": field(record, "policy_id")}, (record,),
                                "Follow the record's policy_id when it is present")
                policy_link = action(f"{record}-policy-link", "check_policy", {"id": field(policy, "linked_id")},
                                     (policy,), "Follow linked_id within the policy service if present")
                policy_sources.extend(((policy, "audit_id"), (policy_link, "audit_id")))
            else:
                policy_sources.append((record, "audit_primary_id"))
            peer = action(f"{record}-peer", "inspect_partner", {"id": field(record, "partner_id")}, (record,),
                          "Follow the record's partner_id when it is present")
            peer_link = action(f"{record}-peer-link", "inspect_partner", {"id": field(peer, "linked_id")}, (peer,),
                               "Follow linked_id within the partner service if present")
            peer_sources.append((peer, peer_link))

        filing = re.search(r"(?:filed as |reviewable |按 |将 )([a-z]+(?:_[a-z]+)+)", prompt)
        for index, (source, endpoint) in enumerate(policy_sources):
            peers = peer_sources[index // 2] if "check_policy" in names else peer_sources[index]
            for peer_index, peer in enumerate(peers):
                name = f"cross-check-{index}-{peer_index}"
                audit = action(name, "audit_read", {"id": field(source, endpoint), "peer_id": field(peer, "audit_id")},
                               (source, peer), "Cross-check only available endpoints from the same active record")
                if filing and index == 0 and peer_index == 0:
                    assessment = field(audit, "assessment")
                    if re.search(r"(?:at most|at least|最多|至少)\s*\d+", wire["messages"][0]["content"]):
                        assessment = {**field(audit, "observed_metric"), "evaluate": "policy_assessment"}
                    draft = action("draft", "stage", {"reference": ref, "assessment": assessment, "action": filing[1]},
                                   (audit,), "Only stage once, after verified assessment and permitted scope")
                    if "verify_draft" in names:
                        action("verify-draft", "verify_draft", {"draft_id": field(draft, "draft_id")}, (draft,))
                    elif "request_confirmation" in names:
                        confirmation = action("confirmation", "request_confirmation",
                                              {"draft_id": field(draft, "draft_id")}, (draft,))
                        delivery = action("delivery", "commit", {"draft_id": field(draft, "draft_id"),
                                                                 "approval": field(confirmation, "approval")},
                                          (draft, confirmation), "Commit once only after explicit external approval")
                        if "verify_delivery" in names:
                            action("verify-delivery", "verify_delivery", {"audit_ref": field(delivery, "audit_ref")},
                                   (delivery,))
    elif names == {"commit", "lookup", "stage"}:
        objective = "verified_delivery"
        subgoals = ["Ask for the missing delivery scope before authorizing any work"]
    elif "lookup" in names and "status" in prompt:
        objective = "verified_status"
        subgoals = ["Verify current state", "Retrieve the original classification"]
        action("discover", "lookup", {"reference": ref})
        action("primary", "read_record", {"id": field("discover", "id")}, ("discover",))
        action("history", "archive", {"reference": ref})
    else:
        status = "status" in prompt
        classification = "classification" in prompt
        subgoals = []
        if status:
            action("read-current", "status", {"reference": ref})
            subgoals.append("Read current status")
        if classification:
            action("read-history", "archive", {"reference": ref})
            subgoals.append("Read historical classification")
        objective = ("status_and_history" if status and classification else
                     "current_status" if status else "record_classification")
    return {
        "goal": {"subject": ref, "objective": objective},
        "subgoals": subgoals,
        "actions": actions,
        "success_conditions": ["Return the requested facts or the applicable clarification"],
        "stop_conditions": ["Stop when facts are verified or additional information is needed"],
    }
