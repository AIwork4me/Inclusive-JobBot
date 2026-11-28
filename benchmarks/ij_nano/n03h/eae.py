"""Trusted EAE integration for the 48H campaign (order sections 3.2/4).

Consumes the pinned EAE snapshot at ``runtime/eae_pin/3cdd066`` (git
archive of committed objects only — never the sibling session's live
worktree), re-verifies every file digest against ``PIN_MANIFEST.json``,
registers the trusted ExecutionEvidence through the REAL contract
(replicating the EAE release scripts' registration byte-for-byte on the
pinned artifacts), and hands the IJ-NANO ``EAEExecutionAuthorizationProvider``
the pinned module so physical dispatch is authorized fail-closed.

The registration re-derives every readiness flag from digest-verified
artifacts inside the pin; caller-asserted Booleans are never consulted.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]

#: current pinned EAE revision (bumped only by re-pin + re-verify)
CURRENT_PIN_REV = "7a3e8dc"
PIN = ROOT / "runtime" / "eae_pin" / CURRENT_PIN_REV
PIN_SRC = PIN / "src"
EVID = PIN / "evidence" / "IJEVAL" / "EA03_N03"
AUTH1 = PIN / "evidence" / "IJEVAL" / "AUTH1"
AUTH2 = PIN / "evidence" / "IJEVAL" / "AUTH2"
AUTH2B = PIN / "evidence" / "IJEVAL" / "AUTH2B"
EA13 = PIN / "evidence" / "IJEVAL" / "EA13"
EA13B = PIN / "evidence" / "IJEVAL" / "EA13B"
EA18 = PIN / "evidence" / "IJEVAL" / "EA18"
SRC = PIN_SRC / "eval_assurance"

MODELS = ["MiniCPM5-2B", "LFM3-1.7B", "Qwen3.5-2B"]
PRIMITIVES_BATCH_A = [f"C{i:02d}" for i in range(1, 9)]
PRIMITIVES_BATCH_B = [f"C{i:02d}" for i in range(9, 17)]

SCOPES = {
    "AUTH-1": {
        "experiment_id": "N03-AUTH1-DIAGNOSTIC-PANEL-v1",
        "auth_level": "AUTH-1",
        "primitives": PRIMITIVES_BATCH_A,
        "roster_file": AUTH1 / "diagnostic_roster.json",
        "dataset_dir": EVID / "pinned",
        "acceptance_file": AUTH1 / "auth1_acceptance.json",
        "canary_file": AUTH1 / "canary_integration.json",
        "breaker_file": AUTH1 / "breaker_drill.json",
        "state_file": AUTH1 / "authoritative_state.json",
        "witness_file": EVID / "dualpath_witnesses.json",
        "mutation_file": EVID / "production_mutation_campaign.json",
        "legs": "a",
        "ea13_scope_file": None,
        "ea18_scope_file": None,
    },
    "AUTH-2": {
        "experiment_id": "N03-AUTH2-DEVELOPMENT-BATCH-A-v1",
        "auth_level": "AUTH-2",
        "primitives": PRIMITIVES_BATCH_A,
        "roster_file": AUTH2 / "development_roster_480.json",
        "dataset_dir": EVID / "pinned",
        "acceptance_file": AUTH2 / "auth2_shared_core_acceptance.json",
        "canary_file": AUTH1 / "canary_integration.json",
        "breaker_file": AUTH1 / "breaker_drill.json",
        "state_file": AUTH2 / "authoritative_state.json",
        "witness_file": EVID / "dualpath_witnesses.json",
        "mutation_file": EVID / "production_mutation_campaign.json",
        "legs": "a",
        "ea13_scope_file": EA13 / "primitive_qualification.json",
        "ea18_scope_file": EA18 / "independent_acceptance.json",
    },
    "AUTH-2B": {
        "experiment_id": "N03-AUTH2-DEVELOPMENT-BATCH-B-v1",
        "auth_level": "AUTH-2",
        "primitives": PRIMITIVES_BATCH_B,
        "roster_file": AUTH2B / "development_roster_480.json",
        "dataset_dir": EVID / "pinned_full",
        "acceptance_file": AUTH2B / "auth2b_shared_core_acceptance.json",
        "canary_file": AUTH2B / "canary_integration.json",
        "breaker_file": AUTH2B / "breaker_drill.json",
        "state_file": AUTH2B / "authoritative_state.json",
        "witness_file": EVID / "dualpath_witnesses_batch_b.json",
        "mutation_file": EVID / "production_mutation_campaign_batch_b.json",
        "legs": "b",
        "ea13_scope_file": EA13B / "primitive_qualification_batch_b.json",
        "ea18_scope_file": EA18 / "independent_acceptance.json",
    },
}

#: expected authorization checksums per scope (from the EAE releases);
#: bootstrap fails loudly when a fresh issuance does not reproduce them.
#: This closes the cross-batch certificate-confusion hazard: at a
#: revision where a batch's own certificate is revoked, registration
#: would otherwise silently cite whichever certificate IS valid and
#: issue an authorization that never matches the released one.
EXPECTED_CHECKSUMS = {
    "AUTH-1": "4a09f5253a3aaa164720be30643aecf7a39aa7dbbd7a635066a7adc886135da6",
    "AUTH-2": "a22bcc68b8e199741227ce4360035292abd24103ecd1df7f0182413f1ee57ebc",
    "AUTH-2B": "fc4cdb2c0d36f189dd9f0249edbba2310a5b957f3ecd40b99af8a1c8d2a9133d",
}


def sha256_file(p: pathlib.Path) -> str:
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def import_pin_module(dotted: str):
    """Import a module from the pinned snapshot (path-only; no evidence
    registration). For containment components usable pre-authorization."""
    src_str = str(PIN_SRC)
    if src_str not in sys.path:
        sys.path.insert(0, src_str)
    import importlib
    return importlib.import_module(dotted)


def verify_pin() -> dict:
    """Fail-closed: recompute every pinned-file digest against
    PIN_MANIFEST.json; any mismatch/absence refuses integration."""
    manifest_path = PIN / "PIN_MANIFEST.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"pin manifest missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    problems = []
    seen = 0
    for rel, want in manifest["files_sha256"].items():
        p = PIN / rel
        if not p.is_file():
            problems.append(f"missing: {rel}")
            continue
        seen += 1
        if sha256_file(p) != want:
            problems.append(f"digest mismatch: {rel}")
    extra = [str(p.relative_to(PIN)).replace("\\", "/")
             for p in PIN.rglob("*")
             if p.is_file() and "__pycache__" not in p.parts and
             str(p.relative_to(PIN)).replace("\\", "/")
             not in manifest["files_sha256"] and p.name != "PIN_MANIFEST.json"]
    if extra:
        problems.append(f"unpinned files present: {extra[:5]}")
    if problems:
        raise RuntimeError("EAE pin verification FAILED (fail-closed): "
                           + "; ".join(problems[:10]))
    return {"files_verified": seen, "pin": manifest["pin"],
            "subtrees": manifest["subtrees"]}


def bootstrap(scope: str):
    """Register the trusted ExecutionEvidence for ``scope`` ("AUTH-1" or
    "AUTH-2") on the pinned module and return everything the campaign
    controller needs. Replicates the corresponding EAE release script's
    registration call exactly (auth1_release.py / auth2_release.py at
    3cdd066) on pinned paths."""
    if scope not in SCOPES:
        raise ValueError(f"unknown scope {scope!r}")
    pin_report = verify_pin()
    sys.dont_write_bytecode = True     # keep the pin dir source-only

    src_str = str(PIN_SRC)
    if src_str not in sys.path:
        sys.path.insert(0, src_str)

    from eval_assurance import canary as canary_mod
    from eval_assurance.authoritative import AuthoritativeQualificationState
    from eval_assurance.breaker import CircuitBreaker
    from eval_assurance.compat import execution_authorization
    from eval_assurance.dualpath import DualPathSession
    from eval_assurance.qualification.store import CertificateStore

    sc = SCOPES[scope]
    roster_file = sc["roster_file"]
    dataset_file = sc["dataset_dir"] / "n03_cases.public.jsonl"
    expectations_file = sc["dataset_dir"] / "n03_dev_expectations.jsonl"

    # Runtime-mutable EAE state (registry + authoritative state) is
    # COPIED from the pristine pin into the campaign state area on
    # first use: the pin stays digest-immutable; the authoritative
    # state is durable and legitimately updated (evidence-generation
    # bookkeeping) — in OUR workdir, never in the pin.
    import shutil
    runtime_state = ROOT / "runs" / "n03h" / "_eae_state" / \
        sc["experiment_id"]
    runtime_state.mkdir(parents=True, exist_ok=True)
    registry_copy = runtime_state / "registry.json"
    state_copy = runtime_state / "authoritative_state.json"
    if not registry_copy.is_file():
        shutil.copy2(EVID / "certificates" / "registry.json",
                     registry_copy)
    if not state_copy.is_file():
        shutil.copy2(sc["state_file"], state_copy)

    store = CertificateStore.load_registry(registry_copy)
    state = AuthoritativeQualificationState(store, state_copy)

    if sc["legs"] == "b":
        parser_file = SRC / "production" / "parser_b.py"
        evaluator_file = SRC / "production" / "evaluator_b.py"
        interpreter_file = SRC / "reference" / "interpreter_b.py"
        oracle_file = SRC / "reference" / "oracle_b.py"
    else:
        parser_file = SRC / "production" / "parser.py"
        evaluator_file = SRC / "production" / "evaluator.py"
        interpreter_file = SRC / "reference" / "interpreter.py"
        oracle_file = SRC / "reference" / "oracle.py"

    execution_authorization.clear_execution_evidence()
    dispatch_limits = {"max_trials": len(
        json.loads(roster_file.read_text(encoding="utf-8"))["slots"])}
    evidence = execution_authorization.register_trusted_execution_evidence(
        authoritative_state=state,
        experiment_id=sc["experiment_id"],
        auth_purpose=sc["auth_level"],
        primitives=sc["primitives"],
        protocols=["chat"], models=MODELS,
        dataset_file=dataset_file,
        roster_file=roster_file,
        parser_file=parser_file,
        evaluator_file=evaluator_file,
        interpreter_file=interpreter_file,
        oracle_file=oracle_file,
        certificate_store=store,
        shared_core_acceptance_file=sc["acceptance_file"],
        canary_evidence_file=sc["canary_file"],
        breaker_evidence_file=sc["breaker_file"],
        witness_suite_file=sc["witness_file"],
        mutation_report_file=sc["mutation_file"],
        ea13_scope_file=sc["ea13_scope_file"],
        ea18_scope_file=sc["ea18_scope_file"],
        dispatch_limits=dispatch_limits)

    # -- the REAL IJ-NANO consumer provider, pinned to the contract ----
    from benchmarks.ij_nano.n03.authorization import (
        DispatchGate, EAEExecutionAuthorizationProvider)
    provider = EAEExecutionAuthorizationProvider(
        pinned_revision=execution_authorization.EAE_CONTRACT_REVISION,
        contract_module="eval_assurance.compat.execution_authorization")
    gate = DispatchGate(provider)

    # -- verify the fresh authorization reproduces the released checksum -
    released = EXPECTED_CHECKSUMS.get(scope)
    if released is not None:
        try:
            probe = execution_authorization.issue_execution_authorization(
                experiment_id=sc["experiment_id"],
                dataset_digest=sha256_file(dataset_file),
                roster_digest=sha256_file(roster_file),
                primitives=sc["primitives"],
                protocols=["chat"], models=MODELS,
                auth_level=sc["auth_level"],
                eae_revision=execution_authorization.EAE_CONTRACT_REVISION)
        except Exception as e:                     # noqa: BLE001
            raise RuntimeError(
                f"scope {scope} is not consumable at pin "
                f"{CURRENT_PIN_REV}: fresh issuance failed fail-closed "
                f"({e}); released checksum {released[:16]}… cannot be "
                "reproduced (scope blocked at this revision)") from e
        if probe.checksum != released:
            raise RuntimeError(
                f"released checksum mismatch for {scope}: fresh issuance "
                f"{probe.checksum} != released {released} — the fresh "
                "authorization does not match the EAE release (cross-"
                "batch certificate confusion or revoked chain refused)")

    # -- canary witnesses (software-error rows excluded, as at release) -
    witnesses = json.loads(
        sc["witness_file"].read_text(encoding="utf-8"))["rows"]
    exps = {json.loads(l)["case_id"]: json.loads(l) for l in
            expectations_file.read_text(encoding="utf-8")
            .splitlines() if l.strip()}
    cases_by_id = {json.loads(l)["case_id"]: json.loads(l) for l in
                   dataset_file.read_text(encoding="utf-8")
                   .splitlines() if l.strip()}

    # -- canary leg injection (same override the EAE release scripts use) -
    canary_legs = None
    if sc["legs"] == "b":
        from eval_assurance.production import evaluator_b, parser_b
        canary_legs = {"production_parser": parser_b.parse_response,
                       "production_evaluator":
                           evaluator_b.ProductionEvaluatorB()}

    return {
        "scope": scope,
        "pin_report": pin_report,
        "canary_legs": canary_legs,
        "contract": execution_authorization,
        "evidence": evidence,
        "provider": provider,
        "gate": gate,
        "store": store,
        "state": state,
        "roster_file": roster_file,
        "dataset_file": dataset_file,
        "legs": sc["legs"],
        "expectations": exps,
        "cases_by_id": cases_by_id,
        "witnesses": [w for w in witnesses if w["kind"] != "software-error"],
        "modules": {
            "canary": canary_mod,
            "execution_authorization": execution_authorization,
            "CircuitBreaker": CircuitBreaker,
            "DualPathSession": DualPathSession,
        },
        "identity": {
            "experiment_id": sc["experiment_id"],
            "auth_level": sc["auth_level"],
            "dataset_digest": sha256_file(dataset_file),
            "roster_digest": sha256_file(roster_file),
            "primitives": sc["primitives"],
            "protocols": ["chat"],
            "models": MODELS,
            "eae_revision":
                execution_authorization.EAE_CONTRACT_REVISION,
            "dispatch_limits": dispatch_limits,
        },
    }
