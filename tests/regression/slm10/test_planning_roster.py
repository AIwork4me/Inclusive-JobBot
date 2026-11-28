"""Software controls for independent Planning V2 freeze and allocation."""

from collections import Counter
from copy import deepcopy
from hashlib import sha256

import pytest

from benchmarks.slm10 import planning_roster as roster
from evaluation.aeve.runtime import canonical


def reference(source, field):
    return {"from": source, "field": field}


def case_and_controls(*, scope_revision=False):
    subject, revised, status = "SUB-401", "SUB-COBALT", "approved-blue"
    tool = {"inputs": ["reference"], "outputs": ["code", "status"]}
    tool_schema = {"type": "object", "properties": {"reference": {"type": "string"}},
                   "required": ["reference"], "additionalProperties": False}
    contract = {"goal": "confirm_status", "public_fields": ["subject"], "event_fields": ["revised_reference"],
                "tools": {"lookup_status": tool | {"input_schema": tool_schema},
                          "fallback_status": tool | {"input_schema": tool_schema}}, "action_budget": 3}
    case = {"case_id": "SLM-AP2-L5-example", "level": "L5", "language": "en",
            "task": "Check the current status of SUB-401 and follow a trusted update or recover if needed.",
            "public": {"subject": subject}, "contract": contract,
            "limits": {"tool_calls": 3, "model_requests": 8, "peak_context_tokens": 4096, "retries": 0}}
    root = {"id": "first", "tool": "lookup_status", "arguments": {"reference": reference("public", "subject")},
            "when": True, "depends_on": []}
    ready = lambda source: {"op": "exists", "ref": reference(source, "status")}
    stop = lambda source: {"when": ready(source), "disposition": "completed",
                           "facts": {"status": reference(source, "status")}}
    initial = {"tool": "lookup_status", "args": {"reference": subject}, "result": {"code": "ok", "status": status}}
    if scope_revision:
        changed = initial | {"event": {"source": "synthetic_external_user", "revised_reference": revised}}
        updated = {"id": "updated", "tool": "lookup_status",
                   "arguments": {"reference": reference("event", "revised_reference")},
                   "when": True, "depends_on": []}
        path = [changed, {"tool": "lookup_status", "args": {"reference": revised},
                          "result": {"code": "ok", "status": "revised-green"}}]
    else:
        incident = {"op": "eq", "left": reference("first", "code"), "right": "unavailable"}
        updated = {"id": "updated", "tool": "fallback_status",
                   "arguments": {"reference": reference("public", "subject")},
                   "when": incident, "depends_on": ["first"]}
        path = [initial | {"result": {"code": "unavailable"}},
                {"tool": "fallback_status", "args": {"reference": subject},
                 "result": {"code": "ok", "status": "recovered-green"}}]
    worlds = [{"world_id": "ordinary", "steps": [initial], "disposition": "completed", "facts": {"status": status}},
              {"world_id": "alternate", "steps": path, "disposition": "completed",
               "facts": {"status": path[-1]["result"]["status"]}}]
    review = {"case_id": case["case_id"], "variant": "recovery",
              "witness": {"version": 2, "goal": contract["goal"], "actions": [root, updated],
                          "stops": [stop("first"), stop("updated")]}, "worlds": worlds}
    return case, review


def test_core_allocation_covers_all_five_models_and_keeps_repeat_tracks_separate():
    cases = [{"case_id": f"SLM-AP2-{level}-{i:03d}", "level": level,
              "language": "en" if i % 2 else "zh"} for level in roster.LEVELS for i in range(100)]
    variants = {case["case_id"]: "fixed" for case in cases}
    rows = roster.allocate(cases, variants, "f" * 64)
    assert len(rows) == len({row["trial_id"] for row in rows}) == 20800
    assert roster.allocation()["core_total"] == 36550
    assert Counter(row["candidate"] for row in rows) == dict.fromkeys("ABDFG", 4160)
    subset = [row for row in rows if row["candidate"] == "F" and row["level"] == "L7"]
    assert Counter((row["track"], row["panel"]) for row in subset) == {
        ("direct_plan_first", "first"): 100, ("direct_acting_first", "first"): 100,
        ("sdk_plan_first", "first"): 100, ("sdk_acting_first", "first"): 100,
        ("sdk_plan_first", "repeat"): 60, ("sdk_acting_first", "repeat"): 60,
    }
    repeat = [row for row in subset if row["panel"] == "repeat"]
    assert len({row["case_id"] for row in repeat}) == 20
    assert set(Counter(row["case_id"] for row in repeat).values()) == {6}
    assert rows == roster.allocate(list(reversed(cases)), variants, "f" * 64)
    assert rows[0]["trial_id"] != roster.allocate(cases, variants, "e" * 64)[0]["trial_id"]


@pytest.mark.parametrize("scope_revision, capability", [(False, "recovery"), (True, "scope_revision")])
def test_independent_branch_controls_prove_recovery_or_scope_revision(scope_revision, capability):
    case, proof = case_and_controls(scope_revision=scope_revision)
    result = roster.validate_control(case, proof)
    assert result["counterfactuals"][capability] == 1
    assert result["distinct_routes"] == 2


