"""Synthetic controls for the independent benchmark release intake."""

from pathlib import Path

import pytest

from benchmarks.slm10 import independent_release as release


def test_phase_one_template_binds_exact_planning_cases_without_reading_scenarios(monkeypatch):
    opened = []
    original = Path.read_bytes

    def track(path):
        opened.append(path.name)
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", track)
    template = release.phase_one_template()
    assert len(template["expectations"]) == 800
    assert [row["case_id"] for row in template["expectations"]] == sorted(
        row["case_id"] for row in template["expectations"]
    )
    assert all("scenario_id" not in row and row["branches"] == [] for row in template["expectations"])
    assert "SCENARIO_INPUTS.jsonl" not in opened
    with pytest.raises(ValueError, match="phase-one expectation"):
        release.validate_phase_one(template)


def test_phase_one_digest_ignores_row_order_but_requires_identity_and_content():
    template = release.phase_one_template()
    template["reviewer_id"] = "reviewer-software-control"
    for row in template["expectations"]:
        row["branches"] = [
            {"condition": "if the input is well formed", "required_dependencies": [],
             "acceptable_actions": [], "forbidden_actions": [], "terminal_facts": {"status": "symbolic"},
             "authority_requirements": []},
        ]
    digest = release.validate_phase_one(template)
    template["expectations"].reverse()
    assert release.validate_phase_one(template) == digest
    template["expectations"][0]["scenario_id"] = "premature"
    with pytest.raises(ValueError, match="phase-one expectation"):
        release.validate_phase_one(template)


def test_release_status_without_issuer_or_human_receipts():
    readiness = release.readiness()
    assert set(readiness) == {"MULTITOOL-V2", "AGENTIC-PLAN-V2"}
    assert all(set(scopes) == set(release.SCOPES) for scopes in readiness.values())
    for scopes in readiness.values():
        for row in scopes.values():
            assert row == {"independent_human_review": "NOT_RUN", "authenticated_intake": "BLOCKED",
                           "reconciliation": "NOT_RUN", "issuance": "BLOCKED", "formal_dispatch": "BLOCKED"}
    with pytest.raises(ValueError, match="authorized release trust"):
        release.verify_release("MULTITOOL-V2", release.SCOPES[0], None, None)


def test_known_older_planning_packet_cannot_enter_active_intake():
    historical = release.OUT / "PLANNING_V2_BLIND_REVIEW_PACKET"
    with pytest.raises(ValueError, match="active.*packet"):
        release.active_packet("AGENTIC-PLAN-V2", historical)


def _write(path, value):
    from hashlib import sha256
    from evaluation.aeve.runtime import canonical

    raw = canonical(value) + b"\n"
    path.write_bytes(raw)
    return sha256(raw).hexdigest()


def _sign(folder, filename, role, keys, payload):
    from evaluation.aeve.runtime import canonical

    actor = f"software-control-{role}"
    message = canonical([f"IJ-SLM-RELEASE/{filename}/1.0", actor, payload])
    return _write(folder / filename, {"actor_id": actor, "payload": payload,
                                      "signature": keys[role].sign(message).hex()})


