"""Resolve advanced Planning requests from public messages and tool feedback."""

import re

from .planning_intent_witness import REFERENCE


def response(subject, disposition="completed", **facts):
    return {"disposition": disposition, "facts": {"subject": subject, **facts}}


def state_agrees(before, after, records, final):
    mutated = any(row["tool"] in {"stage", "commit"} and row["observation"]["code"] == "ok" for row in records)
    if not mutated:
        return before == after
    if final["disposition"] == "escalate":
        return len(after["drafts"]) == 1 and not after["deliverables"]
    facts = final["facts"]
    if "draft_id" in facts:
        return set(after["drafts"]) == {facts["draft_id"]} and not after["deliverables"]
    return set(after["deliverables"]) == {facts.get("audit_ref")} and len(after["drafts"]) == 1


def solve(wire, execute):
    prompt = wire["messages"][-1]["content"]
    public_policy = wire["messages"][0]["content"]
    ref = REFERENCE.search(prompt)[0]
    allowed = {tool["function"]["name"] for tool in wire["tools"]}

    def call(tool, **args):
        if tool not in allowed:
            raise ValueError(f"the public contract does not expose {tool}")
        return execute(tool, args)

    def denial(observed):
        code = observed["code"]
        if code in {"permission_denied", "approval_declined"}:
            return response(ref, "escalate", reason=code)
        return None

    def incoming(response):
        if response["code"] != "ok":
            raise ValueError(f"unexpected tool response: {response['code']}")
        return response["data"]

    def primary(reference):
        found = call("lookup", reference=reference)
        if found["code"] != "ok":
            return found
        key = found["data"]["id"]
        row = call("read_record", id=key)
        if row.get("data", {}).get("permitted_source") == "replica" or "backup_id" in row.get("data", {}):
            return call("read_backup", id=row["data"].get("backup_id", key))
        return row

    if "assessment" not in prompt and "status" not in prompt:
        return response(ref, "clarify", reason="delivery_scope_required")
    if "audit_read" not in allowed:
        row = primary(ref)
        stop = denial(row)
        if stop:
            return stop
        current_ref = row.get("external_event", {}).get("revised_reference", ref)
        if current_ref != ref:
            row = primary(current_ref)
        if row.get("data", {}).get("permitted_source") == "independent_status_service":
            row = call("status_mirror", reference=current_ref)
        stop = denial(row)
        if stop:
            return stop
        status = incoming(row)["status"]
        classification = incoming(call("archive", reference=ref))["classification"]
        return response(ref, status=status, classification=classification)

    row = primary(ref)
    current_ref = row.get("external_event", {}).get("revised_reference", ref)
    if current_ref != ref:
        row = primary(current_ref)
    stop = denial(row)
    if stop:
        return stop
    main = incoming(row)
    while "linked_id" in main:
        main = incoming(call("read_record", id=main["linked_id"]))
    if "policy_id" in main:
        row = call("check_policy", id=main["policy_id"])
        stop = denial(row)
        if stop:
            return stop
        lead = incoming(row)
        while "linked_id" in lead:
            lead = incoming(call("check_policy", id=lead["linked_id"]))
        primary_endpoint = lead["audit_id"]
    else:
        primary_endpoint = main["audit_primary_id"]
    peer = incoming(call("inspect_partner", id=main["partner_id"]))
    while "linked_id" in peer:
        peer = incoming(call("inspect_partner", id=peer["linked_id"]))
    observed = incoming(call("audit_read", id=primary_endpoint, peer_id=peer["audit_id"]))
    if "observed_metric" in observed:
        threshold = re.search(r"(at most|at least|最多|至少)\s*(\d+)", public_policy)
        if threshold is None:
            raise ValueError("the observation has no visible decision rule")
        bound = int(threshold[2])
        maximum = threshold[1] in {"at most", "最多"}
        measured = observed["observed_metric"]
        meets = measured <= bound if maximum else measured >= bound
        assessment = "meets_policy" if meets else "outside_policy"
    else:
        assessment = observed["assessment"]
    if "draft_id" not in prompt and "audit_ref" not in prompt:
        return response(ref, assessment=assessment)
    action = re.search(r"(?:filed as |reviewable |按 |将 )([a-z]+(?:_[a-z]+)+)", prompt)
    if action is None:
        raise ValueError("the public request has no explicit action")
    stage = call("stage", reference=ref, assessment=assessment, action=action[1])
    stop = denial(stage)
    if stop:
        return stop
    draft_id = incoming(stage)["draft_id"]
    if "draft_id" in prompt:
        draft = incoming(call("verify_draft", draft_id=draft_id))
        return response(ref, assessment=assessment, outcome=draft["outcome"], draft_id=draft_id)

    confirmation = call("request_confirmation", draft_id=draft_id)
    stop = denial(confirmation)
    if stop:
        return stop
    authorization = incoming(confirmation)["approval"]
    delivery = incoming(call("commit", draft_id=draft_id, approval=authorization))
    audit_ref = delivery["audit_ref"]
    verified = incoming(call("verify_delivery", audit_ref=audit_ref))
    return response(ref, assessment=assessment, outcome=verified["outcome"], audit_ref=audit_ref)
