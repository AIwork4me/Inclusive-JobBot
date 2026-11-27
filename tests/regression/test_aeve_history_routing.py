import hashlib

import pytest

from evaluation.aeve.history_routing import BOUND_FIELDS, plan_panel


def profile(code, family, scopes=("D05/read",), status="PASS"):
    return {
        "code": code, "family": family, "status": status, "scopes": list(scopes),
        "model_revision": "0" * 40, "quantization": "Q8_0", "qualification_cycle": "Q3",
        **{field: hashlib.sha256(f"{code}/{field}".encode()).hexdigest() for field in BOUND_FIELDS},
    }


def test_same_family_and_duplicate_variants_do_not_count_toward_routes():
    available = [profile("J", "Qwen"), profile("F", "Mistral"), profile("M14", "mistral"),
                 profile("G31", "Gemma"), profile("B", "LFM")]
    result = plan_panel(available, "qwen", "D05", "read")
    assert result["status"] == "PASS"
    assert result["primary"] == ["F", "G31"]
    assert result["dispute"] == "B"
    assert set(result["bindings"]) == {"F", "G31", "B"}


def test_no_route_without_qualified_third_family_for_the_exact_risk_scope():
    available = [profile("F", "Mistral"), profile("G31", "Gemma"), profile("B", "LFM", ("D05/write",))]
    result = plan_panel(available, "Qwen", "D05", "read")
    assert result == {"status": "BLOCKED", "eligible_distinct_families": ["Mistral", "Gemma"]}


def test_unbound_and_previous_cycle_profiles_fail_closed():
    available = [profile("F", "Mistral"), profile("G31", "Gemma"), profile("B", "LFM")]
    available[2]["qualification_cycle"] = "Q2"
    assert plan_panel(available, "Qwen", "D05", "read")["status"] == "BLOCKED"
    del available[0]["prompt_sha256"]
    with pytest.raises(ValueError, match="incomplete"):
        plan_panel(available, "Qwen", "D05", "read")