@pytest.fixture(params=["MULTITOOL-V2", "AGENTIC-PLAN-V2"])
def synthetic_bundle(tmp_path, request):
    """Generate ephemeral software controls without giving them release authority."""
    from hashlib import sha256

    ed25519 = pytest.importorskip("cryptography.hazmat.primitives.asymmetric.ed25519")
    from evaluation.aeve.runtime import fingerprint
    from benchmarks.slm10.blind_review_receipt import expectation_digest
    from benchmarks.slm10.planning_roster import object_json

    suite, scope = request.param, release.SCOPES[0]
    keys = {role: ed25519.Ed25519PrivateKey.generate() for role in release.ROLES}
    trust_file = tmp_path / "trust.json"
    trust_pin = _write(trust_file, {"schema_version": "1.0"} | {
        role: {"actor_id": f"software-control-{role}", "ed25519_public_key": private.public_key().public_bytes_raw().hex()}
        for role, private in keys.items()
    })
    _, packet_pin, packet = release.active_packet(suite)
    candidate_pin = packet["candidate_manifest_sha256"]
    if suite == release.MULTITOOL:
        _, trials, _ = release.registered_roster()
        trial_id = next(item["trial_id"] for item in trials.values() if item["category"] == "aggregation")
    else:
        path = release.SOURCE[suite] / "candidate-roster.jsonl"
        trial_id = object_json(path.read_bytes().splitlines()[0])["trial_id"]
    trial, (case_id, scenario_id), roster_pin, oracle_pin = release._candidate_trial(
        suite, scope, trial_id, candidate_pin
    )
    identity = {"suite": suite, "review_scope": scope, "packet_manifest_sha256": packet_pin,
                "candidate_manifest_sha256": candidate_pin}
    reviewer = {"reviewer_id": "reviewer-software-control"}
    phase_pin, phase_fields, verdict_phase = None, {}, {}
    if suite == release.PLANNING:
        phase = release.phase_one_template(scope) | reviewer
        for item in phase["expectations"]:
            item["branches"] = [
                {"condition": "software validation branch", "required_dependencies": [],
                 "acceptable_actions": [], "forbidden_actions": [], "terminal_facts": {"status": "symbolic"},
                 "authority_requirements": []},
            ]
        phase_document = _write(tmp_path / "phase-one.json", phase)
        phase_digest = release.validate_phase_one(phase)
        phase_pin = _sign(tmp_path, "phase-one-receipt.json", "registrar", keys, identity | reviewer | {
            "received_at": "2026-11-28T01:00:00Z", "document_sha256": phase_document,
            "expectations_sha256": phase_digest,
        })
        phase_fields = {"phase_one_receipt_sha256": phase_pin, "scenario_released_at": "2026-11-28T02:00:00Z"}
        verdict_phase = {"phase_one_expectations_sha256": phase_digest}
    expectation = {"acceptable_actions": [], "forbidden_actions": [],
                   "terminal_facts": {"status": "software control"}, "state_invariants": []}
    findings = [{"case_id": case_id, "scenario_id": scenario_id, "status": "PASS",
                 "evidence_refs": [], "independent_expectation": expectation, "rationale": "Software control."}]
    verdict = _write(tmp_path / "verdict.json", reviewer | verdict_phase | {
        "packet": packet["packet"], "packet_manifest_sha256": packet_pin, "review_scope": scope,
        "reviewed_date": "2026-11-28", "independence_attested": True, "partition_status": "PASS",
        "expectations_sha256": expectation_digest(findings), "semantic_duplicate_findings": [], "findings": findings,
    })
    final_payload = identity | reviewer | phase_fields | {
        "identity_and_independence_verified": True, "verdict_sha256": verdict, "received_at": "2026-11-28T03:00:00Z",
    }
    receipt_pin = _sign(tmp_path, "final-receipt.json", "registrar", keys, final_payload)
    binding = identity | {"case_id": case_id, "scenario_id": scenario_id,
                          "final_receipt_sha256": receipt_pin, "phase_one_receipt_sha256": phase_pin}
    reconciliation_payload = binding | {
        "reconciled_at": "2026-11-28T04:00:00Z", "partition_status": "PASS",
        "partition_rationale": "Software control.", "status": "PASS",
        "oracle_witness_sha256": oracle_pin, "independent_expectation_sha256": fingerprint(expectation),
        "rationale": "Software control.", "discrepancies": [],
    }
    reconciliation_pin = _sign(tmp_path, "reconciliation.json", "reconciler", keys, reconciliation_payload)
    runtime = dict.fromkeys(("engine_binary_sha256", "model_sha256", "host_sha256", "gpu_physical_sha256",
                             "runner_sha256"), "1" * 64)
    handoff_raw = (release.ROOT / release.HANDOFF).read_bytes()
    handoff = object_json(handoff_raw)
    runtime.update({name: handoff["lease"][name] for name in ("host_sha256", "gpu_physical_sha256")})
    runtime.update(git_sha="b" * 40, backend="vulkan", profile="DIRECT_NATIVE",
                   candidate=trial["candidate"], engine_build="software-control", model_revision="software-control",
                   runtime_session_id="software-control", run_id="software-control")
    evidence = {role: {"path": f"{role}.json", "sha256": _write(tmp_path / f"{role}.json", {"control": role})}
                for role in release.BINDING_EVIDENCE}
    issuance_payload = binding | {
        "trial_id": trial_id, "roster_sha256": roster_pin, "reconciliation_sha256": reconciliation_pin,
        "issued_at": "2026-11-28T05:00:00Z", "status": "PASS", "runtime": runtime,
        "bindings_evidence": evidence, "qualified_requirements": release.SCOPE_REQUIREMENTS[scope],
        "evaluation_contract_sha256": sha256(release.EVALUATION_CONTRACT.read_bytes()).hexdigest(),
        "handoff_sha256": sha256(handoff_raw).hexdigest(),
    }
    _sign(tmp_path, "issuance.json", "issuer", keys, issuance_payload)
    return {"options": (suite, scope, trust_file, trust_pin),
            "arguments": {"folder": tmp_path, "trial_id": trial_id, "runtime": runtime},
            "keys": keys, "final": final_payload, "reconciliation": reconciliation_payload}


