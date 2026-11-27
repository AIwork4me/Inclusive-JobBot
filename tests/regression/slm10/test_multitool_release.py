"""Software-only controls for the candidate 0.3 release-scope verifier."""

from hashlib import sha256

import pytest

from benchmarks.slm10.multitool_v2_statistics import registered_roster
from evaluation.aeve.archive import digest
from evaluation.aeve.gpu_handoff import HANDOFF
from evaluation.aeve.runtime import ROOT, canonical, fingerprint


MANIFEST = "bc9daa18fb5c9dafc63945c5c791637c3b263b3a8d207e5b72dd3ac10264114c"
ROSTER = "7b7b54d2a151942dbe06fb639a5d67cca0431cde358dcf619439717c5e395a8a"
REVIEW = "be1c7d251b166f4ba736489c3f17702a85a51de341e5cbd62ccfd11c2c1fc870"
EVALUATION = "4626897c8e443ade1a07070d5f37457f9d99b84e8c613c5888f6045e7d5fef88"
MECHANICS = dict.fromkeys(("public_contract", "provider_tool_linkage", "actual_call_path",
                           "business_facts", "read_only_scope"), "PASS")
DIMENSIONS = {"D23": "NOT_RUN", "D24_affirmative": "NOT_RUN", "D25": "BLOCKED"}


@pytest.fixture(scope="module")
def roster():
    _, specs, _ = registered_roster()
    return specs


def scope_artifacts():
    return {"release_scope": "READ_ONLY_MECHANICAL", "candidate_manifest_sha256": MANIFEST,
            "roster_sha256": ROSTER, "review_capsule_sha256": REVIEW}


def fixture_credential_files(folder, runtime, *, change=None):
    scope = scope_artifacts()
    hardware = {key: runtime[key] for key in ("host_sha256", "gpu_physical_sha256")}
    bindings = {
        "release_review": scope,
        "matched_runner": scope | {"runner_sha256": runtime["runner_sha256"], "profile": runtime["profile"]},
        "runtime_admission": scope | runtime,
        "hardware_handoff": hardware | {"handoff_sha256": digest(ROOT / HANDOFF)},
        "evaluation": scope | {"evaluation_contract_sha256": EVALUATION, "mechanics": MECHANICS,
                               "dimensions": DIMENSIONS},
    }
    if change is not None:
        change(bindings)
    pins = {}
    for name, binding in bindings.items():
        evidence_path = f"{name}-software-test.json"
        raw = canonical({"software_fixture": True, "credential_role": name})
        (folder / evidence_path).write_bytes(raw)
        record = canonical({"credential": name, "status": "PASS", "bindings": binding,
                            "evidence_path": evidence_path, "evidence_sha256": sha256(raw).hexdigest()})
        (folder / f"{name}.json").write_bytes(record)
        pins[name] = sha256(record).hexdigest()
    return pins


def runtime_identity(trial):
    keys = ("engine_binary_sha256", "model_sha256", "host_sha256", "gpu_physical_sha256", "runner_sha256")
    runtime = dict(zip(keys, (str(index) * 64 for index in range(1, 6)), strict=True))
    runtime.update(candidate=trial["candidate"], git_sha="a" * 40, backend="vulkan", engine_build="fixture-build",
                   model_revision="fixture-model-revision", runtime_session_id="fixture-session", run_id="fixture-run",
                   profile="DIRECT_NATIVE" if trial["track"] == "direct_first" else "SDK_NATIVE")
    if trial["track"].startswith("sdk_"):
        runtime.update(sdk_binary_sha256="8" * 64, sdk_version="0.1.24")
    return runtime


def bind(trial, runtime, pins, folder, monkeypatch, **options):
    from benchmarks.slm10 import multitool_release

    hardware = {key: runtime[key] for key in ("host_sha256", "gpu_physical_sha256")}
    monkeypatch.setattr(multitool_release, "require_handoff", lambda root: {"lease": hardware})
    return multitool_release.require_release_binding(trial, runtime, pins, folder, **options)


