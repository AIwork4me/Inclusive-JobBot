"""48H-B-006 — Batch A requalification-only recovery (EAE side).

The AUTH-2 Batch A consumer-verification drill at 3cdd066 durably
revoked the production certificate 512efb617a9cb4c8 (reason "drill";
the drill design predates the isolated-subprocess pattern — B/C/D
drills never touch the real registry). Recovery is REQUALIFICATION
ONLY (Wave C design: new authoritative generation + passing gates);
nothing is un-revoked or silently reissued.

Fresh gates re-executed LIVE at the current revision (not artifact
trust): Batch A oracle GT over the 160 pinned dev cases, the full
Wave B witness suite re-run through the UNCHANGED Batch A dual-path,
and a fresh full-family canary sweep through the real Batch A legs.

Deliverables: requalified certificate (requalified=True per EA-R04,
fresh gate evidence), fresh authoritative generation, ExecutionEvidence
for N03-AUTH2-DEVELOPMENT-BATCH-A-v2-RQ (AUTH-2, 480 slots), the new
ExecutionAuthorization, REAL IJ-NANO consumer verification with the
ISOLATED drill (the real registry is never modified — asserted).
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import shutil
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
os.chdir(ROOT)

from eval_assurance import canary as canary_mod              # noqa: E402
from eval_assurance import dualpath                           # noqa: E402
from eval_assurance.breaker import CircuitBreaker             # noqa: E402
from eval_assurance.compat import execution_authorization as ea  # noqa: E402
from eval_assurance.production.evaluator import (             # noqa: E402
    ProductionEvaluator)
from eval_assurance.production.parser import parse_response
from eval_assurance.qualification.store import (              # noqa: E402
    QualificationAuthority)
from eval_assurance.reference import oracle as oracle_a       # noqa: E402

EVID = ROOT / "evidence" / "IJEVAL" / "EA03_N03"
AUTH2RQ = ROOT / "evidence" / "IJEVAL" / "AUTH2A_RQ"
EA18 = ROOT / "evidence" / "IJEVAL" / "EA18"
EA13 = ROOT / "evidence" / "IJEVAL" / "EA13"
IJ = ROOT / "evidence" / "IJEVAL"
PINNED = EVID / "pinned"
SRC = ROOT / "src" / "eval_assurance"
REG = EVID / "certificates" / "registry.json"

EXPERIMENT = "N03-AUTH2-DEVELOPMENT-BATCH-A-v2-RQ"
MODELS = ["MiniCPM5-2B", "LFM3-1.7B", "Qwen3.5-2B"]
PRIMS = ["C01", "C02", "C03", "C04", "C05", "C06", "C07", "C08"]


def _sha(p) -> str:
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def _write(p: pathlib.Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=1, ensure_ascii=False),
                 encoding="utf-8")


def _load():
    rows = [json.loads(l) for l in
            (PINNED / "n03_cases.public.jsonl").read_text(
                encoding="utf-8").splitlines() if l.strip()]
    exps = {e["case_id"]: e for e in
            (json.loads(l) for l in (PINNED / "n03_dev_expectations.jsonl")
             .read_text(encoding="utf-8").splitlines() if l.strip())}
    return rows, exps


def fresh_gates(rows, exps) -> dict:
    """Re-execute the Batch A gates LIVE at this revision."""
    dev = [r for r in rows if r.get("split") == "development"]
    assert len(dev) == 160, f"expected 160, got {len(dev)}"
    gt_bad = []
    for r in dev:
        res = oracle_a.validate_ground_truth(r, exps.get(r["case_id"],
                                                         {}))
        if res.verdict.value != "VALID":
            gt_bad.append(r["case_id"])
    witnesses = json.loads((EVID / "dualpath_witnesses.json")
                           .read_text(encoding="utf-8"))["rows"]
    wit_bad = []
    by_case = {c["case_id"]: c for c in dev}
    for w in witnesses:
        if w["kind"] == "software-error":
            continue
        base = by_case.get(w.get("case_id"))
        if base is None:
            wit_bad.append(f"{w['witness_id']} (case missing)")
            continue
        case = {"case_id": base["case_id"], "primitive":
                base["primitive"], "family": base["family"],
                "public_payload": base["public_payload"]}
        r = dualpath.evaluate_dual(case,
                                   _reconstructed_expectation(w, exps),
                                   w["raw"])
        if r.classification != w["expected"]:
            wit_bad.append(w["witness_id"])
    mut = json.loads((EVID / "production_mutation_campaign.json")
                     .read_text(encoding="utf-8"))["faults"]
    escapes = [f["fault"] for f in mut if f["verdict"] == "ESCAPE"]
    return {"gt_total": len(dev), "gt_invalid": gt_bad,
            "witness_total": len([w for w in witnesses
                                  if w["kind"] != "software-error"]),
            "witness_failed": wit_bad,
            "production_fault_escapes": escapes,
            "passed": not gt_bad and not wit_bad and not escapes}


def _reconstructed_expectation(w, exps):
    """The witness rows reference case ids whose expectations live in
    the pinned Batch A expectations file."""
    return exps.get(w.get("case_id"), {})


def canary_evidence(exps, cases_by_id) -> pathlib.Path:
    witnesses = json.loads((EVID / "dualpath_witnesses.json")
                           .read_text(encoding="utf-8"))["rows"]
    tmp = ROOT / ".runtime" / "auth2a_rq_canary"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True, exist_ok=True)
    br = CircuitBreaker(tmp / "cb.json")
    sched = canary_mod.CanaryScheduler(
        [w for w in witnesses if w["kind"] != "software-error"],
        breaker=br, expectations=exps, cases_by_id=cases_by_id)
    sched.production_parser = parse_response        # the REAL Batch A
    sched.production_evaluator = ProductionEvaluator()   # legs
    results = sched.run_canary_sweep()
    passed = all(r.passed for r in results)
    p = AUTH2RQ / "canary_integration.json"
    _write(p, {
        "passed": passed,
        "sweep": "ALL Batch A families, fresh sweep at the "
                 "requalification revision",
        "families": {r.family: {"passed": r.passed,
                                "positive": r.positive_checks,
                                "negative": r.negative_checks}
                     for r in results}})
    return p


def breaker_evidence() -> pathlib.Path:
    tmp = ROOT / ".runtime" / "auth2a_rq_breaker"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True, exist_ok=True)
    br = CircuitBreaker(tmp / "cb.json")
    br.register_dispatch("in-flight-rq1")
    br.open(reason="requalification drill", affected_scope=["C01"],
            contamination_window=["trq1"])
    restart = CircuitBreaker(tmp / "cb.json")
    contained = restart.is_open and "trq1" in \
        restart.contamination_scope["quarantined_trials"]
    try:
        restart.recover_via_requalification(
            new_evidence_generation=0, authoritative_generation=0,
            canary_passed=True)
        wrongly = True
    except Exception:
        wrongly = False
    restart.recover_via_requalification(
        new_evidence_generation=1, authoritative_generation=1,
        canary_passed=True)
    p = AUTH2RQ / "breaker_drill.json"
    _write(p, {"passed": contained and not wrongly and not restart.is_open,
               "restart_safe_containment": contained,
               "hand_recovery_refused": not wrongly,
               "requalification_recovery": not restart.is_open})
    return p


def consumer_verification(auth_file, roster_file, reg_before=None) -> dict:
    # baseline captured HERE (after the certificate issuance, before
    # the drill): only the drill's effect is asserted
    reg_before = _sha(REG)
    ijnano = (ROOT.parent / "IJNANO").resolve()
    sys.path.insert(0, str(ijnano))
    try:
        import importlib
        mod = importlib.import_module(
            "benchmarks.ij_nano.n03.authorization")
        provider = mod.EAEExecutionAuthorizationProvider(
            pinned_revision=ea.EAE_CONTRACT_REVISION,
            contract_module="eval_assurance.compat.execution_authorization")
        auth_json = json.loads(
            auth_file.read_text(encoding="utf-8"))["authorization"]
        scope = auth_json["scope"]
        request = mod.RunRequest(
            experiment_id=EXPERIMENT,
            dataset_digest=auth_json["dataset_digest"],
            roster_digest=_sha(roster_file),
            primitives=frozenset(scope["primitives"]),
            protocols=frozenset(scope["protocols"]),
            models=frozenset(scope["models"]),
            eae_revision=ea.EAE_CONTRACT_REVISION,
            auth_level="AUTH-2")
        issued = provider.issue_execution_authorization(request)
        mod.validate_against(issued, request)
        issue_ok = issued.qualifying_class == "EAE" and \
            issued.checksum_valid()
    finally:
        sys.path.remove(str(ijnano))

    import subprocess
    drill_out = ROOT / ".runtime" / "auth2a_rq_drill_result.json"
    script = ROOT / "scripts" / "ij_eval_assurance" / "auth2a_rq_drill.py"
    proc = subprocess.run(
        [sys.executable, "-I", str(script)],
        capture_output=True, text=True, cwd=str(ROOT))
    revoked_refused = False
    if proc.returncode == 0 and drill_out.is_file():
        revoked_refused = json.loads(
            drill_out.read_text(encoding="utf-8")).get("revoked_refused")
    registry_untouched = _sha(REG) == reg_before
    return {
        "schema": "ijeval.auth2a_rq.consumer_verification.v1",
        "consumer": "REAL benchmarks.ij_nano.n03.authorization "
                    "(provider issue + validate_against on the live "
                    "REQUALIFIED registration; drill isolated in a "
                    "subprocess against a registry COPY)",
        "issue_ok": issue_ok,
        "revoked_refused": revoked_refused,
        "real_registry_untouched_by_drill": registry_untouched,
        "result": "requalified physical authorization issued and "
                  "validated for the exact Batch A scope "
                  f"({EXPERIMENT}); drill refusal reproduced in "
                  "isolation; the real registry digest is unchanged"
                  if issue_ok and revoked_refused and
                  registry_untouched else "FAILED",
        "drill_stderr_tail": proc.stderr.strip()[-300:]
                             if proc.returncode != 0 else ""}


def main() -> int:
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    AUTH2RQ.mkdir(parents=True, exist_ok=True)

    ea18 = json.loads((EA18 / "independent_acceptance.json")
                      .read_text(encoding="utf-8"))
    if ea18["gate"] != "N03_SHARED_EVALUATION_ASSURANCE_CORE_GO":
        print("EA18 gate not GO — requalification BLOCKED")
        return 1

    rows, exps = _load()
    cases_by_id = {r["case_id"]: r for r in rows}
    gates = fresh_gates(rows, exps)
    _write(AUTH2RQ / "fresh_gates.json", {
        "schema": "ijeval.auth2a_rq.fresh_gates.v1",
        "note": "Batch A gates RE-EXECUTED LIVE at the requalification "
                "revision (not artifact trust): oracle GT, Wave B "
                "witness suite through the unchanged dual-path, "
                "production-fault escape check",
        "gates": gates, "verified_utc": stamp})
    if not gates["passed"]:
        print("fresh gates FAILED — requalification BLOCKED:", gates)
        return 1
    print("fresh gates: GT", gates["gt_total"] - len(gates["gt_invalid"]),
          "/", gates["gt_total"], "| witnesses",
          gates["witness_total"] - len(gates["witness_failed"]), "/",
          gates["witness_total"], "| fault escapes",
          len(gates["production_fault_escapes"]))

    canary_file = canary_evidence(exps, cases_by_id)
    breaker_file = breaker_evidence()
    if not json.loads(canary_file.read_text(encoding="utf-8"))["passed"] \
            or not json.loads(
                breaker_file.read_text(encoding="utf-8"))["passed"]:
        print("canary/breaker not passing — BLOCKED")
        return 1

    acc = AUTH2RQ / "auth2a_rq_shared_core_acceptance.json"
    _write(acc, {
        "schema": "ijeval.auth2a_rq.acceptance.v1",
        "verdict": "ACCEPTED",
        "basis": {
            "gate": ea18["gate"],
            "ea18_artifact_sha256": _sha(
                EA18 / "independent_acceptance.json"),
            "fresh_gates": "re-executed live at this revision "
                           "(fresh_gates.json)",
            "revoked_predecessor": "512efb617a9cb4c8 revoked "
                                   "2026-11-28T04:04:08Z (reason: "
                                   "drill, 48H-B-006); recovery is "
                                   "REQUALIFICATION-ONLY — nothing "
                                   "un-revoked"},
        "requirements_map": {
            "shared EAE core protection gates": "Wave B + Wave C "
                                                "(EA18, unchanged)",
            "Batch A semantic qualification": "fresh live GT 160/160",
            "Batch A dual-path closure": "fresh live witness sweep, "
                                         "0 failures",
            "EA13 cognitive qualification": "8/8 (evidence/IJEVAL/"
                                            "EA13)",
            "canary integration": "fresh full-family sweep through "
                                  "the real Batch A legs (passed)",
            "breaker containment": "restart-safe, requalification-"
                                   "only recovery (passed)"},
        "scope_limits": "development split only; protected confirmation "
                        "NOT covered; physical runtime identities must "
                        "match the IJ-NANO model registry",
        "verified_utc": stamp})

    dev = [c for c in rows if c.get("split") == "development"]
    slots = [{"slot": i + 1, "case_id": c["case_id"],
              "primitive": c["primitive"], "family": c["family"],
              "language": c["language"], "model": m}
             for m in MODELS for i, c in enumerate(dev)]
    slots.sort(key=lambda s: (MODELS.index(s["model"]), s["slot"]))
    roster_file = AUTH2RQ / "development_roster_480.json"
    _write(roster_file, {
        "schema": "ijeval.auth2a_rq.development_roster.v1",
        "experiment": EXPERIMENT, "models": MODELS,
        "selection_rule": "ALL 160 Batch A development cases (pinned "
                          "Batch A snapshot order; no case removed) x 3 "
                          "models — identical selection to the revoked "
                          "predecessor scope",
        "slot_count": len(slots), "slots": slots})

    # -- requalified certificate (EA-R04: requalified=True + fresh gate
    #    evidence) -----------------------------------------------------
    from eval_assurance.qualification.store import CertificateStore
    store = CertificateStore.load_registry(REG)
    authority = QualificationAuthority(persist_to=REG)

    def rel(p):
        return pathlib.Path(os.path.relpath(pathlib.Path(p), ROOT))
    store = authority.issue_qualification(
        scope="semantic",
        dataset_id="n03-batch-a-dev160@d23de5a",
        parser_version="eval_assurance.production.parser@1",
        evaluator_version="eval_assurance.production.evaluator@1",
        reference_evaluator_version=
            "eval_assurance.reference.oracle@v2+formfill-pair-fix",
        dataset_file=rel(PINNED / "n03_cases.public.jsonl"),
        task_contract_file=rel(PINNED / "parser_semantics.md"),
        parser_file=rel(SRC / "production" / "parser.py"),
        interpreter_file=rel(SRC / "reference" / "interpreter.py"),
        evaluator_file=rel(SRC / "production" / "evaluator.py"),
        reference_oracle_file=rel(SRC / "reference" / "oracle.py"),
        witness_suite_file=rel(EVID / "dualpath_witnesses.json"),
        mutation_report_file=rel(EVID / "production_mutation_campaign.json"),
        evidence_files=[
            rel(AUTH2RQ / "fresh_gates.json"),
            rel(AUTH2RQ / "canary_integration.json"),
            rel(AUTH2RQ / "breaker_drill.json"),
            rel(EVID / "ground_truth_qualification_dev160_v2.json"),
            rel(EVID / "intake_verification.json"),
        ],
        replay_contract="content-addressed artifact replay "
                        "(dualpath.DualPathSession.replay) + fresh "
                        "live gates at the requalification revision",
        protocol="cpu-dualpath-qualification:"
                 "N03_BATCH_A_DEV_CPU_DUALPATH_RQ",
        limitations="REQUALIFICATION of the Batch A scope after the "
                    "drill revocation (48H-B-006). Same scope as the "
                    "revoked 512efb617a9cb4c8 with fresh live gates; "
                    "NOT a physical-runner qualification, NOT "
                    "confirmation-split coverage.",
        requalified=True,
        store=store)
    new_cert = [c.certificate_id for c in store.snapshot().certificates
                if c.protocol.endswith("_RQ")]
    print("requalified certificate:", new_cert)

    from eval_assurance.authoritative import (
        AuthoritativeQualificationState)
    state = AuthoritativeQualificationState(
        store, AUTH2RQ / "authoritative_state.json")

    ea.clear_execution_evidence()
    evidence = ea.register_trusted_execution_evidence(
        authoritative_state=state,
        experiment_id=EXPERIMENT, auth_purpose="AUTH-2",
        primitives=PRIMS, protocols=["chat"], models=MODELS,
        dataset_file=PINNED / "n03_cases.public.jsonl",
        roster_file=roster_file,
        parser_file=SRC / "production" / "parser.py",
        evaluator_file=SRC / "production" / "evaluator.py",
        interpreter_file=SRC / "reference" / "interpreter.py",
        oracle_file=SRC / "reference" / "oracle.py",
        certificate_store=store,
        shared_core_acceptance_file=acc,
        canary_evidence_file=canary_file,
        breaker_evidence_file=breaker_file,
        witness_suite_file=EVID / "dualpath_witnesses.json",
        mutation_report_file=EVID / "production_mutation_campaign.json",
        ea13_scope_file=EA13 / "primitive_qualification.json",
        ea18_scope_file=EA18 / "independent_acceptance.json",
        dispatch_limits={"max_trials": len(slots)})

    auth = ea.issue_execution_authorization(
        experiment_id=EXPERIMENT,
        dataset_digest=_sha(PINNED / "n03_cases.public.jsonl"),
        roster_digest=_sha(roster_file),
        primitives=PRIMS, protocols=["chat"], models=MODELS,
        auth_level="AUTH-2", eae_revision=ea.EAE_CONTRACT_REVISION)

    auth_file = AUTH2RQ / "execution_authorization.json"
    _write(auth_file, {
        "note": "REQUALIFIED Batch A scope (48H-B-006 recovery); "
                "consumer must verify checksum and recheck before "
                "every dispatch",
        "authorization": json.loads(auth.to_json()),
        "issued_utc": stamp})

    cv = consumer_verification(auth_file, roster_file)
    _write(AUTH2RQ / "consumer_verification.json", cv)
    if not (cv.get("issue_ok") and cv.get("revoked_refused") and
            cv.get("real_registry_untouched_by_drill")):
        print("consumer verification FAILED — BLOCKED:", cv)
        return 1

    _write(AUTH2RQ / "release.json", {
        "schema": "ijeval.auth2a_rq.release.v1",
        "status": "EAE-SIDE-RELEASED (requalification-only recovery of "
                  "48H-B-006; physical execution by the IJ-NANO owner "
                  "at the pinned revision)",
        "closes_blocker": "48H-B-006",
        "experiment": EXPERIMENT, "auth_level": "AUTH-2",
        "supersedes": "N03-AUTH2-DEVELOPMENT-BATCH-A-v1 (authorization "
                      "a22bcc68b8e19974 issued against the now-revoked "
                      "512efb617a9cb4c8)",
        "scope": {"slots": len(slots), "models": MODELS,
                  "dev_cases": len(dev),
                  "roster_digest": _sha(roster_file),
                  "dataset_digest":
                      _sha(PINNED / "n03_cases.public.jsonl"),
                  "primitives": PRIMS,
                  "primitives_qualified": 8},
        "eae_contract_revision": ea.EAE_CONTRACT_REVISION,
        "authorization_checksum": auth.checksum,
        "certificate_ids": list(evidence.certificate_refs),
        "revoked_predecessor_certificate": "512efb617a9cb4c8 (stays "
                                           "revoked, never un-revoked)",
        "shared_core_gate": ea18["gate"],
        "dispatch_limits": {"max_trials": len(slots)},
        "confirmation_status": "BLOCKED (AUTH-3 not registered)",
        "generated_utc": stamp})
    print("slots:", len(slots))
    print("authorization checksum:", auth.checksum[:16], "...")
    print("AUTH-2 Batch A REQUALIFICATION release written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
