import json

import pytest
from jsonschema import Draft202012Validator

from evaluation.aeve import evidence_roles_v2, q2_development


def test_evidence_slot_accepts_empty_group_artifact_and_rejects_injected_id():
    case = next(case for case in q2_development.roster() if case["dimension"] == "D01")
    old = q2_development.request(case,"G","evidence_roles")
    assert old["exhibits"]["reference_candidates"] == []
    schema = lambda s: Draft202012Validator(s["body"]["response_format"]["json_schema"]["schema"])
    evidence = old["exhibits"]["decision_candidates"][0]
    wrong = {"verdict":"PASS","reason_summary":"Observed objective.","decision_refs":[evidence],"source_refs":[evidence]}
    assert schema(old).is_valid(wrong)
    with pytest.raises(ValueError,match="wrong role"):
        q2_development.grade(old,json.dumps(wrong))
    repaired = evidence_roles_v2.use_single_slots(old)
    good = {**wrong,"decision_refs":{evidence:True},"source_refs":{}}
    assert schema(repaired).is_valid(good)
    assert evidence_roles_v2.grade(repaired,json.dumps(good))["evidence_refs"] == [evidence]
    extra = {**good,"source_refs":{evidence:True}}
    assert not schema(repaired).is_valid(extra)
    with pytest.raises(ValueError,match="assigned exhibit group"):
        evidence_roles_v2.grade(repaired,json.dumps(extra))
