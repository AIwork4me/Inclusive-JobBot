"""Check matched world selection against the pinned Planning candidate."""

from collections import Counter
from hashlib import sha256

import pytest

from evaluation.aeve.runtime import canonical
from benchmarks.slm10.planning_roster import allocate, read_bundle


def test_every_seed_model_and_track_uses_the_same_authored_world():
    from benchmarks.slm10.planning_world_allocation import SOURCE, SOURCE_SHA256, build_allocation, bind_trial

    _, cases, controls = read_bundle(SOURCE, SOURCE_SHA256)
    variants = {row["case_id"]: row["variant"] for row in controls}
    allocation = build_allocation()
    assert len(allocation["cases"]) == 800
    assert allocation["source_world_count"] == 2300
    assert allocation["unselected_world_count"] == 1500

    known = {row["case_id"]: {world["world_id"] for world in row["worlds"]} for row in controls}
    bound = {}
    trials = allocate(cases, variants, SOURCE_SHA256)
    for trial in trials:
        identity = bind_trial(allocation, trial)
        item = allocation["cases"][trial["case_id"]]
        assert identity["world_id"] == item["selected_world_id"]
        assert identity["world_sha256"] == item["selected_world_sha256"]
        assert identity["trial_id"] == trial["trial_id"]
        assert bound.setdefault(trial["case_id"], identity["world_sha256"]) == identity["world_sha256"]
        assert {identity["world_id"], *(row["world_id"] for row in item["unselected_worlds"])} == known[trial["case_id"]]
    assert len(trials) == 20800
    chosen = Counter(item["selected_world_id"] for item in allocation["cases"].values())
    assert all(chosen[key] > 0 for key in (
        "alternate_source", "scope_revision", "revised_primary_unavailable", "approved", "declined",
        "later_check_denied", "missing_host_grant",
    ))


def test_forged_trial_id_and_absent_dispatch_credentials_are_rejected():
    from benchmarks.slm10.planning_world_allocation import (
        SOURCE, SOURCE_SHA256, bind_trial, build_allocation, require_dispatch_binding,
    )

    _, cases, controls = read_bundle(SOURCE, SOURCE_SHA256)
    trial = allocate(cases, {row["case_id"]: row["variant"] for row in controls}, SOURCE_SHA256)[0]
    allocation = build_allocation()
    with pytest.raises(ValueError, match="trial identity"):
        bind_trial(allocation, trial | {"seed": 678})
    with pytest.raises(ValueError, match="trial identity"):
        bind_trial(allocation, trial | {"world_id": "forged"})
    with pytest.raises(ValueError, match="credential"):
        require_dispatch_binding(allocation, trial, {}, {}, SOURCE)


def test_read_only_release_requires_own_credentials_and_leaves_d25_blocked(tmp_path, monkeypatch):
    from benchmarks.slm10 import planning_world_allocation as world

    allocation = world.build_allocation()
    _, cases, controls = read_bundle(world.SOURCE, world.SOURCE_SHA256)
    trials = allocate(cases, {row["case_id"]: row["variant"] for row in controls}, world.SOURCE_SHA256)
    read = next(row for row in trials if row["level"] == "L1" and row["track"] == "direct_acting_first")
    stateful = next(row for row in trials if row["level"] == "L6" and row["track"] == "direct_acting_first")
    runtime = dict.fromkeys(("engine_binary_sha256", "model_sha256", "sdk_binary_sha256", "host_sha256",
                             "gpu_physical_sha256", "runner_sha256"), "1" * 64)
    runtime.update(dict.fromkeys(("engine_build", "model_revision", "sdk_version", "runtime_session_id", "run_id"), "fixture"))
    runtime.update(git_sha="a" * 40, backend="vulkan", profile="DIRECT_NATIVE")
    hardware = {name: runtime[name] for name in ("host_sha256", "gpu_physical_sha256")}
    monkeypatch.setattr(world, "require_handoff", lambda _root: {"lease": hardware})

    source = {"source_manifest_sha256": world.SOURCE_SHA256,
              "world_allocation_sha256": sha256(canonical(allocation) + b"\n").hexdigest(),
              "release_scope": "READ_ONLY_MECHANICAL"}
    mechanics = dict.fromkeys(("public_contract", "provider_tool_linkage", "actual_call_path",
                              "business_facts", "read_only_scope"), "PASS")
    expected = {
        "release_review": source,
        "matched_runner": source | {"runner_sha256": runtime["runner_sha256"], "profile": "DIRECT_NATIVE"},
        "runtime_admission": source | runtime | {"candidate": read["candidate"]},
        "hardware_handoff": hardware | {"handoff_sha256": world.digest(world.ROOT / world.HANDOFF)},
        "evaluation": source | {"evaluation_contract_sha256": allocation["evaluation_contract_sha256"],
                                "mechanics": mechanics,
                                "dimensions": {"D12": "BLOCKED", "D23": "NOT_RUN", "D24_affirmative": "NOT_RUN",
                                               "D25": "BLOCKED"}},
    }
    pins = {}
    for name, bindings in expected.items():
        raw = canonical({"credential": name, "status": "PASS", "bindings": bindings, "evidence_sha256": "9" * 64})
        (tmp_path / f"{name}.json").write_bytes(raw)
        pins[name] = sha256(raw).hexdigest()
    qualified = world.require_dispatch_binding(allocation, read, runtime, pins, tmp_path,
                                               release_scope="READ_ONLY_MECHANICAL")
    assert qualified["release_scope"] == "READ_ONLY_MECHANICAL"
    assert qualified["strict_e2e"] == "BLOCKED"
    with pytest.raises(ValueError, match="stateful"):
        world.require_dispatch_binding(allocation, stateful, runtime, pins, tmp_path, release_scope="READ_ONLY_MECHANICAL")
    with pytest.raises(ValueError, match="release_review"):
        world.require_dispatch_binding(allocation, read, runtime, pins, tmp_path)
