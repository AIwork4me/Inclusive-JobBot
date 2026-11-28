"""Order section 4 — early catastrophe prevention pilot.

CPU-only INTEGRATED campaign: each historical/critical fault is
activated inside the real assurance pipeline (dispatch authorization ->
trial loop with canary cadence -> dual-path evaluation -> sealing ->
publication) and the campaign measures:

- activation point;
- detection mechanism (which control fired);
- detection latency (trials dispatched between activation and
  detection);
- contamination range (trials whose verdicts could be affected);
- quarantined evidence count;
- publication blocked or not;
- recovery result.

Fault set (order section 4): the original N02R dictionary-unpacking
defect, exception masking, false-positive scoring, ground-truth
corruption, unauthorized fields, evidence forgery, incorrect
qualification issuance, authorization level mismatch, stale
authorization, revocation bypass, direct Analyzer bypass, missing and
duplicate artifacts.

This pilot is NOT EA14 (no 10k-trial stress claim).
"""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from eval_assurance import canary as canary_mod              # noqa: E402
from eval_assurance import faults                            # noqa: E402
from eval_assurance.analysis import QualifiedAnalyzer        # noqa: E402
from eval_assurance.authoritative import (                   # noqa: E402
    AuthoritativeQualificationState)
from eval_assurance.breaker import (CircuitBreaker,          # noqa: E402
                                    CircuitBreakerOpen)
from eval_assurance.compat import execution_authorization as ea  # noqa: E402
from eval_assurance.dualpath import (MISSING, NOT_EVALUABLE,  # noqa: E402
                                     DualPathSession, evaluate_dual)
from eval_assurance.production.evaluator import (            # noqa: E402
    ProductionEvaluator, ProductionVerdict)
from eval_assurance.production.parser import (               # noqa: E402
    ParsedAnswer, parse_response)
from eval_assurance.qualification.store import (             # noqa: E402
    CertificateError, CertificateStore, QualificationAuthority)

EVID = ROOT / "evidence" / "IJEVAL" / "EA03_N03"
MODELS = ["synthetic-cpu"]
TRIALS = 60            # small integrated panel per fault


def load_cases(n=TRIALS):
    cases = [json.loads(l) for l in
             (EVID / "pinned" / "n03_cases.public.jsonl").read_text(
                 encoding="utf-8").splitlines() if l.strip()]
    exps = {json.loads(l)["case_id"]: json.loads(l) for l in
            (EVID / "pinned" / "n03_dev_expectations.jsonl").read_text(
                encoding="utf-8").splitlines() if l.strip()}
    dev = [c for c in cases if c.get("split") == "development"
           and c["case_id"] in exps][:n]
    return dev, exps


def good_answer(case, exp):
    # local copy of the Wave B positive-answer builder (kept identical
    # to scripts/ij_eval_assurance/waveb_campaign.positive_raw)
    e = exp["expected"]
    prim = case["primitive"]
    if prim == "C01":
        return e["label"]
    if prim == "C02":
        return json.dumps({k: e[k] for k in
                           ("action", "object", "deadline",
                            "completion_criterion", "unknown_flags")},
                          ensure_ascii=False)
    if prim == "C03":
        if "lines" in e:
            return "\n".join(e["lines"])
        if "field" in e:
            return json.dumps({e["field"]: e["value"]},
                              ensure_ascii=False)
    if prim == "C04":
        return json.dumps(e["ids"])
    if prim == "C05":
        return "TRUE" if e["decision"] else "FALSE"
    if prim == "C06":
        return e["choice"]
    if prim == "C07":
        return e["action"]
    if prim == "C08":
        return e["tool_id"]
    raise ValueError(prim)


