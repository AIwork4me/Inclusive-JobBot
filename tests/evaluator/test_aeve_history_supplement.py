from pathlib import Path
from evaluation.aeve.history import sid
from evaluation.aeve.history_supplement import fixture_fact,origin_link,software_packet


def metadata(case, evidence_class="software_witness"):
    return {"trial_id":"software","case_id":case,"class":evidence_class,"sources":[["source","locator","sha"]]}


def test_mutation_status_is_not_an_unseen_model_response():
    raw = {"case_id":"AP1-L0-001","negative_trace_results":{"wrong_goal":"FAIL"}}
    assert software_packet(metadata(raw["case_id"],"mutation"),raw) is None


def test_authored_witness_provides_a_software_subject():
    raw = {"case_id":"AP1-L0-001","witness":{"disposition":"understood","facts":{}}}
    p = software_packet(metadata(raw["case_id"]),raw)
    assert p["source_family"] == "no-model"
    assert set(p["dimensions"]) >= {"D01","D02"}
    assert "disposition" in p["events"][-1]["content"]


def test_replay_link_requires_unique_original_identity():
    row = {"original_run_id":"run","id":"case"}
    assert origin_link(Path("evidence/ij/rescoring/table.jsonl"), row, {},
                       ({},{("run","case"):["one","two"]},{})) is None
    assert origin_link(Path("evidence/ij/rescoring/table.jsonl"), row, {},
                       ({},{("run","case"):["one"]},{})) == "one"


def test_archived_run_and_attempt_both_bind_the_planning_replay():
    row = {"run_id":"r1","trial":{"case_id":"c","trial_id":"try2"}}
    good = sid("r1","c","try2")
    assert origin_link(Path("archive_replay.json"),row,{},({good:{}},{},{})) == good
    assert origin_link(Path("archive_replay.json"),row,{},({sid("r2","c","try2"):{}},{},{})) is None


def test_missing_parser_fixture_stages_cannot_pass():
    assert fixture_fact({"id":"text-00","complete":{},"stream":{}}) == {"D21":"BLOCKED"}
    assert fixture_fact({"id":"text-00","complete":{}}) == {}
