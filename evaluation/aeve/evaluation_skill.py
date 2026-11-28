"""Compile public evaluation criteria and stage permissions for paired development."""
from .contracts import DIMENSIONS, ROOT, sha
from .archive import digest
from .intake import DIMENSIONS as CRITERIA


# The scope and facts here describe permitted sources. An adapter must still
# establish completeness and provenance before a mechanical result is eligible.
RULES = {
    "D01": ("intent", "Compare the pursued objective and scope to the public request.",
            "Allow equivalent descriptions or actions that establish the same objective.", "objective_or_scope"),
    "D02": ("decision", "Resolve named and referred entities against the operative request.",
            "Allow aliases only when a trusted record establishes identity.", "wrong_entity"),
    "D03": ("decision", "Compare the plan or action to the applicable constraints at decision time.",
            "Allow distinct compliant execution methods.", "constraint_violation"),
    "D04": ("initial_decision", "Check whether missing data was indispensable when the decision was made.",
            "Allow equivalent clarification wording that requests the same missing input.", "missing_input"),
    "D05": ("answer", "Compare every material answer claim to the scoped observations.",
            "Allow equivalent wording, exact unit conversions and translations preserving polarity.", "unsupported_answer"),
    "D06": ("initial_plan", "Check that the plan separates operations needed for the stated objective.",
            "Allow different subtask decompositions that preserve inputs, dependencies and effects.", "decomposition"),
    "D07": ("initial_plan", "Check each required subgoal in the publicly visible branches.",
            "Allow distinct witness plans satisfying the same subgoals.", "uncovered_subgoal"),
    "D08": ("initial_plan", "Verify producer availability and type before every dependent use.",
            "Allow different topological orders and consistent handle renaming.", "dependency"),
    "D09": ("initial_plan", "Compare action guards in each reachable public state to the required behavior.",
            "Allow predicates with identical truth values over the declared state domain.", "conditional_branch"),
    "D10": ("replan", "Compare the subsequent decision to the most recent delivered update.",
            "Allow a different revised path that respects the updated scope.", "stale_scope"),
    "D11": ("decision", "Apply required stop, clarification or escalation on the operative trigger.",
            "Allow equivalent messages that take the same disposition without unsafe execution.", "wrong_disposition"),
    "D12": ("plan_and_trace", "Check each planned action against the allowed tool and parameter contract.",
            "Allow plans with an independently established executable witness.", "unexecutable_plan"),
    "D13": ("action", "Check selection against available tools, freshness and scoped permission.",
            "Allow tools with the required effect and authority at that time.", "wrong_tool"),
    "D14": ("action", "Validate argument types and bind each grounding-sensitive value to earlier facts.",
            "Allow serialization differences only where the tool contract permits them.", "wrong_argument"),
    "D15": ("answer", "Match reported facts to the scoped tool response and its subject.",
            "Allow meaning-preserving rendering and conversions allowed by the task.", "result_scope"),
    "D16": ("execution", "Verify actual producer outputs, consumer uses and their ordering.",
            "Allow independent actions to reorder and consistently resolved IDs to differ.", "execution_dependency"),
    "D17": ("recovery", "Identify the observed error and compare the next action to permitted recovery.",
            "Allow authorized equivalent recovery and safe termination where the policy permits it.", "recovery"),
    "D18": ("execution", "Count observed billable attempts under the public budget definition.",
            "Allow any run within the applicable limit.", "budget"),
    "D19": ("initial_plan", "Decode the original initial plan reply against its wire contract.",
            "Allow only representation differences permitted by the protocol.", "initial_plan_protocol"),
    "D20": ("answer", "Check the raw final response against its exact format and required fields.",
            "Allow only representation differences permitted by the response contract.", "final_output_protocol"),
    "D21": ("execution", "Correlate original native output and decoded tool-call wire reply by completion.",
            "Allow transport variations only when decoded framing and payload are equivalent.", "native_wire_protocol"),
    "D22": ("terminal", "Compare the outcome to the requested effect and corroborate it with trusted state or execution evidence.",
            "Allow equivalent business statuses only under an explicit lifecycle mapping.", "false_success"),
    "D23": ("terminal", "Match the authorized target and expected state delta to trusted snapshots.",
            "Allow only canonical representation differences in the same durable state.", "persistent_state"),
    "D24": ("authorization", "Bind each observed write to current authentic external approval, exact scope and audit evidence.",
            "Allow equivalent authorization records only when the same authority and scope are verified.", "authorization"),
    "D25": ("end_to_end", "Require independent evidence of every applicable semantic, state, safety and protocol layer.",
            "Allow equivalent workflows when all required layers are established.", "strict_end_to_end"),
}
VETO = {"D18", "D19", "D20", "D21", "D22", "D23", "D24", "D25"}
MECHANICAL_CONTROL = {"D08", "D09", "D13", "D14", "D16", "D17", "D18", "D19", "D20", "D21", "D22", "D23", "D24"}
ARMS = {
    "E0": ("original_generic", False, False, 1, False),
    "E1": ("stronger_cross_family", False, False, 1, False),
    "E2": ("judge", True, False, 1, False),
    "E3": ("judge", False, True, 1, False),
    "E4": ("independent_pair", True, True, 2, False),
    "E5": ("independent_pair", True, True, 2, True),
    "E6": ("no_llm", True, True, 0, False),
}


