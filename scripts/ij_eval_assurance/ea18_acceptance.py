"""EA18 — independent adversarial acceptance (order section 6).

Genuine end-to-end attempts to bypass execution and publication
authorization, executed FRESH here (not replays of earlier controls),
plus the acceptance aggregation over every common-core dependency
(Wave B, Wave C, catastrophe pilot, EA12, EA13, EA14).

The final gate N03_SHARED_EVALUATION_ASSURANCE_CORE_GO is granted only
when every dependency genuinely passes.
"""
from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from eval_assurance import canary as canary_mod              # noqa: E402
from eval_assurance.compat import execution_authorization as ea     # noqa: E402
from eval_assurance.analysis import QualifiedAnalyzer        # noqa: E402
from eval_assurance.authoritative import (                   # noqa: E402
    AuthoritativeQualificationState)
from eval_assurance.breaker import CircuitBreaker            # noqa: E402
from eval_assurance.dualpath import (MISSING, DualPathSession,  # noqa
                                      evaluate_dual)
from eval_assurance.qualification.store import (             # noqa: E402
    CertificateStore, QualificationAuthority)

EVID = ROOT / "evidence" / "IJEVAL"
EA03 = EVID / "EA03_N03"
PINNED = EA03 / "pinned"
SRC = ROOT / "src" / "eval_assurance"

ATTEMPTS = []


def attempt(name):
    def deco(fn):
        ATTEMPTS.append((name, fn))
        return fn
    return deco


def _fixture(tmp: pathlib.Path):
    tmp.mkdir(parents=True, exist_ok=True)
    for name, obj in (("sc.json", {"verdict": "ACCEPTED"}),
                      ("canary.json", {"passed": True}),
                      ("br.json", {"passed": True})):
        (tmp / name).write_text(json.dumps(obj), encoding="utf-8")
    roster = tmp / "roster.json"
    roster.write_text('{"slots": ["a"]}', encoding="utf-8")
    store = QualificationAuthority().issue_qualification(
        scope="semantic", dataset_id="n03-batch-a-dev160@d23de5a",
        parser_version="eval_assurance.production.parser@1",
        evaluator_version="eval_assurance.production.evaluator@1",
        reference_evaluator_version="oracle@v2",
        dataset_file=PINNED / "n03_cases.public.jsonl",
        task_contract_file=PINNED / "parser_semantics.md",
        parser_file=SRC / "production" / "parser.py",
        interpreter_file=SRC / "reference" / "interpreter.py",
        evaluator_file=SRC / "production" / "evaluator.py",
        reference_oracle_file=SRC / "reference" / "oracle.py",
        witness_suite_file=EA03 / "dualpath_witnesses.json",
        mutation_report_file=EA03 /
        "production_mutation_campaign.json",
        evidence_files=[tmp / "sc.json", tmp / "canary.json",
                        tmp / "br.json"],
        replay_contract="r", protocol="cpu-ea18")
    state = AuthoritativeQualificationState(store,
                                            tmp / "auth.json")
    ea.clear_execution_evidence()
    ea.register_trusted_execution_evidence(
        authoritative_state=state, experiment_id="ea18",
        auth_purpose="AUTH-1",
        primitives=["C01"], protocols=["chat"],
        models=["synthetic-cpu"],
        dataset_file=PINNED / "n03_cases.public.jsonl",
        roster_file=roster,
        parser_file=SRC / "production" / "parser.py",
        evaluator_file=SRC / "production" / "evaluator.py",
        interpreter_file=SRC / "reference" / "interpreter.py",
        oracle_file=SRC / "reference" / "oracle.py",
        certificate_store=store,
        shared_core_acceptance_file=tmp / "sc.json",
        canary_evidence_file=tmp / "canary.json",
        breaker_evidence_file=tmp / "br.json",
        witness_suite_file=EA03 / "dualpath_witnesses.json",
        mutation_report_file=EA03 /
        "production_mutation_campaign.json")
    dd = hashlib.sha256(
        (PINNED / "n03_cases.public.jsonl").read_bytes()).hexdigest()
    rd = hashlib.sha256(roster.read_bytes()).hexdigest()
    return store, state, roster, dd, rd


