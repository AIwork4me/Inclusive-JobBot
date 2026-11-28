from evaluation.aeve.gold import iter_gold
from evaluation.aeve.q1_source_audit import assess_citations, source_proof


def q1_case(case_id):
    return next(case for case in iter_gold("qualification") if case["case_id"] == case_id)


def test_protocol_counterexample_needs_only_the_broken_wire():
    case = q1_case("76a2ee5d562297fc27cc-a")
    proof = source_proof(case["packet"])
    assert proof == {"verdict": "FAIL", "minimal_sets": [["e2"]]}
    assert assess_citations(case["packet"], proof, "FAIL", ["e1", "e2"])["sufficient"]
    assert not assess_citations(case["packet"], proof, "FAIL", ["e1"])["sufficient"]
    assert not assess_citations(case["packet"], proof, "PASS", ["e2"])["sufficient"]
    assert assess_citations(case["packet"], proof, "FAIL", ["e2", "e999"])["invalid"] == ["e999"]


def test_persisted_state_can_disprove_a_claim_without_trusting_the_final_answer():
    case = q1_case("f1347fbaa34b2db63aa2-c")
    proof = source_proof(case["packet"])
    assert proof["verdict"] == "FAIL"
    assert ["e3"] in proof["minimal_sets"]
    assert not assess_citations(case["packet"], proof, "PASS", ["e1", "e4"])["sufficient"]


def test_source_rule_changes_when_observed_dependency_order_changes():
    case = q1_case("c42c4ec19c19dd2ec5f6-a")
    packet = case["packet"]
    proof = source_proof(packet)
    assert proof["verdict"] == "FAIL"
    packet["events"][1]["value"]["execution_order"].reverse()
    assert source_proof(packet)["verdict"] == "PASS"
    packet["events"].pop(0)
    assert source_proof(packet)["verdict"] == "BLOCKED"
