"""Verify independent review, reconciliation and issuer records for the active candidates."""

import argparse
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import re

from evaluation.aeve.gpu_handoff import HANDOFF
from evaluation.aeve.runtime import ROOT, canonical, fingerprint

from .blind_review_packets import scenario_id
from .blind_review_receipt import (
    ACTIVE_PACKETS, MULTITOOL, OUT, PLANNING, SCOPES, STATUS, active_packet,
    inspect_review, key, phase_one_template, validate_phase_one,
)
from .multitool_release import (
    READ_ONLY_MECHANICS, _runtime_identity, require_read_only_case,
)
from .multitool_v2_revised import FOLDER as MULTITOOL_SOURCE
from .multitool_v2_statistics import registered_roster
from .planning_partition_candidate import OUT as PLANNING_SOURCE
from .planning_roster import is_sha256, object_json, pinned_content
from .planning_world_allocation import EVALUATION_CONTRACT, READ_ONLY_LEVELS

ROLES = ("registrar", "reconciler", "issuer")
BINDING_EVIDENCE = ("matched_runner", "runtime_admission", "hardware_handoff", "evaluation")
MECHANICS = dict.fromkeys(READ_ONLY_MECHANICS, "PASS")
SCOPE_REQUIREMENTS = {
    SCOPES[0]: MECHANICS,
    SCOPES[1]: {"D23": "PASS"},
    SCOPES[2]: {"D23": "PASS", "D24_affirmative": "PASS"},
    SCOPES[3]: dict.fromkeys(("D12", "D23", "D24_affirmative", "D25"), "PASS"),
}
SOURCE = {MULTITOOL: MULTITOOL_SOURCE, PLANNING: PLANNING_SOURCE}
DISCREPANCY_COMPONENTS = {"phase_one", "prompt", "world", "oracle", "witness", "evaluator", "partition"}


def readiness():
    return {
        suite: {scope: {"independent_human_review": "NOT_RUN", "authenticated_intake": "BLOCKED",
                        "reconciliation": "NOT_RUN", "issuance": "BLOCKED", "formal_dispatch": "BLOCKED"}
                for scope in SCOPES}
        for suite in ACTIVE_PACKETS
    }


def _require_fields(record, fields, label):
    if not isinstance(record, dict) or record.keys() != set(fields):
        raise ValueError(f"{label} has an invalid field set")


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _record(folder, name, pin):
    return object_json(pinned_content(folder, name, pin).decode("utf-8"))


def _trust(trust_file, trust_sha256):
    if trust_file is None or not is_sha256(trust_sha256):
        raise ValueError("authorized release trust requires an independently pinned key registry")
    raw = trust_file.read_bytes()
    if sha256(raw).hexdigest() != trust_sha256:
        raise ValueError("authorized release trust differs from its independent digest")
    registry = object_json(raw.decode("utf-8"))
    _require_fields(registry, ("schema_version", *ROLES), "authorized release trust")
    if registry["schema_version"] != "1.0":
        raise ValueError("unsupported authorized release trust version")
    actors = [registry[role] for role in ROLES]
    for role, actor in zip(ROLES, actors, strict=True):
        _require_fields(actor, ("actor_id", "ed25519_public_key"), f"authorized {role}")
        if not _text(actor["actor_id"]) or not is_sha256(actor["ed25519_public_key"]):
            raise ValueError(f"invalid authorized {role} identity or public key")
    for field in ("actor_id", "ed25519_public_key"):
        if len({actor[field] for actor in actors}) != len(actors):
            raise ValueError("release trust requires separate registrar, reconciler and issuer")
    return registry


def _signed(folder, name, role, trust):
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    raw = (folder / name).read_bytes()
    record = object_json(raw.decode("utf-8"))
    _require_fields(record, ("actor_id", "payload", "signature"), role)
    actor, payload, signature = record["actor_id"], record["payload"], record["signature"]
    identity = trust[role]
    if (actor != identity["actor_id"] or not isinstance(payload, dict)
            or not isinstance(signature, str) or not re.fullmatch(r"[0-9a-f]{128}", signature)):
        raise ValueError(f"invalid authorized {role} record")
    message = canonical([f"IJ-SLM-RELEASE/{name}/1.0", actor, payload])
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(identity["ed25519_public_key"])).verify(
            bytes.fromhex(signature), message
        )
    except InvalidSignature:
        raise ValueError(f"{role} signature verification failed") from None
    return payload, sha256(raw).hexdigest()


def _utc(value):
    if not isinstance(value, str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value) is None:
        raise ValueError("review record requires a UTC timestamp")
    return datetime.fromisoformat(value)


