"""Software fixtures only. These tests do not render or authorize a historical review."""
import copy
import gzip
import json

import pytest

from evaluation.aeve import human_review as hr
from jsonschema import Draft202012Validator
from evaluation.aeve.runtime import canonical, write_json


def fixture_gate():
    result = {"status":"BLOCKED", "primary_recorded":2,"invalid":[],"disputed":True,"third_recorded":True,
              "votes":{"a":"PASS","b":"FAIL","c":"BLOCKED"},
              "citation_support":{"a":"supported","b":"supported","c":"abstention"}}
    row = {"class":"physical_trial","repeat":False,"source_family":"fixture-subject","trial_id":"trial-0",
           "case_id":"case-0","current":{},"reviews":{"formal":{"expected":["D05"],"judgments":{"D05":result}}}}
    families = {k:"fixture-"+k for k in "abc"}
    q = {"protocol_sha256":"fixture-freeze","admission": {k: {"status":"PASS"} for k in families}}
    summary = {"admitted_judges":list(families),"qualification_protocol":q["protocol_sha256"],
               "scope":{"formal":{"eligible_trials":1,"eligible_dimensions":1,"packet_inventory_present":True}},
               "trial_counts":{"trials":1}}
    summary["scope"]["supplement"] = {"eligible_trials": 0,"eligible_dimensions": 0,"packet_inventory_present": True}
    summary["nonphysical_inventory"] = {"status":"PASS","registered":0,"independent_inputs":0,"linked_source_records":0}
    return row, families, q, summary


@pytest.mark.parametrize("defect", ["unrun", "missing_coverage", "ineligible", "unknown_citations", "self", "duplicate", "no_third"])
def test_formal_gate_rejects_incomplete_or_dependent_reviews(defect):
    row, families, q, summary = fixture_gate()
    formal = row["reviews"]["formal"]
    vote = formal["judgments"]["D05"]
    if defect == "unrun":
        vote["status"] = "NOT_RUN"
    elif defect == "missing_coverage":
        formal["expected"].append("D20")
    elif defect == "ineligible":
        q["admission"]["b"]["status"] = "FAIL"
    elif defect == "unknown_citations":
        vote["citation_support"]["a"] = "pending"
    elif defect == "self":
        row["source_family"] = families["a"]
    elif defect == "duplicate":
        families["b"] = families["a"]
    else:
        vote["third_recorded"] = False
    with pytest.raises(ValueError):
        hr.verify_coverage(summary, [row], q, families)


def test_completed_genuine_abstentions_are_covered():
    row, families, q, summary = fixture_gate()
    totals = hr.verify_coverage(summary, [row], q, families)
    assert totals == {"eligible_dimensions":1,"eligible_trials":1,"trials":1}


def test_preregistered_draw_is_reproducible_disjoint_and_reports_inclusion_weights():
    def candidate(i,j):
        return {"suite":"S","case_id":f"case-{i}", "trial_id":f"trial-{i}-{j}", "level":"L0" if i%3 else "L1",
                "language":"zh" if i%2 else "en","disposition":"clarify",
                "challenge":[hr.BUCKETS[i%len(hr.BUCKETS)]]}
    population = [candidate(i,j) for i in range(850) for j in range(2)]
    legacy = {("S",f"case-{i}") for i in range(22)}
    plan = {"representative":{"n":160},"challenge":{"n":80},"seed":"fixture-only"}
    rows, stats = hr.draw(population, legacy, plan)
    assert (rows, stats) == hr.draw(list(reversed(population)), legacy, plan)
    assert (stats["representative_n"], stats["challenge_n"]) == (160,80)
    assert len({r["case_id"] for r,_ in rows}) == 240
    assert not legacy.intersection((r["suite"],r["case_id"]) for r,_ in rows)
    assert all(s["original_pi"] == s["original_n"]/s["population"] and
               s["weight"] == s["population"]/s["final_n"] for s in stats["strata"])


def test_sample_extension_and_capacity_exhaustion_are_explicit():
    rows = [{"suite":"fixture","language":"en","case_id":str(i),"trial_id":str(i),"level":"L0",
             "disposition":"clarify","challenge":[]} for i in range(500)]
    selection, stats = hr.draw(rows,set(),{"representative":{"n":10}, "challenge":{"n":80},"seed":"fixture"})
    assert 10 < len(selection) <= 300
    assert stats["initial_margin_95"] > .08 >= stats["final_margin_95"]
    assert stats["challenge_n"] == 0
    assert stats["strata"][0]["original_n"] == 10


@pytest.mark.parametrize("value", [{"new_score":"PASS"}, {"x":[{"modelName":"secret"}]}, {"GOLD_LABEL":"fixture"}, "旧评分：通过",
                                   '{"judge_verdict":"FAIL"}', "reply by Qwen3-14B"])
def test_nested_label_and_identity_hints_fail_closed(value):
    with pytest.raises(ValueError):
        hr.visible_events([{"kind":"answer","content":value}])


