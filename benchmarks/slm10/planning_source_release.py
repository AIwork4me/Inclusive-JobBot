"""Audit release provenance for the unchanged Planning V2 source candidate."""

import argparse
from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from benchmarks.agentic_planning_v2.events import external_event, refused, scope_changed
from benchmarks.agentic_planning_v2.oracle import verify
from benchmarks.tool_calling_v2.oracle import equal
from evaluation.aeve.archive import digest
from evaluation.aeve.runtime import canonical

from .planning_controls import validate_control, validate_world
from .planning_roster import ATLAS, output_files, read_bundle
from .planning_world_allocation import SOURCE, SOURCE_SHA256


VERSION = "IJ-SLM-PLANNING-SOURCE-RELEASE-AUDIT/1.0"
BASELINE = ATLAS / "planning-v2-source-candidate"
BASELINE_SHA256 = "9898cee394c8f050f83b3a8b206dd54a9b2a42de6edef5d3c4a5487fd04d2ec1"
OUTPUT = ATLAS / "planning-v2-source-release-audit"
REGRESSION_WORLDS = {
    "L5": "revised_primary_unavailable", "L6": "later_check_denied", "L7": "missing_host_grant",
}


def ancestors(steps):
    closure = []
    for index, step in enumerate(steps):
        parents = set(step.get("after", range(index)))
        closure.append(parents.union(*(closure[parent] for parent in parents)))
    return closure


def audit_reference(step):
    if (step["tool"] == "audit_read" or "audit_read" in step.get("equivalent_tools", ())) and (
            step["result"].get("code", "ok") == "ok"):
        return step["args"].get("reference")
    return None


def interruptions(step):
    event = external_event({"external_event": step.get("event")})
    return scope_changed(event), refused({"code": step["result"].get("code", "ok")}, event)


def stage_sources(case, world):
    steps = world["steps"]
    if not any(step["tool"] == "stage" for step in steps):
        return []
    public = case["public"]
    closure = ancestors(steps)
    disruptors = [interruptions(step) for step in steps]
    audited = {}
    denial_seen = False
    sources = []
    for index, step in enumerate(steps):
        reference = audit_reference(step)
        if reference is not None and step["tool"] == "audit_read":
            audited[reference] = (index, step["result"].get("assessment"))
        if step["tool"] == "stage":
            args = step["args"]
            reference = args.get("reference")
            if not isinstance(public.get("action"), str) or not equal(args.get("action"), public["action"]):
                raise ValueError("stage action differs from the exact public requested action")
            if denial_seen:
                raise ValueError("stage follows a denial that revoked audit authority")
            audit_index, assessment = audited.get(reference, (None, None))
            if (reference != public.get("subject") or not isinstance(assessment, str) or not assessment
                    or not equal(args.get("assessment"), assessment)):
                raise ValueError("stage lacks the latest same-reference audit assessment")
            if audit_index not in closure[index] or steps[audit_index].get("equivalent_tools"):
                raise ValueError("stage lacks an exact causal audit dependency")
            for other, candidate in enumerate(steps):
                if other in (audit_index, index) or index in closure[other]:
                    continue
                relevant = audit_reference(candidate) == reference or any(disruptors[other])
                if relevant and other not in closure[audit_index]:
                    raise ValueError("stage audit is not uniquely latest under allowed step orders")
            sources.append((index, audit_index))
        changed, denied = disruptors[index]
        if changed or denied:
            audited.clear()
        denial_seen |= denied
    return sources


def validate_stage_provenance(case, world):
    """Check authoritative audit and action dependencies of stage calls in a checked world."""
    return len(stage_sources(case, world))


def rewrite_draft_field(world, stage_index, field, value):
    stages = world["steps"][stage_index:]
    stage = stages[0]
    draft_id = stage["result"].get("draft_id")
    stage["args"][field] = value
    for step in stages:
        for key in ("before", "after_state"):
            state = step[key]
            draft = state["drafts"].get(draft_id)
            if draft is not None:
                draft[field] = value
            for delivery in state["deliverables"].values():
                if delivery.get("draft_id") == draft_id:
                    delivery[field] = value


def verify_fresh_assessment(case, proof, world, stage_index, audit_index):
    changed = deepcopy(world)
    audit = changed["steps"][audit_index]
    observed = [step["result"].get("assessment") for step in changed["steps"]
                if audit_reference(step) == audit["args"]["reference"]]
    value = audit["result"]["assessment"] + " (source release probe)"
    while value in observed:
        value += " refreshed"
    audit["result"]["assessment"] = value
    rewrite_draft_field(changed, stage_index, "assessment", value)
    if verify(proof["witness"], case["contract"], [validate_world(case, changed)])["status"] != "PASS":
        raise ValueError("witness stage does not bind the latest audit observation")