def test_authenticates_exact_candidate_scope_and_still_blocks_dispatch(synthetic_bundle):
    options, arguments = synthetic_bundle["options"], synthetic_bundle["arguments"]
    report = release.verify_release(*options, **arguments)
    assert report["authenticated_intake"] == "PASS"
    assert report["discrepancy_reconciliation"] == "PASS"
    assert report["issuer_record_verification"] == "PASS"
    assert report["formal_dispatch"] == "BLOCKED"
    assert report["review_dispositions"]["PASS"] == 1
    assert report["review_dispositions"]["NOT_RUN"] > 0
    with pytest.raises(ValueError, match="physical dispatcher registration"):
        release.require_formal_dispatch(*options, **arguments)
    suite, _, trust_file, trust_pin = options
    with pytest.raises(ValueError, match="scope binding"):
        release.verify_release(suite, "STATEFUL", trust_file, trust_pin, **arguments)
    different_runtime = arguments["runtime"] | {"model_sha256": "0" * 64}
    with pytest.raises(ValueError, match="release issuance differs"):
        release.verify_release(*options, **(arguments | {"runtime": different_runtime}))


def test_rejects_tampered_signature_and_signed_unresolved_discrepancy(synthetic_bundle):
    options, arguments = synthetic_bundle["options"], synthetic_bundle["arguments"]
    folder = arguments["folder"]
    from benchmarks.slm10.planning_roster import object_json

    issuance = object_json((folder / "issuance.json").read_bytes())
    issuance["signature"] = "0" * 128
    _write(folder / "issuance.json", issuance)
    with pytest.raises(ValueError, match="issuer signature"):
        release.verify_release(*options, **arguments)
    discrepancy = {"component": "world", "independent_expectation": "One consequence.",
                   "candidate_expectation": "Another consequence.", "counterevidence": "Synthetic control.",
                   "impact": "The requested release scope."}
    payload = synthetic_bundle["reconciliation"] | {"discrepancies": [discrepancy]}
    _sign(folder, "reconciliation.json", "reconciler", synthetic_bundle["keys"], payload)
    with pytest.raises(ValueError, match="unresolved"):
        release.verify_release(*options, **arguments)


def test_rejects_missing_attested_independence_and_premature_disclosure(synthetic_bundle):
    options, arguments = synthetic_bundle["options"], synthetic_bundle["arguments"]
    folder = arguments["folder"]
    final = synthetic_bundle["final"]
    _sign(folder, "final-receipt.json", "registrar", synthetic_bundle["keys"],
          final | {"identity_and_independence_verified": False})
    with pytest.raises(ValueError, match="reviewer independence"):
        release.verify_release(*options, **arguments)
    if options[0] == release.PLANNING:
        _sign(folder, "final-receipt.json", "registrar", synthetic_bundle["keys"],
              final | {"scenario_released_at": "2026-11-28T00:59:59Z"})
        with pytest.raises(ValueError, match="before scenario disclosure"):
            release.verify_release(*options, **arguments)


@pytest.mark.parametrize("synthetic_bundle", ["AGENTIC-PLAN-V2"], indirect=True)
def test_authenticates_phase_one_before_reading_scenario_input(synthetic_bundle, monkeypatch):
    options, arguments = synthetic_bundle["options"], synthetic_bundle["arguments"]
    _, scope, trust_file, trust_pin = options
    original = Path.read_bytes

    def reject_scenario_read(path):
        assert path.name not in ("SCENARIO_INPUTS.jsonl", "final-receipt.json")
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", reject_scenario_read)
    verified = release.verify_phase_one_receipt(scope, trust_file, trust_pin, folder=arguments["folder"])
    assert verified["phase_one_receipt_sha256"] == synthetic_bundle["final"]["phase_one_receipt_sha256"]
    assert verified["phase_one_receipt_verification"] == "PASS"
