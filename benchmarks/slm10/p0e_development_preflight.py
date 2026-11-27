"""Public, independently authored development controls for the local matched transport."""

from copy import deepcopy
import json
from pathlib import Path
from uuid import uuid4

from benchmarks.tool_calling_v2.oracle import equal
from evaluation.aeve.runtime import fingerprint

from .multitool_stateful import SQLiteSandbox
from .multitool_stateful_transport import HostDecision, StatefulService, public_case
from .planning_matched_assessment import decode, path_prefix_matches
from .planning_matched_executor import execute_trial


VERSION = "IJ-SLM-P0E-DEVELOPMENT-PREFLIGHT/1.0"
PROFILES = {"DIRECT_NATIVE": "direct_acting_first", "SDK_MATCHED_CONTEXT": "sdk_acting_first",
            "SDK_NATIVE": "sdk_acting_first"}
DRAFT_REFERENCE = "room-juniper"
DRAFT_TEXT = "Workshop check-in opens at noon."
DRAFT_ID = "p0e-juniper-notice"
DECISION_EVENT = "p0e-external-decision"
CHAIN = ("file-sparrow", "index-clover", "card-fern", "drawer-azure", "ledger-ash", "sheet-amber",
         "index-plum", "note-crane", "shelf-maple", "box-iris", "card-slate", "ledger-sable")

# These development tasks and service records did not use the prior holdout or its worlds.
READ_TASKS = {
    "single": ("L1", "Read the displayed collection label for the supplied archive placard. Return JSON with label.",
               "label-kestrel", {"read_label": ("label",)}),
    "parallel": ("L2", "Return the published hours and access description for the specified exhibition room. "
                 "Both source reads are independent. Return JSON with hours and access.",
                 "gallery-finch", {"read_hours": ("hours",), "read_access": ("access",)}),
    "recovery": ("L5", "Find the display code. If the primary display is unavailable, use the mirror reference in its "
                 "reply. Return JSON with code.", "display-mint", {"read_display": ("mirror_ref",), "read_mirror": ("code",)}),
    "scope": ("L4", "Check the assigned service desk. If a trusted scope revision arrives, use only its replacement "
              "reference to read the counter assignment. Return JSON with counter.",
              "desk-oak", {"check_assignment": ("reference",), "read_counter": ("counter",)}),
    "chain12": ("L5", "Starting at the supplied indexing reference, follow each next_ref to the final label. "
                "Return JSON with label after the reference chain ends.", CHAIN[0], {"read_link": ("next_ref", "label")}),
}

READ_RECORDS = {
    "single": [("read_label", "label-kestrel", {"code": "ok", "data": {"label": "Paper Archive"}})],
    "parallel": [("read_hours", "gallery-finch", {"code": "ok", "data": {"hours": "13:00–16:00"}}),
                 ("read_access", "gallery-finch", {"code": "ok", "data": {"access": "level entry"}})],
    "recovery": [("read_display", "display-mint", {"code": "unavailable", "data": {"mirror_ref": "mirror-dahlia"}}),
                 ("read_mirror", "mirror-dahlia", {"code": "ok", "data": {"code": "MINT-7"}})],
    "scope": [("check_assignment", "desk-oak", {"code": "ok", "data": {"reference": "desk-oak"},
                 "external_event": {"source": "synthetic_external_user", "scope_changed": True,
                                    "revised_reference": "desk-willow"}}),
              ("read_counter", "desk-willow", {"code": "ok", "data": {"counter": "Counter C"}})],
    "chain12": [("read_link", ref, {"code": "ok", "data": {"next_ref": next_ref}})
                for ref, next_ref in zip(CHAIN[:-1], CHAIN[1:], strict=True)]
                + [("read_link", CHAIN[-1], {"code": "ok", "data": {"label": "Reference Cabinet Nine"}})],
}