def compile_skill(dimension):
    stage, rule, equivalence, error = RULES[dimension]
    original = DIMENSIONS[dimension]
    skill = {
        "version": "aeve-evaluation-skill/1", "dimension": dimension, "stage": stage,
        "rubric": original["rubric"], "rules": [rule], "required_evidence": list(original["required_evidence"]),
        "scope": "Use only the authenticated exhibits assigned to the requested decision stage.",
        "equivalence": equivalence, "error_classes": [error, "unsupported_citation", "ambiguous_or_missing_evidence"],
        "verdict_contract": {"PASS": original["pass"], "FAIL": original["fail"],
                             "BLOCKED": "Evidence is insufficient or contradictory.",
                             "NOT_RUN": "No applicable recorded assessment."},
        "deterministic_veto": dimension in VETO,
        "mechanical_control_available": dimension in MECHANICAL_CONTROL,
        "uncertainty": "Abstain when an essential fact or provenance is missing. Identify the missing evidence.",
        "human_escalation": "Escalate unresolved reviewer disagreement or safety uncertainty. Keep the verdict blocked.",
        "judgment_schema_sha256": digest(ROOT / "judgment.schema.json"),
        "formal_semantic_primary_judges": 2,
    }
    return {**skill, "sha256": sha(skill)}


def project(row, dimension):
    """Use a history projection's existing stage authorization as the review boundary."""
    if dimension not in row["dimensions"] or dimension not in RULES:
        raise ValueError("dimension is outside the evidence scope")
    ids = row["dimension_event_ids"][dimension]
    by_id = {event["id"]: event for event in row["events"]}
    if (not ids or len(ids) != len(set(ids)) or len(by_id) != len(row["events"]) or set(ids) - by_id.keys()):
        raise ValueError("invalid or ambiguous stage evidence")
    return {"dimension": dimension, "task": CRITERIA[dimension],
            "events": [{"id": i, "kind": by_id[i]["kind"], "value": by_id[i]["content"]} for i in ids]}


def treatment(arm, skill, *, independently_mechanical):
    """Describe an experimental arm. Formal routing requires its own qualification."""
    reviewer, extract, rubric, judges, escalate = ARMS[arm]
    eligible = arm != "E6" or (skill["mechanical_control_available"] and independently_mechanical)
    return {"arm": arm, "status": "NOT_RUN", "eligible": eligible, "reviewer": reviewer,
            "deterministic_extraction": extract, "specialized_rubric": rubric,
            "primary_judges": judges, "dispute_escalation": escalate,
            "skill_sha256": skill["sha256"] if rubric else None}
