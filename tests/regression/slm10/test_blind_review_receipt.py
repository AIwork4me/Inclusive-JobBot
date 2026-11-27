import pytest

from benchmarks.slm10.blind_review_receipt import coverage


def test_review_coverage_requires_every_pinned_case_and_scenario_once():
    cases = [{"case_id": "a", "scenarios": [{"scenario_id": "1"}, {"scenario_id": "2"}]},
             {"case_id": "b"}]
    approved = [{"case_id": "a", "scenario_id": "1", "status": "PASS"},
                {"case_id": "a", "scenario_id": "2", "status": "BLOCKED"}]
    assert coverage(cases, approved) == {"PASS": 1, "FAIL": 0, "BLOCKED": 1, "NOT_RUN": 1}
    with pytest.raises(ValueError, match="duplicate"):
        coverage(cases, approved + [approved[0]])
    with pytest.raises(ValueError, match="outside"):
        coverage(cases, [{"case_id": "a", "scenario_id": "3", "status": "PASS"}])



def test_planning_path_packet_hides_scenario_replies_until_supplement():
    from benchmarks.slm10.blind_review_packets import planning_fixture_supplement, planning_rows
    from benchmarks.slm10.planning_public_authoring import public_cases
    from benchmarks.slm10.planning_source_controls import build_control

    case = next(row for row in public_cases() if row["level"] == "L7")
    control = build_control(case)
    path, = planning_rows([case], [control], path_phase=True)
    supplement, = planning_fixture_supplement([control])
    assert "goal" not in path["public_tool_contract"]
    assert all(set(row) == {"scenario_id"} for row in path["scenarios"])
    assert {row["scenario_id"] for row in path["scenarios"]} == {
        row["scenario_id"] for row in supplement["scenarios"]}
    assert any({"confirmation_service_response": {"decision": "approved"}} in row["service_observations"]
               and not row["external_events"] for row in supplement["scenarios"])
    assert all("approval" not in event for row in supplement["scenarios"] for event in row["external_events"])