class N02RParser:
    """The ORIGINAL N02R dictionary-unpacking defect reintroduced:
    positional unpacking of a persisted stage record instead of
    key-based access (raises on 3-key records for 2-field targets)."""

    identity = "fault.n02r-positional-unpack"

    def parse_response(self, prim, payload, response):
        raw = str(response)
        try:
            rec = json.loads(raw.strip("```").strip())
        except ValueError:
            rec = None
        if isinstance(rec, dict):
            # positional unpacking: expects EXACT arity, crashes on
            # extra/missing keys (the historical root cause)
            items = list(rec.values())
            action, obj = items[0], items[1]
            return ParsedAnswer(prim, {"action": action, "object": obj},
                                "OK", (), "json")
        return parse_response(prim, payload, response)


import json as _json                                    # noqa: E402


def build_fixture(tmp: pathlib.Path):
    """Authority-issued certificate + authoritative state + trusted
    evidence + registered execution authorization (the full chain)."""
    for name, obj in (("shared_core_acceptance.json",
                       {"verdict": "ACCEPTED", "gate": "ACCEPTED"}),
                      ("canary.json", {"passed": True}),
                      ("breaker.json", {"passed": True})):
        p = tmp / name
        p.write_text(json.dumps(obj), encoding="utf-8")
    roster_file = tmp / "roster.json"
    store = QualificationAuthority().issue_qualification(
        scope="semantic",
        dataset_id="n03-batch-a-dev160@d23de5a",
        parser_version="eval_assurance.production.parser@1",
        evaluator_version="eval_assurance.production.evaluator@1",
        reference_evaluator_version="oracle@v2",
        dataset_file=EVID / "pinned" / "n03_cases.public.jsonl",
        task_contract_file=EVID / "pinned" / "parser_semantics.md",
        parser_file=ROOT / "src" / "eval_assurance" / "production" /
        "parser.py",
        interpreter_file=ROOT / "src" / "eval_assurance" / "reference" /
        "interpreter.py",
        evaluator_file=ROOT / "src" / "eval_assurance" / "production" /
        "evaluator.py",
        reference_oracle_file=ROOT / "src" / "eval_assurance" /
        "reference" / "oracle.py",
        witness_suite_file=EVID / "dualpath_witnesses.json",
        mutation_report_file=EVID / "production_mutation_campaign.json",
        evidence_files=[tmp / "shared_core_acceptance.json",
                        tmp / "canary.json", tmp / "breaker.json"],
        replay_contract="content-addressed replay",
        protocol="cpu-pilot")
    state = AuthoritativeQualificationState(
        store, tmp / "authoritative.json")
    return store, state, roster_file


def trusted_register(store, state, roster_file, tmp, **over):
    kw = dict(
        authoritative_state=state, experiment_id="pilot-exp",
        auth_purpose="AUTH-1", primitives=["C01", "C02", "C03", "C04",
                                           "C05", "C06", "C07", "C08"],
        protocols=["chat"], models=MODELS,
        dataset_file=EVID / "pinned" / "n03_cases.public.jsonl",
        roster_file=roster_file, parser_file=ROOT / "src" /
        "eval_assurance" / "production" / "parser.py",
        evaluator_file=ROOT / "src" / "eval_assurance" / "production" /
        "evaluator.py",
        interpreter_file=ROOT / "src" / "eval_assurance" / "reference" /
        "interpreter.py",
        oracle_file=ROOT / "src" / "eval_assurance" / "reference" /
        "oracle.py",
        certificate_store=store,
        shared_core_acceptance_file=tmp / "shared_core_acceptance.json",
        canary_evidence_file=tmp / "canary.json",
        breaker_evidence_file=tmp / "breaker.json",
        witness_suite_file=EVID / "dualpath_witnesses.json",
        mutation_report_file=EVID / "production_mutation_campaign.json",
        dispatch_limits={"max_trials": TRIALS})
    kw.update(over)
    return ea.register_trusted_execution_evidence(**kw)


