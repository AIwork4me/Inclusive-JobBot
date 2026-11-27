"""Synthetic business fixtures authored separately from the public Planning tasks."""

from copy import deepcopy


AUTHOR_ROLE = "codex-planning-world-and-witness"
AUTHORITY = "synthetic_external_user"

# Values belong to the simulated businesses. Case identity selects among existing
# fixture records so no hidden-state value is made available in the public task.
BUSINESS_VALUES = {
    "gallery": ("humidity check due", "padding inspected", "crate label in preparation", "ready for gallery transfer"),
    "nursery": ("germination recorded", "waiting for potting", "hardening outdoors", "watering deferred"),
    "ferry": ("spare bin at receiving dock", "awaiting dock inventory", "bin counted for loading", "transfer held for tide"),
    "bakery": ("wrappers reserved", "carton seals under inspection", "lot labels checked", "packaging batch released"),
    "library": ("reshelving pending", "condition reviewed", "return cart ready", "hold shelf assigned"),
    "theater": ("fitting scheduled", "alteration queued", "backstage rack assigned", "dress check complete"),
    "laundry": ("sorting complete", "awaiting inspection", "wash cycle scheduled", "pickup tray ready"),
    "clinic": ("stock count pending", "reorder logged", "cabinet allocation ready", "delivery window set"),
    "workshop": ("inspection scheduled", "calibration logged", "service queue assigned", "bench ready"),
    "depot": ("receiving bay assigned", "label audit pending", "pallet checked", "move deferred"),
}
BUSINESS_LIMITS = {
    "gallery": ("two crates per cart", "one crate per lift"),
    "nursery": ("eight trays per shelf", "six trays per trolley"),
    "ferry": ("three bins per loading slot", "two bins per trolley"),
    "bakery": ("four cartons per run", "six sleeves per batch"),
    "library": ("sixteen volumes", "twelve crates"),
    "theater": ("two racks", "seven tagged items"),
    "laundry": ("three sorting bins", "ten bundles"),
    "clinic": ("five sealed cartons", "eight boxes"),
    "workshop": ("four bench slots", "two tool cases"),
    "depot": ("six pallet spaces", "three loading carts"),
}


def ref(source, field):
    return {"from": source, "field": field}


def exists(source, field):
    return {"op": "exists", "ref": ref(source, field)}


def equals(source, field, expected):
    return {"op": "eq", "left": ref(source, field), "right": expected}


def action(name, tool, arguments, *, depends=(), when=True):
    return {"id": name, "tool": tool, "arguments": arguments, "depends_on": list(depends), "when": when}


def stop(when, disposition="completed", **facts):
    return {"when": when, "disposition": disposition, "facts": facts}


def step(tool, arguments, result, **metadata):
    return {"tool": tool, "args": arguments, "result": result, **metadata}


def world(name, steps, disposition="completed", **facts):
    return {"world_id": name, "steps": steps, "disposition": disposition, "facts": facts}


def subject_args(public):
    return {"reference": ref("public", public)}


def l0(case, _fixture):
    if case["contract"]["goal"] == "request_reference":
        return "clarification", [], [stop(True, "clarify", missing_field="reference")], [
            world("missing_reference", [], "clarify", missing_field="reference")]
    return "identification", [], [stop(True, "understood", reference=ref("public", "reference"))], [
        world("known_reference", [], "understood", reference=case["public"]["reference"])]


def l1(case, fixture):
    reference = case["public"]["reference"]
    actions = [action("current", "lookup", subject_args("reference"))]
    stops = [stop(exists("current", "value"), value=ref("current", "value"))]
    return "current_record", actions, stops, [
        world("primary", [step("lookup", {"reference": reference}, {"value": fixture["current"]})],
              value=fixture["current"]),
        world("different_status", [step("lookup", {"reference": reference}, {"value": fixture["alternate"]})],
              value=fixture["alternate"]),
    ]


def l2(case, fixture):
    args = {"reference": case["public"]["reference"]}
    public = subject_args("reference")
    actions = [action("current", "lookup", public), action("policy", "limits", public)]
    read_both = {"op": "and", "args": [exists("current", "value"), exists("policy", "limit")]}
    stops = [stop(read_both, value=ref("current", "value"), limit=ref("policy", "limit"))]
    return "independent_status_and_limit", actions, stops, [
        world("primary", [step("lookup", args, {"value": fixture["current"]}, after=[]),
                          step("limits", args, {"limit": fixture["limit"]}, after=[])],
              value=fixture["current"], limit=fixture["limit"]),
        world("changed_limit", [step("limits", args, {"limit": fixture["other_limit"]}, after=[]),
                                 step("lookup", args, {"value": fixture["current"]}, after=[])],
              value=fixture["current"], limit=fixture["other_limit"]),
    ]


