"""Check source-level business and audit provenance without changing frozen worlds."""

from copy import deepcopy

import pytest


CASE = {"case_id": "planning-source-provenance-control", "public": {"subject": "ITEM-1", "action": "return_to_storage"}}


def audit(reference, assessment):
    return {"tool": "audit_read", "args": {"reference": reference}, "result": {"assessment": assessment}}


def stage(assessment):
    return {"tool": "stage", "args": {"reference": "ITEM-1", "action": "return_to_storage", "assessment": assessment},
            "result": {"draft_id": "draft-1"}}


def checked(steps):
    from benchmarks.slm10.planning_source_release import validate_stage_provenance

    return validate_stage_provenance(CASE, {"world_id": "test-control", "steps": steps})


def test_stage_uses_latest_successful_audit_for_same_reference():
    steps = [audit("ITEM-1", "first"), audit("ITEM-1", "latest"), audit("ITEM-OTHER", "unrelated"), stage("latest")]
    assert checked(steps) == 1

    stale = deepcopy(steps)
    stale[-1]["args"]["assessment"] = "first"
    with pytest.raises(ValueError, match="latest same-reference audit assessment"):
        checked(stale)
    foreign = deepcopy(steps)
    foreign[-1]["args"]["assessment"] = "unrelated"
    with pytest.raises(ValueError, match="latest same-reference audit assessment"):
        checked(foreign)


def test_audit_authority_must_be_causally_before_stage_in_every_valid_order():
    disconnected = stage("clear") | {"after": []}
    with pytest.raises(ValueError, match="causal audit dependency"):
        checked([audit("ITEM-1", "clear"), disconnected])

    # The later-listed audit could legally execute before the draft, making the
    # proposed assessment non-unique across the fixture's allowed schedules.
    competing = audit("ITEM-1", "changed") | {"after": [0]}
    with pytest.raises(ValueError, match="uniquely latest"):
        checked([audit("ITEM-1", "clear"), stage("clear"), competing])


def test_scope_change_invalidates_audit_until_new_same_reference_success():
    change = {"tool": "check", "args": {"reference": "ITEM-1"}, "result": {},
              "event": {"source": "synthetic_external_user", "scope_changed": True}}
    with pytest.raises(ValueError, match="latest same-reference audit assessment"):
        checked([audit("ITEM-1", "old scope"), change, stage("old scope")])
    assert checked([audit("ITEM-1", "old scope"), change, audit("ITEM-1", "fresh"), stage("fresh")]) == 1


def test_denial_revokes_audit_authority_for_later_stage():
    refused = {"tool": "check", "args": {"reference": "ITEM-1"}, "result": {"code": "permission_denied"}}
    with pytest.raises(ValueError, match="denial"):
        checked([audit("ITEM-1", "clear"), refused, stage("clear")])


def test_witness_assessment_tracks_latest_observation_when_audits_initially_agree():
    from benchmarks.slm10.planning_controls import validate_control
    from benchmarks.slm10.planning_public_authoring import public_cases
    from benchmarks.slm10.planning_source_controls import build_control
    from benchmarks.slm10.planning_source_release import validate_release_control

    case = next(row for row in public_cases() if row["level"] == "L6")
    proof = build_control(case)
    successful = next(world for world in proof["worlds"] if world["world_id"] == "reviewed_draft")
    successful["steps"].insert(-1, deepcopy(successful["steps"][-2]))
    case["contract"]["action_budget"] += 1
    case["limits"]["tool_calls"] += 1
    nodes = proof["witness"]["actions"]
    nodes.insert(-1, deepcopy(nodes[-2]) | {"id": "second_audit", "depends_on": ["reviewed"]})
    nodes[-1]["depends_on"].append("second_audit")
    validate_control(case, proof)
    with pytest.raises(ValueError, match="latest audit observation"):
        validate_release_control(case, proof)
    nodes[-1]["arguments"]["assessment"]["from"] = "second_audit"
    assert validate_release_control(case, proof)["stages"] == 1


def test_pinned_release_keeps_repaired_controls_and_rejects_coherent_provenance_forgeries():
    from benchmarks.slm10.planning_source_release import build_release_report

    result = build_release_report()
    assert result["source_replay"] == {"status": "PASS", "cases": 800, "worlds": 2300,
                                      "stateful_worlds": 900, "stages": 500}
    assert result["added_world_regressions"]["total"] == 300
    assert result["added_world_regressions"]["prior_witness"] == {"FAIL": 300}
    assert result["added_world_regressions"]["revised_witness"] == {"PASS": 300}
    for field in ("action", "assessment"):
        assert result["provenance_controls"][field] == {"status": "PASS", "tested": 100,
                                                        "structural_validator_accepted": 100,
                                                        "release_validator_rejected": 100}
    assert result["fresh_assessment_replays"] == {"status": "PASS", "stages": 500}
    assert result["unfrozen_l5_repair"] == {"status": "PASS", "original_worlds": {"PASS": 500},
                                          "alternate_denials": {"PASS": 200}, "formal_credit": "NOT_RUN"}
    assert result["findings"]["l5_alternate_denial"]["observed"] == {"FAIL": 200}
    assert result["findings"]["cross_level_expected_value_dependence"]["value_predictions"] == 800
    assert result["findings"]["cross_level_expected_value_dependence"]["actual_model_leakage"] == "NOT_RUN"
    assert result["release_disposition"] == "BLOCKED"
    assert result["physical_execution"] == "NOT_RUN"
