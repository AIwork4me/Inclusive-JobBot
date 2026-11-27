"""EA02-R (EA-D01) — qualification certificates and scope binding.

Formal eligibility (qualified statistics, formal publication, RL rewards)
must require the actual applicable qualification certificate with verified
scope binding — not a caller-provided enum. Until the complete EA17
certificate system exists, formal eligibility fails closed: no certificate
store, no formal consumption.

Certificates are evidence-bound records, not guarantees against future bugs
(mission order EA17). Revocation is explicit and timestamped.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import time
from dataclasses import dataclass, field

from ..contracts.core import MANDATORY_PROVENANCE_KEYS

CERTIFICATE_SCHEMA_VERSION = "1.0.0"


class CertificateError(ValueError):
    """Certificate lookup/binding failure (fail-closed signal)."""


@dataclass(frozen=True)
class QualificationCertificate:
    scope: str                     # e.g. "ij_nano.n02r" or "family:slot_extraction"
    dataset_id: str
    parser_version: str
    evaluator_version: str
    reference_evaluator_version: str
    issued_utc: str
    certificate_id: str
    evidence_ref: str = ""
    revoked_utc: str | None = None

    def identity_binding(self) -> dict:
        return {"dataset_id": self.dataset_id,
                "parser_version": self.parser_version,
                "evaluator_version": self.evaluator_version}

    def is_valid(self) -> bool:
        return self.revoked_utc is None


class CertificateStore:
    """In-memory store with optional JSON persistence. The authoritative
    registry for formal eligibility decisions."""

    def __init__(self, persist_to: pathlib.Path | None = None):
        self._persist_to = persist_to
        self._certs: dict[str, QualificationCertificate] = {}
        if persist_to is not None and persist_to.exists():
            raw = json.loads(persist_to.read_text(encoding="utf-8"))
            for rec in raw.get("certificates", []):
                cert = QualificationCertificate(**rec)
                self._certs[cert.certificate_id] = cert

    def issue(self, *, scope: str, dataset_id: str, parser_version: str,
              evaluator_version: str, reference_evaluator_version: str,
              evidence_ref: str = "") -> QualificationCertificate:
        cert_id = hashlib.sha256(json.dumps(
            [CERTIFICATE_SCHEMA_VERSION, scope, dataset_id, parser_version,
             evaluator_version, reference_evaluator_version,
             time.time_ns()], sort_keys=True).encode()).hexdigest()[:16]
        cert = QualificationCertificate(
            scope=scope, dataset_id=dataset_id, parser_version=parser_version,
            evaluator_version=evaluator_version,
            reference_evaluator_version=reference_evaluator_version,
            issued_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            certificate_id=cert_id, evidence_ref=evidence_ref)
        self._certs[cert_id] = cert
        self._persist()
        return cert

    def revoke(self, certificate_id: str, *, reason: str) -> None:
        cert = self._certs.get(certificate_id)
        if cert is None:
            raise CertificateError(f"unknown certificate {certificate_id}")
        self._certs[certificate_id] = QualificationCertificate(
            **{**cert.__dict__,
               "revoked_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                            time.gmtime())})
        self._persist({"revocation_reason": reason})

    def _persist(self, extra: dict | None = None) -> None:
        if self._persist_to is None:
            return
        payload = {"schema_version": CERTIFICATE_SCHEMA_VERSION,
                   "certificates": [c.__dict__ for c in
                                    self._certs.values()]}
        if extra:
            payload.update(extra)
        self._persist_to.parent.mkdir(parents=True, exist_ok=True)
        self._persist_to.write_text(
            json.dumps(payload, indent=1, ensure_ascii=False),
            encoding="utf-8")

    def valid_certificate_for(self, provenance: dict,
                              scope: str) -> QualificationCertificate | None:
        """The actual applicable certificate for a record's identity binding,
        or None. Matching is by scope AND the identity fields the certificate
        binds (dataset/parser/evaluator) against the record's provenance —
        a caller-provided enum is never consulted."""
        for cert in self._certs.values():
            if not cert.is_valid() or cert.scope != scope:
                continue
            binding = cert.identity_binding()
            if (binding["dataset_id"] == provenance.get("dataset_id")
                    and binding["parser_version"]
                    == provenance.get("parser_version")
                    and binding["evaluator_version"]
                    == provenance.get("evaluator_version")):
                return cert
        return None


#: identity fields a certificate must agree on with the record provenance
CERTIFICATE_PROVENANCE_KEYS = MANDATORY_PROVENANCE_KEYS
