"""Wave C continuous-protection controls (order sections 3.1-3.6).

§3.2 end-to-end revocation (11 scenarios), §3.3 trusted
ExecutionEvidence registration, §3.4 canary cadence, §3.5 persistent
circuit breaker, §3.6 qualified analyzer — executed against the real
modules and the pinned witness corpus.
"""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
EVID = ROOT / "evidence" / "IJEVAL" / "EA03_N03"

from eval_assurance import canary as canary_mod                  # noqa: E402
from eval_assurance.compat import execution_authorization as ea  # noqa: E402
from eval_assurance.authoritative import (                       # noqa: E402
    AuthoritativeQualificationState, AuthoritativeStateError)
from eval_assurance.breaker import (CircuitBreaker,              # noqa: E402
                                    CircuitBreakerOpen)
from eval_assurance.analysis import QualifiedAnalyzer            # noqa: E402
from eval_assurance.dualpath import DualPathSession              # noqa: E402
from eval_assurance.qualification.store import (                 # noqa: E402
    CertificateError, CertificateStore, QualificationAuthority)

REV = "1.1.1"
DATASET = "d045cf42fdfe1a03f688dae939511912cdeb8c6756bc060d4303456e16687c7f4"
ROSTER = "r0" * 32


def _write(p: pathlib.Path, obj) -> pathlib.Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=1, ensure_ascii=False),
                 encoding="utf-8")
    return p