def validate_release_control(case, proof):
    """Layer source provenance over the existing world and witness validator."""
    result = validate_control(case, proof)
    sources = [(world, stage, audit) for world in proof["worlds"] for stage, audit in stage_sources(case, world)]
    audit_nodes = {node["id"] for node in proof["witness"]["actions"] if node["tool"] == "audit_read"}
    for node in proof["witness"]["actions"]:
        if node["tool"] != "stage":
            continue
        action, assessment = (node["arguments"][field] for field in ("action", "assessment"))
        if action != {"from": "public", "field": "action"}:
            raise ValueError("witness stage action lacks a public requested action binding")
        if (not isinstance(assessment, dict) or assessment.get("from") not in audit_nodes
                or assessment.get("field") != "assessment"):
            raise ValueError("witness stage assessment lacks an audit observation binding")
    for world, stage, audit in sources:
        verify_fresh_assessment(case, proof, world, stage, audit)
    return result | {"stages": len(sources)}


def check_forgery(case, proof, field):
    altered = deepcopy(proof)
    world = next(item for item in altered["worlds"] if item["world_id"] == "reviewed_draft")
    stage = world["steps"][-1]
    forged = stage["args"][field] + " without authoritative evidence"
    rewrite_draft_field(world, len(world["steps"]) - 1, field, forged)
    next(node for node in altered["witness"]["actions"] if node["tool"] == "stage")["arguments"][field] = forged
    validate_control(case, altered)
    try:
        validate_release_control(case, altered)
    except ValueError as error:
        expected = "exact public requested action" if field == "action" else "latest same-reference audit assessment"
        if expected not in str(error):
            raise
        return
    raise ValueError(f"release validator accepted a coherent {field} forgery")


def denied_route(case, proof, world):
    denied = deepcopy(world)
    denied["steps"][-1]["result"] = {"code": "permission_denied"}
    denied.update(disposition="escalate", facts={"reason": "permission_denied"})
    return verify(proof["witness"], case["contract"], [validate_world(case, denied)])["status"]


def l5_repair_probe(case, proof):
    """Replay the original worlds and denied alternates under a supplemental contract."""
    fixed_case, fixed_proof = deepcopy(case), deepcopy(proof)
    alternate = fixed_case["contract"]["tools"]["alternate"]
    alternate["outputs"].append("code")
    alternate["description"] += " If access is denied, its code is permission_denied."
    for node in fixed_proof["witness"]["actions"]:
        if node["tool"] == "alternate":
            code = {"from": node["id"], "field": "code"}
            fixed_proof["witness"]["stops"].append({
                "when": {"op": "eq", "left": code, "right": "permission_denied"},
                "disposition": "escalate", "facts": {"reason": code},
            })
    original_worlds = validate_control(fixed_case, fixed_proof)["worlds"]
    denied = Counter(denied_route(fixed_case, fixed_proof, world) for world in fixed_proof["worlds"]
                     if world["world_id"] in ("alternate_source", "revised_primary_unavailable"))
    return original_worlds, denied


def cross_level_dependency(cases, proofs):
    references = Counter()
    for case in cases:
        if case["level"] != "L0":
            public = case["public"]
            references[public.get("reference", public.get("subject"))] += 1
    l1_values = {
        (case["public"]["reference"], world["world_id"]): world["facts"]["value"]
        for case in cases if case["level"] == "L1" for world in proofs[case["case_id"]]["worlds"]
    }
    aliases = {"primary": "primary", "changed_limit": "primary", "changed_index": "different_status",
               "alternate_source": "different_status"}
    counts = Counter()
    for case in cases:
        if case["level"] not in ("L2", "L3", "L4", "L5"):
            continue
        for world in proofs[case["case_id"]]["worlds"]:
            if world["world_id"] in aliases:
                predicted = l1_values[case["public"]["reference"], aliases[world["world_id"]]]
                counts["tested"] += 1
                counts["matches"] += equal(predicted, world["facts"]["value"])
    if len(references) != 100 or sum(references.values()) != 700 or counts != {"tested": 800, "matches": 800}:
        raise ValueError("cross-level dependence differs from the pinned 0.2 findings")
    return {"status": "BLOCKED", "distinct_reused_references": len(references), "cases_with_reused_references": 700,
            "value_predictions": counts["matches"], "predictions_tested": counts["tested"],
            "assumption": "hypothetical exposure to L1 fixture observations",
            "actual_model_leakage": "NOT_RUN"}


