import json
from decimal import Decimal
from types import SimpleNamespace

import pytest

from evaluation.aeve.history_dimension_checks import native_matches
from evaluation.aeve.history_dimensions import DIMENSIONS, OUT, apply_facts, read_addendum
from evaluation.aeve.history import lines


def test_native_decimal_and_boolean_are_compared_by_business_value():
    reply = SimpleNamespace(calls=[SimpleNamespace(name="read",arguments_raw='{"a":12.50,"b":true}')])
    assert native_matches(("json",[("read",{"a":Decimal("12.5"),"b":True})]),reply)
    assert not native_matches(("json",[("read",{"a":12.5,"b":1})]),reply)


def test_added_dimensions_bind_sources_and_preserve_frozen_scores():
    path, facts = read_addendum(OUT)
    assert path is not None
    original = {r["trial_id"]:set(r["dimensions"]) for r in lines(OUT/"judge_inputs_v2.jsonl.gz")}
    for r in lines(path):
        assert r["dimensions"] == ["D04"]
        assert "D04" not in original[r["trial_id"]]
    trials = {r["trial_id"]:r for r in lines(OUT/"registry.jsonl.gz") if r["trial_id"] in facts}
    assert len(trials) == len(facts)
    for trial in trials.values():
        updated = apply_facts(trial,facts)
        assert all(dim in DIMENSIONS and updated["deterministic"][dim] == entry["status"] for dim,entry in facts[trial["trial_id"]].items())
    key = next(iter(facts))
    with pytest.raises(ValueError,match="different source"):
        apply_facts({**trials[key],"sources":[]},facts)
    audit = json.loads((OUT/"physical_addendum.json").read_bytes())
    assert set(audit["classification"]) == set(DIMENSIONS)
    assert all(sum(values.values()) == audit["physical_trials"] for values in audit["classification"].values())
