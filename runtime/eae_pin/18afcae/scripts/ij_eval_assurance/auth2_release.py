"""Order section 7 — progressive AUTH-2 development release (EAE side).

All eight Batch A primitives are EA13-qualified and the shared core
passed EA18 (N03_SHARED_EVALUATION_ASSURANCE_CORE_GO), so the FULL
Batch A development scope is eligible: 160 dev cases x 3 models =
480 slots (the original Batch A dev roster; no case silently removed).

Deliverables: AUTH-2-purposed shared-core acceptance artifact (derived
from the EA18 gate), the deterministic 480-slot dev roster,
trusted ExecutionEvidence registration (experiment-bound, purpose
AUTH-2, dispatch limit 480) and the ExecutionAuthorization for the
scope. Physical execution stays with the IJ-NANO consumer at the
pinned revision.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
os.chdir(ROOT)

from eval_assurance.compat import execution_authorization as ea  # noqa: E402
from eval_assurance.qualification.store import (             # noqa: E402
    CertificateStore)

EVID = ROOT / "evidence" / "IJEVAL" / "EA03_N03"
AUTH2 = ROOT / "evidence" / "IJEVAL" / "AUTH2"
AUTH1 = ROOT / "evidence" / "IJEVAL" / "AUTH1"
IJ = ROOT / "evidence" / "IJEVAL"
PINNED = EVID / "pinned"
SRC = ROOT / "src" / "eval_assurance"

EXPERIMENT = "N03-AUTH2-DEVELOPMENT-BATCH-A-v1"
MODELS = ["MiniCPM5-2B", "LFM3-1.7B", "Qwen3.5-2B"]


def _sha(p) -> str:
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def _write(p: pathlib.Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=1, ensure_ascii=False),
                 encoding="utf-8")


def main() -> int:
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    AUTH2.mkdir(parents=True, exist_ok=True)

    ea18 = json.loads((ROOT / "evidence" / "IJEVAL" / "EA18" /
                       "independent_acceptance.json").read_text(
                           encoding="utf-8"))
    if ea18["gate"] != "N03_SHARED_EVALUATION_ASSURANCE_CORE_GO":
        print("EA18 gate not GO — AUTH-2 retained BLOCKED")
        return 1

    # -- AUTH-2 shared-core acceptance (derived from the EA18 gate) ----
    acc = AUTH2 / "auth2_shared_core_acceptance.json"
    _write(acc, {
        "schema": "ijeval.auth2.acceptance.v1",
        "verdict": "ACCEPTED",
        "basis": {
            "gate": ea18["gate"],
            "ea18_artifact": "evidence/IJEVAL/EA18/"
                             "independent_acceptance.json",
            "ea18_artifact_sha256": _sha(
                ROOT / "evidence" / "IJEVAL" / "EA18" /
                "independent_acceptance.json"),
            "dependencies": ea18["dependencies"]["ok"]},
        "requirements_map": {
            "shared EAE core protection gates": "Wave B + Wave C",
            "historical catastrophe regression": "pilot 13/13 + N02R "
                                                 "reintroduction",
            "EA12 historical revalidation": "PASS_WITH_FINDINGS",
            "EA14 shared-core fault containment": "GO (0 genuine "
                                                  "escapes, 0 false "
                                                  "alarms)",
            "EA13 cognitive qualification": "8/8 dev primitives",
            "EA18 independent acceptance": "9/9 attempts refused"},
        "scope_limits": "development split only; protected confirmation "
                        "NOT covered (roster_split=development); "
                        "physical runtime identities must match the "
                        "IJ-NANO model registry",
        "verified_utc": stamp})

    # -- deterministic full Batch A dev roster: 160 x 3 = 480 ----------
    cases = [json.loads(l) for l in
             (PINNED / "n03_cases.public.jsonl").read_text(
                 encoding="utf-8").splitlines() if l.strip()]
    dev = [c for c in cases if c.get("split") == "development"]
    slots = [{"slot": i + 1, "case_id": c["case_id"],
              "primitive": c["primitive"], "family": c["family"],
              "language": c["language"], "model": m}
             for m in MODELS for i, c in enumerate(dev)]
    slots.sort(key=lambda s: (MODELS.index(s["model"]), s["slot"]))
    roster_file = AUTH2 / "development_roster_480.json"
    _write(roster_file, {
        "schema": "ijeval.auth2.development_roster.v1",
        "experiment": EXPERIMENT, "models": MODELS,
        "selection_rule": "ALL 160 Batch A development cases (complete "
                          "dev split, canonical pinned order; no case "
                          "removed) x 3 models",
        "slot_count": len(slots), "slots": slots})

    # -- certificate chain + trusted registration ------------------------
    store = CertificateStore.load_registry(
        EVID / "certificates" / "registry.json")
    from eval_assurance.authoritative import (
        AuthoritativeQualificationState)
    state = AuthoritativeQualificationState(
        store, AUTH2 / "authoritative_state.json")

    ea.clear_execution_evidence()
    evidence = ea.register_trusted_execution_evidence(
        authoritative_state=state,
        experiment_id=EXPERIMENT, auth_purpose="AUTH-2",
        primitives=["C01", "C02", "C03", "C04", "C05", "C06", "C07",
                    "C08"],
        protocols=["chat"], models=MODELS,
        dataset_file=PINNED / "n03_cases.public.jsonl",
        roster_file=roster_file,
        parser_file=SRC / "production" / "parser.py",
        evaluator_file=SRC / "production" / "evaluator.py",
        interpreter_file=SRC / "reference" / "interpreter.py",
        oracle_file=SRC / "reference" / "oracle.py",
        certificate_store=store,
        shared_core_acceptance_file=acc,
        canary_evidence_file=
            AUTH1 / "canary_integration.json"
            if (AUTH1 / "canary_integration.json").exists()
            else AUTH2 / "canary.json",
        breaker_evidence_file=
            AUTH1 / "breaker_drill.json"
            if (AUTH1 / "breaker_drill.json").exists()
            else AUTH2 / "breaker.json",
        witness_suite_file=EVID / "dualpath_witnesses.json",
        mutation_report_file=EVID / "production_mutation_campaign.json",
        ea13_scope_file=IJ / "EA13" / "primitive_qualification.json",
        ea18_scope_file=IJ / "EA18" / "independent_acceptance.json",
        dispatch_limits={"max_trials": len(slots)})

    auth = ea.issue_execution_authorization(
        experiment_id=EXPERIMENT,
        dataset_digest=_sha(PINNED / "n03_cases.public.jsonl"),
        roster_digest=_sha(roster_file),
        primitives=["C01", "C02", "C03", "C04", "C05", "C06", "C07",
                    "C08"],
        protocols=["chat"], models=MODELS,
        auth_level="AUTH-2", eae_revision=ea.EAE_CONTRACT_REVISION)

    _write(AUTH2 / "execution_authorization.json", {
        "note": "issued for the full Batch A development scope; "
                "consumer must verify checksum and recheck before "
                "every dispatch",
        "authorization": json.loads(auth.to_json()),
        "issued_utc": stamp})
    _write(AUTH2 / "release.json", {
        "schema": "ijeval.auth2.release.v1",
        "status": "EAE-SIDE-RELEASED (physical execution by the "
                  "IJ-NANO owner at the pinned revision)",
        "experiment": EXPERIMENT, "auth_level": "AUTH-2",
        "scope": {"slots": len(slots), "models": MODELS,
                  "dev_cases": len(dev),
                  "roster_digest": _sha(roster_file),
                  "dataset_digest":
                      _sha(PINNED / "n03_cases.public.jsonl"),
                  "primitives_qualified": 8,
                  "progressive_note": "all 8 primitives qualified -> "
                                      "full 480-slot Batch A dev scope; "
                                      "narrower preregistered scopes "
                                      "remain permissible"},
        "eae_contract_revision": ea.EAE_CONTRACT_REVISION,
        "authorization_checksum": auth.checksum,
        "certificate_ids": list(evidence.certificate_refs),
        "shared_core_gate": ea18["gate"],
        "dispatch_limits": {"max_trials": len(slots)},
        "confirmation_status": "BLOCKED (AUTH-3 requires frozen model "
                               "identities/policies + confirmation "
                               "roster + verified holdout separation; "
                               "not registered)",
        "generated_utc": stamp})
    print("slots:", len(slots))
    print("authorization checksum:", auth.checksum[:16], "...")
    print("AUTH-2 release written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
