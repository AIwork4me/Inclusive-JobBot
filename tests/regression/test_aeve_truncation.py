import json

from evaluation.aeve import truncation


def test_physical_arms_change_only_one_wire_field():
    item = truncation.roster()[0]
    base = truncation.spec_for(item, "baseline")
    budget = truncation.spec_for(item, "token_budget")
    contract = truncation.spec_for(item, "output_contract")
    assert base["body"]["max_tokens"] == 160
    assert budget["body"] == {**base["body"], "max_tokens": 320}
    assert set(contract["body"]) == set(base["body"])
    assert [k for k in base["body"] if base["body"][k] != contract["body"][k]] == ["response_format"]
    refs = [base["packet"]["events"][0]["id"]]
    raw = json.dumps({"v": "PASS", "e": refs, "r": "Evidence comparison."})
    assert truncation.grade(contract, raw) == {
        "verdict": "PASS", "evidence_refs": refs, "reason_summary": "Evidence comparison.",
    }


def test_original_truncations_are_enrolled_once_for_each_treatment():
    items = truncation.roster()
    assert len(items) == 131
    assert len({(row["judge"], row["case_id"]) for row in items}) == 131
    assert truncation.freeze()["required"] == 393