def test_fixture_release_preserves_originals_and_separates_reviewers(tmp_path, monkeypatch):
    row, families, q, summary = fixture_gate()
    monkeypatch.setattr(hr, "ROOT", tmp_path)
    monkeypatch.setattr(hr, "measure", lambda _: q)
    registry = tmp_path / "models.json"
    write_json(registry, {"candidates":{k:{"family":name} for k,name in families.items()}})
    monkeypatch.setattr(hr,"REGISTRY",registry)
    legacy = tmp_path / "a1-blind-review-packet.json"
    provenance = tmp_path / "a1-blind-review-provenance.json"
    items = [{"review_id":f"legacy-{i}", "public_input":{"prompt":f"fictional task {i}"},
              "suite":"fixture","answer":"fictional candidate answer"} for i in range(22)]
    write_json(legacy, {"items":items})
    write_json(provenance, {r["review_id"]:{"case_id":f"frozen-{i}","suite":"fixture"} for i,r in enumerate(items)})
    expected = {"count":22,"packet":legacy.name,"packet_sha256":hr.digest(legacy),
                "provenance_sha256":hr.digest(provenance)}
    protocol = tmp_path / "protocol.json"
    write_json(protocol, {"preserved":expected,"sample":{"representative":{"n":160},"challenge":{"n":80},"seed":"fixture"}})
    monkeypatch.setattr(hr,"PROTOCOL",protocol)
    archived = gzip.compress(canonical(row) + b"\n", mtime=0)
    (tmp_path/"rescore.jsonl.gz").write_bytes(archived)
    write_json(tmp_path/"rescore_summary.json",summary)
    own_packet = {"trial_id":row["trial_id"], "events":[{"kind":"task","content":"fixture task"},
                  {"kind":"answer","content":"observed fixture answer"},
                  {"kind":"persisted_state","content":{"private_oracle":"fixture internal material"}}]}
    (tmp_path/"judge_inputs_v2.jsonl.gz").write_bytes(gzip.compress(canonical(own_packet)+b"\n"))
    monkeypatch.setattr(hr,"case_metadata", lambda _: {"case-0":{"suite":"fixture"}})
    def replay(history, results, out):
        out.mkdir()
        (out/"rescore.jsonl.gz").write_bytes(archived)
        return copy.deepcopy(summary)
    monkeypatch.setattr(hr,"build",replay)
    target = tmp_path / "fixture-output"
    hr.release(tmp_path,tmp_path,target)
    reviewer = json.loads((target/"reviewer/packet.json").read_bytes())
    private = json.loads((target/"custodian/draw.json").read_bytes())
    schema = json.loads((target/"reviewer/submission.schema.json").read_bytes())
    Draft202012Validator.check_schema(schema)
    assert set(schema["properties"]["dimensions"]["required"]) == set(reviewer["questions"])
    assert set(schema["properties"]["review_id"]["enum"]) == set(private["mapping"])
    assert len(reviewer["items"]) == len(private["mapping"]) == 23
    assert all(set(r) == {"events","review_id"} for r in reviewer["items"])
    raw = json.dumps(reviewer)
    for secret in ("fixture internal material","legacy-0","trial-0","case-0","source_family","private_oracle","judge disagreement"):
        assert secret not in raw
    assert private["human_review"] == "NOT_RUN" and private["human_submissions"] == 0
    assert hr.digest(legacy) == expected["packet_sha256"]
    with pytest.raises(FileExistsError):
        hr.release(tmp_path,tmp_path,target)
    q["admission"]["a"]["status"] = q["admission"]["b"]["status"] = "NOT_RUN"
    forbidden = tmp_path/"must-not-exist"
    with pytest.raises(ValueError, match="qualification incomplete"):
        hr.release(tmp_path,tmp_path,forbidden)
    assert not forbidden.exists()

def test_supplemental_coverage_tracks_software_and_derived_sources_separately():
    physical, families, q, summary = fixture_gate()
    decision = physical["reviews"]["formal"]["judgments"]["D05"]
    empty = {"expected": [], "judgments": {}}
    software = {**physical, "class": "software_witness", "trial_id": "software",
                "reviews": {"formal": empty, "supplement": {"expected": ["D05"], "judgments": {"D05": decision}}},
                "supplement": {"subject_family": "no-model", "source_trial_id": None,
                               "semantic_disposition": "eligible_independent_software_evidence"}}
    derived = {**software, "class": "offline_replay", "trial_id": "derived",
               "reviews": {"formal": empty, "supplement": empty},
               "supplement": {"source_trial_id": "software", "subject_family": "no-model",
                              "semantic_disposition": "reuse_source_semantic_evaluation"}}
    summary["scope"]["supplement"].update(eligible_trials=1, eligible_dimensions=1)
    summary["nonphysical_inventory"].update(registered=2, independent_inputs=1, linked_source_records=1)
    summary["trial_counts"]["trials"] = 3
    rows = [derived, software, physical]
    totals = hr.verify_coverage(summary, rows, q, families)
    assert totals["eligible_trials"] == totals["nonphysical_eligible_trials"] == 1
    assert totals["nonphysical_registered"] == 2 and totals["nonphysical_linked_to_reviewed_source"] == 1
    for key, value in [("source_trial_id", "nonexistent"), ("subject_family", "unknown")]:
        altered = copy.deepcopy(rows)
        altered[0]["supplement"][key] = value
        with pytest.raises(ValueError, match="lacks a fully reviewed"):
            hr.verify_coverage(summary, altered, q, families)
    altered = copy.deepcopy(rows)
    altered[1]["supplement"]["subject_family"] = "unknown"
    with pytest.raises(ValueError, match="unresolved"):
        hr.verify_coverage(summary, altered, q, families)
    altered = copy.deepcopy(rows)
    altered[1]["reviews"]["supplement"]["judgments"] = {}
    with pytest.raises(ValueError, match="incomplete"):
        hr.verify_coverage(summary, altered, q, families)
    summary["nonphysical_inventory"]["status"] = "BLOCKED"
    with pytest.raises(ValueError, match="supplemental nonphysical inventory incomplete"):
        hr.verify_coverage(summary, rows, q, families)