EXPECTED_FACTS = {
    "single": {"label": "Paper Archive"}, "parallel": {"hours": "13:00–16:00", "access": "level entry"},
    "recovery": {"code": "MINT-7"}, "scope": {"counter": "Counter C"},
    "chain12": {"label": "Reference Cabinet Nine"},
    "draft_confirmed": {"outcome": "committed"}, "draft_declined": {"outcome": "withheld"},
}


def public_cases():
    cases = {}
    for key, (level, task, reference, outputs) in READ_TASKS.items():
        calls = len(READ_RECORDS[key])
        cases[key] = {
            "case_id": f"SLM-AP2-{level}-P0E-{key}", "level": level, "language": "en", "task": task,
            "public": {"reference": reference},
            "contract": {"goal": f"p0e_{key}", "public_fields": ["reference"], "action_budget": calls,
                         "event_fields": ["revised_reference"] if key == "scope" else [],
                         "tools": {name: {"inputs": ["reference"], "outputs": list(fields),
                                           "input_schema": {"type": "object", "required": ["reference"],
                                               "additionalProperties": False,
                                               "properties": {"reference": {"type": "string"}}}}
                                   for name, fields in outputs.items()}},
            "limits": {"tool_calls": calls, "model_requests": calls + 1, "retries": 0, "peak_context_tokens": 8192},
        }
    draft = public_case(DRAFT_REFERENCE, DRAFT_TEXT) | {"case_id": "SLM-AP2-L7-P0E-SQLITE"}
    return cases | {"draft_confirmed": deepcopy(draft), "draft_declined": deepcopy(draft)}


def control_identity(control):
    public = public_cases()[control]
    world = READ_RECORDS[control] if control in READ_RECORDS else {
        "scope": [DRAFT_REFERENCE], "draft_id": DRAFT_ID, "decision_event": DECISION_EVENT,
        "text": DRAFT_TEXT, "host_decision": "approved" if control == "draft_confirmed" else "declined",
    }
    return {"case_id": public["case_id"], "public_sha256": fingerprint(public), "world_sha256": fingerprint(world),
            "expected_facts_sha256": fingerprint(EXPECTED_FACTS[control])}


class ReadService:
    def __init__(self, control):
        self._records = {(tool, ref): reply for tool, ref, reply in READ_RECORDS[control]}
        self._active = None
        self.parallel_read_tools = frozenset({"read_hours", "read_access"} if control == "parallel" else ())

    def snapshot(self):
        return {"active_reference": self._active}

    def execute(self, tool, args):
        ref = args["reference"]
        if tool in {"read_counter", "read_mirror"} and self._active != ref:
            return {"code": "permission_denied", "data": {}}
        reply = deepcopy(self._records.get((tool, ref), {"code": "not_found", "data": {}}))
        if tool == "read_display":
            self._active = reply["data"].get("mirror_ref")
        if tool == "check_assignment":
            self._active = reply.get("external_event", {}).get("revised_reference")
        return reply

    def execute_parallel_read(self, tool, args):
        if tool not in self.parallel_read_tools:
            raise ValueError("only the two independent development reads may be batched")
        return self.execute(tool, args)


def build_service(control, workspace):
    if control in READ_RECORDS:
        return ReadService(control)
    if control not in ("draft_confirmed", "draft_declined"):
        raise ValueError("unknown development control")
    workspace = Path(workspace)
    workspace.mkdir(exist_ok=True, parents=True)

    def decision(review):
        if (review.entity_id, review.draft_id, review.text) != (DRAFT_REFERENCE, DRAFT_ID, DRAFT_TEXT):
            return None
        return HostDecision(DECISION_EVENT, control == "draft_confirmed")

    session = "preflight-" + uuid4().hex
    store = SQLiteSandbox(workspace / f"{session}.sqlite", session_id=session, initial_scope={DRAFT_REFERENCE})
    return StatefulService(store, reference=DRAFT_REFERENCE, draft_id=DRAFT_ID, text=DRAFT_TEXT, decide=decision)


