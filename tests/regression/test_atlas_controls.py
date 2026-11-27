from scripts.tools.atlas_controls import multitool_witness
from benchmarks.multitool_v1.dataset import load_freeze


def test_draft_fixture_wire_replay_matches_state_despite_generated_audit_ids(tmp_path):
    case = load_freeze().active["MT-08-002"]
    result = multitool_witness(case, tmp_path)
    assert result["status"] == "PASS", result["findings"]
    assert len(result["after_sqlite"]["review_drafts"]) == 1
    assert len(result["after_sqlite"]["audit_events"]) == 1
