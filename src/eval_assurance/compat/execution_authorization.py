"""ExecutionAuthorization contract — compat v1.1.0 (order section 5).

Separates PRE-DISPATCH execution authorization from POST-EXECUTION
publication authorization:

- ``ExecutionAuthorization`` (this module) is required BEFORE physical
  GPU dispatch. It binds the qualification evidence chain (scope,
  digests, certificates, shared-core acceptance, canary/circuit-breaker
  readiness, revocation state, dispatch limits) and NEVER depends on
  results of the experiment being authorized: no AggregationReport, no
  accuracy, no completed model benchmark. The first physical experiment
  is therefore authorizable without completed model results.
- ``RunnerAuthorization`` (``compat.authorization``, schema 1.0.0) stays
  the PUBLICATION-side contract: it consumes a qualified
  ``AggregationReport`` and is not a pre-dispatch requirement.

Consumer integration (IJ-NANO PR #11 ``EAEExecutionAuthorizationProvider``):
the consumer imports THIS module at a PINNED IJEVAL git revision and calls
``issue_execution_authorization(...)`` with the keyword signature below;
the returned object carries ``qualifying_class == "EAE"`` and a
``checksum_valid()`` method, which the consumer's DispatchGate verifies
before physical dispatch (test doubles are structurally rejected there).

Fail-closed: with no registered evidence the module raises
``AuthorizationError`` — no fabricated evidence, no hand-edited status.

Trust model (documented, not implied): checksums bind fields against
accidental drift and in-process mutation; they are NOT a defense against
a hostile process with code execution (which could recompute them).
Revocation is an explicit registry re-checked at issue time and at every
consumer recheck. Single-user OS: no OS-level sandbox is claimed.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

EXECUTION_AUTHORIZATION_SCHEMA = "1.1.0"
EAE_CONTRACT_REVISION = "1.1.0"          # semantic revision of this module
AUTH_LEVELS = ("AUTH-1", "AUTH-2", "AUTH-3")
#: AUTH-2 is the only level that may touch protected confirmation
#: execution; AUTH-1 covers development-scope dispatch, AUTH-3 covers
#: scoped subordinate re-authorization (never wider than its parent).
CONFIRMATION_LEVEL = "AUTH-2"


class AuthorizationError(RuntimeError):
    """Fail-closed refusal (never silently downgraded)."""


@dataclass(frozen=True)
class ExecutionEvidence:
    """The qualification evidence an ExecutionAuthorization binds to.

    Registered by the qualification pipeline (EA03-EA18) once the
    applicable shared-core, scope and protection evidence exists. The
    evidence contains NO model accuracy and NO experiment results —
    by construction it cannot encode a results dependency.
    """
    compat_revision: str                 # EAE revision this evidence was
    #                                       produced at (git rev)
    primitives: tuple[str, ...]          # qualified cognitive scope
    protocols: tuple[str, ...]           # qualified protocol scope
    models: tuple[str, ...]              # applicable runtime identities
    dataset_digest: str                  # pinned public dataset digest
    roster_digest: str                   # frozen trial roster digest
    evaluator_identity: str              # reference oracle digest/identity
    certificate_refs: tuple[str, ...]    # active qualification certificates
    certificate_digests: tuple[tuple[str, str], ...]
    shared_core_acceptance: str          # NOT_STARTED | PARTIAL | ACCEPTED
    shared_core_evidence_digest: str
    ea13_scope_evidence: str             # digest or "" when not applicable
    ea18_scope_evidence: str             # digest or "" when not applicable
    canary_ready: bool
    circuit_breaker_ready: bool
    confirmation_execution: bool = False  # protected confirmation covered?
    dispatch_limits: dict = field(default_factory=dict)  # e.g. max_trials

    def validate(self) -> None:
        if self.shared_core_acceptance != "ACCEPTED":
            raise AuthorizationError(
                "shared-core qualification missing (status "
                f"{self.shared_core_acceptance!r}); physical dispatch "
                "refused")
        if not self.canary_ready or not self.circuit_breaker_ready:
            raise AuthorizationError(
                "canary/circuit-breaker readiness missing; physical "
                "dispatch refused")
        if not self.certificate_refs:
            raise AuthorizationError(
                "empty certificate collection; physical dispatch refused")


class RevocationRegistry:
    """Explicit revocation state, re-checked at issue and at recheck."""

    def __init__(self):
        self._revoked: set[str] = set()

    def revoke(self, ref: str) -> None:
        self._revoked.add(ref)

    def is_revoked(self, ref: str) -> bool:
        return ref in self._revoked

    def check(self, refs) -> None:
        hit = sorted(r for r in refs if self.is_revoked(r))
        if hit:
            raise AuthorizationError(
                f"qualification revoked: {hit}; authorization refused")


#: module-level evidence registry (fail-closed default: EMPTY)
_REGISTERED_EVIDENCE: ExecutionEvidence | None = None
#: module-level revocation registry shared with the qualification pipeline
REVOCATIONS = RevocationRegistry()
#: certificate references the qualification authority marked trusted
TRUSTED_CERTIFICATE_REFS: frozenset = frozenset()


def register_execution_evidence(evidence: ExecutionEvidence,
                                trusted_certificate_refs=()) -> None:
    """Qualification-pipeline entry point: publish the evidence chain."""
    global _REGISTERED_EVIDENCE, TRUSTED_CERTIFICATE_REFS
    if not isinstance(evidence, ExecutionEvidence):
        raise AuthorizationError(
            "evidence must be an ExecutionEvidence produced by the "
            "qualification pipeline; arbitrary payloads (e.g. fabricated "
            "aggregation reports) register nothing")
    evidence.validate()
    _REGISTERED_EVIDENCE = evidence
    TRUSTED_CERTIFICATE_REFS = frozenset(trusted_certificate_refs)


def clear_execution_evidence() -> None:
    """Test/rotation hook — removes the registered evidence (fail-closed
    again until re-registered)."""
    global _REGISTERED_EVIDENCE, TRUSTED_CERTIFICATE_REFS
    _REGISTERED_EVIDENCE = None
    TRUSTED_CERTIFICATE_REFS = frozenset()


def registered_evidence() -> ExecutionEvidence | None:
    return _REGISTERED_EVIDENCE


@dataclass(frozen=True, init=False)
class ExecutionAuthorization:
    """Pre-dispatch authorization object (schema 1.1.0)."""
    _create_key: object
    schema: str
    experiment_id: str
    auth_level: str
    scope: dict                         # primitives/protocols/models lists
    dataset_digest: str
    roster_digest: str
    eae_revision: str
    certificate_ref: str                # primary certificate
    issued_by: str
    qualifying_class: str               # always "EAE" from this module
    payload: dict                       # bound evidence summary + limits
    checksum: str = ""

    def __init__(self, _create_key=None, **kw):
        if _create_key is not _EXECUTION_CREATE_KEY:
            raise PermissionError(
                "ExecutionAuthorization cannot be constructed directly; "
                "use issue_execution_authorization()")
        for f in ("schema", "experiment_id", "auth_level", "dataset_digest",
                  "roster_digest", "eae_revision", "certificate_ref",
                  "issued_by", "qualifying_class"):
            object.__setattr__(self, f, kw[f])
        object.__setattr__(self, "scope", dict(kw["scope"]))
        object.__setattr__(self, "payload", dict(kw["payload"]))
        object.__setattr__(self, "checksum", kw.get("checksum", ""))

    def canonical_material(self) -> str:
        return json.dumps(
            [self.schema, self.experiment_id, self.auth_level,
             self.scope, self.dataset_digest, self.roster_digest,
             self.eae_revision, self.certificate_ref, self.issued_by,
             self.qualifying_class, self.payload],
            sort_keys=True, ensure_ascii=False, default=str)

    def compute_checksum(self) -> str:
        return hashlib.sha256(
            self.canonical_material().encode("utf-8")).hexdigest()

    def with_checksum(self) -> "ExecutionAuthorization":
        return ExecutionAuthorization(
            _EXECUTION_CREATE_KEY, schema=self.schema,
            experiment_id=self.experiment_id, auth_level=self.auth_level,
            scope=self.scope, dataset_digest=self.dataset_digest,
            roster_digest=self.roster_digest, eae_revision=self.eae_revision,
            certificate_ref=self.certificate_ref, issued_by=self.issued_by,
            qualifying_class=self.qualifying_class, payload=self.payload,
            checksum=self.compute_checksum())

    def checksum_valid(self) -> bool:
        return bool(self.checksum) and \
            self.checksum == self.compute_checksum()

    def to_json(self) -> str:
        return json.dumps({
            "schema": self.schema, "experiment_id": self.experiment_id,
            "auth_level": self.auth_level, "scope": self.scope,
            "dataset_digest": self.dataset_digest,
            "roster_digest": self.roster_digest,
            "eae_revision": self.eae_revision,
            "certificate_ref": self.certificate_ref,
            "issued_by": self.issued_by,
            "qualifying_class": self.qualifying_class,
            "payload": self.payload, "checksum": self.checksum,
        }, indent=1, sort_keys=True, ensure_ascii=False)


_EXECUTION_CREATE_KEY = object()

_ISSUER = "eval_assurance.compat.execution_authorization"


def issue_execution_authorization(
        experiment_id: str, dataset_digest: str, roster_digest: str,
        primitives: list[str], protocols: list[str], models: list[str],
        auth_level: str, eae_revision: str,
        confirmation_execution: bool = False) -> ExecutionAuthorization:
    """Consumer-facing factory (exact signature the pinned IJ-NANO
    provider calls). Fail-closed on every control below."""
    ev = _REGISTERED_EVIDENCE
    if ev is None:
        raise AuthorizationError(
            "fail-closed: no ExecutionEvidence registered; physical "
            "dispatch refused (shared-core/scope evidence not published)")
    if auth_level not in AUTH_LEVELS:
        raise AuthorizationError(f"unknown authorization level {auth_level!r}")
    if eae_revision != ev.compat_revision:
        raise AuthorizationError(
            f"EAE revision mismatch: request {eae_revision} != evidence "
            f"{ev.compat_revision}")
    if dataset_digest != ev.dataset_digest:
        raise AuthorizationError(
            "dataset digest mismatch (modified dataset refused)")
    if roster_digest != ev.roster_digest:
        raise AuthorizationError(
            "roster digest mismatch (modified planned roster refused)")
    missing_prims = sorted(set(primitives) - set(ev.primitives))
    if missing_prims:
        raise AuthorizationError(
            f"cognitive scope not qualified: {missing_prims}")
    missing_protos = sorted(set(protocols) - set(ev.protocols))
    if missing_protos:
        raise AuthorizationError(
            f"protocol scope not qualified: {missing_protos}")
    missing_models = sorted(set(models) - set(ev.models))
    if missing_models:
        raise AuthorizationError(
            f"model/runtime identity not covered: {missing_models}")
    if confirmation_execution:
        if auth_level != CONFIRMATION_LEVEL:
            raise AuthorizationError(
                "protected confirmation execution requires "
                f"{CONFIRMATION_LEVEL}; {auth_level} refused")
        if not ev.confirmation_execution:
            raise AuthorizationError(
                "protected confirmation execution is not covered by the "
                "registered evidence")
    untrusted = sorted(set(ev.certificate_refs) - TRUSTED_CERTIFICATE_REFS)
    if untrusted:
        raise AuthorizationError(
            f"untrusted certificate store entries: {untrusted}")
    if not ev.certificate_refs:
        raise AuthorizationError("empty certificate collection")
    REVOCATIONS.check(ev.certificate_refs)
    ev.validate()
    auth = ExecutionAuthorization(
        _EXECUTION_CREATE_KEY,
        schema=EXECUTION_AUTHORIZATION_SCHEMA,
        experiment_id=experiment_id,
        auth_level=auth_level,
        scope={"primitives": sorted(primitives),
               "protocols": sorted(protocols),
               "models": sorted(models)},
        dataset_digest=dataset_digest,
        roster_digest=roster_digest,
        eae_revision=eae_revision,
        certificate_ref=ev.certificate_refs[0],
        issued_by=_ISSUER,
        qualifying_class="EAE",
        payload={
            "certificates": list(ev.certificate_refs),
            "certificate_digests": [list(d) for d in
                                    ev.certificate_digests],
            "evaluator_identity": ev.evaluator_identity,
            "shared_core_acceptance": ev.shared_core_acceptance,
            "shared_core_evidence_digest": ev.shared_core_evidence_digest,
            "ea13_scope_evidence": ev.ea13_scope_evidence,
            "ea18_scope_evidence": ev.ea18_scope_evidence,
            "canary_ready": ev.canary_ready,
            "circuit_breaker_ready": ev.circuit_breaker_ready,
            "confirmation_execution": confirmation_execution,
            "dispatch_limits": dict(ev.dispatch_limits),
            "results_dependency": "none",   # no model results involved
        })
    return auth.with_checksum()


def recheck_execution_authorization(auth: ExecutionAuthorization) -> None:
    """Time-of-check integrity: revocation after issuance fails closed."""
    if not auth.checksum_valid():
        raise AuthorizationError("authorization checksum drifted")
    REVOCATIONS.check([auth.certificate_ref]
                      + list(auth.payload.get("certificates", [])))
    ev = _REGISTERED_EVIDENCE
    if ev is None or auth.eae_revision != ev.compat_revision:
        raise AuthorizationError(
            "registered evidence no longer covers this authorization "
            "(stale authorization refused)")