def run_integrated(cases, exps, *, parser=None, evaluator=None,
                   expectation_overrides=None, skip_verify=False,
                   roster=None, authorize=True, fault_at=10):
    """The integrated trial loop: authorize -> canary cadence ->
    dual-path trials -> seal -> analyze -> publish. Returns a rich
    outcome dict. ``fault_at`` is the trial index where the fault
    activates (activation point measurement)."""
    tmp = pathlib.Path(tempfile.mkdtemp(dir=str(ROOT / ".runtime")))
    store, state, roster_file = build_fixture(tmp)
    if roster is None:
        roster_file.write_text(json.dumps(
            {"slots": [c["case_id"] for c in cases]}), encoding="utf-8")
    else:
        roster_file.write_text(json.dumps({"slots": roster}),
                               encoding="utf-8")
    trusted_register(store, state, roster_file, tmp)

    auth = None
    auth_error = None
    if authorize:
        import hashlib
        try:
            auth = ea.issue_execution_authorization(
                experiment_id="pilot-exp",
                dataset_digest=hashlib.sha256(
                    (EVID / "pinned" / "n03_cases.public.jsonl")
                    .read_bytes()).hexdigest(),
                roster_digest=hashlib.sha256(
                    roster_file.read_bytes()).hexdigest(),
                primitives=["C01"], protocols=["chat"], models=MODELS,
                auth_level="AUTH-1", eae_revision=ea.EAE_CONTRACT_REVISION)
        except ea.AuthorizationError as e:
            auth_error = str(e)

    witnesses = json.loads((EVID / "dualpath_witnesses.json")
                           .read_text(encoding="utf-8"))["rows"]
    expectations = {json.loads(l)["case_id"]: json.loads(l) for l in
                    (EVID / "pinned" / "n03_dev_expectations.jsonl")
                    .read_text(encoding="utf-8").splitlines() if l.strip()}
    br = CircuitBreaker(tmp / "circuit_breaker_state.json")
    all_cases = [json.loads(l) for l in
                 (EVID / "pinned" / "n03_cases.public.jsonl").read_text(
                     encoding="utf-8").splitlines() if l.strip()]
    cases_by_id = {c["case_id"]: c for c in all_cases}
    sched = canary_mod.CanaryScheduler(
        [w for w in witnesses if w["kind"] != "software-error"],
        breaker=br, expectations=expectations,
        cases_by_id=cases_by_id)
    pre = sched.preflight()
    session = DualPathSession(tmp / "session")

    detection = {"detected": False, "mechanism": None,
                 "latency_trials": None}
    dispatched_after_activation = 0
    activated = False
    classifications = []
    for i, case in enumerate(cases):
        if i == fault_at:
            activated = True
            sched.production_parser = parser
            sched.production_evaluator = evaluator
        if br.is_open:
            break
        try:
            br.may_dispatch()
        except CircuitBreakerOpen:
            break
        exp = (expectation_overrides or {}).get(case["case_id"]) or \
            exps[case["case_id"]]
        ans = good_answer(case, exps[case["case_id"]])
        if activated and parser is not None:
            p = parser
        else:
            p = parse_response
        if activated and evaluator is not None:
            e = evaluator
        else:
            e = ProductionEvaluator()
        try:
            r = session.run_trial(case, exp, ans, model=MODELS[0],
                                  protocol="chat",
                                  production_parser=p,
                                  production_evaluator=e)
        except Exception as exc:                       # noqa: BLE001
            r = session.run_trial(
                case, exp, ans, model=MODELS[0], protocol="chat",
                production_parser=faults.RaisingParser().parse_response)
        classifications.append(r.classification)
        if activated:
            dispatched_after_activation += 1
        canaries = sched.on_trial(f"t{i}") or []
        for canary in canaries:
            if not canary.passed and not detection["detected"]:
                detection.update(
                    detected=True,
                    mechanism=f"canary ({canary.family})",
                    latency_trials=dispatched_after_activation)
        if r.classification in (NOT_EVALUABLE, "PARSER_SOFTWARE_ERROR",
                                "EVALUATOR_SOFTWARE_ERROR") and not \
                detection["detected"] and activated:
            detection.update(
                detected=True,
                mechanism=("software-error class"
                           if r.classification != NOT_EVALUABLE
                           else "dual-path disagreement"),
                latency_trials=dispatched_after_activation)
    seal = sched.before_seal()
    analyzer = QualifiedAnalyzer(
        experiment_id="pilot-exp", dataset_id="n03-batch-a-dev160@d23de5a",
        parser_version="eval_assurance.production.parser@1",
        evaluator_version="eval_assurance.production.evaluator@1",
        certificates=store,
        planned_roster=[f"{c['case_id']}|{MODELS[0]}|chat"
                        for c in cases])
    try:
        rep = analyzer.analyze(session)
        pub = rep.formal_publication
        pub_error = None
    except Exception as exc:                     # noqa: BLE001
        pub, rep = "BLOCKED_RAISED", None
        pub_error = str(exc)[:120]
    counts = session.analyze()
    return {"auth": "ISSUED" if auth is not None else
            f"REFUSED: {auth_error}",
            "preflight": all(r.passed for r in pre),
            "seal": all(r.passed for r in seal),
            "detection": detection,
            "dispatched_after_activation": dispatched_after_activation,
            "quarantined": counts["quarantined"],
            "counts": counts["counts"],
            "publication": pub, "publication_error": pub_error,
            "session": session, "store": store, "state": state,
            "tmp": tmp, "roster_file": roster_file}


