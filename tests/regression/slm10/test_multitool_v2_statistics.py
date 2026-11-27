import json
from hashlib import sha256

import pytest


def test_no_seals_reports_registered_denominators_and_zero_evidence():
    from benchmarks.slm10.multitool_v2_statistics import statistics

    report = statistics()
    assert report["physical_execution"] == "NOT_RUN"
    assert report["planned_trials"] == 7500
    assert report["physical_trials"] == report["formal_trial_attribution"] == 0
    assert set(report["models"]) == {"A", "B", "D", "F", "G"}
    model = report["models"]["B"]
    first = model["tracks"]["direct_first"]
    assert first["bands"]["16-20"]["outcomes"]["NOT_RUN"] == 120
    assert first["categories"]["serial"]["outcomes"]["NOT_RUN"] == 75
    assert first["risks"]["synthetic-read-only"]["outcomes"]["NOT_RUN"] == 600
    assert first["overall"]["outcomes"]["wilson_95"] is None
    assert first["overall"]["dimensions"]["authored_actions"]["n"] == 600
    assert first["overall"]["dimensions"]["actual_tool_calls"]["n"] == 0
    assert model["repeat"]["overall"]["all_three"]["NOT_RUN"] == 100
    assert report["maximum_verified_depth"]["status"] == "BLOCKED"
    assert report["maximum_verified_depth"]["value"] is None


def test_repeat_state_and_counts_use_three_exact_seed_outcomes():
    from benchmarks.slm10.multitool_v2_statistics import repeat_summary

    specs = [{"trial_id": f"{case}-{seed}", "case_id": case, "band": "2-3", "category": "serial",
              "risk": "synthetic-read-only"} for case in ("ok", "failed", "missing", "blocked") for seed in range(3)]
    states = {"ok-0": "PASS", "ok-1": "PASS", "ok-2": "PASS", "failed-0": "FAIL",
              "missing-0": "PASS", "blocked-0": "BLOCKED"}
    observations = {key: {"status": state, "physical_observed": state in {"PASS", "FAIL"}}
                    for key, state in states.items()}
    result = repeat_summary(specs, observations)["overall"]
    assert result["all_three"]["PASS"] == result["all_three"]["FAIL"] == 1
    assert result["all_three"]["BLOCKED"] == result["all_three"]["NOT_RUN"] == 1
    assert result["fully_observed_cases"] == result["fully_scored_cases"] == 1
    assert result["seeds_physically_observed"] == 5
    assert result["all_three"]["rate"] == .5


def test_capture_counts_explicit_instruments_without_inferring_user_turns():
    from benchmarks.slm10.multitool_v2_statistics import capture_dimensions

    trace = {"calls": [{"turn": 0}, {"turn": 0}, {"turn": 1}],
             "wire": [{"provider_request_id": "provider-0"}, {"provider_request_id": "provider-1"}, {}],
             "events": [{"event_id": "moderation"}]}
    assert capture_dimensions(trace) == {"actual_tool_calls": 3, "model_requests": 2, "user_turns": None}
    assert capture_dimensions(trace | {"user_turns": [{"user_turn_id": "u0"}]})["user_turns"] == 1
    with pytest.raises(ValueError, match="duplicate"):
        capture_dimensions(trace | {"wire": [trace["wire"][0]] * 2})


def test_rejects_unregistered_or_mock_rows_before_attribution(tmp_path):
    from benchmarks.slm10.multitool_v2_statistics import FOLDER, statistics
    from evaluation.aeve.archive import digest

    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"identity": {"suite": "MULTITOOL-V2/candidate-0.3",
                                            "candidate_manifest_sha256": digest(FOLDER / "manifest.json"),
                                            "scope": "software-fixture", "run_id": tmp_path.name}}), encoding="utf-8")
    with pytest.raises(ValueError, match="scope"):
        statistics([path])


def test_wire_links_actions_to_the_measurement_with_matching_bytes():
    from benchmarks.slm10.multitool_v2_statistics import verify_capture_provenance

    args = '{"ref":"REF-SYNTHETIC"}'
    response = json.dumps({"id": "provider-completion", "object": "chat.completion", "created": 1,
                           "model": "fixture", "choices": [{"index": 0, "finish_reason": "tool_calls", "message": {
                               "role": "assistant", "tool_calls": [{"id": "provider-call", "type": "function",
                                   "function": {"name": "read_label", "arguments": args}}]}}]})
    call = {"call_id": "provider-call", "completion_id": "provider-completion", "tool": "read_label",
            "turn": 0, "arguments_raw": args}
    event = {"trial_id": "fixture-trial", "provider_request_id": "provider-request", "http_status": 200,
             "content_type": "application/json", "provider_request": '{"stream":false}', "response": response,
             "response_sha256": sha256(response.encode()).hexdigest(), "completion_id": "provider-completion",
             "native_evidence": {"status": "PASS"}, "source_generation": {"completion_id": "provider-completion"}}
    trace = {"trial_id": "fixture-trial", "calls": [call], "wire": [event]}
    verify_capture_provenance(trace, "FAIL")
    with pytest.raises(ValueError, match="terminal"):
        verify_capture_provenance(trace, "PASS")
    with pytest.raises(ValueError, match="provider proposal"):
        verify_capture_provenance(trace | {"calls": [call | {"arguments_raw": '{}'}]}, "FAIL")