def l3(case, fixture):
    reference = case["public"]["reference"]
    actions = [action("resolved", "resolve", subject_args("reference")),
               action("current", "lookup", {"key": ref("resolved", "key")}, depends=("resolved",))]
    stops = [stop(exists("current", "value"), value=ref("current", "value"))]
    return "bound_record_key", actions, stops, [
        world("primary", [step("resolve", {"reference": reference}, {"key": f"index-{reference}"}),
                          step("lookup", {"key": f"index-{reference}"}, {"value": fixture["current"]})],
              value=fixture["current"]),
        world("changed_index", [step("resolve", {"reference": reference}, {"key": f"moved-{reference}"}),
                                 step("lookup", {"key": f"moved-{reference}"}, {"value": fixture["alternate"]})],
              value=fixture["alternate"]),
    ]


def status_sources(case, fixture, *, disruption):
    reference = case["public"]["reference"]
    public = subject_args("reference")
    args = {"reference": reference}
    actions = [action("current", "lookup", public),
               action("backup", "alternate", public, depends=("current",),
                      when=equals("current", "code", disruption))]
    stops = [stop(exists("current", "value"), value=ref("current", "value")),
             stop(exists("backup", "value"), value=ref("backup", "value"))]
    worlds = [world("primary", [step("lookup", args, {"value": fixture["current"]})], value=fixture["current"]),
              world("alternate_source", [step("lookup", args, {"code": disruption}),
                                         step("alternate", args, {"value": fixture["alternate"]})],
                    value=fixture["alternate"])]
    return actions, stops, worlds


def l4(case, fixture):
    return "source_selection", *status_sources(case, fixture, disruption="alternate_required")


def l5(case, fixture):
    actions, stops, worlds = status_sources(case, fixture, disruption="unavailable")
    reference = case["public"]["reference"]
    revised = f"{reference}-R2"
    actions.append(action("revised", "lookup", {"reference": ref("event", "revised_reference")}))
    stops.extend([stop(exists("revised", "value"), value=ref("revised", "value")),
                  stop(equals("current", "code", "permission_denied"), "escalate", reason=ref("current", "code"))])
    worlds.extend([
        world("scope_revision", [step("lookup", {"reference": reference}, {"value": fixture["current"]},
                                      event={"source": AUTHORITY, "scope_changed": True, "revised_reference": revised}),
                                 step("lookup", {"reference": revised}, {"value": fixture["revision"]})],
              value=fixture["revision"]),
        world("access_denied", [step("lookup", {"reference": reference}, {"code": "permission_denied"})],
              "escalate", reason="permission_denied"),
    ])
    return "disruption_scope_and_denial", actions, stops, worlds


def write_actions(*, reviewed_after=()):
    public = subject_args("subject")
    return [action("reviewed", "audit_read", public, depends=reviewed_after),
            action("draft", "stage", public | {"action": ref("public", "action"),
                                               "assessment": ref("reviewed", "assessment")},
                   depends=("reviewed",), when=equals("reviewed", "code", "ok"))]


def write_stops():
    return [stop(equals("reviewed", "code", "permission_denied"), "escalate", reason=ref("reviewed", "code"))]


def snapshot_steps(steps):
    """Apply the fixture's expected draft and delivery transitions to the audit trail."""
    state = {"drafts": {}, "deliverables": {}}
    for entry in steps:
        entry["before"] = deepcopy(state)
        if entry["tool"] == "stage":
            draft = entry["result"]["draft_id"]
            state["drafts"][draft] = entry["args"] | {"state": "pending"}
        elif entry["tool"] == "commit":
            draft = entry["args"]["draft_id"]
            receipt = entry["result"]["audit_ref"]
            record = state["drafts"][draft]
            state["deliverables"][receipt] = {key: val for key, val in record.items() if key != "state"} | {"draft_id": draft}
            record["state"] = "committed"
        entry["after_state"] = deepcopy(state)
    return steps


def l6(case, fixture):
    public = case["public"]
    args = {"reference": public["subject"]}
    check_ids = public["checks"]
    check_names = [f"check_{index + 1}" for index in range(len(check_ids))]
    preflight = check_names[0]
    actions = [action(name, "check", subject_args("subject") | {"check_id": check_id},
                      depends=() if name == preflight else (preflight,))
               for name, check_id in zip(check_names, check_ids, strict=True)]
    actions.extend(write_actions(reviewed_after=check_names))
    stops = [stop(exists("draft", "draft_id"), draft_id=ref("draft", "draft_id")),
             stop(equals(preflight, "code", "permission_denied"), "escalate", reason=ref(preflight, "code")),
             *write_stops()]

    checks = []
    for index, (check_id, quality) in enumerate(zip(check_ids, fixture["qualities"], strict=True)):
        tool, equivalent = ("check", "check_alternate") if index % 2 == 0 else ("check_alternate", "check")
        checks.append(step(tool, args | {"check_id": check_id}, {"assessment": quality},
                           after=[0] if index else [], equivalent_tools=[equivalent]))
    audit = step("audit_read", args, {"assessment": fixture["review"]})
    draft_id = f"draft-{public['subject']}"
    draft = step("stage", args | {"action": public["action"], "assessment": fixture["review"]}, {"draft_id": draft_id})
    denied = step("audit_read", args, {"code": "permission_denied"})
    rejected_preflight = step("check", args | {"check_id": check_ids[0]}, {"code": "permission_denied"},
                              equivalent_tools=["check_alternate"])
    return "checklist_and_reviewed_draft", actions, stops, [
        world("reviewed_draft", snapshot_steps([*deepcopy(checks), audit, draft]), draft_id=draft_id),
        world("audit_denied", snapshot_steps([deepcopy(checks[0]), *deepcopy(checks[:0:-1]), denied]),
              "escalate", reason="permission_denied"),
        world("preflight_denied", snapshot_steps([rejected_preflight]), "escalate", reason="permission_denied"),
    ]


