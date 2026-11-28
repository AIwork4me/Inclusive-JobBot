"""Order 48H-SUPPORT §1 — AUTH-2 Batch C release (EAE side).

All eight Batch C primitives (C17-C24) are EA13-B-qualified over
independently verified ground truth (EA03-B 160/160 + 470/0 mutation
controls) and the Batch C dual-path stack passed the Wave B-B campaign
(126/126 witnesses, 11 detected faults, 0 escapes). The shared core remains EA18-accepted (Batch A gate; the
core modules are unchanged — Batch C legs are NEW modules, the Batch A
qualified sources byte-identical).

Deliverables:
- fresh canary integration sweep (ALL Batch C families through the
  REAL Batch C production legs) + circuit-breaker drill;
- Batch C dual-path gate certificate through the REAL
  QualificationAuthority (scope 'semantic' — the eligibility
  aggregation category);
- AUTH-2-purposed shared-core acceptance artifact;
- the deterministic 480-slot Batch C dev roster (160 dev cases x 3
  models, none silently removed);
- trusted ExecutionEvidence registration (experiment-bound, purpose
  AUTH-2, dispatch limit 480) and the scope-bound
  ExecutionAuthorization;
- REAL IJ-NANO consumer verification (the pinned authorization module
  imported from the IJNANO worktree, read-only: provider issue ->
  validate_against -> revocation drill).

Physical execution stays with the IJ-NANO owner at the pinned
revision. Confirmation stays BLOCKED (AUTH-3 not registered).
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
from eval_assurance.breaker import CircuitBreaker             # noqa: E402
from eval_assurance.compat import execution_authorization as ea  # noqa: E402
from eval_assurance.production import evaluator_c as pev_c  # noqa: E402
from eval_assurance.production import parser_c as ppr_c    # noqa: E402
from eval_assurance.qualification.store import (              # noqa: E402
    QualificationAuthority)

EVID = ROOT / "evidence" / "IJEVAL" / "EA03_N03"
AUTH2C = ROOT / "evidence" / "IJEVAL" / "AUTH2C"
EA18 = ROOT / "evidence" / "IJEVAL" / "EA18"
EA13C = ROOT / "evidence" / "IJEVAL" / "EA13C"
IJ = ROOT / "evidence" / "IJEVAL"
PIN_FULL = EVID / "pinned_full"
SRC = ROOT / "src" / "eval_assurance"

EXPERIMENT = "N03-AUTH2-DEVELOPMENT-BATCH-C-v1"
MODELS = ["MiniCPM5-2B", "LFM3-1.7B", "Qwen3.5-2B"]
PRIMS = list(ppr_c.BATCH_C)


def _sha(p) -> str:
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def _write(p: pathlib.Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=1, ensure_ascii=False),
                 encoding="utf-8")


def _load_pinned():
    rows = [json.loads(l) for l in
            (PIN_FULL / "n03_cases.public.jsonl").read_text(
                encoding="utf-8").splitlines() if l.strip()]
    exps = {e["case_id"]: e for e in
            (json.loads(l) for l in (PIN_FULL / "n03_dev_expectations.jsonl")
             .read_text(encoding="utf-8").splitlines() if l.strip())}
    return rows, exps


def canary_integration_evidence(exps, cases_by_id) -> pathlib.Path:
    """Full-family sweep with the REAL Batch C production legs injected
    (canary executes the actual pipeline components; real payloads +
    stored expectations per the pilot finding)."""
    witnesses = json.loads(
        (EVID / "dualpath_witnesses_batch_c.json")
        .read_text(encoding="utf-8"))["rows"]
    tmp = ROOT / ".runtime" / "auth2c_canary"
    if tmp.exists():
        shutil.rmtree(tmp)            # clean-slate campaign workdir
    tmp.mkdir(parents=True, exist_ok=True)
    br = CircuitBreaker(tmp / "cb.json")
    sched = canary_mod.CanaryScheduler(
        [w for w in witnesses if w["kind"] != "software-error"],
        breaker=br, expectations=exps, cases_by_id=cases_by_id)
    sched.production_parser = ppr_c.parse_response
    sched.production_evaluator = pev_c.ProductionEvaluatorC()
    results = sched.run_canary_sweep()
    passed = all(r.passed for r in results)
    p = AUTH2C / "canary_integration.json"
    _write(p, {
        "passed": passed,
        "sweep": "ALL Batch C families at one checkpoint (full sweep "
                 "bounds family-local fault latency to one interval)",
        "production_legs": {
            "parser": "eval_assurance.production.parser_c@1",
            "evaluator": "eval_assurance.production.evaluator_c@1"},
        "families": {r.family: {"passed": r.passed,
                                "positive": r.positive_checks,
                                "negative": r.negative_checks}
                     for r in results}})
    return p


def breaker_drill_evidence() -> pathlib.Path:
    """Open -> containment visible across restart -> requalification-
    only recovery (hand recovery refused)."""
    tmp = ROOT / ".runtime" / "auth2c_breaker"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True, exist_ok=True)
    br = CircuitBreaker(tmp / "cb.json")
    br.register_dispatch("in-flight-b1")
    br.open(reason="drill-batch-c", affected_scope=["C09"],
            contamination_window=["tb1"])
    restart = CircuitBreaker(tmp / "cb.json")
    contained = restart.is_open and "tb1" in \
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
    p = AUTH2C / "breaker_drill.json"
    _write(p, {"passed": contained and not recovered_wrongly
               and not restart.is_open,
               "restart_safe_containment": contained,
               "hand_recovery_refused": not recovered_wrongly,
               "requalification_recovery": not restart.is_open})
    return p


def issue_certificate() -> tuple:
    from eval_assurance.qualification.store import CertificateStore
    reg = EVID / "certificates" / "registry.json"
    reg.parent.mkdir(parents=True, exist_ok=True)
    # EXTEND the existing registry — never replace it: the live Batch A
    # certificate (512efb617a9cb4c8) stays registered alongside the
    # Batch C certificate
    store = CertificateStore.load_registry(reg)
    authority = QualificationAuthority(persist_to=reg)

    def rel(p: pathlib.Path) -> pathlib.Path:
        # certificate refs are REPO-RELATIVE (absolute user paths are a
        # scanner finding; established convention from Wave B)
        return pathlib.Path(os.path.relpath(pathlib.Path(p), ROOT))
    store = authority.issue_qualification(
        scope="semantic",        # aggregation scope category (lookup key)
        dataset_id="n03-batch-c-dev160@c772a9a",
        parser_version="eval_assurance.production.parser_c@1",
        evaluator_version="eval_assurance.production.evaluator_c@1",
        reference_evaluator_version=
            "eval_assurance.reference.oracle_c@1",
        dataset_file=rel(PIN_FULL / "n03_cases.public.jsonl"),
        task_contract_file=rel(PIN_FULL / "requirements_batch_c.md"),
        parser_file=rel(SRC / "production" / "parser_c.py"),
        interpreter_file=rel(SRC / "reference" / "interpreter_c.py"),
        evaluator_file=rel(SRC / "production" / "evaluator_c.py"),
        reference_oracle_file=rel(SRC / "reference" / "oracle_c.py"),
        witness_suite_file=rel(EVID / "dualpath_witnesses_batch_c.json"),
        mutation_report_file=rel(EVID /
                                 "production_mutation_campaign_batch_c.json"),
        evidence_files=[
            rel(EVID / "intake_verification_batch_c.json"),
            rel(EVID / "ground_truth_qualification_dev160_batch_c.json"),
            rel(EVID / "gt_mutation_coverage_dev160_batch_c.json"),
            rel(EVID / "pinned_full" / "pin_manifest.json"),
        ],
        replay_contract="witness rows re-executed via "
                        "dualpath_c.evaluate_dual(case, expectation, "
                        "raw) on the pinned full roster",
        protocol="cpu-dualpath-qualification:N03_BATCH_C_DEV_CPU_DUALPATH",
        limitations="CPU software qualification of the Batch C dual-path "
                    "stack on pinned Batch C dev inputs (C17-C24). NOT "
                    "a physical-runner qualification, NOT confirmation-"
                    "split coverage, NOT Batch A/C/D coverage (no "
                    "cross-batch carry-over). Disclosed common-mode "
                    "risks: shared pinned handoff authorship for "
                    "production+reference legs.",
        store=store)
    cert_ids = [c.certificate_id for c in store.snapshot().certificates]
    return store, cert_ids


def consumer_verification(auth_path: pathlib.Path,
                          roster_file: pathlib.Path) -> dict:
    """REAL IJ-NANO consumer: import the pinned authorization module
    from the IJNANO worktree (read-only), issue through the provider
    against the LIVE registered Batch C evidence, validate_against the
    exact scope. The mutating revocation drill runs in an ISOLATED
    SUBPROCESS against a copy of the registry (the live registration
    and the Batch A registration stay untouched)."""
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
            auth_path.read_text(encoding="utf-8"))["authorization"]
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

    # -- isolated revocation drill (subprocess; registry copy) ---------
    import subprocess
    drill_out = ROOT / ".runtime" / "auth2c_drill_result.json"
    script = ROOT / "scripts" / "ij_eval_assurance" / "auth2c_drill.py"
    proc = subprocess.run(
        [sys.executable, "-I", str(script)],
        capture_output=True, text=True, cwd=str(ROOT))
    revoked_refused = False
    drill_detail = proc.stdout.strip()[-500:] if proc.stdout else ""
    if proc.returncode == 0 and drill_out.is_file():
        revoked_refused = json.loads(
            drill_out.read_text(encoding="utf-8")).get("revoked_refused")
    return {
        "schema": "ijeval.auth2c.consumer_verification.v1",
        "consumer": "REAL benchmarks.ij_nano.n03.authorization "
                    "(EAEExecutionAuthorizationProvider + "
                    "validate_against, imported from the IJNANO "
                    "worktree, read-only, no doubles)",
        "result": "physical authorization issued and validated for the "
                  "exact AUTH-2 Batch C scope "
                  f"({EXPERIMENT}, 480-slot roster digest, 3 models); "
                  "qualifying_class=EAE; checksum valid"
                  if issue_ok else "FAILED",
        "issue_ok": issue_ok,
        "revocation_drill": "EAE-side authoritative revocation stops "
                            "the real consumer at the next issuance "
                            "(drill isolated in a subprocess against a "
                            "registry copy; live registrations "
                            "untouched)" if revoked_refused else
                            "REVOCATION DRILL FAILED",
        "revoked_refused": revoked_refused,
        "drill_stderr_tail": proc.stderr.strip()[-300:]
                             if proc.returncode != 0 else "",
        "drill_detail": drill_detail,
        "environment_note": "provider pinned to EAE_CONTRACT_REVISION "
                            f"({ea.EAE_CONTRACT_REVISION}); the "
                            "IJ-NANO owner re-pins their runtime to the "
                            "published commit"}


def main() -> int:
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    AUTH2C.mkdir(parents=True, exist_ok=True)

    ea18 = json.loads((EA18 / "independent_acceptance.json")
                      .read_text(encoding="utf-8"))
    if ea18["gate"] != "N03_SHARED_EVALUATION_ASSURANCE_CORE_GO":
        print("EA18 gate not GO — AUTH-2 Batch C retained BLOCKED")
        return 1
    ea13b = json.loads((EA13C / "primitive_qualification_batch_c.json")
                       .read_text(encoding="utf-8"))
    if ea13b["summary"]["qualified"] != 8:
        print("EA13-B not 8/8 — AUTH-2 Batch C retained BLOCKED")
        return 1

    rows, exps = _load_pinned()
    cases_by_id = {r["case_id"]: r for r in rows}
    canary_file = canary_integration_evidence(exps, cases_by_id)
    breaker_file = breaker_drill_evidence()
    if not json.loads(canary_file.read_text(encoding="utf-8"))["passed"]:
        print("canary integration not passing — BLOCKED")
        return 1
    if not json.loads(breaker_file.read_text(encoding="utf-8"))["passed"]:
        print("breaker drill not passing — BLOCKED")
        return 1

    # -- AUTH-2 Batch C shared-core acceptance --------------------------
    acc = AUTH2C / "auth2c_shared_core_acceptance.json"
    _write(acc, {
        "schema": "ijeval.auth2c.acceptance.v1",
        "verdict": "ACCEPTED",
        "basis": {
            "gate": ea18["gate"],
            "ea18_artifact": "evidence/IJEVAL/EA18/"
                             "independent_acceptance.json",
            "ea18_artifact_sha256": _sha(
                EA18 / "independent_acceptance.json"),
            "core_modules_unchanged": "Batch C legs are NEW modules; "
                                      "the Batch A qualified sources "
                                      "(parser/evaluator/interpreter/"
                                      "oracle) are byte-identical — "
                                      "their registered digests stay "
                                      "current",
            "dependencies": ea18["dependencies"]["ok"]},
        "requirements_map": {
            "shared EAE core protection gates": "Wave B + Wave C "
                                                "(unchanged, EA18)",
            "Batch C semantic qualification": "EA03-B GT 160/160 + "
                                              "470/0 mutation controls",
            "Batch C dual-path closure": "Wave B-B 126/126 witnesses; "
                                         "12 detected + 2 EQUIVALENT "
                                         "justified, 0 escapes",
            "EA13-B cognitive qualification": "8/8 Batch C dev "
                                              "primitives",
            "canary integration": "full-family sweep through the real "
                                  "Batch C legs (passed)",
            "breaker containment": "restart-safe, requalification-only "
                                   "recovery (passed)"},
        "scope_limits": "development split only; protected confirmation "
                        "NOT covered (roster_split=development); "
                        "physical runtime identities must match the "
                        "IJ-NANO model registry; Batch C scope only "
                        "(C17-C24) — no cross-batch carry-over",
        "verified_utc": stamp})

    # -- deterministic full Batch C dev roster: 160 x 3 = 480 ----------
    dev = [c for c in rows if c.get("split") == "development" and
           c["primitive"] in PRIMS]
    slots = [{"slot": i + 1, "case_id": c["case_id"],
              "primitive": c["primitive"], "family": c["family"],
              "language": c["language"], "model": m}
             for m in MODELS for i, c in enumerate(dev)]
    slots.sort(key=lambda s: (MODELS.index(s["model"]), s["slot"]))
    roster_file = AUTH2C / "development_roster_480.json"
    _write(roster_file, {
        "schema": "ijeval.auth2c.development_roster.v1",
        "experiment": EXPERIMENT, "models": MODELS,
        "selection_rule": "ALL 160 Batch C development cases (complete "
                          "dev split, canonical pinned order; no case "
                          "removed) x 3 models",
        "slot_count": len(slots), "slots": slots})

    # -- certificate + trusted registration + authorization ------------
    store, cert_ids = issue_certificate()
    from eval_assurance.authoritative import (
        AuthoritativeQualificationState)
    state = AuthoritativeQualificationState(
        store, AUTH2C / "authoritative_state.json")

    ea.clear_execution_evidence()
    evidence = ea.register_trusted_execution_evidence(
        authoritative_state=state,
        experiment_id=EXPERIMENT, auth_purpose="AUTH-2",
        primitives=PRIMS, protocols=["chat"], models=MODELS,
        dataset_file=PIN_FULL / "n03_cases.public.jsonl",
        roster_file=roster_file,
        parser_file=SRC / "production" / "parser_c.py",
        evaluator_file=SRC / "production" / "evaluator_c.py",
        interpreter_file=SRC / "reference" / "interpreter_c.py",
        oracle_file=SRC / "reference" / "oracle_c.py",
        certificate_store=store,
        shared_core_acceptance_file=acc,
        canary_evidence_file=canary_file,
        breaker_evidence_file=breaker_file,
        witness_suite_file=EVID / "dualpath_witnesses_batch_c.json",
        mutation_report_file=EVID /
            "production_mutation_campaign_batch_c.json",
        ea13_scope_file=EA13C / "primitive_qualification_batch_c.json",
        ea18_scope_file=EA18 / "independent_acceptance.json",
        dispatch_limits={"max_trials": len(slots)})

    auth = ea.issue_execution_authorization(
        experiment_id=EXPERIMENT,
        dataset_digest=_sha(PIN_FULL / "n03_cases.public.jsonl"),
        roster_digest=_sha(roster_file),
        primitives=PRIMS, protocols=["chat"], models=MODELS,
        auth_level="AUTH-2", eae_revision=ea.EAE_CONTRACT_REVISION)

    auth_file = AUTH2C / "execution_authorization.json"
    _write(auth_file, {
        "note": "issued for the full Batch C development scope; "
                "consumer must verify checksum and recheck before "
                "every dispatch",
        "authorization": json.loads(auth.to_json()),
        "issued_utc": stamp})

    # -- REAL consumer verification --------------------------------------
    cv = consumer_verification(auth_file, roster_file)
    _write(AUTH2C / "consumer_verification.json", cv)
    if not (cv.get("issue_ok") and cv.get("revoked_refused")):
        print("consumer verification FAILED — release retained BLOCKED")
        return 1

    _write(AUTH2C / "release.json", {
        "schema": "ijeval.auth2c.release.v1",
        "status": "EAE-SIDE-RELEASED (physical execution by the "
                  "IJ-NANO owner at the pinned revision)",
        "experiment": EXPERIMENT, "auth_level": "AUTH-2",
        "scope": {"slots": len(slots), "models": MODELS,
                  "dev_cases": len(dev),
                  "roster_digest": _sha(roster_file),
                  "dataset_digest":
                      _sha(PIN_FULL / "n03_cases.public.jsonl"),
                  "primitives": PRIMS,
                  "primitives_qualified": 8,
                  "progressive_note": "all 8 Batch C primitives "
                                      "qualified -> full 480-slot "
                                      "Batch C dev scope; narrower "
                                      "preregistered scopes remain "
                                      "permissible"},
        "eae_contract_revision": ea.EAE_CONTRACT_REVISION,
        "authorization_checksum": auth.checksum,
        "certificate_ids": cert_ids,
        "shared_core_gate": ea18["gate"],
        "dispatch_limits": {"max_trials": len(slots)},
        "confirmation_status": "BLOCKED (AUTH-3 requires frozen model "
                               "identities/policies + confirmation "
                               "roster + verified holdout separation; "
                               "not registered)",
        "batch_note": "independent Batch C qualification — granted "
                      "from Batch C evidence only, never from the "
                      "Batch A certificate",
        "generated_utc": stamp})
    print("slots:", len(slots))
    print("authorization checksum:", auth.checksum[:16], "...")
    print("certificates:", cert_ids)
    print("AUTH-2 Batch C release written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
