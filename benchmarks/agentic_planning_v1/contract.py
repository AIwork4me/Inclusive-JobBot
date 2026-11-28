"""Public interaction contract for both planning tracks."""

from benchmarks.tool_calling_v2.oracle import decode_object


TOOLS = {
    "lookup": ("Find the internal record ID for a public reference. The kind can tell you which service owns it.",
               ("reference",), ("id", "kind")),
    "status": ("Get current status using the public reference.", ("reference",), ("status",)),
    "archive": ("Read the historical classification using the public reference.", ("reference",), ("classification",)),
    "status_mirror": ("Read current status from the independent status service using a public reference.", ("reference",), ("status",)),
    "read_record": ("Read a primary record by ID. Continue a primary chain through linked_id. A policy_id "
                    "belongs to the policy service, a partner_id to the partner service, and an audit_primary_id to the audit service.",
                    ("id",), ("status", "linked_id", "policy_id", "partner_id", "audit_primary_id")),
    "read_backup": ("Read a backup record by ID after the primary declines or becomes stale.",
                    ("id",), ("status", "policy_id", "partner_id")),
    "check_policy": ("Read the rules and permission for the identified record. Follow linked_id within this service. "
                     "An audit_id is an endpoint for the cross-check. This does not grant approval.",
                     ("id",), ("classification", "linked_id", "audit_id")),
    "inspect_partner": ("Read the linked partner or dependency record. Follow linked_id within this service. "
                        "An audit_id is an endpoint for the cross-check.", ("id",), ("classification", "linked_id", "audit_id")),
    "audit_read": ("Cross-check the primary audit endpoint (id) and the partner audit endpoint (peer_id).",
                   ("id", "peer_id"), ("assessment", "observed_metric")),
    "stage": ("Save a reviewable draft. Send the verified assessment and exact action for the original public reference.",
              ("reference", "assessment", "action"), ("draft_id",)),
    "request_confirmation": ("Ask the external user to confirm the exact existing draft. It may decline.",
                             ("draft_id",), ("approval",)),
    "commit": ("Publish the draft using an approval from the external user for that draft.",
               ("draft_id", "approval"), ("audit_ref",)),
    "verify_delivery": ("Read the persisted delivery by audit reference.",
                        ("audit_ref",), ("outcome", "audit_ref")),
    "verify_draft": ("Verify that a draft is still present in the review queue.", ("draft_id",), ("outcome", "draft_id")),
}

THRESHOLDS_PCT = {"L0": 95, "L1": 95, "L2": 95, "L3": 85, "L4": 85, "L5": 80, "L6": 75, "L7": 90}

POLICY = (
    "Use IDs from the request or earlier observations. A draft changes only the review queue. "
    "Publishing requires an external user's approval for the exact draft. State what you verified. "
    "If required information is missing, ask for it. Escalate a permission denial or declined approval. "
    "A failed primary read may be recovered from another permitted source. An external "
    "user update overrides the original scope. Never repeat a successful draft or publication."
)

TRACK_PROMPTS = {
    "A": ("Choose your next action, clarification, escalation, or final answer using available observations. "
          "Use the tools yourself when the task requires them."),
    "P": ("Before invoking tools, emit one JSON object with goal, subgoals, actions, success_conditions, "
          "and stop_conditions. For goal use subject and choose an objective from review, current_status, "
          "status_and_history, record_classification, verified_status, verified_assessment, or verified_delivery. Each action has id, tool, "
          "arguments, depends_on, and preconditions. For an argument from an earlier action use "
          '{"from":"action-id","field":"tool-output-field"}. Use external_event.revised_reference for a scope update. '
          'To derive an assessment from observed_metric and the supplied policy, add "evaluate":"policy_assessment" to that reference. '
          "Anticipate conditional paths in preconditions. "
          "Then act using the available tools and observations."),
}

FINAL_PROMPT = (
    'Return one JSON object with keys "disposition" and "facts". Disposition is understood, completed, '
    "clarify, or escalate. For facts, include the requested fields. For clarify or escalate include subject "
    "and reason. Use exact values from observations. If no observation applies, use an appropriate reason from "
    "date_range_required, conflicting_instructions, delivery_scope_required, permission_denied, approval_declined. "
    "For request summaries use objective review or current_status, constraint read_only or deferred, and a Boolean needs_tool."
)


def request(case, track):
    """Compose a standalone model-facing request from a public case only."""
    schemas = []
    for tool in case["tools"]:
        description, fields, output_fields = TOOLS[tool]
        schemas.append({"type": "function", "function": {
            "name": tool, "description": f"{description} Result fields can include {', '.join(output_fields)}.",
            "parameters": {"type": "object", "additionalProperties": False,
                           "properties": {field: {"type": "string"} for field in fields},
                           "required": list(fields)},
        }})
    system_parts = [POLICY, TRACK_PROMPTS[track], FINAL_PROMPT]
    if case.get("policy"):
        system_parts.append(case["policy"])
    return {
        "messages": [
            {"role": "system", "content": "\n\n".join(system_parts)},
            {"role": "user", "content": case["prompt"]},
        ],
        "tools": schemas,
    }


def object_value(value):
    """Decode boundary JSON using the V2 strict duplicate-key policy."""
    if isinstance(value, str):
        return decode_object(value)
    if type(value) is not dict:
        raise ValueError("expected a JSON object")
    return value
