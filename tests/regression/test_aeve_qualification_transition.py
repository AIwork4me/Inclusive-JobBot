from evaluation.aeve.qualification_transition import routing_readiness


def test_q2_pass_is_not_a_q3_route_credential():
    plan = {"models": {"A": {"status": "PASS"}, "B": {"status": "PASS"}, "C": {"status": "PASS"}}}
    readiness = routing_readiness(plan, {"MiniCPM": 10, "Qwen": 24})
    assert readiness["q2_passing"] == ["A", "B", "C"]
    assert readiness["formal_history"] == "BLOCKED"
    assert readiness["subject_families"]["Qwen"] == {"physical_trials": 24, "status": "BLOCKED"}
