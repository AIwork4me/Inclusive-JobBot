"""Order section 3.2 — the authoritative qualification state.

Single durable source of truth consulted before EVERY affected dispatch:

- binds the persisted ``CertificateStore`` (trusted-issuance registry)
  to a durable, checksummed revocation + evidence-generation file;
- revocation is durable across process restarts and atomic on write;
- evidence replacement bumps the evidence generation/identity, so
  authorizations issued against the replaced evidence go STALE and are
  refused at recheck (no stale-authorization survival);
- a certificate reissued after revocation without fresh gate evidence
  is refused by the authority (``requalified=True`` demands new
  evidence), and the binding stays in the revocation history;
- ``consult(...)`` is the pre-dispatch check the physical dispatcher
  must call; ``execution_authorization.recheck_execution_authorization``
  consults this state whenever one is bound (module hook), so consumer
  rechecks do not rely solely on a local revocation set.

Trust model: durable files are checksummed against accidental drift
(corruption/tampering fails closed). No defense against a hostile
process with code execution is claimed.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import threading
import time

from .compat.execution_authorization import AuthorizationError
from .qualification.store import CertificateError, CertificateStore

STATE_SCHEMA = "1.0.0"


class AuthoritativeStateError(AuthorizationError):
    """Fail-closed authoritative-state refusal (corrupt file, stale
    authorization, revoked or non-current qualification). Subclasses
    AuthorizationError so consumers see one refusal family."""


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class AuthoritativeQualificationState:
    """Durable qualification state: certificates + revocations + the
    currently-registered execution evidence generation."""

    def __init__(self, store: CertificateStore,
                 state_file: pathlib.Path):
        if not isinstance(store, CertificateStore) or not store.trusted:
            raise AuthoritativeStateError(
                "authoritative state requires a TRUSTED certificate "
                "store (arbitrary caller stores never authorize)")
        self._lock = threading.RLock()
        self.store = store
        self.state_file = pathlib.Path(state_file)
        self._revocations: list[dict] = []
        self._evidence_generation = 0
        self._evidence_identity = ""
        if self.state_file.exists():
            self._load()               # restart-safe: durable state wins

    # -- persistence ---------------------------------------------------------
    def _checksum(self, payload: dict) -> str:
        return hashlib.sha256(json.dumps(
            [STATE_SCHEMA, payload["revocations"],
             payload["evidence_generation"], payload["evidence_identity"]],
            sort_keys=True).encode()).hexdigest()

    def _save(self) -> None:
        payload = {"schema": STATE_SCHEMA,
                   "revocations": self._revocations,
                   "evidence_generation": self._evidence_generation,
                   "evidence_identity": self._evidence_identity}
        payload["checksum"] = self._checksum(payload)
        tmp = self.state_file.with_suffix(".tmp")
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(payload, indent=1, ensure_ascii=False),
                       encoding="utf-8")
        tmp.replace(self.state_file)            # atomic publish

    def _load(self) -> None:
        try:
            raw = json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            raise AuthoritativeStateError(
                f"authoritative state unreadable: {e}") from e
        for key in ("schema", "revocations", "evidence_generation",
                    "evidence_identity", "checksum"):
            if key not in raw:
                raise AuthoritativeStateError(
                    f"authoritative state missing key {key!r}")
        if raw["schema"] != STATE_SCHEMA or \
                self._checksum(raw) != raw["checksum"]:
            raise AuthoritativeStateError(
                "authoritative state checksum mismatch (tampered?)")
        self._revocations = list(raw["revocations"])
        self._evidence_generation = int(raw["evidence_generation"])
        self._evidence_identity = str(raw["evidence_identity"])

    # -- revocation ------------------------------------------------------------
    def revoke(self, certificate_id: str, *, reason: str) -> None:
        """Durable revocation: certificate store + this state + evidence
        invalidation in one step. Survives restart; an authorization in
        the field goes stale immediately."""
        with self._lock:
            self.store.revoke(certificate_id, reason=reason)
            self._revocations.append({
                "certificate_id": certificate_id,
                "revoked_utc": _now(), "reason": reason})
            self._evidence_generation += 1   # evidence invalidated
            self._save()

    def is_revoked(self, certificate_id: str) -> bool:
        with self._lock:
            if any(r["certificate_id"] == certificate_id
                   for r in self._revocations):
                return True
            cert = self.store.get(certificate_id)
            return cert is not None and not cert.is_valid()

    # -- evidence currency -------------------------------------------------------
    def register_evidence_identity(self, identity: str) -> int:
        """Record a NEW evidence registration (replacement). Returns the
        new generation; authorizations bound to the old identity are
        stale from this point."""
        with self._lock:
            if identity != self._evidence_identity:
                self._evidence_generation += 1
                self._evidence_identity = identity
                self._save()
            return self._evidence_generation

    @property
    def evidence_identity(self) -> str:
        with self._lock:
            return self._evidence_identity

    # -- the pre-dispatch consult ---------------------------------------------------
    def consult(self, *, certificate_refs, evidence_identity: str = "",
                require_generation: int | None = None) -> None:
        """THE authoritative pre-dispatch check: every affected
        certificate must be currently valid in the trusted store, not
        durably revoked, and the requesting authorization's evidence
        identity must still be the current one (no stale survival)."""
        with self._lock:
            for ref in certificate_refs or ():
                cert = self.store.get(ref)
                if cert is None:
                    raise AuthoritativeStateError(
                        f"certificate {ref!r} unknown to the "
                        "authoritative state (never issued here)")
                if not cert.is_valid() or self.is_revoked(ref):
                    raise AuthoritativeStateError(
                        f"qualification {ref!r} revoked; dispatch "
                        "refused (authoritative state)")
            if evidence_identity and \
                    evidence_identity != self._evidence_identity:
                raise AuthoritativeStateError(
                    "stale authorization: the registered execution "
                    "evidence was replaced after issuance (evidence "
                    "identity mismatch)")
            if require_generation is not None and \
                    require_generation != self._evidence_generation:
                raise AuthoritativeStateError(
                    "stale authorization: evidence generation "
                    f"{require_generation} != current "
                    f"{self._evidence_generation}")


def reissue_without_requalification_is_refused(
        authority, store: CertificateStore, **issue_kwargs) -> None:
    """Order section 3.2 scenario probe: reissuing an equivalent
    certificate after revocation MUST fail without
    ``requalified=True`` + fresh gate evidence (delegated to the
    QualificationAuthority, asserted here for the campaign)."""
    try:
        authority.issue_qualification(store=store, **issue_kwargs)
    except CertificateError:
        return
    raise AuthoritativeStateError(
        "authority permitted reissue without requalification")
