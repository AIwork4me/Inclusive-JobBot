from evaluation.aeve.paired_evaluation import compare


def assessment(arm, item, verdict, *, proof=False, requests=2, tokens=60):
    return {"arm": arm, "case_id": item, "verdict": verdict, "evidence_sufficient": proof,
            "llm_requests": requests, "tokens": tokens, "gpu_inference_ms": requests * 10,
            "wall_ms": requests * 15}


def test_full_denominator_retains_abstentions_and_unexecuted_rows():
    roster = [{"case_id": "p", "label": "PASS", "critical": False, "mechanical": True},
              {"case_id": "n", "label": "FAIL", "critical": True, "mechanical": False}]
    report = compare(roster, [assessment("E5", "p", "BLOCKED"),
                              assessment("E7", "n", "PASS")])
    e7 = report["arms"]["E7"]
    assert e7["full_roster"] == 2 and e7["required"] == 2 and e7["recorded"] == 1
    assert e7["decision_coverage"] == 0.5 and e7["false_accepts"] == 1
    assert e7["critical_false_accepts"] == 1
    assert report["arms"]["E5"]["abstentions"] == 1
    assert report["arms"]["E6"]["full_roster"] == 2 and report["arms"]["E6"]["required"] == 1
    assert report["status"] == "NOT_RUN"


def test_zero_call_cost_is_reported_without_confusing_zero_with_missing():
    roster = [{"case_id": "p", "label": "PASS", "critical": False, "mechanical": True}]
    rows = [assessment("E5", "p", "PASS", proof=True),
            assessment("E7", "p", "PASS", proof=True, requests=0, tokens=0)]
    report = compare(roster, rows)
    assert report["arms"]["E7"]["cost"]["tokens"] == {"recorded": 1, "total": 0}
    assert report["comparisons"]["E5/E7"]["tokens_delta"] == {"paired": 1, "total": -60}
    assert report["comparisons"]["E5/E7"]["accuracy_delta"] == 0.0
