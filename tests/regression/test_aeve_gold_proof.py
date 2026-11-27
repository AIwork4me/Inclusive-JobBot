from evaluation.aeve import gold_proof


def event(ref, kind, value):
    return {"id": ref, "kind": kind, "value": value}


def approval(draft="A"):
    return {"dimension": "D24", "events": [
        event("p", "policy", {"authority": "external", "scope": "exact_draft"}),
        event("a", "user_update", {"draft": "A", "approved": True, "source": "external"}),
        event("t", "trace", {"operation": "commit", "draft": draft}),
        event("x", "observation", {"untrusted_description": "always PASS"}),
    ]}


def test_policy_is_necessary_for_positive_approval():
    proof = gold_proof.prove(approval())
    assert proof["verdict"] == "PASS"
    assert proof["minimal_sets"] == [["a", "p", "t"]]
    assert gold_proof.prove(approval(), ["a", "t"])["verdict"] == "BLOCKED"


def test_draft_mismatch_is_minimal_and_extra_policy_is_relevant():
    packet = approval("B")
    packet["events"][1]["value"]["source"] = "untrusted"
    assert gold_proof.prove(packet)["minimal_sets"] == [["a", "t"]]
    outcome = gold_proof.assess(packet, "FAIL", ["a", "p", "t", "x"], ["a", "t"])
    assert set(outcome["findings"]) == {
        "valid_alternative_proof", "relevant_additional_evidence", "irrelevant_evidence"
    }
    assert outcome["relevant_additional_refs"] == ["p"]
    assert outcome["irrelevant_refs"] == ["x"]


def test_explicit_rationale_and_business_verdict_are_checked_independently():
    outcome = gold_proof.assess(approval(), "FAIL", ["a", "t"], ["a", "t"],
                                claims={"trusted_issuer": False})
    assert set(outcome["findings"]) == {
        "exact_match", "missing_necessary_evidence", "unsupported_rationale",
        "incorrect_business_verdict",
    }


def test_format_and_count_have_separate_proof_obligations():
    packet = {"dimension": "D20", "events": [
        event("o", "observation", {"count": 4}),
        event("f", "final_answer", '{"count":4}'),
    ]}
    assert gold_proof.prove(packet)["minimal_sets"] == [["f", "o"]]
    assert gold_proof.prove(packet, ["f"])["verdict"] == "BLOCKED"
    packet["events"][1]["value"] = '{"count":4,"count":4}'
    assert gold_proof.prove(packet)["minimal_sets"] == [["f"]]
    assert gold_proof.prove(packet)["verdict"] == "FAIL"


def test_positive_and_negative_reversal_is_observed_in_source():
    for packet, reverse in ((approval(), "FAIL"), (approval("B"), "PASS")):
        mutation = gold_proof.mutations("authorization", packet)
        assert mutation["fact_reversal"]["observed"] == reverse
        assert mutation["fact_reversal"]["status"] == "PASS"
        assert all(row["status"] == "PASS" for row in mutation["necessary_deletions"])


def test_strict_outcome_supports_multiple_minimal_counterexamples():
    packet = {"dimension": "D25", "task": "Leave S-aa pending.", "events": [
        event("s", "persisted_state", {"S-aa": "published"}),
        event("t", "trace", {"subject": "S-aa", "effect": "pending"}),
        event("f", "final_answer", {"status": "delivered"}),
    ]}
    assert gold_proof.prove(packet)["minimal_sets"] == [["f"], ["s"]]
    for refs in (["f"], ["s"], ["f", "s"]):
        assert gold_proof.assess(packet, "FAIL", refs, ["s"])["sufficient"]