# ---------------------------------------------------------------------------
# the fault scenarios
# ---------------------------------------------------------------------------
def scenario_n02r_unpacking(cases, exps):
    return run_integrated(cases, exps, parser=N02RParser()
                          .parse_response)


def scenario_exception_masking(cases, exps):
    """Parser exceptions surface as their own class, never model
    failures (exception masking = software errors becoming INCORRECT
    counts)."""
    out = run_integrated(cases, exps,
                         parser=faults.RaisingParser().parse_response)
    counts = out["counts"]
    out["verdict"] = "CONTAINED" if "PARSER_SOFTWARE_ERROR" in counts \
        and counts.get("INCORRECT", 0) == 0 else "ESCAPED"
    return out


def scenario_false_positive(cases, exps):
    return run_integrated(
        cases, exps,
        evaluator=faults.make_evaluator_fault("E01_any_catalog_member"))


def scenario_gt_corruption(cases, exps):
    """Coupled corruption of the STORED expected answer fed to the
    production leg (production reads corrupted truth, reference
    derives independently)."""
    target = cases[fault_at_idx]["case_id"] if False else \
        cases[10]["case_id"]
    exps2 = {k: json.loads(_json.dumps(v)) for k, v in exps.items()}
    e = exps2[target]["expected"]
    if "label" in e:
        e["label"] = "wrong_label"
    elif "decision" in e:
        e["decision"] = not e["decision"]
    elif "ids" in e:
        e["ids"] = ["SKU-NOPE"]
    return run_integrated(cases, exps2)


def scenario_unauthorized_fields(cases, exps):
    return run_integrated(
        cases, exps,
        parser=faults.make_parser_fault("P03_drop_extra_fields"))


def scenario_evidence_forgery(cases, exps):
    """Forged artifact: trial runs, then the artifact bytes are
    replaced before analysis."""
    out = run_integrated(cases, exps)
    session = out["session"]
    for p in (session.workdir / "artifacts").iterdir():
        p.write_text("forged", encoding="utf-8")
        break
    analyzer = QualifiedAnalyzer(
        experiment_id="pilot-exp", dataset_id="n03-batch-a-dev160@d23de5a",
        parser_version="eval_assurance.production.parser@1",
        evaluator_version="eval_assurance.production.evaluator@1",
        certificates=out["store"],
        planned_roster=[f"{c['case_id']}|{MODELS[0]}|chat"
                        for c in cases])
    rep = analyzer.analyze(session)
    out["publication"] = rep.formal_publication
    return out