class WaveCBase(unittest.TestCase):
    """Shared fixture: real authority-issued certificate + authoritative
    state + trusted evidence artifacts on disk."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=str(ROOT / ".runtime"))
        self.addCleanup(self.tmp.cleanup)
        self.dir = pathlib.Path(self.tmp.name)
        self.evid_files = []
        for name in ("shared_core_acceptance.json", "canary.json",
                     "breaker.json"):
            self.evid_files.append(_write(self.dir / name,
                                          {"passed": True,
                                           "verdict": "ACCEPTED"}
                                          if "acceptance" in name
                                          else {"passed": True}))
        # a roster file whose digest the evidence binds
        self.roster_file = _write(self.dir / "roster.json",
                                  {"slots": ["s1", "s2"]})
        self.dataset_file = EVID / "pinned" / "n03_cases.public.jsonl"
        self.witness_file = EVID / "dualpath_witnesses.json"
        self.mutation_file = EVID / "production_mutation_campaign.json"
        self.parser_file = ROOT / "src" / "eval_assurance" / \
            "production" / "parser.py"
        self.evaluator_file = ROOT / "src" / "eval_assurance" / \
            "production" / "evaluator.py"
        self.interpreter_file = ROOT / "src" / "eval_assurance" / \
            "reference" / "interpreter.py"
        self.oracle_file = ROOT / "src" / "eval_assurance" / \
            "reference" / "oracle.py"

        self.authority = QualificationAuthority()
        self.store = self.authority.issue_qualification(
            scope="semantic",
            dataset_id="n03-batch-a-dev160@d23de5a",
            parser_version="eval_assurance.production.parser@1",
            evaluator_version="eval_assurance.production.evaluator@1",
            reference_evaluator_version="oracle@v2",
            dataset_file=self.dataset_file,
            task_contract_file=EVID / "pinned" / "parser_semantics.md",
            parser_file=self.parser_file, interpreter_file=
            self.interpreter_file,
            evaluator_file=self.evaluator_file,
            reference_oracle_file=self.oracle_file,
            witness_suite_file=self.witness_file,
            mutation_report_file=self.mutation_file,
            evidence_files=self.evid_files,
            replay_contract="content-addressed replay",
            protocol="cpu-dualpath-qualification")
        self.cert_ids = [c.certificate_id
                         for c in self.store.snapshot().certificates]
        self.state_file = self.dir / "authoritative_state.json"
        self.state = AuthoritativeQualificationState(
            self.store, self.state_file)

        ea.clear_execution_evidence()
        ea.bind_authoritative_state(None)
        self.evidence = ea.register_trusted_execution_evidence(
            authoritative_state=self.state,
            experiment_id="exp-wavec-1", auth_purpose="AUTH-1",
            primitives=["C01", "C02"], protocols=["chat"],
            models=["synthetic-cpu"],
            dataset_file=self.dataset_file, roster_file=self.roster_file,
            parser_file=self.parser_file,
            evaluator_file=self.evaluator_file,
            interpreter_file=self.interpreter_file,
            oracle_file=self.oracle_file,
            certificate_store=self.store,
            shared_core_acceptance_file=self.evid_files[0],
            canary_evidence_file=self.evid_files[1],
            breaker_evidence_file=self.evid_files[2],
            witness_suite_file=self.witness_file,
            mutation_report_file=self.mutation_file,
            dispatch_limits={"max_trials": 48})

    def issue(self, **over):
        kw = dict(experiment_id="exp-wavec-1",
                  dataset_digest=self._dataset_digest(),
                  roster_digest=self._roster_digest(),
                  primitives=["C01"], protocols=["chat"],
                  models=["synthetic-cpu"], auth_level="AUTH-1",
                  eae_revision=REV)
        kw.update(over)
        return ea.issue_execution_authorization(**kw)

    def _roster_digest(self):
        import hashlib
        return hashlib.sha256(
            self.roster_file.read_bytes()).hexdigest()

    def _dataset_digest(self):
        import hashlib
        return hashlib.sha256(
            self.dataset_file.read_bytes()).hexdigest()


class RevocationScenarios(WaveCBase):
    """Order §3.2: the eleven end-to-end revocation scenarios."""

    def test_01_revocation_before_authorization(self):
        self.state.revoke(self.cert_ids[0], reason="pre")
        with self.assertRaises(ea.AuthorizationError):
            self.issue()

    def test_02_revocation_after_authorization(self):
        auth = self.issue()
        self.state.revoke(self.cert_ids[0], reason="post")
        with self.assertRaises(ea.AuthorizationError):
            ea.recheck_execution_authorization(auth)

    def test_03_revocation_between_requests(self):
        self.issue()
        self.state.revoke(self.cert_ids[0], reason="between")
        with self.assertRaises(ea.AuthorizationError):
            self.issue()

    def test_04_revocation_during_active_inference(self):
        auth = self.issue()
        in_flight = "trial-7"
        br = CircuitBreaker(self.dir / "breaker4.json")
        br.register_dispatch(in_flight)
        self.state.revoke(self.cert_ids[0], reason="during")
        with self.assertRaises(ea.AuthorizationError):
            ea.recheck_execution_authorization(auth)
        br.open(reason="qualification revoked",
                affected_scope=["C01"],
                contamination_window=[in_flight])
        with self.assertRaises(CircuitBreakerOpen):
            br.may_dispatch("trial-8")

    def test_05_non_primary_certificate_revocation(self):
        # add a second certificate and revoke the NON-primary one
        self.authority.issue_qualification(
            scope="semantic",
            dataset_id="n03-batch-a-dev160@d23de5a",
            parser_version="eval_assurance.production.parser@1",
            evaluator_version="eval_assurance.production.evaluator@1",
            reference_evaluator_version="oracle@v2b",
            dataset_file=self.dataset_file,
            task_contract_file=EVID / "pinned" / "parser_semantics.md",
            parser_file=self.parser_file,
            interpreter_file=self.interpreter_file,
            evaluator_file=self.evaluator_file,
            reference_oracle_file=self.oracle_file,
            witness_suite_file=self.witness_file,
            mutation_report_file=self.mutation_file,
            evidence_files=self.evid_files,
            replay_contract="content-addressed replay",
            protocol="cpu-dualpath-qualification", store=self.store)
        ea.clear_execution_evidence()
        ea.bind_authoritative_state(self.state)
        # re-register with both certificates applicable
        ev = ea.register_trusted_execution_evidence(
            authoritative_state=self.state,
            experiment_id="exp-wavec-1", auth_purpose="AUTH-1",
            primitives=["C01"], protocols=["chat"],
            models=["synthetic-cpu"],
            dataset_file=self.dataset_file,
            roster_file=self.roster_file,
            parser_file=self.parser_file,
            evaluator_file=self.evaluator_file,
            interpreter_file=self.interpreter_file,
            oracle_file=self.oracle_file,
            certificate_store=self.store,
            shared_core_acceptance_file=self.evid_files[0],
            canary_evidence_file=self.evid_files[1],
            breaker_evidence_file=self.evid_files[2],
            witness_suite_file=self.witness_file,
            mutation_report_file=self.mutation_file)
        self.assertGreaterEqual(len(ev.certificate_refs), 2)
        non_primary = ev.certificate_refs[1]
        auth = self.issue()
        self.state.revoke(non_primary, reason="non-primary")
        with self.assertRaises(ea.AuthorizationError):
            ea.recheck_execution_authorization(auth)

    def test_06_stale_authorization_after_evidence_replacement(self):
        auth = self.issue()
        # replace the evidence (new registration -> new identity)
        ea.register_trusted_execution_evidence(
            authoritative_state=self.state,
            experiment_id="exp-wavec-2", auth_purpose="AUTH-1",
            primitives=["C01"], protocols=["chat"],
            models=["synthetic-cpu"],
            dataset_file=self.dataset_file,
            roster_file=self.roster_file,
            parser_file=self.parser_file,
            evaluator_file=self.evaluator_file,
            interpreter_file=self.interpreter_file,
            oracle_file=self.oracle_file,
            certificate_store=self.store,
            shared_core_acceptance_file=self.evid_files[0],
            canary_evidence_file=self.evid_files[1],
            breaker_evidence_file=self.evid_files[2],
            witness_suite_file=self.witness_file,
            mutation_report_file=self.mutation_file)
        with self.assertRaises(ea.AuthorizationError):
            ea.recheck_execution_authorization(auth)   # stale refused

    def test_07_process_restart_with_revocation_state(self):
        self.state.revoke(self.cert_ids[0], reason="restart")
        restarted = AuthoritativeQualificationState(
            self.store, self.state_file)
        with self.assertRaises(ea.AuthorizationError):
            ea.register_trusted_execution_evidence(
                authoritative_state=restarted,
                experiment_id="exp-wavec-3", auth_purpose="AUTH-1",
                primitives=["C01"], protocols=["chat"],
                models=["synthetic-cpu"],
                dataset_file=self.dataset_file,
                roster_file=self.roster_file,
                parser_file=self.parser_file,
                evaluator_file=self.evaluator_file,
                interpreter_file=self.interpreter_file,
                oracle_file=self.oracle_file,
                certificate_store=restarted.store,
                shared_core_acceptance_file=self.evid_files[0],
                canary_evidence_file=self.evid_files[1],
                breaker_evidence_file=self.evid_files[2],
                witness_suite_file=self.witness_file,
                mutation_report_file=self.mutation_file)

    def test_08_reissue_without_requalification_refused(self):
        self.state.revoke(self.cert_ids[0], reason="reissue")
        with self.assertRaises(CertificateError):
            self.authority.issue_qualification(
                scope="semantic",
                dataset_id="n03-batch-a-dev160@d23de5a",
                parser_version="eval_assurance.production.parser@1",
                evaluator_version="eval_assurance.production.evaluator@1",
                reference_evaluator_version="oracle@v2",
                dataset_file=self.dataset_file,
                task_contract_file=EVID / "pinned" /
                "parser_semantics.md",
                parser_file=self.parser_file,
                interpreter_file=self.interpreter_file,
                evaluator_file=self.evaluator_file,
                reference_oracle_file=self.oracle_file,
                witness_suite_file=self.witness_file,
                mutation_report_file=self.mutation_file,
                evidence_files=self.evid_files,
                replay_contract="content-addressed replay",
                protocol="cpu-dualpath-qualification", store=self.store)

    def test_09_changed_experiment_identity(self):
        with self.assertRaises(ea.AuthorizationError):
            self.issue(experiment_id="exp-OTHER")

    def test_10_changed_roster(self):
        with self.assertRaises(ea.AuthorizationError):
            self.issue(roster_digest="f" * 64)

    def test_11_changed_authorization_level(self):
        with self.assertRaises(ea.AuthorizationError):
            self.issue(auth_level="AUTH-2")   # evidence purpose AUTH-1


class TrustedRegistration(WaveCBase):
    """Order §3.3: caller-asserted readiness never registers."""

    def test_caller_accepted_string_refused(self):
        bad = _write(self.dir / "bad_acceptance.json",
                     {"verdict": "ACCEPTED"})
        # a file SAYING accepted but no passing canary artifact:
        bad_canary = _write(self.dir / "bad_canary.json",
                            {"passed": False})
        with self.assertRaises(ea.AuthorizationError):
            ea.register_trusted_execution_evidence(
                authoritative_state=self.state,
                experiment_id="e", auth_purpose="AUTH-1",
                primitives=["C01"], protocols=["chat"], models=["m"],
                dataset_file=self.dataset_file,
                roster_file=self.roster_file,
                parser_file=self.parser_file,
                evaluator_file=self.evaluator_file,
                interpreter_file=self.interpreter_file,
                oracle_file=self.oracle_file,
                certificate_store=self.store,
                shared_core_acceptance_file=bad,
                canary_evidence_file=bad_canary,
                breaker_evidence_file=self.evid_files[2],
                witness_suite_file=self.witness_file,
                mutation_report_file=self.mutation_file)

    def test_shared_core_not_accepted_refused(self):
        not_accepted = _write(self.dir / "partial.json",
                              {"verdict": "PARTIAL"})
        with self.assertRaises(ea.AuthorizationError):
            ea.register_trusted_execution_evidence(
                authoritative_state=self.state,
                experiment_id="e", auth_purpose="AUTH-1",
                primitives=["C01"], protocols=["chat"], models=["m"],
                dataset_file=self.dataset_file,
                roster_file=self.roster_file,
                parser_file=self.parser_file,
                evaluator_file=self.evaluator_file,
                interpreter_file=self.interpreter_file,
                oracle_file=self.oracle_file,
                certificate_store=self.store,
                shared_core_acceptance_file=not_accepted,
                canary_evidence_file=self.evid_files[1],
                breaker_evidence_file=self.evid_files[2],
                witness_suite_file=self.witness_file,
                mutation_report_file=self.mutation_file)

    def test_revoked_certificate_refused_at_registration(self):
        self.state.revoke(self.cert_ids[0], reason="x")
        with self.assertRaises(ea.AuthorizationError):
            ea.register_trusted_execution_evidence(
                authoritative_state=self.state,
                experiment_id="e", auth_purpose="AUTH-1",
                primitives=["C01"], protocols=["chat"], models=["m"],
                dataset_file=self.dataset_file,
                roster_file=self.roster_file,
                parser_file=self.parser_file,
                evaluator_file=self.evaluator_file,
                interpreter_file=self.interpreter_file,
                oracle_file=self.oracle_file,
                certificate_store=self.store,
                shared_core_acceptance_file=self.evid_files[0],
                canary_evidence_file=self.evid_files[1],
                breaker_evidence_file=self.evid_files[2],
                witness_suite_file=self.witness_file,
                mutation_report_file=self.mutation_file)

    def test_evidence_identity_binds_content(self):
        ev1 = ea.registered_evidence()
        ident1 = ev1.evidence_identity()
        ea.register_trusted_execution_evidence(
            authoritative_state=self.state,
            experiment_id="exp-wavec-1", auth_purpose="AUTH-1",
            primitives=["C01"], protocols=["chat"],
            models=["synthetic-cpu"],
            dataset_file=self.dataset_file, roster_file=self.roster_file,
            parser_file=self.parser_file,
            evaluator_file=self.evaluator_file,
            interpreter_file=self.interpreter_file,
            oracle_file=self.oracle_file,
            certificate_store=self.store,
            shared_core_acceptance_file=self.evid_files[0],
            canary_evidence_file=self.evid_files[1],
            breaker_evidence_file=self.evid_files[2],
            witness_suite_file=self.witness_file,
            mutation_report_file=self.mutation_file)
        self.assertNotEqual(ident1,
                            ea.registered_evidence()
                            .evidence_identity())


class CanaryCadence(WaveCBase):
    """Order §3.4: production-path canary cadence and class exclusion."""

    @classmethod
    def setUpClass(cls):
        cls.witnesses = json.loads(
            (EVID / "dualpath_witnesses.json").read_text(
                encoding="utf-8"))["rows"]
        cls.expectations = {json.loads(l)["case_id"]: json.loads(l)
                            for l in
                            (EVID / "pinned" /
                             "n03_dev_expectations.jsonl").read_text(
                                encoding="utf-8").splitlines()
                            if l.strip()}

    def test_preflight_and_intervals(self):
        cases_by_id = {json.loads(l)["case_id"]: json.loads(l)
                       for l in
                       (EVID / "pinned" / "n03_cases.public.jsonl")
                       .read_text(encoding="utf-8").splitlines()
                       if l.strip()}
        sched = canary_mod.CanaryScheduler(
            [w for w in self.witnesses if w["kind"] != "software-error"],
            breaker=CircuitBreaker(self.dir / "cb1.json"),
            expectations=self.expectations, cases_by_id=cases_by_id)
        first = sched.preflight()           # full family sweep
        self.assertTrue(all(r.passed for r in first))
        self.assertEqual(len(first), 8)     # every family swept
        ran = None
        for i in range(24):
            ran = sched.on_trial(f"t{i}")
            self.assertIsNone(ran)          # 24 < 25: no canary yet
        ran = sched.on_trial("t24")         # 25th trial triggers sweep
        self.assertIsNotNone(ran)
        self.assertTrue(all(r.passed for r in ran))

    def test_time_interval_whichever_first(self):
        t = {"now": 0.0}
        cases_by_id = {json.loads(l)["case_id"]: json.loads(l)
                       for l in
                       (EVID / "pinned" / "n03_cases.public.jsonl")
                       .read_text(encoding="utf-8").splitlines()
                       if l.strip()}
        sched = canary_mod.CanaryScheduler(
            self.witnesses, interval_trials=1000, interval_seconds=300,
            clock=lambda: t["now"], expectations=self.expectations,
            cases_by_id=cases_by_id)
        sched.preflight()
        t["now"] = 200.0
        self.assertIsNone(sched.on_trial("t1"))    # < 5 min
        t["now"] = 301.0
        result = sched.on_trial("t2")              # 5 min elapsed first
        self.assertIsNotNone(result)
        self.assertTrue(all(r.passed for r in result))

    def test_failing_canary_opens_breaker_and_quarantines_window(self):
        br = CircuitBreaker(self.dir / "cb2.json")
        witnesses = [dict(w) for w in self.witnesses
                     if w["kind"] != "software-error"]
        cases_by_id = {json.loads(l)["case_id"]: json.loads(l)
                       for l in
                       (EVID / "pinned" / "n03_cases.public.jsonl")
                       .read_text(encoding="utf-8").splitlines()
                       if l.strip()}
        # the fault develops MID-RUN (after a healthy preflight): the
        # C08 production leg starts misclassifying. With full-family
        # sweeps the next checkpoint catches it; the contamination
        # window (trials dispatched since health) is quarantined.
        healthy = [w for w in witnesses
                   if not (w["kind"] == "positive"
                           and w["primitive"] == "C08")]
        sched = canary_mod.CanaryScheduler(
            healthy, breaker=br, expectations=self.expectations,
            cases_by_id=cases_by_id)
        first = sched.preflight()
        self.assertTrue(all(r.passed for r in first))
        # runtime corruption of the C08 witnesses (emulates a
        # production-leg behavior change for the same inputs)
        for w in witnesses:
            if w["kind"] == "positive" and w["primitive"] == "C08":
                w["raw"] = "definitely-not-a-tool-id ... with spaces"
        sched.witnesses = witnesses
        sched.on_trial("t1")
        sched.on_trial("t2")
        result = sched.run_canary("C08")
        self.assertFalse(result.passed)
        self.assertTrue(br.is_open)
        scope = br.contamination_scope
        self.assertIn("t1", scope["quarantined_trials"])
        self.assertIn("t2", scope["quarantined_trials"])

    def test_canaries_never_in_benchmark_denominator(self):
        rec = canary_mod.CanaryResult("C01", True)
        session = DualPathSession(self.dir / "sess")
        session.record_canary_control(rec.as_control_record())
        analyzer = QualifiedAnalyzer(
            experiment_id="e", dataset_id="d",
            parser_version="eval_assurance.production.parser@1",
            evaluator_version="eval_assurance.production.evaluator@1",
            certificates=self.store, planned_roster=["a|b|c"])
        report = analyzer.analyze(session)
        self.assertEqual(report.canary_controls, 1)
        self.assertEqual(report.total_records, 1)


class PersistentBreaker(WaveCBase):
    """Order §3.5: restart-safe containment and requalification-only
    recovery."""

    def test_restart_safe_open_state(self):
        br = CircuitBreaker(self.dir / "cb3.json")
        br.register_dispatch("in-flight-1")
        br.open(reason="fault", affected_scope=["C02"],
                contamination_window=["t1"])
        br2 = CircuitBreaker(self.dir / "cb3.json")   # restart
        self.assertTrue(br2.is_open)
        self.assertIn("in-flight-1",
                      br2.contamination_scope["quarantined_trials"])
        with self.assertRaises(CircuitBreakerOpen):
            br2.may_dispatch("new-trial")

    def test_evidence_preservation(self):
        br = CircuitBreaker(self.dir / "cb4.json")
        br.open(reason="fault", affected_scope=["C03"])
        preserved = br.preserve_evidence(["abc123", "def456"])
        self.assertEqual(sorted(preserved), ["abc123", "def456"])
        br2 = CircuitBreaker(self.dir / "cb4.json")
        self.assertEqual(br2.contamination_scope["preserved_evidence"],
                         ["abc123", "def456"])

    def test_recovery_requires_new_authoritative_generation(self):
        br = CircuitBreaker(self.dir / "cb5.json")
        br.open(reason="fault", affected_scope=["C01"])
        with self.assertRaises(CircuitBreakerOpen):
            br.recover_via_requalification(
                new_evidence_generation=0, authoritative_generation=0,
                canary_passed=True)      # no new generation
        with self.assertRaises(CircuitBreakerOpen):
            br.recover_via_requalification(
                new_evidence_generation=1, authoritative_generation=2,
                canary_passed=True)      # mismatched generations
        with self.assertRaises(CircuitBreakerOpen):
            br.recover_via_requalification(
                new_evidence_generation=1, authoritative_generation=1,
                canary_passed=False)     # canary did not pass
        gen = self.state.register_evidence_identity("fresh-evidence")
        br.recover_via_requalification(
            new_evidence_generation=gen, authoritative_generation=gen,
            canary_passed=True)
        self.assertFalse(br.is_open)

    def test_tampered_breaker_state_fails_closed(self):
        br = CircuitBreaker(self.dir / "cb6.json")
        br.open(reason="fault", affected_scope=["C01"])
        p = self.dir / "cb6.json"
        p.write_text(json.dumps({"schema": "1.0.0", "state": "CLOSED"}),
                     encoding="utf-8")
        with self.assertRaises(CircuitBreakerOpen):
            CircuitBreaker(p)            # tamper -> stays suspended


class QualifiedAnalyzerControls(WaveCBase):
    """Order §3.6: analyzer boundary controls on a real session."""

    def _session_with_trials(self):
        cases = [json.loads(l) for l in
                 (EVID / "pinned" / "n03_cases.public.jsonl")
                 .read_text(encoding="utf-8").splitlines() if l.strip()]
        exps = {json.loads(l)["case_id"]: json.loads(l) for l in
                (EVID / "pinned" / "n03_dev_expectations.jsonl")
                .read_text(encoding="utf-8").splitlines() if l.strip()}
        s = DualPathSession(self.dir / "an")
        chosen = [c for c in cases if c["split"] == "development"][:5]
        for c in chosen:
            s.run_trial(c, exps[c["case_id"]], "some answer",
                        model="m1", protocol="chat")
        return s, [f"{c['case_id']}|m1|chat" for c in chosen]

    def test_full_roster_allowed_and_metrics_separated(self):
        s, roster = self._session_with_trials()
        an = QualifiedAnalyzer(
            experiment_id="e", dataset_id="n03-batch-a-dev160@d23de5a",
            parser_version="eval_assurance.production.parser@1",
            evaluator_version="eval_assurance.production.evaluator@1",
            certificates=self.store, planned_roster=roster)
        rep = an.analyze(s)
        self.assertTrue(rep.formal_publication.startswith("ALLOWED"))
        self.assertIsNotNone(rep.conditional_semantic_accuracy)
        self.assertIsNotNone(rep.evaluation_coverage)

    def test_missing_roster_slots_block_or_partial(self):
        s, roster = self._session_with_trials()
        an = QualifiedAnalyzer(
            experiment_id="e", dataset_id="n03-batch-a-dev160@d23de5a",
            parser_version="eval_assurance.production.parser@1",
            evaluator_version="eval_assurance.production.evaluator@1",
            certificates=self.store,
            planned_roster=roster + ["missing|slot"])
        rep = an.analyze(s)
        self.assertEqual(rep.formal_publication,
                         "BLOCKED_INCOMPLETE_ROSTER")
        rep2 = an.analyze(s, partial_scope_allowed=True)
        self.assertEqual(rep2.formal_publication, "ALLOWED_PARTIAL")
        self.assertEqual(rep2.scope_declaration, "partial")

    def test_final_boundary_revocation_recheck(self):
        s, roster = self._session_with_trials()
        an = QualifiedAnalyzer(
            experiment_id="e", dataset_id="n03-batch-a-dev160@d23de5a",
            parser_version="eval_assurance.production.parser@1",
            evaluator_version="eval_assurance.production.evaluator@1",
            certificates=self.store, planned_roster=roster)
        rep = an.analyze(s)
        # revocation between aggregation and publication
        self.state.revoke(self.cert_ids[0], reason="late")
        with self.assertRaises(RuntimeError):
            an.publication_eligibility(rep)

    def test_tampered_artifact_blocks_publication(self):
        s, roster = self._session_with_trials()
        an = QualifiedAnalyzer(
            experiment_id="e", dataset_id="n03-batch-a-dev160@d23de5a",
            parser_version="eval_assurance.production.parser@1",
            evaluator_version="eval_assurance.production.evaluator@1",
            certificates=self.store, planned_roster=roster)
        art = next((s.workdir / "artifacts").iterdir())
        art.write_text("tampered", encoding="utf-8")
        rep = an.analyze(s)
        self.assertEqual(rep.formal_publication,
                         "BLOCKED_EVIDENCE_INTEGRITY")


if __name__ == "__main__":
    unittest.main()
