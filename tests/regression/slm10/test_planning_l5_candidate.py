from benchmarks.slm10.planning_l5_candidate import repair
from benchmarks.slm10.planning_roster import read_bundle
from benchmarks.slm10.planning_world_allocation import SOURCE, SOURCE_SHA256


def test_l5_candidate_preserves_old_worlds_and_terminates_both_new_denial_branches():
    _, cases, proofs = read_bundle(SOURCE, SOURCE_SHA256)
    case = next(case for case in cases if case["level"] == "L5")
    original = next(proof for proof in proofs if proof["case_id"] == case["case_id"])
    _, candidate, replay = repair(case, original)
    assert candidate["worlds"][:5] == original["worlds"]
    assert len(original["worlds"]) == 5
    assert replay["worlds"] == 7
    expected = {"alternate_source_denied", "revised_primary_unavailable_denied"}
    new_worlds = {world["world_id"]: world for world in candidate["worlds"][5:]}
    assert set(new_worlds) == expected
    for world in new_worlds.values():
        assert world["steps"][-1]["result"] == {"code": "permission_denied"}
        assert world["facts"] == {"reason": "permission_denied"}
        assert world["disposition"] == "escalate"
