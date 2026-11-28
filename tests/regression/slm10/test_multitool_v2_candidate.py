from collections import Counter
from copy import deepcopy
import json

import pytest


def test_candidate_roster_preserves_the_matched_plan_and_exact_complexity():
    from benchmarks.slm10.multitool_v2_candidate import candidate, trial_roster

    rows, repeats = candidate()
    assert len(rows) == len({public["case_id"] for public, _, _ in rows}) == 600
    assert set(Counter(public["category"] for public, _, _ in rows).values()) == {75}
    assert Counter(public["language"] for public, _, _ in rows) == {"en": 200, "zh": 200, "mixed": 200}
    assert {public["required_actions"] for public, _, _ in rows} == set(range(2, 21))
    assert {oracle["critical_path"] for public, _, oracle in rows if public["category"] == "serial"} == set(range(2, 21))
    assert len(repeats) == len(set(repeats)) == 100
    roster = trial_roster("A", rows, repeats)
    assert len(roster) == len({row["trial_id"] for row in roster}) == 1500
    assert Counter(row["track"] for row in roster) == {"direct_first": 600, "sdk_first": 600, "sdk_repeat": 300}
    by_track = {track: {row["case_id"]: row["input_sha256"] for row in roster if row["track"] == track}
                for track in ("direct_first", "sdk_first")}
    assert by_track["direct_first"] == by_track["sdk_first"]
    assert set(repeats) == {row["case_id"] for row in roster if row["track"] == "sdk_repeat"}
    assert {sum(row["case_id"] == case and row["track"] == "sdk_repeat" for row in roster) for case in repeats} == {3}


def test_reference_solver_replays_every_candidate_and_leaves_physical_gate_blocked():
    from benchmarks.slm10.multitool_v2_candidate import qualification

    report = qualification()
    assert report["software_qualification"] == "PASS"
    assert report["formal_dispatch"] == "BLOCKED"
    assert report["physical_execution"] == "NOT_RUN"
    assert report["independent_witnesses"]["PASS"] == 600
    assert report["positive_by_exact_action_count"]["20"] > 0
    assert report["controls"]["forged_moderation"]["observed"] == "FAIL"
    assert report["controls"]["wrong_typed_enum"]["observed"] == "FAIL"
    assert report["controls"]["legal_repeat"]["observed"] == "PASS"
    assert report["coverage"]["persisted_authorized_draft"] == "NOT_RUN"


def test_source_only_witness_ignores_oracle_and_detects_variants_from_world():
    from benchmarks.slm10.multitool_v2_candidate import candidate, evaluate
    from benchmarks.slm10.multitool_v2_witness import witness

    public, world, oracle = next(row for row in candidate()[0]
                                 if row[0]["category"] == "serial" and row[0]["required_actions"] == 2)
    evidence = witness(public, world)
    assert evaluate(public, world, oracle, evidence)["status"] == "PASS"
    revised = deepcopy(world)
    terminal = evidence["calls"][-1]
    revised["records"][terminal["tool"]][terminal["observation_locator"]][0]["label"] = "changed"
    changed = witness(public, revised)
    assert changed["answer"] == {"label": "changed"}
    assert evaluate(public, revised, oracle, changed)["status"] == "FAIL"


def test_software_consent_boundary_denies_premature_and_withheld_excerpt():
    from benchmarks.slm10.multitool_v2_candidate import candidate
    from benchmarks.slm10.multitool_v2_witness import Scenario, witness

    public, world, oracle = next(row for row in candidate()[0] if row[0]["category"] == "authorization"
                                 and row[0]["required_actions"] == 2 and row[2]["answer"]["decision"] == "withheld")
    evidence = witness(public, world)
    source, tool_call = evidence["calls"]
    guide_args = json.loads(tool_call["arguments_raw"])
    service = Scenario(public, world)
    with pytest.raises(ValueError, match="prior consent"):
        service.read("read_public_excerpt", guide_args, 0, "premature")
    service.read("read_consent", json.loads(source["arguments_raw"]), 0, "permission")
    with pytest.raises(ValueError, match="prior consent"):
        service.read("read_redaction_guide", guide_args, 0, "concurrent")
    with pytest.raises(ValueError, match="prior consent"):
        service.read("read_public_excerpt", guide_args, 1, "withheld")
    with pytest.raises(ValueError, match="out of contract"):
        service.read("commit_release", guide_args, 1, "write")
    assert service.read("read_redaction_guide", guide_args, 1, "correct")[0] == {"note": oracle["answer"]["note"]}