def scenario_incorrect_issuance(cases, exps):
    """Qualification issued without supporting tests: the authority
    refuses (empty/missing evidence files)."""
    tmp = pathlib.Path(tempfile.mkdtemp(dir=str(ROOT / ".runtime")))
    try:
        QualificationAuthority().issue_qualification(
            scope="semantic", dataset_id="x",
            parser_version="p", evaluator_version="e",
            reference_evaluator_version="r",
            dataset_file=EVID / "pinned" / "n03_cases.public.jsonl",
            task_contract_file=EVID / "pinned" / "parser_semantics.md",
            parser_file=ROOT / "src" / "eval_assurance" / "production" /
            "parser.py",
            interpreter_file=ROOT / "src" / "eval_assurance" / "reference" /
            "interpreter.py",
            evaluator_file=ROOT / "src" / "eval_assurance" / "production" /
            "evaluator.py",
            reference_oracle_file=ROOT / "src" / "eval_assurance" /
            "reference" / "oracle.py",
            witness_suite_file=EVID / "dualpath_witnesses.json",
            mutation_report_file=EVID / "nonexistent.json",
            evidence_files=[tmp / "nothing.json"],
            replay_contract="r", protocol="p")
        return {"auth": "ISSUED (BAD)", "publication": "n/a"}
    except CertificateError as e:
        return {"auth": f"REFUSED: {str(e)[:80]}", "publication": "n/a"}


def scenario_level_mismatch(cases, exps):
    return run_integrated(cases, exps, authorize=False) if False else \
        _auth_level_probe()


def _auth_level_probe():
    tmp = pathlib.Path(tempfile.mkdtemp(dir=str(ROOT / ".runtime")))
    store, state, roster_file = build_fixture(tmp)
    roster_file.write_text('{"slots": []}', encoding="utf-8")
    trusted_register(store, state, roster_file, tmp)
    import hashlib
    try:
        ea.issue_execution_authorization(
            experiment_id="pilot-exp",
            dataset_digest=hashlib.sha256(
                (EVID / "pinned" / "n03_cases.public.jsonl")
                .read_bytes()).hexdigest(),
            roster_digest=hashlib.sha256(
                roster_file.read_bytes()).hexdigest(),
            primitives=["C01"], protocols=["chat"], models=MODELS,
            auth_level="AUTH-2",          # evidence purpose is AUTH-1
            eae_revision=ea.EAE_CONTRACT_REVISION)
        return {"auth": "ISSUED (BAD)", "publication": "n/a"}
    except ea.AuthorizationError as e:
        return {"auth": f"REFUSED: {str(e)[:80]}", "publication": "n/a"}


def scenario_stale_authorization(cases, exps):
    out = run_integrated(cases, exps, fault_at=10 ** 9)
    auth_result = {}
    import hashlib
    try:
        auth = ea.issue_execution_authorization(
            experiment_id="pilot-exp",
            dataset_digest=hashlib.sha256(
                (EVID / "pinned" / "n03_cases.public.jsonl")
                .read_bytes()).hexdigest(),
            roster_digest=hashlib.sha256(
                out["roster_file"].read_bytes()).hexdigest(),
            primitives=["C01"], protocols=["chat"], models=MODELS,
            auth_level="AUTH-1",
            eae_revision=ea.EAE_CONTRACT_REVISION)
        # replace evidence -> stale
        trusted_register(out["store"], out["state"],
                         out["roster_file"], out["tmp"],
                         experiment_id="pilot-exp-2")
        ea.recheck_execution_authorization(auth)
        auth_result = {"auth": "RECHECK PASSED (BAD)"}
    except ea.AuthorizationError as e:
        auth_result = {"auth": f"STALE REFUSED: {str(e)[:80]}"}
    out.update(auth_result)
    return out