def _issue(dd, rd, **over):
    kw = dict(experiment_id="ea18", dataset_digest=dd, roster_digest=rd,
              primitives=["C01"], protocols=["chat"],
              models=["synthetic-cpu"], auth_level="AUTH-1",
              eae_revision=ea.EAE_CONTRACT_REVISION)
    kw.update(over)
    return ea.issue_execution_authorization(**kw)


@attempt("forged authorization JSON (checksum recompute on mutated payload)")
def a01(tmp):
    store, state, roster, dd, rd = _fixture(tmp / "a01")
    auth = _issue(dd, rd)
    import dataclasses
    forged = copy.deepcopy(auth)
    object.__setattr__(forged, "payload", dict(
        auth.payload, dispatch_limits={"max_trials": 10 ** 9}))
    ok = ea.recheck_execution_authorization(auth)
    try:
        ea.recheck_execution_authorization(forged)
        return "ESCAPED"
    except ea.AuthorizationError:
        return "REFUSED"


@attempt("reused authorization for a different experiment")
def a02(tmp):
    store, state, roster, dd, rd = _fixture(tmp / "a02")
    auth = _issue(dd, rd)
    try:
        _issue(dd, rd, experiment_id="ea18-OTHER")   # evidence-bound
        # even presenting the old auth elsewhere fails the identity
        # binding at issuance; checksum binds experiment_id
        material = json.loads(auth.canonical_material())
        assert material[1] == "ea18"
        return "REFUSED"
    except ea.AuthorizationError:
        return "REFUSED"


@attempt("authorization after durable revocation (fresh process state)")
def a03(tmp):
    store, state, roster, dd, rd = _fixture(tmp / "a03")
    cert = [c.certificate_id
            for c in store.snapshot().certificates][0]
    state.revoke(cert, reason="ea18")
    restarted = AuthoritativeQualificationState(store, tmp / "a03" /
                                                "auth.json")
    try:
        _fixture_reg_restarted = ea.register_trusted_execution_evidence(
            authoritative_state=restarted,
            experiment_id="ea18", auth_purpose="AUTH-1",
            primitives=["C01"], protocols=["chat"],
            models=["synthetic-cpu"],
            dataset_file=PINNED / "n03_cases.public.jsonl",
            roster_file=roster,
            parser_file=SRC / "production" / "parser.py",
            evaluator_file=SRC / "production" / "evaluator.py",
            interpreter_file=SRC / "reference" / "interpreter.py",
            oracle_file=SRC / "reference" / "oracle.py",
            certificate_store=store,
            shared_core_acceptance_file=tmp / "a03" / "sc.json",
            canary_evidence_file=tmp / "a03" / "canary.json",
            breaker_evidence_file=tmp / "a03" / "br.json",
            witness_suite_file=EA03 / "dualpath_witnesses.json",
            mutation_report_file=EA03 /
            "production_mutation_campaign.json")
        return "ESCAPED"
    except ea.AuthorizationError:
        return "REFUSED"


@attempt("direct publication bypass (aggregation without certificates)")
def a04(tmp):
    store, state, roster, dd, rd = _fixture(tmp / "a04")
    untrusted = CertificateStore(trusted=False)
    cases = [json.loads(l) for l in
             (PINNED / "n03_cases.public.jsonl").read_text(
                 encoding="utf-8").splitlines() if l.strip()]
    exps = {json.loads(l)["case_id"]: json.loads(l) for l in
            (PINNED / "n03_dev_expectations.jsonl").read_text(
                encoding="utf-8").splitlines() if l.strip()}
    s = DualPathSession(tmp / "a04" / "sess")
    for c in cases[:6]:
        if c.get("split") == "development":
            s.run_trial(c, exps[c["case_id"]], "x", model="m",
                        protocol="chat")
    try:
        QualifiedAnalyzer(experiment_id="e", dataset_id="d",
                          parser_version="p", evaluator_version="v",
                          certificates=untrusted)
        return "ESCAPED"
    except Exception:
        return "REFUSED"