def _packet_identity(suite, scope):
    packet, packet_pin, manifest = active_packet(suite)
    return packet, {
        "suite": suite, "review_scope": scope, "packet_manifest_sha256": packet_pin,
        "candidate_manifest_sha256": manifest["candidate_manifest_sha256"],
    }


def _authenticated_phase_one(folder, trust, identity):
    phase, phase_pin = _signed(folder, "phase-one-receipt.json", "registrar", trust)
    _require_fields(phase, (*identity, "reviewer_id", "document_sha256",
                            "expectations_sha256", "received_at"), "phase-one receipt")
    if (any(phase[name] != value for name, value in identity.items())
            or any(phase["reviewer_id"] == trust[role]["actor_id"] for role in ROLES)):
        raise ValueError("Planning phase-one receipt differs from exact reviewer or scope binding")
    document = _record(folder, "phase-one.json", phase["document_sha256"])
    if (document.get("reviewer_id") != phase["reviewer_id"]
            or document.get("review_scope") != phase["review_scope"]
            or validate_phase_one(document) != phase["expectations_sha256"]):
        raise ValueError("Planning phase-one receipt differs from its exact expectation document")
    return document, phase, phase_pin, _utc(phase["received_at"])


def verify_phase_one_receipt(scope, trust_file, trust_sha256, *, folder):
    """Authenticate Planning's case-only receipt while the scenario packet is sealed."""
    if scope not in (*SCOPES, "CONTENT_AND_PARTITION"):
        raise ValueError("Planning phase-one receipt requires an exact review scope")
    trust = _trust(trust_file, trust_sha256)
    _, identity = _packet_identity(PLANNING, scope)
    _, phase, pin, _ = _authenticated_phase_one(folder, trust, identity)
    return identity | {"phase_one_receipt_sha256": pin, "expectations_sha256": phase["expectations_sha256"],
                       "phase_one_receipt_verification": "PASS", "formal_dispatch": "BLOCKED"}


def _authenticated_review(suite, scope, folder, trust):
    packet, identity = _packet_identity(suite, scope)
    final, final_pin = _signed(folder, "final-receipt.json", "registrar", trust)
    planning_fields = ("phase_one_receipt_sha256", "scenario_released_at") if suite == PLANNING else ()
    _require_fields(final, (*identity, "reviewer_id", "identity_and_independence_verified",
                            "verdict_sha256", "received_at", *planning_fields), "final receipt")
    if (any(final[name] != value for name, value in identity.items())
            or final["identity_and_independence_verified"] is not True
            or any(final["reviewer_id"] == trust[role]["actor_id"] for role in ROLES)):
        raise ValueError("authorized receipt lacks exact reviewer independence or release scope binding")
    verdict = pinned_content(folder, "verdict.json", final["verdict_sha256"])
    received = _utc(final["received_at"])
    phase_one = phase_pin = digest = None
    if suite == PLANNING:
        phase_one, phase, phase_pin, first_received = _authenticated_phase_one(folder, trust, identity)
        if (phase["reviewer_id"] != final["reviewer_id"]
                or phase_pin != final["phase_one_receipt_sha256"]
                or not first_received < _utc(final["scenario_released_at"]) <= received):
            raise ValueError("Planning first-phase receipt was not authenticated before scenario disclosure")
        digest = phase["expectations_sha256"]
    review, _, report = inspect_review(
        suite, packet, verdict, final["verdict_sha256"], phase_one=phase_one,
        phase_one_sha256=digest,
    )
    if (review["reviewer_id"] != final["reviewer_id"] or review["review_scope"] != scope
            or review["reviewed_date"] > received.date().isoformat()):
        raise ValueError("review verdict differs from its authenticated intake")
    return identity, review, report, final_pin, phase_pin, received


