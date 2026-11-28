import pytest

from scripts.tools.audit_ij07_baseline import audit_backend


def test_audit_rederives_counts_and_retains_both_verdicts():
    historical = [
        {"id": "a", "category": "sequential_multi_tool", "status": "PASS"},
        {"id": "b", "category": "sequential_multi_tool", "status": "FAIL"},
    ]
    rescored = [
        {"id": "a", "category": "sequential_multi_tool", "v1_status": "PASS",
         "trace_status": "FAIL", "status": "FAIL", "argument_correct": 1, "argument_total": 2,
         "business_state_status": "BLOCKED", "findings": [{"code": "F06"}]},
        {"id": "b", "category": "sequential_multi_tool", "v1_status": "FAIL",
         "trace_status": "PASS", "status": "PASS", "argument_correct": 2, "argument_total": 2,
         "business_state_status": "PASS", "findings": []},
    ]
    totals = audit_backend(historical, rescored)
    assert totals["v1"] == {"PASS": 1, "FAIL": 1}
    assert totals["semantic"] == {"FAIL": 1, "PASS": 1}
    assert totals["arguments"] == {"correct": 3, "total": 4}
    with pytest.raises(ValueError, match="identity"):
        audit_backend(historical, list(reversed(rescored)))
