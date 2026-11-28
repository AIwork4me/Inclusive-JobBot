"""Verify the separation of Planning V2 authoring and candidate replay."""

from hashlib import sha256

from benchmarks.slm10.planning_source_candidate import candidate, verify_candidate
from benchmarks.slm10.planning_roster import read_bundle, output_files


def test_candidate_binds_distinct_authors_and_replays_every_task(tmp_path):
    bundle, certificate = candidate()
    source = tmp_path / "source"
    output_files(source, bundle, False)
    expected = sha256(bundle["manifest.json"]).hexdigest()
    manifest, public, controls = read_bundle(source, expected)
    assert len(public) == len(controls) == 800
    assert len({item["sha256"] for item in manifest["authoring_sources"].values()}) == 2
    assert all("witness" not in case and "worlds" not in case for case in public)
    checked = verify_candidate(source, expected)
    assert checked == certificate
    assert checked["formal_freeze"] == "NOT_RUN"
    assert checked["release_review"] == "NOT_RUN"
    assert checked["formal_trials_recorded"] == 0
    assert checked["software_roster_slots"] == 20800