def _candidate_trial(suite, scope, trial_id, candidate_pin):
    folder = SOURCE[suite]
    manifest = _record(folder, "manifest.json", candidate_pin)
    if suite == MULTITOOL:
        if scope in ("STATEFUL", "AFFIRMATIVE_WRITE"):
            raise ValueError("MULTITOOL 0.3 has no stateful or affirmative-write roster")
        registered_pin, trials, cases = registered_roster()
        if registered_pin != candidate_pin:
            raise ValueError("MULTITOOL release candidate differs from the active packet")
        trial = trials.get(trial_id)
        if trial is None:
            raise ValueError("MULTITOOL trial falls outside the exact candidate roster")
        public, world, oracle = cases[trial["case_id"]]
        if scope == SCOPES[0]:
            require_read_only_case(public, world, oracle)
        roster_pin = manifest["files"]["roster.json"]
        row = trial["case_id"], None
        oracle_witness_pin = fingerprint(oracle)
    else:
        pins = manifest["artifacts"]
        roster_pin = pins["candidate-roster.jsonl"]
        trials = map(object_json, pinned_content(folder, "candidate-roster.jsonl", roster_pin).splitlines())
        trial = next((row for row in trials if row["trial_id"] == trial_id), None)
        if trial is None:
            raise ValueError("Planning trial falls outside the exact candidate roster")
        if scope == SCOPES[0] and trial["level"] not in READ_ONLY_LEVELS:
            raise ValueError("Planning read-only scope excludes stateful levels")
        controls = map(object_json, pinned_content(folder, "holdout-controls.jsonl", pins["holdout-controls.jsonl"]).splitlines())
        source = next(row for row in controls if row["case_id"] == trial["case_id"])
        world = next(row for row in source["worlds"] if row["world_id"] == trial["world_id"])
        if fingerprint(world) != trial["world_sha256"]:
            raise ValueError("Planning selected world differs from the exact candidate roster")
        writes = any(step["tool"] == "commit" for step in world["steps"])
        if scope == "STATEFUL" and (trial["level"] in READ_ONLY_LEVELS or writes):
            raise ValueError("Planning stateful scope requires a stateful world without an affirmative commit")
        if scope == "AFFIRMATIVE_WRITE" and not writes:
            raise ValueError("Planning affirmative-write scope requires the selected world to include a commit")
        row = trial["case_id"], scenario_id(trial["case_id"], world)
        oracle_witness_pin = fingerprint({"world": world, "witness": source["witness"]})
    return trial, row, roster_pin, oracle_witness_pin


def _reconciled(folder, trust, expected, independent, oracle_witness_pin, received):
    result, result_pin = _signed(folder, "reconciliation.json", "reconciler", trust)
    _require_fields(result, (*expected, "reconciled_at", "partition_status", "partition_rationale",
                             "status", "oracle_witness_sha256", "independent_expectation_sha256",
                             "rationale", "discrepancies"), "reconciliation")
    if (any(result[name] != value for name, value in expected.items())
            or result["oracle_witness_sha256"] != oracle_witness_pin
            or result["independent_expectation_sha256"] != fingerprint(independent["independent_expectation"])
            or not _text(result["rationale"]) or not _text(result["partition_rationale"])
            or _utc(result["reconciled_at"]) < received or not isinstance(result["discrepancies"], list)):
        raise ValueError("reconciliation differs from its authenticated review, oracle or witness")
    for finding in result["discrepancies"]:
        fields = ("component", "independent_expectation", "candidate_expectation", "counterevidence", "impact")
        _require_fields(finding, fields, "discrepancy")
        if finding["component"] not in DISCREPANCY_COMPONENTS or any(not _text(finding[field]) for field in fields):
            raise ValueError("reconciliation discrepancy requires evidence and affected scope")
    if result["status"] != "PASS" or result["partition_status"] != "PASS" or result["discrepancies"]:
        raise ValueError("release is blocked by unresolved review or partition reconciliation")
    return result_pin, _utc(result["reconciled_at"])


def _issued(folder, trust, expected, suite, scope, trial, runtime, reconciled_at):
    issuance, issuance_pin = _signed(folder, "issuance.json", "issuer", trust)
    _require_fields(issuance, (*expected, "issued_at", "status", "runtime", "bindings_evidence",
                               "qualified_requirements", "evaluation_contract_sha256", "handoff_sha256"),
                    "release issuance")
    # Track names differ, but both candidate suites share the same exact runtime identities.
    track = "direct_first" if trial["track"].startswith("direct_") else "sdk_first"
    identity = _runtime_identity(trial | {"track": track}, runtime)
    expected_contract = sha256(EVALUATION_CONTRACT.read_bytes()).hexdigest()
    raw_handoff = (ROOT / HANDOFF).read_bytes()
    handoff = object_json(raw_handoff)
    if (any(issuance[name] != value for name, value in expected.items()) or issuance["status"] != "PASS"
            or issuance["runtime"] != identity or issuance["qualified_requirements"] != SCOPE_REQUIREMENTS[scope]
            or issuance["evaluation_contract_sha256"] != expected_contract
            or issuance["handoff_sha256"] != sha256(raw_handoff).hexdigest()
            or handoff["status"] != "PASS"
            or any(identity[name] != handoff["lease"][name] for name in ("host_sha256", "gpu_physical_sha256"))
            or _utc(issuance["issued_at"]) < reconciled_at):
        raise ValueError("release issuance differs from the reviewed trial, scope, runtime, handoff or evaluator")
    if suite == PLANNING and trial["evaluation_contract_sha256"] != expected_contract:
        raise ValueError("Planning evaluation contract differs from the candidate roster")
    evidence = issuance["bindings_evidence"]
    _require_fields(evidence, BINDING_EVIDENCE, "release binding evidence")
    for role in BINDING_EVIDENCE:
        entry = evidence[role]
        _require_fields(entry, ("path", "sha256"), role)
        if not pinned_content(folder, entry["path"], entry["sha256"]).strip():
            raise ValueError(f"release evidence is empty for {role}")
    if len({entry["sha256"] for entry in evidence.values()}) != len(evidence):
        raise ValueError("release requires separate runner, runtime, hardware and evaluator evidence")
    return issuance_pin