def test_stale_or_untrusted_scope_change_cannot_earn_mechanical_credit():
    case, proof = case_and_controls(scope_revision=True)
    forged = deepcopy(proof)
    forged["worlds"][-1]["steps"][0]["event"]["source"] = "tool_result"
    with pytest.raises(ValueError, match="trusted host event"):
        roster.validate_control(case, forged)
    stale = deepcopy(proof)
    stale["worlds"][-1]["steps"][1]["args"]["reference"] = case["public"]["subject"]
    with pytest.raises(ValueError, match="V2 witness"):
        roster.validate_control(case, stale)


def test_case_level_cannot_overstate_valid_lower_complexity_witness():
    case, proof = case_and_controls()
    case["level"] = "L6"
    with pytest.raises(ValueError, match="L6"):
        roster.validate_control(case, proof)


def test_public_validation_rejects_schema_resolution_outside_the_local_object():
    case, _ = case_and_controls()
    case["contract"]["tools"]["lookup_status"]["input_schema"] = {"$ref": "https://example.invalid/remote.json"}
    with pytest.raises(ValueError, match="local JSON Schema references"):
        roster.validate_public(case, set())


def test_write_world_requires_independent_snapshots_even_before_plan_validation():
    case, proof = case_and_controls()
    case["contract"]["tools"]["stage"] = {
        "inputs": ["reference", "action", "assessment"], "outputs": ["draft_id"],
    }
    proof["worlds"][0]["steps"] = [{
        "tool": "stage",
        "args": {"reference": case["public"]["subject"], "action": "review", "assessment": "verified"},
        "result": {"draft_id": "draft-001"},
    }]
    with pytest.raises(ValueError, match="state snapshots"):
        roster.validate_control(case, proof)


def test_recovery_must_change_when_the_disruption_is_removed():
    case, proof = case_and_controls()
    proof["witness"]["actions"][1]["when"] = True
    with pytest.raises(ValueError, match="does not depend on the observed disruption"):
        roster.validate_control(case, proof)


def test_bundle_hash_binds_both_holdout_files_and_distinct_source_roles(tmp_path):
    case, proof = case_and_controls()
    artifacts = {"holdout-public.jsonl": canonical(case) + b"\n",
                 "holdout-controls.jsonl": canonical(proof) + b"\n",
                 "source/public.txt": b"Illustrative public authoring transcript for software test.",
                 "source/oracle.txt": b"Separate illustrative oracle proof inputs for software test."}
    for name, raw in artifacts.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    seal = {"version": roster.SOURCE_VERSION, "mission": "IJ-SLM-1.0", "suite": "AGENTIC-PLAN-V2",
            "partition": "sealed_holdout", "origin": "independent_synthetic_authoring",
            "artifacts": {name: sha256(raw).hexdigest() for name, raw in artifacts.items() if name.endswith(".jsonl")},
            "authoring_sources": {"public_authoring": {"path": "source/public.txt",
                                                        "sha256": sha256(artifacts["source/public.txt"]).hexdigest()},
                                  "world_and_witness_authoring": {"path": "source/oracle.txt",
                                                                "sha256": sha256(artifacts["source/oracle.txt"]).hexdigest()}}}
    manifest = canonical(seal)
    (tmp_path / "manifest.json").write_bytes(manifest)
    digest = sha256(manifest).hexdigest()
    assert roster.read_bundle(tmp_path, digest) == (seal, [case], [proof])
    with pytest.raises(ValueError, match="pinned SHA256"):
        roster.read_bundle(tmp_path, "0" * 64)
    with pytest.raises(ValueError, match="100 independent cases per level"):
        roster.freeze(tmp_path, digest)
    (tmp_path / "holdout-controls.jsonl").write_bytes(b"{}")
    with pytest.raises(ValueError, match="pinned SHA256"):
        roster.read_bundle(tmp_path, digest)


def test_public_case_rejects_historical_prompt_even_if_renamed():
    case, _ = case_and_controls()
    old = next(iter(roster.historical_tasks()))
    case["task"] = old
    with pytest.raises(ValueError, match="historical"):
        roster.validate_public(case, roster.historical_tasks())


def test_missing_bundle_leaves_formal_planning_blocked():
    report = roster.readiness()
    assert report["planned"] == 20800
    assert report["historical_trials_imported"] == report["formal_trials_recorded"] == 0
    assert report["independent_roster"] == "BLOCKED"
    assert report["mechanical_world_replay"] == "NOT_RUN"
    assert report["dispatch_readiness"] == "BLOCKED"


def test_freeze_output_is_immutable_and_replayable(tmp_path):
    output = tmp_path / "freeze"
    files = {"roster.jsonl": b'{"trial_id":"illustrative-software-test"}\n',
             "manifest.json": b'{"evidence_class":"software test"}\n'}
    roster.output_files(output, files, False)
    roster.output_files(output, files, True)
    with pytest.raises(ValueError, match="differs from the existing output"):
        roster.output_files(output, files | {"roster.jsonl": b"{}\n"}, False)
    assert (output / "roster.jsonl").read_bytes() == files["roster.jsonl"]


def test_output_directory_cannot_stand_in_for_a_frozen_artifact(tmp_path):
    (tmp_path / "roster.jsonl").mkdir()
    with pytest.raises(ValueError, match="differs from the existing output"):
        roster.output_files(tmp_path, {"roster.jsonl": b"{}\n"}, False)
