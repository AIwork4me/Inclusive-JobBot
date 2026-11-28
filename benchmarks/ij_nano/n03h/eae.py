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

#: pinned EAE revisions — a scope is consumable ONLY at the revision
#: where its released authorization checksum reproduces (the registry
#: accumulates certificates across releases, so later pins carry more
#: valid certs and would change the authorization payload).
PIN_REVS = {
    "3cdd066": "EAE @ 3cdd06d685d5d9a824af60f2189d7ded612d735 (historical: AUTH-1/AUTH-2 Batch A releases; cert 512efb617a9cb4c8 revoked by drill)",
    "7a3e8dc": "EAE @ 7a3e8dc64dfb0a677fe4aa53c33f81b0d01e72d6 (AUTH-2B Batch B release bffce5a)",
    "a50c3c5": "EAE @ a50c3c5ceb8d1ca4979d00a8e8faa310ea24842e (AUTH-2C Batch C release 2094238)",
    "18afcae": "EAE @ 18afcae (AUTH-2A-RQ requalification + AUTH-2W adapter scope)",
    "9b0ba89": "EAE @ 9b0ba89 (AUTH-2D Batch D release commit)",
}
#: default pin for module-level constants (Batch A pinned data exists
#: at every revision; SCOPES carry their own pin_rev)
CURRENT_PIN_REV = "a50c3c5"
PIN = ROOT / "runtime" / "eae_pin" / CURRENT_PIN_REV
PIN_SRC = PIN / "src"
EVID = PIN / "evidence" / "IJEVAL" / "EA03_N03"
EA18 = EVID.parent / "EA18"
SRC = PIN_SRC / "eval_assurance"


#: revision whose eval_assurance package this process imported
_LOADED_PIN_REV: str | None = None


def _pin_paths(rev: str) -> dict:
    pin = ROOT / "runtime" / "eae_pin" / rev
    evid = pin / "evidence" / "IJEVAL" / "EA03_N03"
    return {
        "pin": pin, "pin_src": pin / "src", "evid": evid,
        "auth1": evid.parent / "AUTH1",
        "auth2": evid.parent / "AUTH2",
        "auth2b": evid.parent / "AUTH2B",
        "auth2c": evid.parent / "AUTH2C",
        "ea13": evid.parent / "EA13",
        "ea13b": evid.parent / "EA13B",
        "ea13c": evid.parent / "EA13C",
        "ea18": evid.parent / "EA18",
        "src": (pin / "src" / "eval_assurance"),
    }

MODELS = ["MiniCPM5-2B", "LFM3-1.7B", "Qwen3.5-2B"]
PRIMITIVES_BATCH_A = [f"C{i:02d}" for i in range(1, 9)]
PRIMITIVES_BATCH_B = [f"C{i:02d}" for i in range(9, 17)]
PRIMITIVES_BATCH_C = [f"C{i:02d}" for i in range(17, 25)]
PRIMITIVES_BATCH_D = [f"C{i:02d}" for i in range(25, 33)]
PRIMITIVES_ALL = [f"C{i:02d}" for i in range(1, 33)]