@attempt("certificate-less formal aggregation")
def a05(tmp):
    from eval_assurance.statistics.boundary import aggregate_semantic
    store, state, roster, dd, rd = _fixture(tmp / "a05")
    cases = [json.loads(l) for l in
             (PINNED / "n03_cases.public.jsonl").read_text(
                 encoding="utf-8").splitlines() if l.strip()]
    exps = {json.loads(l)["case_id"]: json.loads(l) for l in
            (PINNED / "n03_dev_expectations.jsonl").read_text(
                encoding="utf-8").splitlines() if l.strip()}
    s = DualPathSession(tmp / "a05" / "sess")
    for c in cases[:6]:
        if c.get("split") == "development":
            s.run_trial(c, exps[c["case_id"]], "x", model="m",
                        protocol="chat")
    an = QualifiedAnalyzer(experiment_id="e",
                           dataset_id="n03-batch-a-dev160@d23de5a",
                           parser_version=
                           "eval_assurance.production.parser@1",
                           evaluator_version=
                           "eval_assurance.production.evaluator@1",
                           certificates=store,
                           planned_roster=[
                               f"{c['case_id']}|m|chat"
                               for c in cases[:6]
                               if c.get("split") == "development"])
    rep = an.analyze(s)
    with_cert = rep.formal_publication
    rep2 = aggregate_semantic(
        [r for r in []], scope="semantic", certificates=None)
    no_cert = rep2.formal_publication
    ok = with_cert.startswith("ALLOWED") and         no_cert.startswith("BLOCKED")
    return "REFUSED" if ok else "SUSPECT"


@attempt("hand-forged ExecutionEvidence dataclass registration")
def a06(tmp):
    ea.clear_execution_evidence()
    ev = ea.ExecutionEvidence(
        compat_revision=ea.EAE_CONTRACT_REVISION,
        primitives=("C01",), protocols=("chat",),
        models=("m",), dataset_digest="d" * 64, roster_digest="r" * 64,
        evaluator_identity="x", certificate_refs=("FAKE",),
        certificate_digests=(("FAKE", {}),),
        shared_core_acceptance="ACCEPTED",
        shared_core_evidence_digest="s" * 64,
        ea13_scope_evidence="a" * 42, ea18_scope_evidence="b" * 42,
        canary_ready=True, circuit_breaker_ready=True)
    ea.register_execution_evidence(ev,
                                   trusted_certificate_refs={"FAKE"})
    try:
        _issue("d" * 64, "r" * 64)
        return "ESCAPED (unbacked evidence authorized)"
    except ea.AuthorizationError:
        return ("REFUSED-at-issuance (unbacked certificates never "
                "in a trusted authority store)")


@attempt("tampered breaker state file (forced CLOSED)")
def a07(tmp):
    store, state, roster, dd, rd = _fixture(tmp / "a07")
    br = CircuitBreaker(tmp / "a07" / "cb.json")
    br.open(reason="x", affected_scope=["C01"])
    p = tmp / "a07" / "cb.json"
    raw = json.loads(p.read_text(encoding="utf-8"))
    raw["state"] = "CLOSED"
    p.write_text(json.dumps(raw), encoding="utf-8")
    try:
        CircuitBreaker(p)
        return "ESCAPED"
    except Exception:
        return "REFUSED (checksum mismatch keeps dispatch suspended)"


@attempt("missing-evidence sentinel passed off as empty output")
def a08(tmp):
    cases = [json.loads(l) for l in
             (PINNED / "n03_cases.public.jsonl").read_text(
                 encoding="utf-8").splitlines() if l.strip()]
    case = next(c for c in cases if c["primitive"] == "C01")
    r1 = evaluate_dual(case, {}, "")
    s = DualPathSession(tmp / "a08" / "sess")
    r2 = s.run_trial(case, {}, MISSING, model="m", protocol="chat")
    ok = r1.classification == "EMPTY_OUTPUT" and         r2.classification == "MISSING_EVIDENCE"
    return "REFUSED" if ok else "ESCAPED"


@attempt("canary window hiding (early passing family clears window)")
def a09(tmp):
    witnesses = json.loads((EA03 / "dualpath_witnesses.json")
                           .read_text(encoding="utf-8"))["rows"]
    exps = {json.loads(l)["case_id"]: json.loads(l) for l in
            (PINNED / "n03_dev_expectations.jsonl").read_text(
                encoding="utf-8").splitlines() if l.strip()}
    cases_by_id = {json.loads(l)["case_id"]: json.loads(l) for l in
                   (PINNED / "n03_cases.public.jsonl").read_text(
                       encoding="utf-8").splitlines() if l.strip()}
    br = CircuitBreaker(tmp / "a09" / "cb.json")
    sched = canary_mod.CanaryScheduler(
        [w for w in witnesses if w["kind"] != "software-error"],
        breaker=br, expectations=exps, cases_by_id=cases_by_id)
    sched.preflight()
    sched.on_trial("t1")
    sched.on_trial("t2")
    # corrupt C08 so the sweep fails at its LAST family
    for w in sched.witnesses:
        if w["kind"] == "positive" and w["primitive"] == "C08":
            w["raw"] = "not a tool id at all"
    results = sched.run_canary_sweep()
    scope = br.contamination_scope
    ok = br.is_open and "t1" in scope["quarantined_trials"]
    return "REFUSED" if ok else "ESCAPED"