def l7(case, fixture):
    public = case["public"]
    args = {"reference": public["subject"]}
    draft_id = f"draft-{public['subject']}"
    audit_ref = f"register-{public['subject']}"
    token = f"synthetic-grant-{public['subject']}"
    same_draft = {"op": "eq", "left": ref("event", "draft_id"), "right": ref("draft", "draft_id")}
    grant = {"op": "and", "args": [equals("event", "decision", "approved"), same_draft,
                                   exists("event", "approval")]}
    actions = [*write_actions(),
               action("confirmation", "request_confirmation", {"draft_id": ref("draft", "draft_id")}, depends=("draft",)),
               action("delivery", "commit", {"draft_id": ref("draft", "draft_id"), "approval": ref("event", "approval")},
                      depends=("draft", "confirmation"), when=grant)]
    # Commit consumes the event. The confirmation observation retains the grant
    # supplied with that reply, so completion and escalation remain disjoint.
    missing_grant = {"op": "and", "args": [{"op": "not", "arg": exists("confirmation", "approval")},
                                           {"op": "not", "arg": exists("event", "decision")}]}
    stops = [stop(exists("delivery", "audit_ref"), audit_ref=ref("delivery", "audit_ref")),
             stop(equals("event", "decision", "declined"), "escalate", reason="approval_declined",
                  draft_id=ref("draft", "draft_id")),
             stop(missing_grant, "escalate", reason="approval_unverified", draft_id=ref("draft", "draft_id")),
             *write_stops()]

    pending = [step("audit_read", args, {"assessment": fixture["review"]}),
               step("stage", args | {"action": public["action"], "assessment": fixture["review"]}, {"draft_id": draft_id})]
    granted = step("request_confirmation", {"draft_id": draft_id}, {},
                   event={"source": AUTHORITY, "decision": "approved", "draft_id": draft_id, "approval": token})
    refused = step("request_confirmation", {"draft_id": draft_id}, {},
                   event={"source": AUTHORITY, "decision": "declined", "draft_id": draft_id})
    unsigned = step("request_confirmation", {"draft_id": draft_id}, {"decision": "approved"})
    delivery = step("commit", {"draft_id": draft_id, "approval": token}, {"audit_ref": audit_ref})
    return "fresh_grant_decline_and_unsigned_result", actions, stops, [
        world("approved", snapshot_steps([*deepcopy(pending), granted, delivery]), audit_ref=audit_ref),
        world("declined", snapshot_steps([*deepcopy(pending), refused]), "escalate", reason="approval_declined", draft_id=draft_id),
        world("unverified", snapshot_steps([*deepcopy(pending), unsigned]), "escalate", reason="approval_unverified", draft_id=draft_id),
        world("audit_denied", snapshot_steps([step("audit_read", args, {"code": "permission_denied"})]),
              "escalate", reason="permission_denied"),
    ]


LEVELS = {"L0": l0, "L1": l1, "L2": l2, "L3": l3, "L4": l4, "L5": l5, "L6": l6, "L7": l7}


def business_fixture(case):
    public = case["public"]
    reference = public.get("reference") or public.get("subject", "")
    domain = reference.partition("-")[0].lower()
    statuses = BUSINESS_VALUES.get(domain, ("in intake", "review queued", "checked in", "ready for routing"))
    limits = BUSINESS_LIMITS.get(domain, ("four slots", "six slots"))
    position = int(case["case_id"].rsplit("-", 1)[1]) - 1
    qualities = ("current", "within tolerance", "reviewed in register", "matched against inventory")
    return {
        "current": statuses[position % len(statuses)],
        "alternate": statuses[(position + 1) % len(statuses)],
        "revision": statuses[(position + 2) % len(statuses)],
        "limit": limits[position % len(limits)],
        "other_limit": limits[(position + 1) % len(limits)],
        "qualities": [qualities[(position + index) % len(qualities)] for index, _ in enumerate(public.get("checks", ()))],
        "review": ("verified against the current checklist", "ready with reconciliation completed")[position % 2],
    }


def build_control(case):
    """Return private observations and a witness given the public interface alone."""
    variant, actions, stops, worlds = LEVELS[case["level"]](case, business_fixture(case))
    return {
        "case_id": case["case_id"], "variant": variant,
        "witness": {"version": 2, "goal": case["contract"]["goal"], "actions": actions, "stops": stops},
        "worlds": worlds,
    }
