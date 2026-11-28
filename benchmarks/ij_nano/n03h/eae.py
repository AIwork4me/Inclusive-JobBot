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
PIN = ROOT / "runtime" / "eae_pin" / "3cdd066"
PIN_SRC = PIN / "src"
EVID = PIN / "evidence" / "IJEVAL" / "EA03_N03"
AUTH1 = PIN / "evidence" / "IJEVAL" / "AUTH1"
AUTH2 = PIN / "evidence" / "IJEVAL" / "AUTH2"
EA13 = PIN / "evidence" / "IJEVAL" / "EA13"
EA18 = PIN / "evidence" / "IJEVAL" / "EA18"
SRC = PIN_SRC / "eval_assurance"

MODELS = ["MiniCPM5-2B", "LFM3-1.7B", "Qwen3.5-2B"]
PRIMITIVES_BATCH_A = [f"C{i:02d}" for i in range(1, 9)]

SCOPES = {
    "AUTH-1": {
        "experiment_id": "N03-AUTH1-DIAGNOSTIC-PANEL-v1",
        "auth_level": "AUTH-1",
        "roster_file": AUTH1 / "diagnostic_roster.json",
        "acceptance_file": AUTH1 / "auth1_acceptance.json",
        "canary_file": AUTH1 / "canary_integration.json",
        "breaker_file": AUTH1 / "breaker_drill.json",
        "state_file": AUTH1 / "authoritative_state.json",
        "ea13_scope_file": None,
        "ea18_scope_file": None,
    },
    "AUTH-2": {
        "experiment_id": "N03-AUTH2-DEVELOPMENT-BATCH-A-v1",
        "auth_level": "AUTH-2",
        "roster_file": AUTH2 / "development_roster_480.json",
        "acceptance_file": AUTH2 / "auth2_shared_core_acceptance.json",
        "canary_file": AUTH1 / "canary_integration.json",
        "breaker_file": AUTH1 / "breaker_drill.json",
        "state_file": AUTH2 / "authoritative_state.json",
        "ea13_scope_file": EA13 / "primitive_qualification.json",
        "ea18_scope_file": EA18 / "independent_acceptance.json",
    },
}


def sha256_file(p: pathlib.Path) -> str:
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


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
    dataset_file = EVID / "pinned" / "n03_cases.public.jsonl"

    store = CertificateStore.load_registry(
        EVID / "certificates" / "registry.json")
    state = AuthoritativeQualificationState(store, sc["state_file"])

    execution_authorization.clear_execution_evidence()
    dispatch_limits = {"max_trials": len(
        json.loads(roster_file.read_text(encoding="utf-8"))["slots"])}
    evidence = execution_authorization.register_trusted_execution_evidence(
        authoritative_state=state,
        experiment_id=sc["experiment_id"],
        auth_purpose=scope,
        primitives=PRIMITIVES_BATCH_A,
        protocols=["chat"], models=MODELS,
        dataset_file=dataset_file,
        roster_file=roster_file,
        parser_file=SRC / "production" / "parser.py",
        evaluator_file=SRC / "production" / "evaluator.py",
        interpreter_file=SRC / "reference" / "interpreter.py",
        oracle_file=SRC / "reference" / "oracle.py",
        certificate_store=store,
        shared_core_acceptance_file=sc["acceptance_file"],
        canary_evidence_file=sc["canary_file"],
        breaker_evidence_file=sc["breaker_file"],
        witness_suite_file=EVID / "dualpath_witnesses.json",
        mutation_report_file=EVID / "production_mutation_campaign.json",
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

    # -- canary witnesses (software-error rows excluded, as at release) -
    witnesses = json.loads(
        (EVID / "dualpath_witnesses.json").read_text(encoding="utf-8")
    )["rows"]
    exps = {json.loads(l)["case_id"]: json.loads(l) for l in
            (EVID / "pinned" / "n03_dev_expectations.jsonl")
            .read_text(encoding="utf-8").splitlines() if l.strip()}
    cases_by_id = {json.loads(l)["case_id"]: json.loads(l) for l in
                   dataset_file.read_text(encoding="utf-8")
                   .splitlines() if l.strip()}

    return {
        "scope": scope,
        "pin_report": pin_report,
        "contract": execution_authorization,
        "evidence": evidence,
        "provider": provider,
        "gate": gate,
        "store": store,
        "state": state,
        "roster_file": roster_file,
        "dataset_file": dataset_file,
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
            "primitives": PRIMITIVES_BATCH_A,
            "protocols": ["chat"],
            "models": MODELS,
            "eae_revision":
                execution_authorization.EAE_CONTRACT_REVISION,
            "dispatch_limits": dispatch_limits,
        },
    }
