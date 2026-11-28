from collections import defaultdict
from copy import deepcopy
import json

import pytest


@pytest.mark.parametrize("category,key", [("conditional", "gate"), ("recovery", "primary"), ("authorization", "consent")])
def test_branch_is_not_in_public_reference_and_follows_observations(category, key):
    from benchmarks.slm10.multitool_v2_revised import branch_taken, build_case, candidate, evaluate, witness
    from benchmarks.slm10.multitool_v2_witness import parse_message

    strata = defaultdict(set)
    for public, world, oracle in candidate()[0]:
        if public["category"] == category:
            identity = parse_message(public["message"])[key]
            strata[int(identity[-1], 16) % 2].add(branch_taken(category, oracle))
    assert dict(strata) == {0: {True, False}, 1: {True, False}}
    public, world_a, oracle_a = build_case(category, 5, "en", 0, branch=True)
    same_public, world_b, oracle_b = build_case(category, 5, "en", 0, branch=False)
    assert public == same_public
    sample_a, sample_b = witness(public, world_a), witness(public, world_b)
    assert [call["tool"] for call in sample_a["calls"]] != [call["tool"] for call in sample_b["calls"]]
    assert evaluate(public, world_a, oracle_a, sample_a)["status"] == "PASS"
    assert evaluate(public, world_b, oracle_b, sample_b)["status"] == "PASS"
    assert evaluate(public, world_b, oracle_b, sample_a)["status"] == "FAIL"


def test_typed_transfer_accepts_reversed_reads_with_exact_preview_order():
    from benchmarks.slm10.multitool_v2_revised import build_case, evaluate, witness

    row = build_case("typed_transfer", 3, "en", 0)
    assert "any order" in row[0]["message"]
    capture = witness(*row[:2])
    first, second, preview = capture["calls"]
    capture["calls"] = [second | {"turn": 0, "completion_id": "alt-0"},
                        first | {"turn": 1, "completion_id": "alt-1"},
                        preview | {"turn": 2, "completion_id": "alt-2"}]
    assert evaluate(*row, capture)["status"] == "PASS"
    arguments = json.loads(capture["calls"][-1]["arguments_raw"])
    arguments["preview"]["entries"].reverse()
    capture["calls"][-1]["arguments_raw"] = json.dumps(arguments)
    assert evaluate(*row, capture)["status"] == "FAIL"


def test_venue_service_denies_guessed_and_stale_scope_at_read_boundary():
    from benchmarks.slm10.multitool_v2_revised import build_case, Scenario, witness
    from benchmarks.slm10.multitool_v2_witness import parse_message

    public, world, _ = build_case("scope_update", 3, "en", 0)
    capture = witness(public, world)
    scenario = Scenario(public, world)
    future = parse_message(world["event"]["message"])
    current = {"venue": future["venue"], "ref": future["refs"][0]}
    with pytest.raises(ValueError, match="active scope"):
        scenario.read("read_venue_access", current, 0, "guessed")
    old, _ = scenario.read("read_booking", json.loads(capture["calls"][0]["arguments_raw"]), 0, "booking")
    stale = {"venue": old["venue"], "ref": old["refs"][0]}
    assert stale != current
    with pytest.raises(ValueError, match="active scope"):
        scenario.read("read_venue_access", current, 1, "undelivered")
    scenario.take_event(1)
    with pytest.raises(ValueError, match="active scope"):
        scenario.read("read_venue_access", stale, 1, "stale")
    with pytest.raises(ValueError, match="active scope"):
        scenario.read("read_venue_access", current, 0, "same-turn")
    assert scenario.read("read_venue_access", current, 1, "valid")[0] == capture["calls"][1]["observation"]


def test_revised_artifacts_are_replayable_and_formal_freeze_remains_pending():
    from benchmarks.slm10.multitool_v2_revised import FOLDER, files

    raw, report = files()
    for name, data in raw.items():
        assert (FOLDER / name).read_bytes() == data
    manifest = json.loads(raw["manifest.json"])
    assert set(manifest["cohort_strata"]["case_bands"].values()) == {120}
    assert manifest["formal_roster_freeze"] == "NOT_RUN"
    assert manifest["attributed_physical_trials"] == 0
    assert report["independent_witnesses"]["PASS"] == 600
    assert report["coverage"]["independent_business_and_content_review"] == "NOT_RUN"
    assert report["coverage"]["independently_authored_expected_outcomes"] == "NOT_RUN"
    assert {control["status"] for control in report["review_regressions"].values()} == {"PASS"}