@pytest.mark.parametrize("track", ["direct_first", "sdk_first", "sdk_repeat"])
def test_read_only_consent_does_not_require_write_or_d25_credentials(tmp_path, monkeypatch, roster, track):
    trial = next(row for row in roster.values() if row["track"] == track and row["category"] == "authorization")
    runtime = runtime_identity(trial)
    pins = fixture_credential_files(tmp_path, runtime)

    result = bind(trial, runtime, pins, tmp_path, monkeypatch)
    assert result["trial_id"] == trial["trial_id"]
    assert all(result[key] == value for key, value in scope_artifacts().items())
    assert result["scope_binding"] == "PASS"
    assert result["formal_release"] == result["physical_execution"] == "NOT_RUN"
    assert result["strict_e2e"] == "BLOCKED"


def test_missing_external_credential_is_not_treated_as_review_approval(tmp_path, monkeypatch, roster):
    trial = next(iter(roster.values()))
    runtime = runtime_identity(trial)
    pins = fixture_credential_files(tmp_path, runtime)
    del pins["release_review"]
    with pytest.raises(ValueError, match="independent credential pins"):
        bind(trial, runtime, pins, tmp_path, monkeypatch)


@pytest.mark.parametrize("scope", ["STRICT", "STATEFUL", "AFFIRMATIVE_WRITE"])
def test_read_only_credentials_cannot_authorize_state_mutation(tmp_path, monkeypatch, roster, scope):
    trial = next(iter(roster.values()))
    runtime = runtime_identity(trial)
    pins = fixture_credential_files(tmp_path, runtime)
    with pytest.raises(ValueError, match="stateful or affirmative"):
        bind(trial, runtime, pins, tmp_path, monkeypatch, release_scope=scope)


def test_mutated_world_and_validly_rehashed_unknown_trial_each_fail(tmp_path, monkeypatch, roster):
    trial = next(iter(roster.values()))
    runtime = runtime_identity(trial)
    pins = fixture_credential_files(tmp_path, runtime)
    forged = trial | {"world_sha256": "0" * 64}
    with pytest.raises(ValueError, match="roster identity"):
        bind(forged, runtime, pins, tmp_path, monkeypatch)
    bare = {key: forged[key] for key in ("suite", "candidate", "case_id", "input_sha256", "world_sha256",
                                        "oracle_sha256", "track", "seed")}
    with pytest.raises(ValueError, match="roster identity"):
        bind(forged | {"trial_id": fingerprint(bare)}, runtime, pins, tmp_path, monkeypatch)


def test_review_credential_must_bind_the_exact_capsule_and_its_evidence(tmp_path, monkeypatch, roster):
    trial = next(iter(roster.values()))
    runtime = runtime_identity(trial)

    def wrong_capsule(bindings):
        bindings["release_review"] = bindings["release_review"] | {"review_capsule_sha256": "1" * 64}

    pins = fixture_credential_files(tmp_path, runtime, change=wrong_capsule)
    with pytest.raises(ValueError, match="release_review"):
        bind(trial, runtime, pins, tmp_path, monkeypatch)
    pins = fixture_credential_files(tmp_path, runtime)
    (tmp_path / "release_review-software-test.json").write_bytes(b'{"changed":true}')
    with pytest.raises(ValueError, match="release_review"):
        bind(trial, runtime, pins, tmp_path, monkeypatch)


def test_versioned_scope_rejects_unknown_callback_even_when_named_like_a_read():
    from benchmarks.slm10.multitool_release import require_read_only_case

    public = {"case_id": "fixture", "tools": {"read_then_publish": {}}}
    world = {"case_id": "fixture", "records": {}, "event": None}
    oracle = {"case_id": "fixture", "actions": [], "schemas": {}}
    with pytest.raises(ValueError, match="read-only"):
        require_read_only_case(public, world, oracle)


def test_all_registered_cases_have_only_read_only_callbacks_and_scope_events():
    from benchmarks.slm10.multitool_release import require_read_only_case

    _, _, cases = registered_roster()
    assert len(cases) == 600
    for case in cases.values():
        require_read_only_case(*case)

    public, world, oracle = next(case for case in cases.values() if case[0]["category"] == "scope_update")
    injected = world | {"event": world["event"] | {"approval": "synthetic-only"}}
    with pytest.raises(ValueError, match="read-only"):
        require_read_only_case(public, injected, oracle)
