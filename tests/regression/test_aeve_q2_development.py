import json

import pytest

from evaluation.aeve.controller import connect
from evaluation.aeve.q2_development import ARMS, freeze, grade, request, roster, seed


def test_development_freeze_does_not_send_author_labels(tmp_path):
    cases = roster()
    assert len({r["base_id"] for r in cases}) == 24
    assert all(r["split"] == "development" for r in cases)
    assert len(freeze()["request_sha256"]) == 5
    for case in cases:
        for arm in ARMS:
            packet = json.loads(request(case, "E", arm)["body"]["messages"][1]["content"])
            assert set(packet) <= {"task", "dimension", "events", "reference_roles"}
    db = connect(tmp_path)
    seed(db)
    seed(db)
    assert db.execute("SELECT count(*) FROM jobs").fetchone()[0] == 360
    db.close()


def test_citation_roles_cannot_be_swapped():
    case = next(c for c in roster() if c["packet"]["dimension"] == "D22")
    spec = request(case, "J", "combined")
    exhibits = spec["exhibits"]
    answer = {"verdict":"FAIL","reason_summary":"Different result.",
              "decision_refs":exhibits["decision_candidates"][:1],"source_refs":exhibits["reference_candidates"][:1]}
    assert set(grade(spec,json.dumps(answer))["evidence_refs"]) == set(answer["decision_refs"] + answer["source_refs"])
    answer["decision_refs"] = answer["source_refs"]
    with pytest.raises(ValueError,match="wrong role"):
        grade(spec,json.dumps(answer))


def test_sealed_revised_gold_is_disjoint_and_selection_requires_complete_development(monkeypatch):
    from evaluation.aeve import q2_qualification
    holdout = q2_qualification.roster()
    assert len({r["base_id"] for r in holdout.values()}) >= 1200
    assert {r["dimension"] for r in holdout.values()} == {f"D{i:02d}" for i in range(1,26)}
    monkeypatch.setattr(q2_qualification,"development_report",lambda _: {"cases":[]})
    with pytest.raises(ValueError,match="roster is incomplete"):
        q2_qualification.protocol(None)
