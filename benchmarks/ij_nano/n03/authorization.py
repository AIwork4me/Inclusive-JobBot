"""N03-B4 executable authorization controller (IJ-NANO-1.3S order
sections 5-6).

Fail-closed by construction:
- Physical GPU dispatch requires an ExecutionAuthorization whose
  ``qualifying_class`` is "EAE", whose checksum verifies, and whose scope
  matches the run request exactly (dataset digest, roster digest, EAE
  revision, primitives, protocols, models).
- Test doubles carry ``qualifying_class == "TEST_DOUBLE"`` and are
  STRUCTURALLY unable to authorize physical execution: the physical gate
  rejects that class unconditionally (they remain usable for AUTH-0
  software tests through the synthetic gate only).
- The real provider consumes the EAE lane's versioned ExecutionAuthorization
  contract through a PINNED git revision. Until that contract is published
  and qualified, ``issue_execution_authorization`` raises - no fabricated
  AggregationReport, no dummy qualified counts, no hand-edited JSON status
  is ever consulted. (The published ``authorize_runner()`` is
  PublicationAuthorization-side; it is NOT a pre-dispatch requirement -
  see order section 6.)
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field


class AuthorizationError(RuntimeError):
    """Fail-closed refusal (never silently downgraded)."""


@dataclass(frozen=True)
class RunRequest:
    experiment_id: str
    dataset_digest: str
    roster_digest: str
    primitives: frozenset
    protocols: frozenset
    models: frozenset
    eae_revision: str
    auth_level: str                    # AUTH-1 / AUTH-2 / AUTH-3


@dataclass(frozen=True)
class ExecutionAuthorization:
    scope: dict                        # primitives/protocols/models lists
    dataset_digest: str
    roster_digest: str
    eae_revision: str
    certificate_ref: str
    auth_level: str
    issued_by: str                     # provider identity
    qualifying_class: str              # "EAE" | "TEST_DOUBLE"
    payload: dict = field(default_factory=dict)
    checksum: str = ""

    def compute_checksum(self) -> str:
        material = json.dumps(
            [self.scope, self.dataset_digest, self.roster_digest,
             self.eae_revision, self.certificate_ref, self.auth_level,
             self.issued_by, self.qualifying_class, self.payload],
            sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def with_checksum(self) -> "ExecutionAuthorization":
        return ExecutionAuthorization(**{**self.__dict__,
                                         "checksum": self.compute_checksum()})

    def checksum_valid(self) -> bool:
        return bool(self.checksum) and \
            self.checksum == self.compute_checksum()


class EAEExecutionAuthorizationProvider:
    """Consumes the EAE lane's ExecutionAuthorization contract at a PINNED
    revision. The IJEVAL lane owns the Execution/Publication separation
    (order section 6); this side never fabricates one."""

    def __init__(self, pinned_revision: str, contract_module: str):
        if not pinned_revision or not contract_module:
            raise AuthorizationError(
                "pinned EAE revision and contract module are mandatory")
        self.pinned_revision = pinned_revision
        self.contract_module = contract_module
        self._revoked: set[str] = set()

    def issue_execution_authorization(
            self, request: RunRequest) -> ExecutionAuthorization:
        if request.eae_revision != self.pinned_revision:
            raise AuthorizationError(
                f"EAE revision mismatch: request {request.eae_revision} "
                f"!= pinned {self.pinned_revision} (stale/foreign "
                f"revision refused)")
        try:
            import importlib
            mod = importlib.import_module(self.contract_module)
        except ImportError as e:
            raise AuthorizationError(
                "fail-closed: the pinned EAE ExecutionAuthorization "
                "contract is not available in this environment "
                f"({e}); physical dispatch is refused until the real "
                "contract is published and qualified") from e
        if not hasattr(mod, "issue_execution_authorization"):
            raise AuthorizationError(
                "pinned contract does not expose "
                "issue_execution_authorization (ExecutionAuthorization); "
                "refusing to substitute any publication-side API")
        auth = mod.issue_execution_authorization(
            experiment_id=request.experiment_id,
            dataset_digest=request.dataset_digest,
            roster_digest=request.roster_digest,
            primitives=sorted(request.primitives),
            protocols=sorted(request.protocols),
            models=sorted(request.models),
            auth_level=request.auth_level,
            eae_revision=self.pinned_revision)
        if auth.qualifying_class != "EAE" or not auth.checksum_valid():
            raise AuthorizationError(
                "EAE provider returned an invalid authorization")
        if auth.certificate_ref in self._revoked:
            raise AuthorizationError(
                f"qualification {auth.certificate_ref} was revoked before "
                "dispatch")
        return auth

    def revoke(self, certificate_ref: str) -> None:
        self._revoked.add(certificate_ref)

    def recheck(self, auth: ExecutionAuthorization) -> None:
        """Pre-dispatch recheck (order section 7: revocation after
        authorization)."""
        if auth.certificate_ref in self._revoked:
            raise AuthorizationError(
                f"qualification {auth.certificate_ref} revoked after "
                "authorization (time-of-check integrity)")
        if not auth.checksum_valid():
            raise AuthorizationError("authorization checksum drifted")


class SyntheticExecutionAuthorizationProvider:
    """TEST DOUBLE - AUTH-0 software testing only. Structurally unable to
    authorize physical execution: every authorization it issues carries
    qualifying_class='TEST_DOUBLE', which the physical gate rejects
    unconditionally."""

    provider_identity = "synthetic-test-double"

    def issue_execution_authorization(
            self, request: RunRequest) -> ExecutionAuthorization:
        auth = ExecutionAuthorization(
            scope={"primitives": sorted(request.primitives),
                   "protocols": sorted(request.protocols),
                   "models": sorted(request.models)},
            dataset_digest=request.dataset_digest,
            roster_digest=request.roster_digest,
            eae_revision=request.eae_revision,
            certificate_ref="SYNTH-CERT-SOFTWARE-ONLY",
            auth_level=request.auth_level,
            issued_by=self.provider_identity,
            qualifying_class="TEST_DOUBLE",
            payload={"note": "never valid for physical execution"})
        return auth.with_checksum()

    def revoke(self, certificate_ref: str) -> None:      # no-op double
        pass

    def recheck(self, auth: ExecutionAuthorization) -> None:
        if not auth.checksum_valid():
            raise AuthorizationError("authorization checksum drifted")


def validate_against(auth: ExecutionAuthorization,
                     request: RunRequest) -> None:
    """Scope/digest/level validation of an existing authorization against
    a concrete run request (used before and after issuance, and at every
    resume)."""
    if not auth.checksum_valid():
        raise AuthorizationError("authorization checksum invalid")
    s = auth.scope
    def _missing(granted, wanted):
        return sorted(set(wanted) - set(granted))
    if _missing(s.get("primitives", []), request.primitives):
        raise AuthorizationError(
            "authorization scope excludes primitives "
            f"{_missing(s.get('primitives', []), request.primitives)}")
    if _missing(s.get("protocols", []), request.protocols):
        raise AuthorizationError(
            "authorization scope excludes protocols "
            f"{_missing(s.get('protocols', []), request.protocols)}")
    if _missing(s.get("models", []), request.models):
        raise AuthorizationError(
            "authorization scope excludes models "
            f"{_missing(s.get('models', []), request.models)}")
    if auth.dataset_digest != request.dataset_digest:
        raise AuthorizationError(
            "dataset digest mismatch (modified dataset refused)")
    if auth.roster_digest != request.roster_digest:
        raise AuthorizationError(
            "roster digest mismatch (modified roster refused)")
    if auth.eae_revision != request.eae_revision:
        raise AuthorizationError(
            "EAE revision drifted since authorization (stale revision "
            "refused)")
    if auth.auth_level != request.auth_level:
        raise AuthorizationError(
            f"authorization level {auth.auth_level} does not cover "
            f"requested {request.auth_level}")


class DispatchGate:
    """The physical/synthetic dispatch boundary."""

    def __init__(self, provider):
        self.provider = provider

    def authorize_physical(self, request: RunRequest,
                           provider=None) -> ExecutionAuthorization:
        prov = provider or self.provider
        auth = prov.issue_execution_authorization(request)
        if auth.qualifying_class != "EAE":
            raise AuthorizationError(
                f"PHYSICAL dispatch refused: authorization "
                f"qualifying_class={auth.qualifying_class!r} (test doubles "
                "structurally cannot authorize physical execution)")
        prov.recheck(auth)
        return auth

    def authorize_synthetic(self, request: RunRequest,
                            provider=None) -> ExecutionAuthorization:
        prov = provider or self.provider
        auth = prov.issue_execution_authorization(request)
        if auth.qualifying_class not in ("EAE", "TEST_DOUBLE"):
            raise AuthorizationError("unknown qualifying class")
        prov.recheck(auth)
        return auth
