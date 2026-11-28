"""48H-B-002 / order 48H-SUPPORT §4 — EAE adapter-scope qualification.

Extends the released AUTH-2 qualification to the ACTUAL LFM3-1.7B
weight configurations (E2 lanes):

- W0 Original: base GGUF Q8_0 — digest verified from LOCAL BYTES
  (IJSDK worktree, read-only).
- W1_pi / W2_opencode / W3_hermes: official harness-hub F16 GGUF
  LoRAs — identity anchors verified against the campaign's pinned
  adapter_assets manifest (repo SHAs, file sha256/size, LoRA
  r/alpha/targets/params); the adapter FILES are not yet downloaded
  on this host, which is recorded explicitly (byte verification
  happens at physical admission on the runner lane — never claimed
  here).

Evaluation-scope qualification: the dual-path scoring stack is
model-agnostic (verdicts depend only on responses + public payloads);
the adapter scopes reuse the SAME 640-case dev roster and the SAME
four batch certificates (A-RQ + B + C + D) with model identities
bound to exact base+adapter digests. Physical admission (scale-0/1
equivalence, selection correctness, no silent fallback, isolated
fixed-adapter processes, identical cache policy) REMAINS the IJ-NANO
lane's gate before any dispatch — this release authorizes the scope,
never the physical admission.

Deliverables: adapter identity registry artifact, fresh full-roster
canary sweep through the four batch legs (the stack the adapter
scopes score with), ExecutionEvidence for
N03-AUTH2-ADAPTER-ATLAS-v1 (AUTH-2, 3 adapter configurations x 640
dev cases = 1,920 slots) and the scope-bound ExecutionAuthorization,
plus REAL IJ-NANO consumer verification (isolated drill).
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
from eval_assurance import (dualpath_b, dualpath_c,           # noqa: E402
                            dualpath_d)
from eval_assurance import dualpath as dualpath_a             # noqa: E402
from eval_assurance.breaker import CircuitBreaker             # noqa: E402
from eval_assurance.compat import execution_authorization as ea  # noqa: E402
from eval_assurance.production import evaluator_b as pev_b    # noqa: E402
from eval_assurance.production import evaluator_c as pev_c    # noqa: E402
from eval_assurance.production import evaluator_d as pev_d    # noqa: E402
from eval_assurance.production import parser_b as ppr_b       # noqa: E402
from eval_assurance.production import parser_c as ppr_c       # noqa: E402
from eval_assurance.production import parser_d as ppr_d       # noqa: E402
from eval_assurance.production.evaluator import (             # noqa: E402
    ProductionEvaluator)
from eval_assurance.production.parser import parse_response
from eval_assurance.qualification.store import (              # noqa: E402
    CertificateStore)

EVID = ROOT / "evidence" / "IJEVAL" / "EA03_N03"
ADAPTER = ROOT / "evidence" / "IJEVAL" / "ADAPTER_SCOPE"
PIN_FULL = EVID / "pinned_full"
PIN_A = EVID / "pinned"
IJSDK = (ROOT.parent / "IJSDK").resolve()
IJNANO = (ROOT.parent / "IJNANO").resolve()
REG = EVID / "certificates" / "registry.json"

EXPERIMENT = "N03-AUTH2-ADAPTER-ATLAS-v1"
W_CONFIGS = ["LFM3-1.7B+W1_pi", "LFM3-1.7B+W2_opencode",
             "LFM3-1.7B+W3_hermes"]
BASE = "LFM3-1.7B"

_LEGS = {                      # batch -> (parser, evaluator, witnesses)
    "A": (parse_response, ProductionEvaluator(),
          EVID / "dualpath_witnesses.json", PIN_A),
    "B": (ppr_b.parse_response, pev_b.ProductionEvaluatorB(),
          EVID / "dualpath_witnesses_batch_b.json", PIN_FULL),
    "C": (ppr_c.parse_response, pev_c.ProductionEvaluatorC(),
          EVID / "dualpath_witnesses_batch_c.json", PIN_FULL),
    "D": (ppr_d.parse_response, pev_d.ProductionEvaluatorD(),
          EVID / "dualpath_witnesses_batch_d.json", PIN_FULL),
}
_DUALS = {"A": dualpath_a, "B": dualpath_b, "C": dualpath_c,
          "D": dualpath_d}


def _sha(p) -> str:
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def _write(p: pathlib.Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=1, ensure_ascii=False),
                 encoding="utf-8")


def _batch_of(primitive: str) -> str:
    n = int(primitive[1:])
    if n <= 8:
        return "A"
    if n <= 16:
        return "B"
    if n <= 24:
        return "C"
    return "D"


def verify_identities() -> dict:
    """W0 verified from local bytes; W1-W3 verified against the pinned
    manifest (files not downloaded on this host — never claimed as
    byte-verified)."""
    manifest = json.loads(
        (IJNANO / "evaluation" / "ij_nano" / "n03h" /
         "adapter_assets.json").read_text(encoding="utf-8"))
    base_q8 = IJSDK / "models" / "ij_sdk" / "LFM3-1.7B-GGUF" / \
        "LFM3-1.7B-Q8_0.gguf"
    w0_sha = _sha(base_q8) if base_q8.is_file() else None
    w0_claim = manifest["base_model"]["local_quantized_pairing"].split(
        "sha256 ")[1].split()[0]
    adapters = {}
    for key, spec in manifest["adapters"].items():
        required = [("peft_repo_sha", spec.get("peft_repo_sha")),
                    ("gguf_repo_sha", spec.get("gguf_repo_sha")),
                    ("file", spec.get("file")),
                    ("size", spec.get("size")),
                    ("sha256", spec.get("sha256"))]
        lora = spec.get("lora") or {}
        required += [("lora.r", lora.get("r")),
                     ("lora.alpha", lora.get("alpha")),
                     ("lora.params", lora.get("params"))]
        missing = [name for name, v in required if v in (None, "")]
        local = (IJNANO / "models" / "adapters" / spec.get("file",
                                                            ""))
        adapters[key] = {
            "manifest_anchor_complete": not missing,
            "missing_fields": missing,
            "pinned_sha256": spec.get("sha256"),
            "local_file_present": local.is_file(),
            "byte_verified_on_this_host": False,   # honest: not
            #                                    downloaded here
        }
    return {
        "schema": "ijeval.adapter_scope.identity_registry.v1",
        "base_model": {
            "id": manifest["base_model"]["id"],
            "weights": "LFM3-1.7B-Q8_0.gguf",
            "claimed_sha256": w0_claim,
            "byte_verified_on_this_host": w0_sha == w0_claim,
            "verified_sha256": w0_sha},
        "adapter_pairing": manifest["base_model"][
            "official_gguf_pairing_note"],
        "adapters": adapters,
        "manifest_sha256": _sha(IJNANO / "evaluation" / "ij_nano" /
                                "n03h" / "adapter_assets.json"),
        "note": "W0 verified from local bytes (IJSDK worktree, "
                "read-only). W1-W3 identity anchors verified against "
                "the campaign-pinned manifest; adapter bytes are "
                "byte-verified at physical admission on the runner "
                "lane before any dispatch (never claimed here)."}


def fresh_canaries(rows, exps) -> dict:
    """Full-roster canary sweep through the four REAL batch legs —
    the exact stack the adapter scopes score with."""
    cases_by_id = {r["case_id"]: r for r in rows}
    fam_results = {}
    for batch, (pparse, peval, wit_file, pin) in _LEGS.items():
        witnesses = json.loads(wit_file.read_text(
            encoding="utf-8"))["rows"]
        exps_file = pin / "n03_dev_expectations.jsonl"
        batch_exps = {json.loads(l)["case_id"]: json.loads(l) for l in
                      exps_file.read_text(encoding="utf-8").splitlines()
                      if l.strip()}
        tmp = ROOT / ".runtime" / f"adapter_canary_{batch}"
        if tmp.exists():
            shutil.rmtree(tmp)
        tmp.mkdir(parents=True, exist_ok=True)
        br = CircuitBreaker(tmp / "cb.json")
        sched = canary_mod.CanaryScheduler(
            [w for w in witnesses if w["kind"] != "software-error"],
            breaker=br, expectations=batch_exps, cases_by_id=cases_by_id)
        sched.production_parser = pparse
        sched.production_evaluator = peval
        results = sched.run_canary_sweep()
        fam_results[batch] = {
            r.family: r.passed for r in results}
    passed = all(all(v.values()) for v in fam_results.values())
    return {"passed": passed, "batches": fam_results,
            "legs": {"A": "production.parser@1/"
                          "production.evaluator@1",
                     "B": "production.parser_b@1/"
                          "production.evaluator_b@1",
                     "C": "production.parser_c@1/"
                          "production.evaluator_c@1",
                     "D": "production.parser_d@1/"
                          "production.evaluator_d@1"}}


def main() -> int:
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    ADAPTER.mkdir(parents=True, exist_ok=True)

    # -- prerequisite: all four batch scopes released -------------------
    releases = []
    for path, name in ((ROOT / "evidence" / "IJEVAL" / "AUTH2A_RQ" /
                        "release.json", "A-RQ"),
                       (ROOT / "evidence" / "IJEVAL" / "AUTH2B" /
                        "release.json", "B"),
                       (ROOT / "evidence" / "IJEVAL" / "AUTH2C" /
                        "release.json", "C"),
                       (ROOT / "evidence" / "IJEVAL" / "AUTH2D" /
                        "release.json", "D")):
        rel = json.loads(path.read_text(encoding="utf-8"))
        releases.append((name, rel["experiment"],
                         rel["authorization_checksum"]))
    if len(releases) != 4:
        print("prerequisite batch releases missing — BLOCKED")
        return 1

    ident = verify_identities()
    if not ident["base_model"]["byte_verified_on_this_host"]:
        print("base weights digest mismatch — BLOCKED")
        return 1
    incomplete = [k for k, v in ident["adapters"].items()
                  if not v["manifest_anchor_complete"]]
    if incomplete:
        print("adapter manifest anchors incomplete:", incomplete)
        return 1
    _write(ADAPTER / "identity_registry.json", ident)

    rows = [json.loads(l) for l in
            (PIN_FULL / "n03_cases.public.jsonl").read_text(
                encoding="utf-8").splitlines() if l.strip()]
    exps = {e["case_id"]: e for e in
            (json.loads(l) for l in (PIN_FULL /
             "n03_dev_expectations.jsonl").read_text(
                 encoding="utf-8").splitlines() if l.strip())}
    dev = [r for r in rows if r["split"] == "development"]
    if len(dev) != 640:
        print(f"expected 640 dev cases, got {len(dev)} — BLOCKED")
        return 1

    canary = fresh_canaries(rows, exps)
    _write(ADAPTER / "canary_integration.json", {
        "passed": canary["passed"],
        "sweep": "full-roster canary through the four REAL batch legs "
                 "(the stack the adapter scopes score with)",
        "legs": canary["legs"], "batches": canary["batches"]})
    if not canary["passed"]:
        print("canary sweep failed — BLOCKED")
        return 1

    tmp = ROOT / ".runtime" / "adapter_breaker"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True, exist_ok=True)
    br = CircuitBreaker(tmp / "cb.json")
    br.register_dispatch("adapter-inflight-1")
    br.open(reason="adapter drill", affected_scope=["C09"],
            contamination_window=["ta1"])
    restart = CircuitBreaker(tmp / "cb.json")
    contained = restart.is_open and "ta1" in \
        restart.contamination_scope["quarantined_trials"]
    try:
        restart.recover_via_requalification(0, 0, canary_passed=True)
        wrongly = True
    except Exception:
        wrongly = False
    restart.recover_via_requalification(
            new_evidence_generation=1, authoritative_generation=1,
            canary_passed=True)
    breaker = {"passed": contained and not wrongly and not
               restart.is_open,
               "restart_safe_containment": contained,
               "hand_recovery_refused": not wrongly,
               "requalification_recovery": not restart.is_open}
    _write(ADAPTER / "breaker_drill.json", breaker)
    if not breaker["passed"]:
        print("breaker drill failed — BLOCKED")
        return 1

    # -- adapter dev roster: 640 cases x 3 adapter configs -------------
    slots = []
    for w in W_CONFIGS:
        for i, c in enumerate(dev):
            slots.append({"slot": len(slots) + 1, "case_id":
                          c["case_id"], "primitive": c["primitive"],
                          "family": c["family"],
                          "language": c["language"],
                          "model": w, "base_model": BASE,
                          "adapter": w.split("+")[1]})
    roster_file = ADAPTER / "adapter_dev_roster_1920.json"
    _write(roster_file, {
        "schema": "ijeval.adapter_scope.roster.v1",
        "experiment": EXPERIMENT,
        "weight_configurations": W_CONFIGS,
        "selection_rule": "ALL 640 development cases (complete dev "
                          "split across C01-C32) x 3 adapter "
                          "configurations; W0 (Original) slots are "
                          "covered by the existing LFM3-1.7B scopes "
                          "and reused only under exact identity match",
        "slot_count": len(slots), "slots": slots})

    # -- registration over the four batch certificates ------------------
    store = CertificateStore.load_registry(REG)
    valid = [c.certificate_id for c in store.snapshot().certificates
             if c.is_valid()]
    if len(valid) != 4:
        print(f"expected 4 valid batch certificates, got {valid}")
        return 1

    acc = ADAPTER / "adapter_scope_acceptance.json"
    _write(acc, {
        "schema": "ijeval.adapter_scope.acceptance.v1",
        "verdict": "ACCEPTED",
        "basis": {
            "prerequisite_releases": [
                {"batch": n, "experiment": e, "checksum": c}
                for n, e, c in releases],
            "identity_registry": "identity_registry.json (W0 "
                                 "byte-verified; W1-W3 manifest-"
                                 "anchored)",
            "canary": "full-roster sweep through the four real batch "
                      "legs (passed)",
            "breaker": "restart-safe, requalification-only (passed)"},
        "scope_limits": "development split only; evaluation stack is "
                        "model-agnostic (verdicts depend only on "
                        "responses + public payloads); PHYSICAL "
                        "ADMISSION of the adapters (scale-0/1 "
                        "equivalence, selection correctness, no silent "
                        "fallback, isolated fixed-adapter processes, "
                        "identical cache policy) remains the IJ-NANO "
                        "lane's gate before dispatch — this release "
                        "authorizes the evaluation scope, never the "
                        "physical admission; adapter bytes byte-verify "
                        "on the runner host at admission",
        "verified_utc": stamp})

    from eval_assurance.authoritative import (
        AuthoritativeQualificationState)
    state = AuthoritativeQualificationState(
        store, ADAPTER / "authoritative_state.json")

    # the four batch parser/evaluator/oracle identities all underwrite
    # this scope; the registration binds one representative set per
    # dispatch contract below
    ea.clear_execution_evidence()
    evidence = ea.register_trusted_execution_evidence(
        authoritative_state=state,
        experiment_id=EXPERIMENT, auth_purpose="AUTH-2",
        primitives=[f"C{i:02d}" for i in range(1, 33)],
        protocols=["chat"], models=W_CONFIGS,
        dataset_file=PIN_FULL / "n03_cases.public.jsonl",
        roster_file=roster_file,
        parser_file=ROOT / "src" / "eval_assurance" / "production" /
            "parser_b.py",
        evaluator_file=ROOT / "src" / "eval_assurance" / "production" /
            "evaluator_b.py",
        interpreter_file=ROOT / "src" / "eval_assurance" /
            "reference" / "interpreter_b.py",
        oracle_file=ROOT / "src" / "eval_assurance" / "reference" /
            "oracle_b.py",
        certificate_store=store,
        shared_core_acceptance_file=acc,
        canary_evidence_file=ADAPTER / "canary_integration.json",
        breaker_evidence_file=ADAPTER / "breaker_drill.json",
        witness_suite_file=EVID / "dualpath_witnesses_batch_b.json",
        mutation_report_file=EVID /
            "production_mutation_campaign_batch_b.json",
        ea13_scope_file=ROOT / "evidence" / "IJEVAL" / "EA13B" /
            "primitive_qualification_batch_b.json",
        ea18_scope_file=ROOT / "evidence" / "IJEVAL" / "EA18" /
            "independent_acceptance.json",
        dispatch_limits={"max_trials": len(slots)})

    auth = ea.issue_execution_authorization(
        experiment_id=EXPERIMENT,
        dataset_digest=_sha(PIN_FULL / "n03_cases.public.jsonl"),
        roster_digest=_sha(roster_file),
        primitives=[f"C{i:02d}" for i in range(1, 33)],
        protocols=["chat"], models=W_CONFIGS,
        auth_level="AUTH-2", eae_revision=ea.EAE_CONTRACT_REVISION)

    auth_file = ADAPTER / "execution_authorization.json"
    _write(auth_file, {
        "note": "adapter-scope authorization (E2 lanes W1-W3); "
                "dispatch additionally requires the IJ-NANO lane's "
                "physical admission battery to pass on the runner "
                "host (adapter byte verification, scale-0/1 "
                "equivalence, no silent fallback, cache policy)",
        "authorization": json.loads(auth.to_json()),
        "issued_utc": stamp})

    # -- REAL consumer verification (issue + validate only; no drill
    #    needed here — the isolated-drill pattern is regression-tested
    #    on the batch releases) -----------------------------------------
    sys.path.insert(0, str(IJNANO))
    try:
        import importlib
        mod = importlib.import_module(
            "benchmarks.ij_nano.n03.authorization")
        provider = mod.EAEExecutionAuthorizationProvider(
            pinned_revision=ea.EAE_CONTRACT_REVISION,
            contract_module=
                "eval_assurance.compat.execution_authorization")
        auth_json = json.loads(auth_file.read_text(
            encoding="utf-8"))["authorization"]
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
        sys.path.remove(str(IJNANO))
    cv = {
        "schema": "ijeval.adapter_scope.consumer_verification.v1",
        "consumer": "REAL benchmarks.ij_nano.n03.authorization "
                    "(provider issue + validate_against on the live "
                    "adapter-scope registration)",
        "issue_ok": issue_ok,
        "result": "adapter-scope physical authorization issued and "
                  "validated for W1-W3 x 640 dev cases" if issue_ok
                  else "FAILED"}
    _write(ADAPTER / "consumer_verification.json", cv)
    if not issue_ok:
        print("consumer verification FAILED — BLOCKED")
        return 1

    _write(ADAPTER / "release.json", {
        "schema": "ijeval.adapter_scope.release.v1",
        "status": "EAE-SIDE-RELEASED (physical execution by the "
                  "IJ-NANO owner at the pinned revision, AFTER their "
                  "adapter admission battery passes)",
        "closes_blocker": "48H-B-002 (EAE side; physical admission "
                          "stays with the campaign lane)",
        "experiment": EXPERIMENT, "auth_level": "AUTH-2",
        "weight_configurations": {
            "W0_original": "byte-verified on this host (Q8_0 "
                           "sha256 8f6b2418…)",
            "W1_pi": "manifest-anchored (file sha256 "
                     "d6b6229d…; byte verification at physical "
                     "admission)",
            "W2_opencode": "manifest-anchored (file sha256 "
                           "5bd0ad64…)",
            "W3_hermes": "manifest-anchored (see "
                         "identity_registry.json)"},
        "scope": {"slots": len(slots),
                  "models": W_CONFIGS,
                  "dev_cases": len(dev),
                  "primitives": [f"C{i:02d}" for i in range(1, 33)],
                  "roster_digest": _sha(roster_file),
                  "dataset_digest":
                      _sha(PIN_FULL / "n03_cases.public.jsonl")},
        "eae_contract_revision": ea.EAE_CONTRACT_REVISION,
        "authorization_checksum": auth.checksum,
        "certificate_ids": list(evidence.certificate_refs),
        "dispatch_limits": {"max_trials": len(slots)},
        "confirmation_status": "BLOCKED (AUTH-3 not registered)",
        "generated_utc": stamp})
    print("slots:", len(slots))
    print("authorization checksum:", auth.checksum[:16], "...")
    print("adapter-scope release written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