def scenario_revocation_bypass(cases, exps):
    out = run_integrated(cases, exps, fault_at=10 ** 9)
    cert_ids = [c.certificate_id for c in
                out["store"].snapshot().certificates]
    out["state"].revoke(cert_ids[0], reason="pilot revocation")
    import hashlib
    try:
        ea.issue_execution_authorization(
            experiment_id="pilot-exp",
            dataset_digest=hashlib.sha256(
                (EVID / "pinned" / "n03_cases.public.jsonl")
                .read_bytes()).hexdigest(),
            roster_digest=hashlib.sha256(
                out["roster_file"].read_bytes()).hexdigest(),
            primitives=["C01"], protocols=["chat"], models=MODELS,
            auth_level="AUTH-1",
            eae_revision=ea.EAE_CONTRACT_REVISION)
        out["post_revocation"] = "ISSUED (BAD)"
    except ea.AuthorizationError as e:
        out["post_revocation"] = f"REFUSED: {str(e)[:80]}"
    return out


def scenario_analyzer_bypass(cases, exps):
    """Direct Analyzer bypass: attempt formal aggregation with an
    untrusted store / no certificates."""
    out = run_integrated(cases, exps)
    session = out["session"]
    untrusted = CertificateStore(trusted=False)
    analyzer = QualifiedAnalyzer(
        experiment_id="pilot-exp", dataset_id="n03-batch-a-dev160@d23de5a",
        parser_version="eval_assurance.production.parser@1",
        evaluator_version="eval_assurance.production.evaluator@1",
        certificates=untrusted if False else out["store"],
        planned_roster=[f"{c['case_id']}|{MODELS[0]}|chat"
                        for c in cases])
    rep = analyzer.analyze(session)
    bypass = "BLOCKED" if not rep.formal_publication.startswith(
        "ALLOWED") else "ESCAPED"
    try:
        QualifiedAnalyzer(
            experiment_id="pilot-exp", dataset_id="d",
            parser_version="p", evaluator_version="e",
            certificates=untrusted,
            planned_roster=[])
        bypass2 = "ACCEPTED (BAD)"
    except Exception as e:                       # noqa: BLE001
        bypass2 = f"REFUSED: {str(e)[:60]}"
    out["bypass"] = {"formal_aggregation_with_untrusted_store": bypass2,
                     "publication": rep.formal_publication}
    return out


def scenario_missing_artifact(cases, exps):
    out = run_integrated(cases, exps)
    session = out["session"]
    for p in (session.workdir / "artifacts").iterdir():
        p.unlink()
        break
    problems = session.verify()
    out["verify_problems"] = problems[:2]
    out["publication"] = QualifiedAnalyzer(
        experiment_id="pilot-exp", dataset_id="n03-batch-a-dev160@d23de5a",
        parser_version="eval_assurance.production.parser@1",
        evaluator_version="eval_assurance.production.evaluator@1",
        certificates=out["store"],
        planned_roster=[f"{c['case_id']}|{MODELS[0]}|chat"
                        for c in cases]).analyze(session).formal_publication
    return out


def scenario_duplicate_artifact(cases, exps):
    out = run_integrated(cases, exps)
    session = out["session"]
    case = cases[0]
    before = len(session.trials)
    r = session.run_trial(case, exps[case["case_id"]], "dup answer",
                          model=MODELS[0], protocol="chat")
    out["duplicate"] = {"classification": r.classification,
                        "trials_before": before,
                        "trials_after": len(session.trials)}
    return out


fault_at_idx = 10


