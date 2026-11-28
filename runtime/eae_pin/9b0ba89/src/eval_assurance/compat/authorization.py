"""Runner authorization (compat contract section: runner_authorization).

N03 is NOT authorized by a PASS string or a bare certificate object. The
only authorization artifact is a checksummed, scope-bound
``RunnerAuthorization`` produced by :func:`authorize_runner`, which enforces
the complete chain:

1. an ``AggregationReport`` produced by the qualified boundary for the
   requested scope;
2. a trusted certificate store with a currently-valid, applicable
   certificate (snapshot recheck — revocation between aggregation and
   authorization fails closed);
3. a publication verdict that is ALLOWED (or ALLOWED_PARTIAL only when the
   runner explicitly accepts a partial scope and the declaration says so);
4. authorization is bound to the exact scope, roster size, coverage,
   certificate ids + digests and snapshot checksum — any drift is visible.

Machine-readable, versioned, and consumable by the IJ-NANO runner.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from ..qualification import CertificateStore, QualificationSnapshot
from ..statistics import AggregationReport, publish_report

AUTHORIZATION_SCHEMA = "1.0.0"
_ALLOWED_VERDICTS = ("ALLOWED", "ALLOWED_PARTIAL")


@dataclass(frozen=True, init=False)
class RunnerAuthorization:
    _create_key: object
    schema: str
    scope: str
    allowed: bool
    verdict: str
    scope_declaration: str
    qualified_eligible: int
    correct: int
    planned_slots: int
    evaluation_coverage: float | None
    conditional_semantic_accuracy: float | None
    certificate_ids: tuple[str, ...]
    certificate_digests: tuple[tuple[str, str], ...]
    snapshot_checksum: str
    reasons: tuple[str, ...]
    authorization_checksum: str

    def __init__(self, _create_key=None, **kw):
        if _create_key is not _AUTH_CREATE_KEY:
            raise PermissionError(
                "RunnerAuthorization cannot be constructed directly; use "
                "authorize_runner() — a PASS string authorizes nothing")
        object.__setattr__(self, "schema", kw["schema"])
        for f in ("scope", "allowed", "verdict", "scope_declaration"):
            object.__setattr__(self, f, kw[f])
        for f in ("qualified_eligible", "correct", "planned_slots"):
            object.__setattr__(self, f, int(kw[f]))
        object.__setattr__(self, "evaluation_coverage", kw["evaluation_coverage"])
        object.__setattr__(
            self, "conditional_semantic_accuracy",
            kw["conditional_semantic_accuracy"])
        object.__setattr__(self, "certificate_ids",
                           tuple(kw["certificate_ids"]))
        object.__setattr__(self, "certificate_digests",
                           tuple(kw["certificate_digests"]))
        object.__setattr__(self, "snapshot_checksum", kw["snapshot_checksum"])
        object.__setattr__(self, "reasons", tuple(kw["reasons"]))
        material = json.dumps(
            [self.schema, self.scope, self.allowed, self.verdict,
             self.scope_declaration, self.qualified_eligible, self.correct,
             self.planned_slots, self.evaluation_coverage,
             self.conditional_semantic_accuracy, list(self.certificate_ids),
             [list(d) for d in self.certificate_digests],
             self.snapshot_checksum, list(self.reasons)],
            sort_keys=True, default=str)
        object.__setattr__(
            self, "authorization_checksum",
            hashlib.sha256(material.encode()).hexdigest())

    def to_json(self) -> str:
        return json.dumps({
            "schema": self.schema, "scope": self.scope,
            "allowed": self.allowed, "verdict": self.verdict,
            "scope_declaration": self.scope_declaration,
            "qualified_eligible": self.qualified_eligible,
            "correct": self.correct, "planned_slots": self.planned_slots,
            "evaluation_coverage": self.evaluation_coverage,
            "conditional_semantic_accuracy":
                self.conditional_semantic_accuracy,
            "certificate_ids": list(self.certificate_ids),
            "certificate_digests": [list(d) for d in
                                    self.certificate_digests],
            "snapshot_checksum": self.snapshot_checksum,
            "reasons": list(self.reasons),
            "authorization_checksum": self.authorization_checksum,
        }, indent=1, sort_keys=True)


_AUTH_CREATE_KEY = object()


def authorize_runner(report: AggregationReport,
                     certificates: CertificateStore,
                     snapshot: QualificationSnapshot | None = None,
                     *, accept_partial: bool = False
                     ) -> RunnerAuthorization:
    """The single authorization entry point for runner consumption."""
    reasons: list[str] = []
    snap = snapshot if snapshot is not None else certificates.snapshot()
    verdict = report.formal_publication
    allowed = verdict in _ALLOWED_VERDICTS
    if verdict == "ALLOWED_PARTIAL" and not accept_partial:
        allowed = False
        reasons.append("partial scope not accepted by this authorization "
                       "request")
    if allowed:
        try:
            publish_report(report, certificates, snap)   # full recheck
        except RuntimeError as e:
            allowed = False
            reasons.append(f"publication recheck failed: {e}")
    elif not reasons:
        reasons.append(f"aggregation verdict {verdict!r} is not an "
                       "authorization verdict")
    certs = []
    for cid in sorted(report.certificate_ids_used):
        cert = certificates.get(cid)
        if cert is not None:
            certs.append((cid, cert.evaluator_sha256 or cert.certificate_id))
    return RunnerAuthorization(
        _AUTH_CREATE_KEY,
        schema=AUTHORIZATION_SCHEMA,
        scope=report.scope,
        allowed=allowed,
        verdict=verdict,
        scope_declaration=report.scope_declaration,
        qualified_eligible=report.qualified_eligible,
        correct=report.correct,
        planned_slots=report.planned_slots,
        evaluation_coverage=report.evaluation_coverage,
        conditional_semantic_accuracy=report.conditional_semantic_accuracy,
        certificate_ids=[c for c, _ in certs],
        certificate_digests=certs,
        snapshot_checksum=snap.checksum,
        reasons=reasons)
