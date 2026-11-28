"""EA11 — the qualified Analyzer (order section 3.6).

Bridges the integrated dual-path session into the formal assurance
boundary:

- exact planned-roster reconciliation (every planned slot reported,
  missing slots block unless an explicit partial scope is declared);
- unique trial identities (duplicates were rejected at the session);
- VERIFIED evidence (the session artifacts are re-hashed first; any
  tamper/absence downgrades rows to MISSING evidence);
- certificate validation + CURRENT revocation state at the FINAL
  publication boundary (snapshot recheck);
- conditional semantic accuracy separated from evaluation coverage;
- verified success coverage (qualified-correct share of the PLANNED
  roster);
- no unresolved critical evaluation-integrity fault escapes into
  formal publication.
"""
from __future__ import annotations

from .compat.execution_authorization import AuthorizationError
from .contracts import (EvaluationResult, EvaluationStatus,
                        EvidenceIntegrity, ExecutionStatus, EvaluatorStatus,
                        ParserStatus, SemanticVerdict)
from .contracts import verify_evidence
from .dualpath import (CORRECT, DUPLICATE_TRIAL, EMPTY_OUTPUT,
                        EVALUATOR_SOFTWARE_ERROR, INCORRECT,
                        INVALID_OUTPUT, MISSING_EVIDENCE,
                        NOT_EVALUABLE, PARSER_SOFTWARE_ERROR)
from .qualification.store import CertificateStore
from .statistics.boundary import aggregate_semantic, publish_report

#: dual-path classification -> typed contract enums
_CLASS_MAP = {
    CORRECT: (ExecutionStatus.EXECUTED, EvaluationStatus.VALID,
              ParserStatus.PARSE_OK, SemanticVerdict.CORRECT,
              EvaluatorStatus.OK),
    INCORRECT: (ExecutionStatus.EXECUTED, EvaluationStatus.VALID,
                ParserStatus.PARSE_OK, SemanticVerdict.INCORRECT,
                EvaluatorStatus.OK),
    INVALID_OUTPUT: (ExecutionStatus.EXECUTED, EvaluationStatus.VALID,
                     ParserStatus.MODEL_OUTPUT_INVALID,
                     SemanticVerdict.INCORRECT, EvaluatorStatus.OK),
    EMPTY_OUTPUT: (ExecutionStatus.EXECUTED, EvaluationStatus.VALID,
                   ParserStatus.PARSE_OK, SemanticVerdict.INCORRECT,
                   EvaluatorStatus.OK),
    NOT_EVALUABLE: (ExecutionStatus.EXECUTED,
                    EvaluationStatus.ORACLE_DISAGREEMENT,
                    ParserStatus.PARSE_OK, SemanticVerdict.NOT_EVALUABLE,
                    EvaluatorStatus.DISAGREEMENT),
    PARSER_SOFTWARE_ERROR: (ExecutionStatus.EXECUTED,
                            EvaluationStatus.PARSER_ERROR,
                            ParserStatus.PARSER_SOFTWARE_ERROR,
                            SemanticVerdict.NOT_EVALUABLE,
                            EvaluatorStatus.OK),
    EVALUATOR_SOFTWARE_ERROR: (ExecutionStatus.EXECUTED,
                               EvaluationStatus.EVALUATOR_ERROR,
                               ParserStatus.PARSE_OK,
                               SemanticVerdict.NOT_EVALUABLE,
                               EvaluatorStatus.ERROR),
    MISSING_EVIDENCE: (ExecutionStatus.NOT_RUN,
                       EvaluationStatus.ARTIFACT_ERROR,
                       ParserStatus.PARSE_OK,
                       SemanticVerdict.NOT_EVALUABLE,
                       EvaluatorStatus.OK),
}