def verify_release(suite, scope, trust_file, trust_sha256, *, folder=None, trial_id=None, runtime=None):
    """Verify external records for one trial and one scope without authorizing physical dispatch."""
    if suite not in ACTIVE_PACKETS or scope not in SCOPES:
        raise ValueError("formal release requires one exact suite and release scope")
    trust = _trust(trust_file, trust_sha256)
    if folder is None or not is_sha256(trial_id):
        raise ValueError("release requires a private bundle and exact trial identity")
    identity, review, report, receipt_pin, phase_pin, received = _authenticated_review(suite, scope, folder, trust)
    trial, (case_id, scenario), roster_pin, oracle_pin = _candidate_trial(
        suite, scope, trial_id, identity["candidate_manifest_sha256"]
    )
    finding = next((item for item in review["findings"] if key(item) == (case_id, scenario)), None)
    if finding is None or finding["status"] != "PASS" or review["partition_status"] != "PASS":
        raise ValueError("release requires a passing independent finding and partition review for the exact case")
    review_binding = identity | {
        "final_receipt_sha256": receipt_pin, "phase_one_receipt_sha256": phase_pin,
        "case_id": case_id, "scenario_id": scenario,
    }
    reconciliation_pin, reconciled_at = _reconciled(folder, trust, review_binding, finding, oracle_pin, received)
    release_binding = review_binding | {"trial_id": trial_id, "roster_sha256": roster_pin,
                                        "reconciliation_sha256": reconciliation_pin}
    issuance_pin = _issued(folder, trust, release_binding, suite, scope, trial, runtime, reconciled_at)
    return release_binding | {
        "issuer_record_sha256": issuance_pin, "authenticated_intake": "PASS",
        "discrepancy_reconciliation": "PASS", "issuer_record_verification": "PASS",
        "formal_dispatch": "BLOCKED", "physical_execution": "NOT_RUN",
        "strict_e2e": "BLOCKED", "review_dispositions": report["dispositions"],
        "dispatch_blocker": "exact-candidate physical dispatcher registration is pending",
    }


def require_formal_dispatch(suite, scope, trust_file, trust_sha256, *, folder=None, trial_id=None, runtime=None):
    """Provide a fail-closed entry point while no exact-candidate launchers are registered."""
    report = verify_release(suite, scope, trust_file, trust_sha256, folder=folder, trial_id=trial_id, runtime=runtime)
    raise ValueError(report["dispatch_blocker"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_subparsers(required=True, dest="action")
    action.add_parser("status")
    phase = action.add_parser("verify-phase-one")
    phase.add_argument("--scope", choices=(*SCOPES, "CONTENT_AND_PARTITION"), required=True)
    verify = action.add_parser("verify")
    verify.add_argument("--suite", choices=tuple(ACTIVE_PACKETS), required=True)
    verify.add_argument("--scope", choices=SCOPES, required=True)
    for command in (phase, verify):
        command.add_argument("--trust", type=Path, required=True)
        command.add_argument("--trust-sha256", required=True)
        command.add_argument("--bundle", type=Path, required=True)
    verify.add_argument("--trial-id", required=True)
    verify.add_argument("--runtime", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.action == "status":
            result = readiness()
        elif args.action == "verify-phase-one":
            result = verify_phase_one_receipt(args.scope, args.trust, args.trust_sha256, folder=args.bundle)
        else:
            result = verify_release(args.suite, args.scope, args.trust, args.trust_sha256,
                                    folder=args.bundle, trial_id=args.trial_id,
                                    runtime=object_json(args.runtime.read_text(encoding="utf-8")))
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
