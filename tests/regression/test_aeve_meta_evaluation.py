import gzip
import json
import re

import pytest

from evaluation.aeve.controller import connect
from evaluation.aeve.gold import iter_gold
from evaluation.aeve.meta_evaluation import compare, control_rows, family_comparison, nominal_alpha, snapshot
from evaluation.aeve.qualification import request_for as frozen_request
from evaluation.aeve.robustness import COLLECTION, FAMILIES, cases, request_for, seed


def test_all_224_controls_have_independently_reconstructible_gold_and_baseline(tmp_path):
    db = connect(tmp_path)
    seed(db)
    seed(db)
    rows = list(db.execute("SELECT item, candidate, spec FROM jobs WHERE collection=?", (COLLECTION,)))
    sources = {r["case_id"]: r for r in iter_gold("development")}
    variants = {c["item"]: c for c in cases()}
    assert len(rows) == len(FAMILIES) * len(variants) == 224
    for item, candidate, raw in rows:
        case = variants[item]
        spec = json.loads(gzip.decompress(raw))
        role, expected_spec = request_for(case, candidate)
        assert spec == expected_spec
        packet = spec["packet"]
        assert json.loads(spec["body"]["messages"][1]["content"]) == packet
        exhibits = {e["id"]: e for e in packet["events"]}
        observation, answer = [exhibits[k] for k in case["required_refs"]]
        record = observation["value"]["record"]
        assert record in packet["task"] and record in answer["value"]
        # Exclude the record ID before parsing the claimed numerical balance.
        numbers = re.findall(r"\b\d+\b", answer["value"].replace(record, ""))
        credits = observation["value"]["credits"]
        assert numbers and ("PASS" if all(int(n) == credits for n in numbers) else "FAIL") == case["expected"]
        source = sources[case["case_id"]]
        base_role, base = frozen_request(source, candidate)
        assert role == base_role
        if case["arm"] in {"baseline", "repeat"}:
            assert spec == base
        if case["arm"] == "json_key_order":
            assert spec["body"]["messages"][1]["content"] != base["body"]["messages"][1]["content"]
        if case["arm"] == "fact_changed":
            assert case["expected"] != source["expected"]
        if case["arm"] == "claim_own":
            assert packet["events"][-1]["value"]["unverified_author_family"] == FAMILIES[candidate]
        if case["arm"] == "claim_other":
            assert packet["events"][-1]["value"]["unverified_author_family"] != FAMILIES[candidate]


def test_nominal_alpha_gaps_constant_and_disagreement():
    assert nominal_alpha([["PASS", "PASS"], ["FAIL", "FAIL"]])["nominal_alpha"] == 1
    report = nominal_alpha([["PASS", "FAIL"], ["NOT_RUN", "BLOCKED", "FAIL"]])
    assert report["nominal_alpha"] == 0
    assert report["units_with_overlap"] == 1
    assert report["conclusive_ratings_with_overlap"] == 2
    assert nominal_alpha([["FAIL", "FAIL"]])["nominal_alpha"] is None
    assert nominal_alpha([])["nominal_alpha"] is None
    assert nominal_alpha([["FAIL", "PASS"], ["FAIL", "PASS"]])["nominal_alpha"] == pytest.approx(-0.5)


def test_unexecuted_controls_and_partial_pairing(tmp_path):
    rows = control_rows(tmp_path)
    assert len(rows) == 224
    assert all(r["prediction"] == "NOT_RUN" and not r["supported_correct"] for r in rows)
    selected = [r for r in rows if r["candidate"] == "J"]
    empty = compare(selected, "injection")
    assert empty["conclusive_pairs"] == 0 and empty["planned_pairs"] == 4
    assert empty["mcnemar_two_sided_exact_p"] is None
    first = next(r for r in selected if r["arm"] == "baseline")
    first.update(prediction=first["expected"], supported_correct=True)
    for arm, want in (("injection", "FAIL"), ("fact_changed", "FAIL")):
        target = next(r for r in selected if r["case_id"] == first["case_id"] and r["arm"] == arm)
        target.update(prediction=want, supported_correct=(target["expected"] == want))
    result = compare(selected, "injection")
    assert result["degraded"] == result["conclusive_pairs"] == 1
    assert result["accuracy_delta_on_matched_pairs"] == -1
    changed = compare(selected, "fact_changed")
    assert changed["correctly_changed_decision"] == changed["both_correct_with_gold_citations"] == 1


def test_shared_family_denominators_and_snapshot_integrity(tmp_path):
    def score(id_, pred, gold):
        return {"case_id": id_, "prediction": pred, "label": gold, "citation_correct": True}
    a = [score("one", "PASS", "PASS"), score("two", "PASS", "FAIL")]
    b = [score("one", "NOT_RUN", "PASS"), score("two", "FAIL", "FAIL")]
    stats = family_comparison(a, b)
    assert stats["conclusive_paired"] == 1 and stats["paired_accuracy_delta_left_minus_right"] == -1
    with pytest.raises(ValueError, match="changed"):
        with snapshot(tmp_path, {"unavailable": "unavailable"}):
            pass