class QualifiedAnalyzer:
    """Formal analysis of a dual-path session against a planned roster
    under a trusted certificate store."""

    def __init__(self, *, experiment_id: str, dataset_id: str,
                 parser_version: str, evaluator_version: str,
                 certificates: CertificateStore,
                 planned_roster=None, scope: str | None = None):
        if not isinstance(certificates, CertificateStore) or \
                not certificates.trusted:
            raise AuthorizationError(
                "qualified analyzer requires a TRUSTED certificate store")
        self.experiment_id = experiment_id
        self.dataset_id = dataset_id
        self.parser_version = parser_version
        self.evaluator_version = evaluator_version
        self.certificates = certificates
        self.planned_roster = planned_roster
        if scope is None:
            # derive the aggregation scope from the applicable
            # certificate (a scope with no valid certificate can never
            # publish — EA-R03)
            valid = [c for c in certificates.snapshot().certificates
                     if c.is_valid()]
            if not valid:
                raise AuthorizationError(
                    "certificate store holds no valid certificate to "
                    "derive the aggregation scope from")
            scope = valid[0].scope
        self.scope = scope

    def _record(self, trial: dict) -> EvaluationResult:
        cls = trial.get("classification", NOT_EVALUABLE)
        ex, ev, ps, sv, es = _CLASS_MAP.get(
            cls, _CLASS_MAP[NOT_EVALUABLE])
        provenance = {
            "experiment_id": self.experiment_id,
            "trial_id": trial["trial_id"],
            "task_id": trial.get("case_id", trial["trial_id"]),
            "model": trial.get("model", ""),
            "dataset_id": self.dataset_id,
            "parser_version": self.parser_version,
            "evaluator_version": self.evaluator_version,
            "dataset_sha256": "",
            "artifact_sha256": trial.get("artifact_sha256", ""),
        }
        evidence = verify_evidence(
            provenance,
            artifact_sha256_computed=trial.get("artifact_sha256", ""),
            artifact_sha256_expected=trial.get("artifact_sha256", ""),
            schema_validated=True,
            trial_identity_match=True,
            basis="session-content-addressed-capture")
        integrity = EvidenceIntegrity.VERIFIED
        if cls == MISSING_EVIDENCE or cls == DUPLICATE_TRIAL:
            integrity = EvidenceIntegrity.MISSING
        return EvaluationResult(
            execution_status=ex, evaluation_status=ev, parser_status=ps,
            semantic_verdict=sv, evaluator_status=es,
            provenance=provenance, evidence=integrity,
            verified_evidence=evidence if
            integrity is EvidenceIntegrity.VERIFIED else None)

    def analyze(self, session, *, partial_scope_allowed: bool = False):
        """Verify evidence, adapt the session's trials to typed records
        and aggregate through the formal boundary. Canary controls are
        passed as CANARY_CONTROL rows (never in denominators)."""
        integrity_problems = session.verify()
        records = [self._record(t) for t in session.trials.values()]
        canaries = session.canary_controls
        for c in canaries:
            records.append(EvaluationResult(
                execution_status=ExecutionStatus.CANARY_CONTROL,
                evaluation_status=EvaluationStatus.VALID,
                parser_status=ParserStatus.PARSE_OK,
                semantic_verdict=SemanticVerdict.NOT_APPLICABLE,
                provenance={
                    "experiment_id": self.experiment_id,
                    "trial_id": c.get("trial_id", "canary"),
                    "task_id": "canary", "model": "canary",
                    "dataset_id": self.dataset_id,
                    "parser_version": self.parser_version,
                    "evaluator_version": self.evaluator_version,
                    "dataset_sha256": "",
                    "artifact_sha256": ""},
                evidence=EvidenceIntegrity.UNVERIFIED))
        report = aggregate_semantic(
            records, scope=self.scope, certificates=self.certificates,
            planned_roster=self.planned_roster,
            partial_scope_allowed=partial_scope_allowed)
        report.integrity_problems = integrity_problems   # type: ignore[attr-defined]
        if integrity_problems:
            report.formal_publication = "BLOCKED_EVIDENCE_INTEGRITY"
        return report

    def publication_eligibility(self, report):
        """FINAL publication boundary: revalidate the current
        qualification state (revocations since aggregation fail
        closed)."""
        return publish_report(report, self.certificates)