def build_release_report():
    _, cases, controls = read_bundle(SOURCE, SOURCE_SHA256)
    _, _, old_controls = read_bundle(BASELINE, BASELINE_SHA256)
    proofs = {row["case_id"]: row for row in controls}
    old_proofs = {row["case_id"]: row for row in old_controls}
    prior, revised, forgeries, alternate, primary = (Counter() for _ in range(5))
    repair_denials = Counter()
    repair_preserved = 0
    world_count, stateful_worlds, stages, alternate_missing_code = 0, 0, 0, 0
    for case in cases:
        case_id, level = case["case_id"], case["level"]
        proof = proofs[case_id]
        old = old_proofs[case_id]
        result = validate_release_control(case, proof)
        world_count += result["worlds"]
        stages += result["stages"]
        stateful_worlds += sum(bool(world["steps"] and "before" in world["steps"][0]) for world in proof["worlds"])
        added = set(world["world_id"] for world in proof["worlds"]) - set(world["world_id"] for world in old["worlds"])
        if added != ({REGRESSION_WORLDS[level]} if level in REGRESSION_WORLDS else set()):
            raise ValueError("added Planning worlds differ from the reviewed source candidate")
        for world in proof["worlds"]:
            if world["world_id"] in added:
                checked = validate_world(case, world)
                prior[verify(old["witness"], case["contract"], [checked])["status"]] += 1
                revised[verify(proof["witness"], case["contract"], [checked])["status"]] += 1
            if level == "L5":
                if world["world_id"] in ("alternate_source", "revised_primary_unavailable"):
                    alternate[denied_route(case, proof, world)] += 1
                if world["world_id"] == "scope_revision":
                    primary[denied_route(case, proof, world)] += 1
        if level == "L5" and "code" not in case["contract"]["tools"]["alternate"]["outputs"]:
            alternate_missing_code += 1
            preserved, denied = l5_repair_probe(case, proof)
            repair_preserved += preserved
            repair_denials.update(denied)
        if level == "L6":
            for field in ("action", "assessment"):
                check_forgery(case, proof, field)
                forgeries[field] += 1
    if (len(cases), world_count, stateful_worlds, stages) != (800, 2300, 900, 500):
        raise ValueError("Planning source release audit lost original cases or stateful routes")
    if prior != {"FAIL": 300} or revised != {"PASS": 300} or forgeries != {"action": 100, "assessment": 100}:
        raise ValueError("Planning source release audit does not reproduce its regression controls")
    if alternate != {"FAIL": 200} or primary != {"PASS": 100} or alternate_missing_code != 100:
        raise ValueError("L5 denial behavior differs from the reviewed source candidate")
    if repair_preserved != 500 or repair_denials != {"PASS": 200}:
        raise ValueError("supplemental L5 repair failed to preserve the original worlds and resolve denial")

    return {
        "version": VERSION, "source_manifest_sha256": SOURCE_SHA256, "baseline_manifest_sha256": BASELINE_SHA256,
        "validator_sha256": digest(Path(__file__)),
        "evidence_class": "software source release audit",
        "source_replay": {"status": "PASS", "cases": len(cases), "worlds": world_count,
                          "stateful_worlds": stateful_worlds, "stages": stages},
        "added_world_regressions": {"status": "PASS", "total": 300, "prior_witness": dict(prior),
                                    "revised_witness": dict(revised)},
        "provenance_controls": {
            field: {"status": "PASS", "tested": count, "structural_validator_accepted": count,
                    "release_validator_rejected": count} for field, count in forgeries.items()
        },
        "fresh_assessment_replays": {"status": "PASS", "stages": stages},
        "unfrozen_l5_repair": {"status": "PASS", "original_worlds": {"PASS": repair_preserved},
                              "alternate_denials": dict(repair_denials), "formal_credit": "NOT_RUN"},
        "findings": {
            "l5_alternate_denial": {"status": "FAIL", "structural_validator_accepted": 200,
                                    "observed": dict(alternate), "revised_primary_comparator": dict(primary),
                                    "public_alternate_omits_code_cases": alternate_missing_code},
            "cross_level_expected_value_dependence": cross_level_dependency(cases, proofs),
        },
        "release_disposition": "BLOCKED", "independent_human_review": "NOT_RUN", "formal_freeze": "NOT_RUN",
        "formal_dispatch": "BLOCKED", "physical_execution": "NOT_RUN", "formal_trials_recorded": 0,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    report = build_release_report()
    raw = canonical(report) + b"\n"
    output_files(args.output, {"manifest.json": raw}, not args.write)
    print(json.dumps({"manifest_sha256": sha256(raw).hexdigest(), "source_replay": report["source_replay"],
                      "release_disposition": report["release_disposition"]}))


if __name__ == "__main__":
    main()