SCOPES = {
    "AUTH-1": {
        "pin_rev": "3cdd066",
        "experiment_id": "N03-AUTH1-DIAGNOSTIC-PANEL-v1",
        "auth_level": "AUTH-1",
        "primitives": PRIMITIVES_BATCH_A,
        "roster_name": "AUTH1/diagnostic_roster.json",
        "dataset": "pinned",
        "acceptance_name": "AUTH1/auth1_acceptance.json",
        "canary_name": "AUTH1/canary_integration.json",
        "breaker_name": "AUTH1/breaker_drill.json",
        "state_name": "AUTH1/authoritative_state.json",
        "witness_name": "EA03_N03/dualpath_witnesses.json",
        "mutation_name": "EA03_N03/production_mutation_campaign.json",
        "legs": "a",
        "ea13_scope_name": None,
        "ea18_scope_name": None,
    },
    "AUTH-2": {
        "pin_rev": "3cdd066",
        "experiment_id": "N03-AUTH2-DEVELOPMENT-BATCH-A-v1",
        "auth_level": "AUTH-2",
        "primitives": PRIMITIVES_BATCH_A,
        "roster_name": "AUTH2/development_roster_480.json",
        "dataset": "pinned",
        "acceptance_name": "AUTH2/auth2_shared_core_acceptance.json",
        "canary_name": "AUTH1/canary_integration.json",
        "breaker_name": "AUTH1/breaker_drill.json",
        "state_name": "AUTH2/authoritative_state.json",
        "witness_name": "EA03_N03/dualpath_witnesses.json",
        "mutation_name": "EA03_N03/production_mutation_campaign.json",
        "legs": "a",
        "ea13_scope_name": "EA13/primitive_qualification.json",
        "ea18_scope_name": "EA18/independent_acceptance.json",
    },
    "AUTH-2B": {
        "pin_rev": "7a3e8dc",
        "experiment_id": "N03-AUTH2-DEVELOPMENT-BATCH-B-v1",
        "auth_level": "AUTH-2",
        "primitives": PRIMITIVES_BATCH_B,
        "roster_name": "AUTH2B/development_roster_480.json",
        "dataset": "pinned_full",
        "acceptance_name": "AUTH2B/auth2b_shared_core_acceptance.json",
        "canary_name": "AUTH2B/canary_integration.json",
        "breaker_name": "AUTH2B/breaker_drill.json",
        "state_name": "AUTH2B/authoritative_state.json",
        "witness_name": "EA03_N03/dualpath_witnesses_batch_b.json",
        "mutation_name": "EA03_N03/production_mutation_campaign_batch_b.json",
        "legs": "b",
        "ea13_scope_name": "EA13B/primitive_qualification_batch_b.json",
        "ea18_scope_name": "EA18/independent_acceptance.json",
    },
    "AUTH-2C": {
        "pin_rev": "a50c3c5",
        "experiment_id": "N03-AUTH2-DEVELOPMENT-BATCH-C-v1",
        "auth_level": "AUTH-2",
        "primitives": PRIMITIVES_BATCH_C,
        "roster_name": "AUTH2C/development_roster_480.json",
        "dataset": "pinned_full",
        "acceptance_name": "AUTH2C/auth2c_shared_core_acceptance.json",
        "canary_name": "AUTH2C/canary_integration.json",
        "breaker_name": "AUTH2C/breaker_drill.json",
        "state_name": "AUTH2C/authoritative_state.json",
        "witness_name": "EA03_N03/dualpath_witnesses_batch_c.json",
        "mutation_name": "EA03_N03/production_mutation_campaign_batch_c.json",
        "legs": "c",
        "ea13_scope_name": "EA13C/primitive_qualification_batch_c.json",
        "ea18_scope_name": "EA18/independent_acceptance.json",
    },
    "AUTH-2A-RQ": {
        "pin_rev": "18afcae",
        "experiment_id": "N03-AUTH2-DEVELOPMENT-BATCH-A-v2-RQ",
        "auth_level": "AUTH-2",
        "primitives": PRIMITIVES_BATCH_A,
        "roster_name": "AUTH2A_RQ/development_roster_480.json",
        "dataset": "pinned",
        "acceptance_name": "AUTH2A_RQ/auth2a_rq_shared_core_acceptance.json",
        "canary_name": "AUTH2A_RQ/canary_integration.json",
        "breaker_name": "AUTH2A_RQ/breaker_drill.json",
        "state_name": "AUTH2A_RQ/authoritative_state.json",
        "witness_name": "EA03_N03/dualpath_witnesses.json",
        "mutation_name": "EA03_N03/production_mutation_campaign.json",
        "legs": "a",
        "ea13_scope_name": "EA13/primitive_qualification.json",
        "ea18_scope_name": "EA18/independent_acceptance.json",
    },
    "AUTH-2D": {
        "pin_rev": "9b0ba89",
        "experiment_id": "N03-AUTH2-DEVELOPMENT-BATCH-D-v1",
        "auth_level": "AUTH-2",
        "primitives": PRIMITIVES_BATCH_D,
        "roster_name": "AUTH2D/development_roster_480.json",
        "dataset": "pinned_full",
        "acceptance_name": "AUTH2D/auth2d_shared_core_acceptance.json",
        "canary_name": "AUTH2D/canary_integration.json",
        "breaker_name": "AUTH2D/breaker_drill.json",
        "state_name": "AUTH2D/authoritative_state.json",
        "witness_name": "EA03_N03/dualpath_witnesses_batch_d.json",
        "mutation_name": "EA03_N03/production_mutation_campaign_batch_d.json",
        "legs": "d",
        "ea13_scope_name": "EA13D/primitive_qualification_batch_d.json",
        "ea18_scope_name": "EA18/independent_acceptance.json",
    },
    "AUTH-2W": {
        "pin_rev": "18afcae",
        "experiment_id": "N03-AUTH2-ADAPTER-ATLAS-v1",
        "auth_level": "AUTH-2",
        "primitives": PRIMITIVES_ALL,
        "models": ["LFM3-1.7B+W1_pi", "LFM3-1.7B+W2_opencode",
                   "LFM3-1.7B+W3_hermes"],
        "roster_name": "ADAPTER_SCOPE/adapter_dev_roster_1920.json",
        "dataset": "pinned_full",
        "acceptance_name": "ADAPTER_SCOPE/adapter_scope_acceptance.json",
        "canary_name": "ADAPTER_SCOPE/canary_integration.json",
        "breaker_name": "ADAPTER_SCOPE/breaker_drill.json",
        "state_name": "ADAPTER_SCOPE/authoritative_state.json",
        "witness_name": "EA03_N03/dualpath_witnesses_batch_b.json",
        "mutation_name": "EA03_N03/production_mutation_campaign_batch_b.json",
        "legs": "b",
        "session_legs": "multi",
        "leg_files_note": "registration digests bind the batch_b stack per the EAE release script; TRIAL evaluation and canaries dispatch per-primitive batch legs (session_legs=multi)",
        "ea13_scope_name": "EA13B/primitive_qualification_batch_b.json",
        "ea18_scope_name": "EA18/independent_acceptance.json",
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
    "AUTH-2C": "c90f234af01db24a2c73796db505e25c7ae68c1afd66f0fd4a21954088b9d29f",
    "AUTH-2D": "b71ab0d0ee3d307b8fdb0c71d6bdd55d45e82a946170040a0d957675c3f9926d",
    "AUTH-2A-RQ": "cf627b26a5f47706639d5df77c20cd7913d7081f59ff05338d2e03e2f6e4d2c7",
    "AUTH-2W": "a6b17c34cbe8eb9fef57811b0b648e609c77eadd7090b3b4a13df798d5b14725",
}


def sha256_file(p: pathlib.Path) -> str:
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def import_pin_module(dotted: str, rev: str | None = None):
    """Import a module from a pinned snapshot (path-only; no evidence
    registration). Binds the process to that revision — the FIRST
    eval_assurance import fixes the package __path__, so the guard is
    identical to bootstrap's (cross-revision import refuses)."""
    global _LOADED_PIN_REV
    rev = rev or CURRENT_PIN_REV
    if _LOADED_PIN_REV is not None and _LOADED_PIN_REV != rev:
        raise RuntimeError(
            f"this process already imported eval_assurance from pin "
            f"{_LOADED_PIN_REV}; refusing to import {dotted!r} from pin "
            f"{rev} (one EAE revision per process)")
    _LOADED_PIN_REV = rev
    src_str = str(ROOT / "runtime" / "eae_pin" / rev / "src")
    if src_str not in sys.path:
        sys.path.insert(0, src_str)
    import importlib
    return importlib.import_module(dotted)


def verify_pin(rev: str = CURRENT_PIN_REV) -> dict:
    """Fail-closed: recompute every pinned-file digest against the
    revision's PIN_MANIFEST.json; any mismatch/absence refuses
    integration."""
    pin_dir = ROOT / "runtime" / "eae_pin" / rev
    manifest_path = pin_dir / "PIN_MANIFEST.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"pin manifest missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    problems = []
    seen = 0
    for rel, want in manifest["files_sha256"].items():
        p = pin_dir / rel
        if not p.is_file():
            problems.append(f"missing: {rel}")
            continue
        seen += 1
        if sha256_file(p) != want:
            problems.append(f"digest mismatch: {rel}")
    extra = [str(p.relative_to(pin_dir)).replace("\\", "/")
             for p in pin_dir.rglob("*")
             if p.is_file() and "__pycache__" not in p.parts and
             str(p.relative_to(pin_dir)).replace("\\", "/")
             not in manifest["files_sha256"] and p.name != "PIN_MANIFEST.json"]
    if extra:
        problems.append(f"unpinned files present: {extra[:5]}")
    if problems:
        raise RuntimeError(f"EAE pin {rev} verification FAILED "
                           "(fail-closed): " + "; ".join(problems[:10]))
    return {"pin_rev": rev, "files_verified": seen,
            "pin": manifest["pin"], "subtrees": manifest["subtrees"]}


def bootstrap(scope: str):
    """Register the trusted ExecutionEvidence for ``scope`` ("AUTH-1" or
    "AUTH-2") on the pinned module and return everything the campaign
    controller needs. Replicates the corresponding EAE release script's
    registration call exactly (auth1_release.py / auth2_release.py at
    3cdd066) on pinned paths."""
    global _LOADED_PIN_REV
    if scope not in SCOPES:
        raise ValueError(f"unknown scope {scope!r}")
    sc = SCOPES[scope]
    rev = sc["pin_rev"]
    if _LOADED_PIN_REV is not None and _LOADED_PIN_REV != rev:
        raise RuntimeError(
            f"this process already imported eval_assurance from pin "
            f"{_LOADED_PIN_REV}; scope {scope} lives at pin {rev}. One "
            "EAE revision per process (restart for the other scope).")
    _LOADED_PIN_REV = rev
    paths = _pin_paths(rev)
    pin_report = verify_pin(rev)
    sys.dont_write_bytecode = True     # keep the pin dir source-only

    # bind the process to this scope's revision (single-revision rule)
    import_pin_module("eval_assurance", rev)
    import importlib
    canary_mod = importlib.import_module("eval_assurance.canary")
    AuthoritativeQualificationState = importlib.import_module(
        "eval_assurance.authoritative").AuthoritativeQualificationState
    CircuitBreaker = importlib.import_module(
        "eval_assurance.breaker").CircuitBreaker
    execution_authorization = importlib.import_module(
        "eval_assurance.compat.execution_authorization")
    DualPathSession = importlib.import_module(
        "eval_assurance.dualpath").DualPathSession
    CertificateStore = importlib.import_module(
        "eval_assurance.qualification.store").CertificateStore

    ev_root = paths["pin"] / "evidence" / "IJEVAL"
    roster_file = ev_root / sc["roster_name"]
    dataset_dir = paths["evid"] / sc["dataset"]
    dataset_file = dataset_dir / "n03_cases.public.jsonl"
    expectations_file = dataset_dir / "n03_dev_expectations.jsonl"

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
        shutil.copy2(paths["evid"] / "certificates" / "registry.json",
                     registry_copy)
    if not state_copy.is_file():
        shutil.copy2(ev_root / sc["state_name"], state_copy)

    store = CertificateStore.load_registry(registry_copy)
    state = AuthoritativeQualificationState(store, state_copy)

    sfx = {"a": "", "b": "_b", "c": "_c", "d": "_d",
           "multi": ""}[sc["legs"]]
    srcdir = paths["src"]
    parser_file = srcdir / "production" / f"parser{sfx}.py"
    evaluator_file = srcdir / "production" / f"evaluator{sfx}.py"
    interpreter_file = srcdir / "reference" / f"interpreter{sfx}.py"
    oracle_file = srcdir / "reference" / f"oracle{sfx}.py"

    execution_authorization.clear_execution_evidence()
    dispatch_limits = {"max_trials": len(
        json.loads(roster_file.read_text(encoding="utf-8"))["slots"])}
    evidence = execution_authorization.register_trusted_execution_evidence(
        authoritative_state=state,
        experiment_id=sc["experiment_id"],
        auth_purpose=sc["auth_level"],
        primitives=sc["primitives"],
        protocols=["chat"], models=sc.get("models", MODELS),
        dataset_file=dataset_file,
        roster_file=roster_file,
        parser_file=parser_file,
        evaluator_file=evaluator_file,
        interpreter_file=interpreter_file,
        oracle_file=oracle_file,
        certificate_store=store,
        shared_core_acceptance_file=ev_root / sc["acceptance_name"],
        canary_evidence_file=ev_root / sc["canary_name"],
        breaker_evidence_file=ev_root / sc["breaker_name"],
        witness_suite_file=ev_root / sc["witness_name"],
        mutation_report_file=ev_root / sc["mutation_name"],
        ea13_scope_file=(ev_root / sc["ea13_scope_name"]
                         if sc["ea13_scope_name"] else None),
        ea18_scope_file=(ev_root / sc["ea18_scope_name"]
                         if sc["ea18_scope_name"] else None),
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
                protocols=["chat"],
                models=sc.get("models", MODELS),
                auth_level=sc["auth_level"],
                eae_revision=execution_authorization.EAE_CONTRACT_REVISION)
        except Exception as e:                     # noqa: BLE001
            raise RuntimeError(
                f"scope {scope} is not consumable at pin "
                f"{rev}: fresh issuance failed fail-closed "
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
        (ev_root / sc["witness_name"]).read_text(encoding="utf-8")
    )["rows"]
    exps = {json.loads(l)["case_id"]: json.loads(l) for l in
            expectations_file.read_text(encoding="utf-8")
            .splitlines() if l.strip()}
    cases_by_id = {json.loads(l)["case_id"]: json.loads(l) for l in
                   dataset_file.read_text(encoding="utf-8")
                   .splitlines() if l.strip()}

    # -- canary leg injection (same override the EAE release scripts use) -
    canary_legs = None
    if sc["legs"] != "a":
        import importlib
        pmod = importlib.import_module(
            "eval_assurance.production.parser" + sfx)
        emod = importlib.import_module(
            "eval_assurance.production.evaluator" + sfx)
        evcls = getattr(emod, "ProductionEvaluator"
                        + (sfx[1].upper() if sfx else ""))
        canary_legs = {"production_parser": pmod.parse_response,
                       "production_evaluator": evcls()}

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
        "legs": sc.get("session_legs", sc["legs"]),
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
            "models": sc.get("models", MODELS),
            "eae_revision":
                execution_authorization.EAE_CONTRACT_REVISION,
            "dispatch_limits": dispatch_limits,
        },
    }
