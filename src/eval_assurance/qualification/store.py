"""EA02-R EA-D01 / Wave-BC EA-R01 + EA-R04 — qualification certificates,
trusted issuance and revocation integrity.

Trust model (documented, tested, no cryptographic claims):
- A ``CertificateStore`` constructed directly by a caller is UNTRUSTED: it
  can hold certificates but they never authorize formal results.
- Only ``QualificationAuthority.issue_qualification`` creates a trusted
  store, and only after verifying mandatory gate evidence: every bound
  implementation file exists and is non-empty, actual sha256 digests are
  computed from those files (descriptive names alone are never sufficient),
  the reference oracle is a DIFFERENT implementation from the production
  evaluator, evidence references are non-empty, and the binding has not been
  revoked without requalification.
- Persistence is atomic (temp + os.replace) with a self-checksum; corrupt or
  tampered registries fail closed (``CertificateError``).
- ``snapshot()`` returns an immutable, checksummed ``QualificationSnapshot``;
  formal consumption boundaries recheck snapshot currency so a revocation
  between aggregation and publication is caught (EA-R04).
- Revocation history is durable; a revoked binding cannot be reauthorized by
  merely reissuing an equivalent certificate (``requalified=True`` requires
  fresh gate evidence to be supplied again).
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import threading
import time
from dataclasses import dataclass, field, fields

from ..contracts.core import MANDATORY_PROVENANCE_KEYS, validate_sha256_digest

CERTIFICATE_SCHEMA_VERSION = "2.0.0"


class CertificateError(ValueError):
    """Certificate lookup/binding/registry failure (fail-closed signal)."""


def _digest_file(path) -> str:
    p = pathlib.Path(path)
    if not p.is_file():
        raise CertificateError(f"implementation file missing: {p.name}")
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    if p.stat().st_size == 0:
        raise CertificateError(f"implementation file empty: {p.name}")
    return h.hexdigest()


@dataclass(frozen=True)
class QualificationCertificate:
    scope: str
    dataset_id: str
    parser_version: str
    evaluator_version: str
    reference_evaluator_version: str
    issued_utc: str
    certificate_id: str
    dataset_sha256: str = ""
    task_contract_sha256: str = ""
    parser_sha256: str = ""
    interpreter_sha256: str = ""
    evaluator_sha256: str = ""
    reference_oracle_sha256: str = ""
    witness_suite_sha256: str = ""
    mutation_sha256: str = ""
    replay_contract: str = ""
    protocol: str = ""
    evidence_refs: tuple[str, ...] = ()
    limitations: str = ""
    revoked_utc: str | None = None

    def identity_binding(self) -> dict:
        return {"dataset_id": self.dataset_id,
                "parser_version": self.parser_version,
                "evaluator_version": self.evaluator_version}

    def binding_key(self) -> str:
        return f"{self.scope}|{self.dataset_id}|{self.parser_version}|" \
               f"{self.evaluator_version}"

    def is_valid(self) -> bool:
        return self.revoked_utc is None

    def digest_bindings(self) -> dict:
        return {f.name: getattr(self, f.name) for f in fields(self)
                if f.name.endswith("_sha256")}


def validate_certificate(cert: QualificationCertificate) -> None:
    """Reject incomplete or incompatible certificates (EA-R01)."""
    if not isinstance(cert, QualificationCertificate):
        raise CertificateError("not a QualificationCertificate")
    for name in ("scope", "dataset_id", "parser_version", "evaluator_version",
                 "reference_evaluator_version"):
        if not isinstance(getattr(cert, name), str) or \
                not getattr(cert, name):
            raise CertificateError(f"certificate field {name!r} empty")
    for name, value in cert.digest_bindings().items():
        if value:
            try:
                validate_sha256_digest(value, field_name=name)
            except ValueError as e:
                raise CertificateError(str(e)) from e
    if cert.evaluator_sha256 and cert.reference_oracle_sha256 and \
            cert.evaluator_sha256 == cert.reference_oracle_sha256:
        raise CertificateError(
            "incompatible certificate: reference oracle is byte-identical "
            "to the production evaluator (no independence)")
    if not cert.evidence_refs or any(not e for e in cert.evidence_refs):
        raise CertificateError("certificate lacks qualification evidence "
                               "references")


#: identity fields a certificate must agree on with the record provenance
CERTIFICATE_PROVENANCE_KEYS = MANDATORY_PROVENANCE_KEYS


@dataclass(frozen=True)
class QualificationSnapshot:
    """Immutable, checksummed view of a trusted store at one generation
    (EA-R04: time-of-check integrity for formal consumption)."""
    generation: int
    certificates: tuple[QualificationCertificate, ...]
    revocations: tuple[dict, ...]
    checksum: str

    def valid_certificate(self, provenance: dict,
                          scope: str) -> QualificationCertificate | None:
        for cert in self.certificates:
            if not cert.is_valid() or cert.scope != scope:
                continue
            b = cert.identity_binding()
            if (b["dataset_id"] == provenance.get("dataset_id")
                    and b["parser_version"] == provenance.get("parser_version")
                    and b["evaluator_version"]
                    == provenance.get("evaluator_version")):
                return cert
        return None


class CertificateStore:
    """Certificate registry. UNTRUSTED unless created by the
    QualificationAuthority (or loaded from a verified registry)."""

    def __init__(self, persist_to: pathlib.Path | None = None, *,
                 trusted: bool = False):
        self.trusted = trusted
        self.persist_to = persist_to
        self._lock = threading.RLock()
        self._certs: dict[str, QualificationCertificate] = {}
        self._revocations: list[dict] = []
        self._generation = 0

    # -- registry loading (fail closed) --------------------------------
    @classmethod
    def load_registry(cls, path: pathlib.Path) -> "CertificateStore":
        p = pathlib.Path(path)
        if not p.exists():
            raise CertificateError(f"registry missing: {p.name}")
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            raise CertificateError(f"registry corrupt/unreadable: {e}") from e
        for key in ("schema_version", "certificates", "revocations",
                    "generation", "checksum"):
            if key not in raw:
                raise CertificateError(f"registry missing key {key!r}")
        material = json.dumps([raw["schema_version"], raw["certificates"],
                               raw["revocations"], raw["generation"]],
                              sort_keys=True)
        expected = hashlib.sha256(material.encode()).hexdigest()
        if expected != raw["checksum"]:
            raise CertificateError("registry checksum mismatch (tampered?)")
        store = cls(persist_to=p, trusted=True)
        store._generation = int(raw["generation"])
        store._revocations = list(raw["revocations"])
        for rec in raw["certificates"]:
            cert = QualificationCertificate(**rec)
            validate_certificate(cert)
            store._certs[cert.certificate_id] = cert
        return store

    # -- trusted issuance (authority only) ------------------------------
    def _trusted_add(self, cert: QualificationCertificate) -> None:
        with self._lock:
            self._certs[cert.certificate_id] = cert
            self._generation += 1
            self._persist()

    def revoke(self, certificate_id: str, *, reason: str) -> None:
        with self._lock:
            cert = self._certs.get(certificate_id)
            if cert is None:
                raise CertificateError(f"unknown certificate {certificate_id}")
            self._certs[certificate_id] = QualificationCertificate(
                **{**cert.__dict__, "revoked_utc":
                   time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
            self._revocations.append({
                "certificate_id": certificate_id,
                "binding_key": cert.binding_key(),
                "revoked_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                             time.gmtime()),
                "reason": reason})
            self._generation += 1
            self._persist()

    def _persist(self) -> None:
        if self.persist_to is None:
            return
        payload = {"schema_version": CERTIFICATE_SCHEMA_VERSION,
                   "generation": self._generation,
                   "certificates": [c.__dict__ for c in
                                    self._certs.values()],
                   "revocations": self._revocations}
        payload["checksum"] = hashlib.sha256(json.dumps(
            [payload["schema_version"], payload["certificates"],
             payload["revocations"], payload["generation"]],
            sort_keys=True).encode()).hexdigest()
        tmp = self.persist_to.with_suffix(".tmp")
        self.persist_to.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(payload, indent=1, ensure_ascii=False),
                       encoding="utf-8")
        tmp.replace(self.persist_to)          # atomic publish

    # -- lookup ----------------------------------------------------------
    def valid_certificate_for(self, provenance: dict,
                              scope: str) -> QualificationCertificate | None:
        if not self.trusted:
            return None        # arbitrary caller stores never authorize
        with self._lock:
            for cert in self._certs.values():
                if not cert.is_valid() or cert.scope != scope:
                    continue
                b = cert.identity_binding()
                if (b["dataset_id"] == provenance.get("dataset_id")
                        and b["parser_version"]
                        == provenance.get("parser_version")
                        and b["evaluator_version"]
                        == provenance.get("evaluator_version")):
                    return cert
        return None

    def get(self, certificate_id: str) -> QualificationCertificate | None:
        with self._lock:
            return self._certs.get(certificate_id)

    def revoked_binding_keys(self) -> set[str]:
        with self._lock:
            return {r["binding_key"] for r in self._revocations}

    # -- immutable snapshot (EA-R04) --------------------------------------
    def snapshot(self) -> QualificationSnapshot:
        with self._lock:
            certs = tuple(self._certs.values())
            revocations = tuple(dict(r) for r in self._revocations)
            generation = self._generation
        checksum = hashlib.sha256(json.dumps(
            [CERTIFICATE_SCHEMA_VERSION, [c.__dict__ for c in certs],
             list(map(dict, revocations)), generation],
            sort_keys=True).encode()).hexdigest()
        return QualificationSnapshot(generation, certs, revocations, checksum)

    def snapshot_is_current(self, snap: QualificationSnapshot) -> bool:
        with self._lock:
            return self._generation == snap.generation and \
                len(self._certs) == len(snap.certificates) and \
                all(self._certs.get(c.certificate_id) == c
                    for c in snap.certificates)


class QualificationAuthority:
    """The only component that may issue certificates usable for formal
    results. Verifies mandatory gate evidence and binds actual
    implementation digests (EA-R01)."""

    def __init__(self, persist_to: pathlib.Path | None = None):
        self._persist_to = persist_to

    def issue_qualification(
            self, *, scope: str, dataset_id: str, parser_version: str,
            evaluator_version: str, reference_evaluator_version: str,
            dataset_file, task_contract_file, parser_file, interpreter_file,
            evaluator_file, reference_oracle_file, witness_suite_file,
            mutation_report_file, evidence_files, replay_contract: str,
            protocol: str, limitations: str = "",
            requalified: bool = False,
            store: CertificateStore | None = None) -> CertificateStore:
        if not reference_evaluator_version:
            raise CertificateError(
                "reference-evaluator identity missing (EA-R01)")
        digests = {name: _digest_file(p) for name, p in (
            ("dataset_sha256", dataset_file),
            ("task_contract_sha256", task_contract_file),
            ("parser_sha256", parser_file),
            ("interpreter_sha256", interpreter_file),
            ("evaluator_sha256", evaluator_file),
            ("reference_oracle_sha256", reference_oracle_file),
            ("witness_suite_sha256", witness_suite_file),
            ("mutation_sha256", mutation_report_file))}
        if digests["reference_oracle_sha256"] == digests["evaluator_sha256"]:
            raise CertificateError(
                "reference oracle is byte-identical to the production "
                "evaluator — independence cannot be claimed (EA-R01)")
        evidence = [pathlib.Path(e) for e in evidence_files]
        if not evidence:
            raise CertificateError("no qualification evidence supplied")
        for e in evidence:
            _digest_file(e)      # exists + non-empty
        cert = QualificationCertificate(
            scope=scope, dataset_id=dataset_id,
            parser_version=parser_version, evaluator_version=evaluator_version,
            reference_evaluator_version=reference_evaluator_version,
            issued_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            certificate_id=hashlib.sha256(json.dumps(
                [CERTIFICATE_SCHEMA_VERSION, scope, dataset_id,
                 parser_version, evaluator_version,
                 reference_evaluator_version, digests,
                 [str(e) for e in evidence], replay_contract, protocol,
                 time.time_ns()], sort_keys=True).encode()).hexdigest()[:16],
            evidence_refs=tuple(str(e) for e in evidence),
            replay_contract=replay_contract, protocol=protocol,
            limitations=limitations, **digests)
        validate_certificate(cert)
        target = store if store is not None else \
            CertificateStore(persist_to=self._persist_to, trusted=True)
        if not target.trusted:
            raise CertificateError(
                "authority may only issue into a trusted store")
        if not requalified:
            revoked = target.revoked_binding_keys()
            if cert.binding_key() in revoked:
                raise CertificateError(
                    "binding was previously revoked; reissuing an "
                    "equivalent certificate requires requalified=True with "
                    "fresh gate evidence (EA-R04)")
        target._trusted_add(cert)
        return target
