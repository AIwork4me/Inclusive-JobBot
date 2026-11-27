import hashlib
import json
import pytest

from evaluation.aeve.contracts import ROOT, adjudicate, blind_packet, load_archive_input, load_input, sha, validate_judgment
from evaluation.aeve.gold import freeze, iter_gold
from evaluation.aeve.metrics import agree, audit_metrics
from evaluation.aeve.verifiers import verify_terminal


def evidence(*pairs):
    kinds = set(json.loads((ROOT/"input.schema.json").read_bytes())["properties"]["missing"]["items"]["enum"])
    return {"version":"aeve.input/1", "trial_id":"private-original", "public_task":"Inspect specimen",
            "missing": sorted(kinds - {k for k,v in pairs}),
            "events":[{"id":str(i), "kind":k, "value":v, "source":"archive.json", "sha256":sha(v),
                       "visibility":"internal" if k=="runtime_identity" else "judge"} for i,(k,v) in enumerate(pairs)]}


def test_anonymous_view_hash_checks_and_sources(tmp_path):
    record = evidence(("runtime_identity",{"model":"HiddenCandidate"}),
                      ("final_answer",{"message":"HiddenCandidate found a balance", "old_score":0}))
    payload, mapping = blind_packet(record, "D05")
    assert "HiddenCandidate" not in json.dumps(payload) and "old_score" not in json.dumps(payload)
    assert mapping == {"e1":"1"}
    original = record["events"][1]["value"]
    p = tmp_path/"archive.json"
    p.write_text(json.dumps([e["value"] for e in record["events"]]), encoding="utf8")
    for i,e in enumerate(record["events"]):
        e.update(source=f"archive.json#/{i}", source_sha256=hashlib.sha256(p.read_bytes()).hexdigest())
    assert load_archive_input(record,tmp_path)["events"][1]["value"] == original
    record["events"][1]["source"] = "archive.json#/0"
    with pytest.raises(ValueError):
        load_archive_input(record,tmp_path)
    record["events"][1]["value"] = "tampered"
    with pytest.raises(ValueError):
        load_input(record)


def test_deterministic_veto_and_disputes():
    packet = {"events":[{"id":"e1"}]}
    yes = {"verdict":"PASS", "reason_summary":"The observed state matches.", "evidence_refs":["e1"]}
    votes = [{"family":name,"answer":yes} for name in ("family-a","family-b","family-c")]
    assert adjudicate(packet,votes,"FAIL")["status"] == "FAIL"
    assert adjudicate(packet,votes,"BLOCKED")["status"] == "BLOCKED"
    assert adjudicate(packet,votes,"NOT_RUN")["status"] == "PASS"
    assert adjudicate(packet,votes[:2],"NOT_RUN",target_family="family-a")["status"] == "NOT_RUN"
    votes[-1]["answer"] = {**yes,"verdict":"FAIL"}
    assert adjudicate(packet,votes,"NOT_RUN")["status"] == "BLOCKED"
    with pytest.raises(ValueError):
        validate_judgment(packet,{**yes,"evidence_refs":["absent"]})


def test_state_proof_requires_actual_observation_and_type_exactness():
    required = {"D22":{"balance":1},"D23":{"balance":1}}
    absent = evidence(("final_answer",{"balance":1}))
    assert verify_terminal(absent, required)["D22"]["status"] == "BLOCKED"
    altered = evidence(("observation",{"balance":1}), ("final_answer",{"balance":1}),
                       ("persisted_state",{"balance":True}))
    assert verify_terminal(altered, required)["D22"]["status"] == "FAIL"
    good = evidence(("final_answer",{"balance":1}),("persisted_state",{"balance":1}))
    assert verify_terminal(good, required)["D22"]["status"] == "PASS"


def test_gold_split_leak_and_metric_denominators():
    manifest = freeze()
    assert manifest["primary_worlds"] >= 1200
    test = list(iter_gold("qualification"))
    assert set(r["dimension"] for r in test) == {f"D{i:02d}" for i in range(1,26)}
    records = []
    for r in test[:2]:
        records.append({"case_id":r["case_id"],"candidate":"unit-test-judge",
                        "answer":{"verdict":r["expected"],"reason_summary":"Software fixture.",
                                  "evidence_refs":r["required_refs"]}})
    result = audit_metrics("qualification",records)["models"]["unit-test-judge"]
    assert result["executed"] == 2 and result["n"] == len(test)
    assert result["coverage"] == 2/len(test) and result["qualification"] == "NOT_RUN"
    assert result["citation_accuracy"] == 1
    records[0]["answer"]["evidence_refs"] = ["imaginary"]
    result = audit_metrics("qualification",records)["models"]["unit-test-judge"]
    assert result["bad_response_count"] == 1 and result["citation_accuracy"] == 0.5
    assert agree(["PASS","FAIL"],["PASS","FAIL"])["cohens_kappa"] == 1