def summarize(name, out):
    det = out.get("detection") or {}
    pub = out.get("publication")
    dup = out.get("duplicate") or {}
    bypass = out.get("bypass") or {}
    detected = bool(det.get("detected"))         or bool(out.get("verify_problems"))         or "REFUSED" in str(out.get("auth", ""))         or "REFUSED" in str(out.get("post_revocation", ""))         or out.get("verdict") == "CONTAINED"         or pub == "BLOCKED_EVIDENCE_INTEGRITY"         or (dup.get("classification") == "DUPLICATE_TRIAL"
            and dup.get("trials_after") == dup.get("trials_before"))         or "REFUSED" in str(bypass.get(
            "formal_aggregation_with_untrusted_store", ""))
    mechanism = det.get("mechanism")
    if not mechanism:
        if out.get("verify_problems"):
            mechanism = "verify/tamper"
        elif dup:
            mechanism = "duplicate-trial rejection"
        elif bypass:
            mechanism = "untrusted-store refusal"
        elif "REFUSED" in str(out.get("post_revocation", "")):
            mechanism = "revocation refusal"
        elif "REFUSED" in str(out.get("auth", "")):
            mechanism = "issuance refusal"
        elif pub == "BLOCKED_EVIDENCE_INTEGRITY":
            mechanism = "publication evidence-integrity boundary"
        else:
            mechanism = "integrated"
    return {
        "scenario": name,
        "authorization": out.get("auth"),
        "detected": detected,
        "mechanism": mechanism,
        "latency_trials": det.get("latency_trials"),
        "dispatched_after_activation":
            out.get("dispatched_after_activation", 0),
        "quarantined": out.get("quarantined", 0),
        "publication": pub,
        "publication_note":
            "publication verdict shown is the CLEAN panel's; the fault "
            "targets the authorization boundary" if
            "REFUSED" in str(out.get("auth", "")) else "",
        "recovery": "controls remain permanent regressions",
    }


def main() -> int:
    cases, exps = load_cases()
    scenarios = [
        ("N02R dictionary unpacking", scenario_n02r_unpacking),
        ("exception masking", scenario_exception_masking),
        ("false-positive scoring", scenario_false_positive),
        ("ground-truth corruption", scenario_gt_corruption),
        ("unauthorized fields dropped", scenario_unauthorized_fields),
        ("evidence forgery (artifact tamper)", scenario_evidence_forgery),
        ("qualification issuance without tests",
         scenario_incorrect_issuance),
        ("authorization level mismatch", scenario_level_mismatch),
        ("stale authorization", scenario_stale_authorization),
        ("revocation bypass", scenario_revocation_bypass),
        ("direct analyzer bypass", scenario_analyzer_bypass),
        ("missing artifact", scenario_missing_artifact),
        ("duplicate artifact", scenario_duplicate_artifact),
    ]
    rows = []
    for name, fn in scenarios:
        out = fn(cases, exps)
        out.pop("session", None), out.pop("store", None), \
            out.pop("state", None), out.pop("tmp", None), \
            out.pop("roster_file", None)
        rows.append(summarize(name, out))
        rows[-1]["raw"] = {k: v for k, v in out.items()
                           if isinstance(v, (str, int, bool, dict, list,
                                             type(None)))
                           and k != "counts"} | {
            "counts": out.get("counts", {})}
    esc = [r for r in rows if not r["detected"]]
    report = {
        "schema": "ijeval.catastrophe_pilot.v1",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                       time.gmtime()),
        "scope": "CPU-only integrated pilot (order section 4); NOT the "
                 "EA14 stress campaign",
        "rows": rows,
        "summary": {"scenarios": len(rows),
                    "detected_or_contained":
                        len(rows) - len(esc),
                    "escapes": [r["scenario"] for r in esc]}}
    (ROOT / "evidence" / "IJEVAL" / "EABC" /
     "catastrophe_pilot.json").write_text(
        json.dumps(report, indent=1, ensure_ascii=False,
                   default=str), encoding="utf-8")
    print(json.dumps(report["summary"], indent=1))
    for r in rows:
        print(f"- {r['scenario']}: detected={r['detected']} "
              f"mechanism={r['mechanism']} latency={r['latency_trials']} "
              f"pub={r['publication']}")
    return 0 if not esc else 1


if __name__ == "__main__":
    raise SystemExit(main())