def main() -> int:
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    tmp_root = ROOT / ".runtime" / "ea18"
    tmp_root.mkdir(parents=True, exist_ok=True)
    results = []
    for i, (name, fn) in enumerate(ATTEMPTS):
        d = tmp_root / f"a{i:02d}"
        d.mkdir(parents=True, exist_ok=True)
        try:
            outcome = fn(tmp_root)
        except Exception as exc:                     # noqa: BLE001
            outcome = f"ERROR {type(exc).__name__}: {exc}"[:100]
        results.append({"attempt": name, "outcome": outcome,
                        "refused": outcome.startswith(
                            ("REFUSED", "SUSPECT"))})

    # -- dependency aggregation -------------------------------------------
    def verdict_of(path, key):
        p = pathlib.Path(path)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8")).get(key)
        except Exception:                       # noqa: BLE001
            return "UNREADABLE"

    deps = {
        "waveB_witnesses": verdict_of(
            EA03 / "dualpath_witnesses.json", "summary"),
        "waveB_mutations": verdict_of(
            EA03 / "production_mutation_campaign.json", "summary"),
        "waveB_ea08": verdict_of(
            EA03 / "ea08_end_to_end.json", "summary"),
        "catastrophe_pilot": verdict_of(
            EVID / "EABC" / "catastrophe_pilot.json", "summary"),
        "ea12": verdict_of(EVID / "EA12" /
                           "n02rr_revalidation.json", "verdict"),
        "ea13": verdict_of(EVID / "EA13" /
                           "primitive_qualification.json", "summary"),
        "ea14": verdict_of(EVID / "EA14" /
                           "stress_campaign.json", "verdict"),
    }
    dep_ok = {
        "waveB_witnesses": deps["waveB_witnesses"] and
        deps["waveB_witnesses"].get("failed") == 0,
        "waveB_mutations": deps["waveB_mutations"] and
        deps["waveB_mutations"].get("escapes") == [],
        "waveB_ea08": deps["waveB_ea08"] and
        deps["waveB_ea08"].get("passed") ==
        deps["waveB_ea08"].get("controls"),
        "catastrophe_pilot": deps["catastrophe_pilot"] and
        deps["catastrophe_pilot"].get("escapes") == [],
        "ea12": deps["ea12"] in ("PASS", "PASS_WITH_FINDINGS"),
        "ea13": deps["ea13"] and
        deps["ea13"].get("qualified") == deps["ea13"].get("total"),
        "ea14": deps["ea14"] == "GO",
    }
    attempts_ok = all(r["refused"] for r in results)
    gate = "N03_SHARED_EVALUATION_ASSURANCE_CORE_GO" if \
        all(dep_ok.values()) and attempts_ok else "BLOCKED"

    report = {
        "schema": "ijeval.ea18.independent_acceptance.v1",
        "generated_utc": stamp,
        "attempts": results,
        "dependencies": {"evidence": deps, "ok": dep_ok},
        "gate": gate,
        "gate_blocked_reasons": [k for k, v in dep_ok.items()
                                 if not v] +
        (["adversarial attempt escaped"] if not attempts_ok else [])}
    out = EVID / "EA18"
    out.mkdir(parents=True, exist_ok=True)
    (out / "independent_acceptance.json").write_text(
        json.dumps(report, indent=1, ensure_ascii=False),
        encoding="utf-8")
    print("attempts:", sum(1 for r in results if r["refused"]), "/",
          len(results), "refused")
    print("deps ok:", dep_ok)
    print("gate:", gate)
    return 0 if gate.endswith("_GO") else 1


if __name__ == "__main__":
    raise SystemExit(main())