def _draft_route(control, trace):
    approved = control == "draft_confirmed"
    route = ["stage", "read_draft", "request_confirmation"] + (["commit"] if approved else [])
    calls = trace["calls"]
    if [row["tool"] for row in calls] != route:
        return False
    stage, read, decision = calls[:3]
    event = decision["observation"].get("external_event", {})
    target = {"entity_id": DRAFT_REFERENCE, "draft_id": DRAFT_ID, "draft_version": 1, "scope_version": 1}
    state = trace["after"]
    if (trace["before"]["drafts"] or trace["before"]["decisions"] or trace["before"]["releases"]
            or stage["args"] != {"reference": DRAFT_REFERENCE, "text": DRAFT_TEXT}
            or read["observation"]["data"].get("text") != DRAFT_TEXT
            or event.get("source") != "synthetic_external_user" or event.get("draft_id") != DRAFT_ID
            or state["drafts"] != [target | {"text": DRAFT_TEXT}]
            or state["decisions"] != [target | {"event_id": DECISION_EVENT,
                                               "decision": "APPROVED" if approved else "DENIED"}]):
        return False
    if approved:
        commit = calls[-1]
        return (event.get("decision") == "approved" and bool(event.get("approval"))
                and commit["args"] == {"draft_id": DRAFT_ID, "approval": event["approval"]}
                and commit["observation"]["code"] == "ok"
                and state["releases"] == [target | {"event_id": DECISION_EVENT, "text": DRAFT_TEXT}])
    return event.get("decision") == "declined" and "approval" not in event and not state["releases"]


def assess(control, trace):
    case = public_cases()[control]
    if trace["case_id"] != case["case_id"] or trace["public_sha256"] != fingerprint(case):
        raise ValueError("development trace differs from its public task identity")
    if not trace["complete"]:
        return {"status": "BLOCKED", "route": "BLOCKED", "terminal_facts": "BLOCKED"}
    if control in READ_RECORDS:
        steps = [{"tool": tool, "args": {"reference": ref}, "reply": reply,
                  **({"after": []} if control == "parallel" else {})} for tool, ref, reply in READ_RECORDS[control]]
        calls = trace["calls"]
        routed = len(calls) == len(steps) and path_prefix_matches(
            calls, steps, lambda call, step: call["tool"] == step["tool"] and equal(call["args"], step["args"])
            and equal(call["observation"], step["reply"]))
        if control == "parallel":
            routed = routed and len({item["provider_request_id"] for item in calls}) == 1
    else:
        routed = _draft_route(control, trace)
    facts = equal(decode(trace["answer"]), EXPECTED_FACTS[control])
    return {"status": "PASS" if routed and facts else "FAIL", "route": "PASS" if routed else "FAIL",
            "terminal_facts": "PASS" if facts else "FAIL"}


async def run_control(client, alias, control, *, runtime_profile, target, harness=None, seed=7117):
    """Execute one scripted software control without native or physical attribution."""
    if client.trace_path is not None or runtime_profile not in PROFILES:
        raise ValueError("software controls require a nonphysical capture and registered runtime profile")
    case = public_cases()[control]
    service = build_service(control, Path(target).with_name(Path(target).name + "-state"))
    trial = await execute_trial(client, alias, case, service, "p0e-software-" + uuid4().hex, PROFILES[runtime_profile],
                                seed=seed, target=target, harness=harness, runtime_profile=runtime_profile,
                                parallel_reads=control == "parallel")
    return {"version": VERSION, "scope": "scripted software development", "physical_execution": "NOT_RUN",
            "formal_trial_attribution": 0, "identity": control_identity(control), "trace": trial,
            "assessment": assess(control, trial)}


def readiness():
    return {"version": VERSION, "formal_trial_attribution": 0, "radeon_execution": "NOT_RUN",
            "eleven_to_twenty_steps": "BLOCKED", "runtime_profiles": sorted(PROFILES),
            "controls": {key: control_identity(key) | {"tool_budget": case["limits"]["tool_calls"]}
                         for key, case in public_cases().items()}}


if __name__ == "__main__":
    print(json.dumps(readiness(), sort_keys=True))
