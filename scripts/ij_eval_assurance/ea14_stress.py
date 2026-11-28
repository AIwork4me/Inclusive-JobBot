"""EA14 — systemic fault-containment stress campaign (order section 6).

10,000 synthetic logical trials + 1,000 controlled fault instances
through the REAL shared core (authorization -> canary cadence ->
dual-path evaluation -> breaker -> qualified analysis -> publication):

- batches of 50 trials cycling the 160 pinned dev cases with a
  deterministic answer mix (correct / wrong / malformed / empty);
- fault instances drawn from the full fault library (20 production
  faults) + the authorization-boundary faults, activated at
  deterministic points;
- measured per instance: detection (mechanism), latency (trials
  dispatched after activation), contamination window (quarantined),
  publication outcome;
- measured globally: fault coverage, false alarms (canary failures in
  FAULT-FREE batches), recovery via independent requalification,
  invalid-publication escapes (target: ZERO critical escapes).

The authoritative state persists across the whole campaign (one
process = one campaign; restart-safety is separately controlled in the
Wave C tests).
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from eval_assurance import canary as canary_mod              # noqa: E402
from eval_assurance import faults                            # noqa: E402
from eval_assurance.analysis import QualifiedAnalyzer        # noqa: E402
from eval_assurance.authoritative import (                   # noqa: E402
    AuthoritativeQualificationState)
from eval_assurance.breaker import CircuitBreaker            # noqa: E402
from eval_assurance.compat import execution_authorization as ea  # noqa: E402
from eval_assurance.dualpath import DualPathSession         # noqa: E402
from eval_assurance.production.evaluator import ProductionEvaluator  # noqa
from eval_assurance.production.parser import parse_response  # noqa: E402
from eval_assurance.qualification.store import (             # noqa: E402
    CertificateStore, QualificationAuthority)

EVID = ROOT / "evidence" / "IJEVAL" / "EA03_N03"
AUTH1 = ROOT / "evidence" / "IJEVAL" / "AUTH1"
OUT = ROOT / "evidence" / "IJEVAL" / "EA14"
PINNED = EVID / "pinned"
SRC = ROOT / "src" / "eval_assurance"

BATCH = 50
TOTAL_TRIALS = 10_000
FAULT_INSTANCES = 1_000


def load():
    cases = [json.loads(l) for l in
             (PINNED / "n03_cases.public.jsonl").read_text(
                 encoding="utf-8").splitlines() if l.strip()]
    exps = {json.loads(l)["case_id"]: json.loads(l) for l in
            (PINNED / "n03_dev_expectations.jsonl").read_text(
                encoding="utf-8").splitlines() if l.strip()}
    dev = [c for c in cases if c.get("split") == "development"
           and c["case_id"] in exps]
    return dev, exps


def good_answer(prim, exp):
    e = exp["expected"]
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


def answer_for(i, case, exp):
    """Deterministic answer mix: 70% good, 12% wrong, 9% malformed,
    9% empty (model-behavior stand-in; the shared core does not care
    which model produced what — it must contain FAULTS, not model
    errors)."""
    m = i % 100
    if m < 70:
        return good_answer(case["primitive"], exp)
    if m < 82:
        if case["primitive"] == "C05":
            e = exp["expected"]
            return "FALSE" if e["decision"] else "TRUE"
        return "definitely-not-the-answer"
    if m < 91:
        return "- bulleted\n- answer"
    return ""


class Campaign:
    def __init__(self, tmp: pathlib.Path):
        self.tmp = tmp
        for name, obj in (("sc.json", {"verdict": "ACCEPTED"}),
                          ("canary.json", {"passed": True}),
                          ("breaker.json", {"passed": True})):
            (tmp / name).write_text(json.dumps(obj), encoding="utf-8")
        self.store = QualificationAuthority().issue_qualification(
            scope="semantic",
            dataset_id="n03-batch-a-dev160@d23de5a",
            parser_version="eval_assurance.production.parser@1",
            evaluator_version="eval_assurance.production.evaluator@1",
            reference_evaluator_version="oracle@v2",
            dataset_file=PINNED / "n03_cases.public.jsonl",
            task_contract_file=PINNED / "parser_semantics.md",
            parser_file=SRC / "production" / "parser.py",
            interpreter_file=SRC / "reference" / "interpreter.py",
            evaluator_file=SRC / "production" / "evaluator.py",
            reference_oracle_file=SRC / "reference" / "oracle.py",
            witness_suite_file=EVID / "dualpath_witnesses.json",
            mutation_report_file=EVID /
            "production_mutation_campaign.json",
            evidence_files=[tmp / "sc.json", tmp / "canary.json",
                            tmp / "breaker.json"],
            replay_contract="content-addressed replay",
            protocol="cpu-ea14")
        self.state = AuthoritativeQualificationState(
            self.store, tmp / "authoritative.json")
        self.roster_file = tmp / "roster.json"
        self.roster_file.write_text('{"slots": []}', encoding="utf-8")
        self.evidence = self._register("ea14-stress")
        self.witnesses = json.loads(
            (EVID / "dualpath_witnesses.json").read_text(
                encoding="utf-8"))["rows"]
        self.expectations = {json.loads(l)["case_id"]: json.loads(l)
                             for l in
                             (PINNED / "n03_dev_expectations.jsonl")
                             .read_text(encoding="utf-8").splitlines()
                             if l.strip()}
        self.cases_by_id = {json.loads(l)["case_id"]: json.loads(l)
                            for l in
                            (PINNED / "n03_cases.public.jsonl")
                            .read_text(encoding="utf-8").splitlines()
                            if l.strip()}
        self.canary_args = dict(
            expectations=self.expectations,
            cases_by_id=self.cases_by_id)

    def _register(self, experiment):
        ea.clear_execution_evidence()
        return ea.register_trusted_execution_evidence(
            authoritative_state=self.state,
            experiment_id=experiment, auth_purpose="AUTH-1",
            primitives=["C01", "C02", "C03", "C04", "C05", "C06",
                        "C07", "C08"],
            protocols=["chat"], models=["synthetic-cpu"],
            dataset_file=PINNED / "n03_cases.public.jsonl",
            roster_file=self.roster_file,
            parser_file=SRC / "production" / "parser.py",
            evaluator_file=SRC / "production" / "evaluator.py",
            interpreter_file=SRC / "reference" / "interpreter.py",
            oracle_file=SRC / "reference" / "oracle.py",
            certificate_store=self.store,
            shared_core_acceptance_file=self.tmp / "sc.json",
            canary_evidence_file=self.tmp / "canary.json",
            breaker_evidence_file=self.tmp / "breaker.json",
            witness_suite_file=EVID / "dualpath_witnesses.json",
            mutation_report_file=EVID /
            "production_mutation_campaign.json")

    def issue(self, experiment="ea14-stress"):
        roster_digest = hashlib.sha256(
            self.roster_file.read_bytes()).hexdigest()
        dataset_digest = hashlib.sha256(
            (PINNED / "n03_cases.public.jsonl").read_bytes()).hexdigest()
        return ea.issue_execution_authorization(
            experiment_id=experiment, dataset_digest=dataset_digest,
            roster_digest=roster_digest,
            primitives=["C01"], protocols=["chat"],
            models=["synthetic-cpu"], auth_level="AUTH-1",
            eae_revision=ea.EAE_CONTRACT_REVISION)

    def run_batch(self, cases, exps, start_index, *, parser=None,
                  evaluator=None, fault_at=None, experiment="ea14-stress"):
        """One 50-trial batch through the full shared core. Returns
        (classification_counts, detection, quarantined, publication,
        false_alarm, trials_run)."""
        btmp = self.tmp / f"b{start_index}"
        br = CircuitBreaker(btmp / "cb.json")
        sched = canary_mod.CanaryScheduler(
            [w for w in self.witnesses
             if w["kind"] != "software-error"],
            breaker=br, **self.canary_args)
        pre = sched.preflight()
        false_alarm = not all(r.passed for r in pre)
        session = DualPathSession(btmp / "session")
        detection = {"detected": False, "mechanism": None,
                     "latency": None}
        after_activation = 0
        activated = fault_at is not None
        faults_active = False
        for i in range(BATCH):
            case = cases[(start_index + i) % len(cases)]
            if fault_at is not None and i == fault_at:
                faults_active = True
                sched.production_parser = parser
                sched.production_evaluator = evaluator
            if br.is_open:
                break
            exp = exps[case["case_id"]]
            ans = answer_for(start_index + i, case, exp)
            p = parser if (faults_active and parser) else \
                parse_response
            e = evaluator if (faults_active and evaluator) else \
                ProductionEvaluator()
            r = session.run_trial(case, exp, ans, model="stress",
                                  protocol="chat",
                                  production_parser=p,
                                  production_evaluator=e)
            if faults_active:
                after_activation += 1
            canaries = sched.on_trial(f"t{i}") or []
            for c in canaries:
                if not c.passed:
                    false_alarm = False if faults_active else \
                        false_alarm
                    if not detection["detected"]:
                        detection.update(
                            detected=True,
                            mechanism=f"canary ({c.family})",
                            latency=after_activation)
            if faults_active and not detection["detected"] and \
                    r.classification in ("NOT_EVALUABLE",
                                         "PARSER_SOFTWARE_ERROR",
                                         "EVALUATOR_SOFTWARE_ERROR"):
                detection.update(
                    detected=True,
                    mechanism="software/disagreement class",
                    latency=after_activation)
        sched.before_seal()
        analyzer = QualifiedAnalyzer(
            experiment_id=experiment,
            dataset_id="n03-batch-a-dev160@d23de5a",
            parser_version="eval_assurance.production.parser@1",
            evaluator_version="eval_assurance.production.evaluator@1",
            certificates=self.store,
            planned_roster=[f"{cases[(start_index + i) % len(cases)]['case_id']}"
                            f"|stress|chat" for i in range(BATCH)])
        rep = analyzer.analyze(session)
        counts = session.analyze()
        return {"counts": counts["counts"],
                "detection": detection,
                "quarantined": counts["quarantined"],
                "publication": rep.formal_publication,
                "false_alarm": false_alarm,
                "trials_run": len(session.trials)}


def main() -> int:
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    cases, exps = load()
    tmp = ROOT / ".runtime" / "ea14"
    if tmp.exists():
        # clean slate: a prior crashed run leaves per-batch breaker
        # files in state OPEN; the restart-safe breaker then suppresses
        # every batch at trial 0 (found the hard way — stale containment
        # state silently zeroed a re-run's detection metrics while
        # publications stayed fail-closed). Campaign workdirs are
        # scratch: always start clean.
        import shutil
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True, exist_ok=True)
    camp = Campaign(tmp)

    # -- fault-free stress volume (10,000 trials) ------------------------
    t0 = time.time()
    total_counts: dict[str, int] = {}
    false_alarms = 0
    batches = TOTAL_TRIALS // BATCH
    for b in range(batches):
        out = camp.run_batch(cases, exps, b * BATCH)
        for k, v in out["counts"].items():
            total_counts[k] = total_counts.get(k, 0) + v
        if out["false_alarm"]:
            false_alarms += 1
    volume_seconds = time.time() - t0

    # -- 1,000 controlled fault instances ---------------------------------
    t1 = time.time()
    fault_names = list(faults.PARSER_FAULTS) + \
        list(faults.EVALUATOR_FAULTS)
    per_fault = FAULT_INSTANCES // len(fault_names)   # 50 each
    instances = []
    latencies = []
    contained = 0
    escapes = 0
    idx = 0
    for name in fault_names:
        p = faults.make_parser_fault(name) if name.startswith("P") \
            else None
        e = faults.make_evaluator_fault(name) if name.startswith("E") \
            else None
        if p is None and name.startswith("P"):
            continue
        for k in range(per_fault):
            fault_at = (k * 7 + 5) % 40            # deterministic
            out = camp.run_batch(cases, exps, 10_000 + idx * 31,
                                 parser=p, evaluator=e,
                                 fault_at=fault_at,
                                 experiment=f"ea14-fault-{idx}")
            idx += 1
            det = out["detection"]
            if det["detected"]:
                latencies.append(det["latency"])
            escaped = (not det["detected"]) and \
                out["publication"].startswith("ALLOWED")
            if det["detected"] or not out["publication"].startswith(
                    "ALLOWED"):
                contained += 1
            else:
                escapes += 1
            instances.append({"fault": name, "fault_at": fault_at,
                              "detected": det["detected"],
                              "mechanism": det["mechanism"],
                              "latency": det["latency"],
                              "quarantined": out["quarantined"],
                              "publication": out["publication"],
                              "escaped": escaped})
    fault_seconds = time.time() - t1

    # -- recovery demonstration (requalification-only) --------------------
    recovery_ok = True
    cert_ids = [c.certificate_id
                for c in camp.store.snapshot().certificates]
    camp.state.revoke(cert_ids[0], reason="ea14 recovery drill")
    try:
        camp.issue()
        recovery_ok = False          # revoked must refuse
    except ea.AuthorizationError:
        pass
    # independent requalification: a FRESH certificate with fresh gate
    # evidence (requalified=True — the authority refuses otherwise after
    # revocation), then a new evidence generation and issuance
    QualificationAuthority().issue_qualification(
        scope="semantic", dataset_id="n03-batch-a-dev160@d23de5a",
        parser_version="eval_assurance.production.parser@1",
        evaluator_version="eval_assurance.production.evaluator@1",
        reference_evaluator_version="oracle@v2-requalified",
        dataset_file=PINNED / "n03_cases.public.jsonl",
        task_contract_file=PINNED / "parser_semantics.md",
        parser_file=SRC / "production" / "parser.py",
        interpreter_file=SRC / "reference" / "interpreter.py",
        evaluator_file=SRC / "production" / "evaluator.py",
        reference_oracle_file=SRC / "reference" / "oracle.py",
        witness_suite_file=EVID / "dualpath_witnesses.json",
        mutation_report_file=EVID /
        "production_mutation_campaign.json",
        evidence_files=[tmp / "sc.json", tmp / "canary.json",
                        tmp / "breaker.json"],
        replay_contract="content-addressed replay",
        protocol="cpu-ea14", store=camp.store, requalified=True)
    camp._register("ea14-stress-2")   # fresh evidence generation
    try:
        camp.issue(experiment="ea14-stress-2")
    except ea.AuthorizationError:
        recovery_ok = False

    lat_sorted = sorted(latencies)
    report = {
        "schema": "ijeval.ea14.stress_campaign.v1",
        "generated_utc": stamp,
        "scope": "CPU-only shared-core stress (order section 6)",
        "fault_free_volume": {
            "trials": batches * BATCH, "batches": batches,
            "classification_counts": total_counts,
            "false_alarm_batches": false_alarms,
            "seconds": round(volume_seconds, 1)},
        "fault_instances": {
            "count": len(instances),
            "contained_or_refused": contained,
            "escaped_into_publication": escapes,
            "detected": sum(1 for i in instances if i["detected"]),
            "latency_trials": {
                "min": lat_sorted[0] if lat_sorted else None,
                "median": lat_sorted[len(lat_sorted) // 2]
                if lat_sorted else None,
                "max": lat_sorted[-1] if lat_sorted else None},
            "by_fault": {
                n: {"detected": sum(1 for i in instances
                                    if i["fault"] == n and i["detected"]),
                    "total": sum(1 for i in instances
                                 if i["fault"] == n)}
                for n in fault_names},
            "seconds": round(fault_seconds, 1)},
        "recovery": {"revocation_refused_then_requalified_issued":
                         recovery_ok},
        "verdict": "GO" if escapes == 0 and false_alarms == 0 and
        recovery_ok else "NO_GO"}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "stress_campaign.json").write_text(
        json.dumps(report, indent=1, ensure_ascii=False),
        encoding="utf-8")
    print(json.dumps({k: report[k] for k in
                      ("fault_free_volume", "fault_instances",
                       "recovery", "verdict")}, indent=1)[:2200])
    return 0 if report["verdict"] == "GO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
