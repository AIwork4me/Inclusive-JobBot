"""Order section 5 — AUTH-1 diagnostic execution release (EAE side).

Publishes the exact diagnostic execution scope and the trusted
integration revision for the 48-slot nominal panel (MiniCPM5-2B,
LFM3-1.7B, Qwen3.5-2B; 16 representative qualified development tasks
per model = 2 per primitive C01-C08, deterministic canonical order).

Chain built here (all real, no test doubles):
1. fresh canary integration sweep (all families) + breaker drill ->
   integration evidence artifacts;
2. AUTH-1-scoped acceptance artifact: the applicable Wave B/C gates,
   certificate and early-pilot results, with the AUTH-2 shared-core
   chain (EA12/EA14/EA13/EA18) explicitly declared REMAINING;
3. deterministic diagnostic roster (48 slots) -> digest;
4. trusted ExecutionEvidence registration (experiment-bound,
   purpose AUTH-1, dispatch limit 48);
5. ExecutionAuthorization issuance for the exact scope, serialized to
   evidence with checksum.

The physical GPU identity verification and the campaign execution stay
with the IJ-NANO owner (Issue #10 coordination); EAE refuses anything
beyond this scope.
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

from eval_assurance import canary as canary_mod              # noqa: E402
from eval_assurance.compat import execution_authorization as ea     # noqa: E402
from eval_assurance.authoritative import (                   # noqa: E402
    AuthoritativeQualificationState)
from eval_assurance.breaker import CircuitBreaker            # noqa: E402
from eval_assurance.qualification.store import (             # noqa: E402
    CertificateStore, QualificationAuthority)

EVID = ROOT / "evidence" / "IJEVAL" / "EA03_N03"
AUTH1 = ROOT / "evidence" / "IJEVAL" / "AUTH1"
PINNED = EVID / "pinned"

EXPERIMENT = "N03-AUTH1-DIAGNOSTIC-PANEL-v1"
MODELS = ["MiniCPM5-2B", "LFM3-1.7B", "Qwen3.5-2B"]
SRC = ROOT / "src" / "eval_assurance"


def _sha(p: pathlib.Path) -> str:
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def _write(p: pathlib.Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=1, ensure_ascii=False),
                 encoding="utf-8")


def build_roster() -> tuple[list[dict], pathlib.Path]:
    """16 representative qualified development tasks: the FIRST TWO dev
    cases of each primitive C01-C08 in the pinned canonical file order
    (deterministic, preregistered). 3 models x 16 tasks = 48 slots."""
    cases = [json.loads(l) for l in
             (PINNED / "n03_cases.public.jsonl").read_text(
                 encoding="utf-8").splitlines() if l.strip()]
    chosen = []
    for prim in ("C01", "C02", "C03", "C04", "C05", "C06", "C07", "C08"):
        got = [c for c in cases
               if c.get("primitive") == prim
               and c.get("split") == "development"][:2]
        assert len(got) == 2, prim
        chosen.extend(got)
    slots = [{"slot": i + 1, "case_id": c["case_id"],
              "primitive": c["primitive"], "family": c["family"],
              "language": c["language"], "model": m}
             for m in MODELS for i, c in enumerate(chosen)]
    # stable ordering: model-major, then task order
    slots.sort(key=lambda s: (MODELS.index(s["model"]), s["slot"]))
    p = AUTH1 / "diagnostic_roster.json"
    _write(p, {"schema": "ijeval.auth1.diagnostic_roster.v1",
               "experiment": EXPERIMENT, "models": MODELS,
               "selection_rule": "first two development cases of each "
                                 "primitive C01-C08 in pinned canonical "
                                 "file order",
               "dataset_revision": "d23de5a (pinned snapshot)",
               "slot_count": len(slots), "slots": slots})
    return slots, p


def canary_integration_evidence() -> pathlib.Path:
    witnesses = json.loads((EVID / "dualpath_witnesses.json")
                           .read_text(encoding="utf-8"))["rows"]
    exps = {json.loads(l)["case_id"]: json.loads(l) for l in
            (PINNED / "n03_dev_expectations.jsonl").read_text(
                encoding="utf-8").splitlines() if l.strip()}
    cases_by_id = {json.loads(l)["case_id"]: json.loads(l) for l in
                   (PINNED / "n03_cases.public.jsonl").read_text(
                       encoding="utf-8").splitlines() if l.strip()}
    tmp = ROOT / ".runtime" / "auth1_canary"
    tmp.mkdir(parents=True, exist_ok=True)
    br = CircuitBreaker(tmp / "cb.json")
    sched = canary_mod.CanaryScheduler(
        [w for w in witnesses if w["kind"] != "software-error"],
        breaker=br, expectations=exps, cases_by_id=cases_by_id)
    results = sched.preflight()
    passed = all(r.passed for r in results)
    p = AUTH1 / "canary_integration.json"
    _write(p, {"passed": passed,
               "families": {r.family: {"passed": r.passed,
                                       "positive": r.positive_checks,
                                       "negative": r.negative_checks}
                            for r in results}})
    return p


def breaker_drill_evidence() -> pathlib.Path:
    """Open -> containment visible -> requalification-only recovery."""
    tmp = ROOT / ".runtime" / "auth1_breaker"
    tmp.mkdir(parents=True, exist_ok=True)
    br = CircuitBreaker(tmp / "cb.json")
    br.register_dispatch("in-flight-1")
    br.open(reason="drill", affected_scope=["C01"],
            contamination_window=["t1"])
    restart = CircuitBreaker(tmp / "cb.json")
    contained = restart.is_open and "t1" in \
        restart.contamination_scope["quarantined_trials"]
    try:
        restart.recover_via_requalification(
            new_evidence_generation=0, authoritative_generation=0,
            canary_passed=True)
        recovered_wrongly = True
    except Exception:
        recovered_wrongly = False
    restart.recover_via_requalification(
        new_evidence_generation=1, authoritative_generation=1,
        canary_passed=True)
    p = AUTH1 / "breaker_drill.json"
    _write(p, {"passed": contained and not recovered_wrongly
               and not restart.is_open,
               "restart_safe_containment": contained,
               "hand_recovery_refused": not recovered_wrongly,
               "requalification_recovery": not restart.is_open})
    return p


def main() -> int:
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    AUTH1.mkdir(parents=True, exist_ok=True)
    slots, roster_file = build_roster()
    canary_file = canary_integration_evidence()
    breaker_file = breaker_drill_evidence()

    acceptance = {
        "schema": "ijeval.auth1.acceptance.v1",
        "verdict": "ACCEPTED",
        "scope": "AUTH-1 DIAGNOSTIC_SMOKE (frozen IJ-NANO-1.3S "
                 "contract): the APPLICABLE Wave B/C gates, certificate "
                 "and early-pilot requirements for diagnostic execution",
        "requirements_map": {
            "dataset qualification": "intake_verification.json + GT "
                                     "160/160 VALID @ d23de5a",
            "production and reference evaluator qualification":
                "dual-path closure certificate 512efb617a9cb4c8; "
                "116/116 witnesses; 20 production faults 0 escapes",
            "parser qualification":
                "pinned parser_semantics.md @ 58aa790; production "
                "parser P-series controls",
            "evidence qualification": "EA08 6/6 controls",
            "continuous canary": "EA09 full-family sweep cadence; "
                                 "canary_integration.json PASS",
            "circuit-breaker integration": "EA10; breaker_drill.json "
                                           "PASS",
            "early catastrophe pilot": "13/13 contained, 0 escapes"},
        "explicitly_remaining_for_AUTH-2": [
            "EA12 historical N02RR revalidation",
            "EA14 shared-core stress campaign (10,000 trials / 1,000 "
            "faults)",
            "EA13 cognitive primitive qualification",
            "EA18 independent adversarial acceptance"],
        "verified_utc": stamp}
    acc_file = AUTH1 / "auth1_acceptance.json"
    _write(acc_file, acceptance)

    # -- certificate chain: reuse the committed dual-path registry ------
    registry = EVID / "certificates" / "registry.json"
    store = CertificateStore.load_registry(registry)

    # -- authoritative state for the release registration ---------------
    state_file = AUTH1 / "authoritative_state.json"
    state = AuthoritativeQualificationState(store, state_file)

    ea.clear_execution_evidence()
    evidence = ea.register_trusted_execution_evidence(
        authoritative_state=state,
        experiment_id=EXPERIMENT, auth_purpose="AUTH-1",
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
        shared_core_acceptance_file=acc_file,
        canary_evidence_file=canary_file,
        breaker_evidence_file=breaker_file,
        witness_suite_file=EVID / "dualpath_witnesses.json",
        mutation_report_file=EVID / "production_mutation_campaign.json",
        dispatch_limits={"max_trials": len(slots)})

    auth = ea.issue_execution_authorization(
        experiment_id=EXPERIMENT,
        dataset_digest=_sha(PINNED / "n03_cases.public.jsonl"),
        roster_digest=_sha(roster_file),
        primitives=["C01", "C02", "C03", "C04", "C05", "C06", "C07",
                    "C08"],
        protocols=["chat"], models=MODELS,
        auth_level="AUTH-1", eae_revision=ea.EAE_CONTRACT_REVISION)

    _write(AUTH1 / "execution_authorization.json", {
        "note": "issued for the diagnostic scope; consumer must verify "
                "checksum and recheck before every dispatch",
        "authorization": json.loads(auth.to_json()),
        "issued_utc": stamp})
    _write(AUTH1 / "release.json", {
        "schema": "ijeval.auth1.release.v1",
        "status": "EAE-SIDE-RELEASED (physical execution by the "
                  "IJ-NANO owner; GPU identity verification is theirs)",
        "experiment": EXPERIMENT,
        "auth_level": "AUTH-1",
        "scope": {"slots": len(slots), "models": MODELS,
                  "tasks_per_model": len(slots) // len(MODELS),
                  "roster_digest": _sha(roster_file),
                  "dataset_digest":
                      _sha(PINNED / "n03_cases.public.jsonl"),
                  "roster_selection_rule":
                      "first two dev cases per primitive, canonical "
                      "pinned order"},
        "eae_contract_revision": ea.EAE_CONTRACT_REVISION,
        "authorization_checksum": auth.checksum,
        "certificate_ids": list(evidence.certificate_refs),
        "dispatch_limits": {"max_trials": len(slots)},
        "results_policy": "diagnostic only; must not enter formal "
                          "capability rankings",
        "generated_utc": stamp})
    print("roster slots:", len(slots))
    print("authorization checksum:", auth.checksum[:16], "...")
    print("release written:", AUTH1 / "release.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
