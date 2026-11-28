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
#: semantic revision of this module. 1.1.1 (2026-11-28) corrects the
#: authorization-level semantics to the frozen IJ-NANO-1.3S contract
#: (AUTH-0 CPU preparation / AUTH-1 diagnostic smoke / AUTH-2 scoped
#: development benchmark / AUTH-3 scoped confirmation benchmark):
#: CONFIRMATION_LEVEL was wrongly "AUTH-2" at <=9c73bbf, letting AUTH-2
#: authorize protected confirmation execution (reproduction:
#: evidence/IJEVAL/COMPAT/auth_semantics_mismatch_9c73bbf.json).
EAE_CONTRACT_REVISION = "1.1.1"
AUTH_LEVELS = ("AUTH-1", "AUTH-2", "AUTH-3")
#: Only AUTH-3 (SCOPED_CONFIRMATION_BENCHMARK) may touch protected
#: confirmation execution. AUTH-1 and AUTH-2 are development-side levels
#: and can NEVER access it (enforced symmetrically below: AUTH-3 also
#: REQUIRES confirmation execution — it is the confirmation benchmark
#: level, and sub-confirmation levels require a development-split roster).
CONFIRMATION_LEVEL = "AUTH-3"
ROSTER_SPLITS = ("development", "confirmation")


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
    roster_split: str = "development"     # development | confirmation
    dispatch_limits: dict = field(default_factory=dict)  # e.g. max_trials
    experiment_id: str = ""               # exact experiment binding (§3.3)
    auth_purpose: str = ""                # the AUTH level this evidence
    #                                          authorizes (§3.3)

    def evidence_identity(self) -> str:
        """Content digest over the bound qualification chain — changes
        whenever ANY bound field changes (used for stale-authorization
        detection after evidence replacement, §3.2)."""
        import hashlib
        material = json.dumps([
            self.compat_revision, sorted(self.primitives),
            sorted(self.protocols), sorted(self.models),
            self.dataset_digest, self.roster_digest,
            self.evaluator_identity, sorted(self.certificate_refs),
            [list(d) for d in self.certificate_digests],
            self.shared_core_acceptance, self.shared_core_evidence_digest,
            self.ea13_scope_evidence, self.ea18_scope_evidence,
            self.canary_ready, self.circuit_breaker_ready,
            self.confirmation_execution, self.roster_split,
            self.dispatch_limits, self.experiment_id, self.auth_purpose],
            sort_keys=True, default=str)
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

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
        if self.roster_split not in ROSTER_SPLITS:
            raise AuthorizationError(
                f"unknown roster split {self.roster_split!r} "
                f"(expected one of {ROSTER_SPLITS})")
        if self.confirmation_execution != (
                self.roster_split == "confirmation"):
            raise AuthorizationError(
                "roster-split mismatch: protected confirmation execution "
                "is exactly the confirmation split (confirmation_execution="
                f"{self.confirmation_execution!r}, roster_split="
                f"{self.roster_split!r}); fail-closed")


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
#: authoritative qualification state hook (§3.2): when bound, issuance
#: and every recheck consult the durable state — a consumer recheck then
#: never relies solely on a local revocation set
_AUTHORITATIVE_STATE = None


def bind_authoritative_state(state) -> None:
    """Bind the durable AuthoritativeQualificationState (order §3.2).
    Rechecks consult it from this point; an unbound state keeps the
    module-local registry (tests / synthetic use)."""
    global _AUTHORITATIVE_STATE
    if state is not None and not hasattr(state, "consult"):
        raise AuthorizationError(
            "authoritative state must expose consult(...) "
            "(AuthoritativeQualificationState)")
    _AUTHORITATIVE_STATE = state


def authoritative_state():
    return _AUTHORITATIVE_STATE


def register_execution_evidence(evidence: ExecutionEvidence,
                                trusted_certificate_refs=(),
                                authoritative_state=None) -> None:
    """Qualification-pipeline entry point: publish the evidence chain.

    The caller-asserted form remains for the qualification pipeline's
    own tests; PRODUCTION registration goes through
    ``register_trusted_execution_evidence`` (order §3.3), which derives
    every readiness flag from digest-verified artifacts instead of
    caller Booleans. Binding an authoritative state records the new
    evidence identity so previously issued authorizations go stale."""
    global _REGISTERED_EVIDENCE, TRUSTED_CERTIFICATE_REFS
    global _AUTHORITATIVE_STATE
    if not isinstance(evidence, ExecutionEvidence):
        raise AuthorizationError(
            "evidence must be an ExecutionEvidence produced by the "
            "qualification pipeline; arbitrary payloads (e.g. fabricated "
            "aggregation reports) register nothing")
    evidence.validate()
    _REGISTERED_EVIDENCE = evidence
    TRUSTED_CERTIFICATE_REFS = frozenset(trusted_certificate_refs)
    if authoritative_state is not None:
        bind_authoritative_state(authoritative_state)
    if _AUTHORITATIVE_STATE is not None:
        _AUTHORITATIVE_STATE.register_evidence_identity(
            evidence.evidence_identity())


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
                f"{CONFIRMATION_LEVEL} (SCOPED_CONFIRMATION_BENCHMARK); "
                f"{auth_level} refused — AUTH-1/AUTH-2 can never access "
                "protected confirmation execution")
        if not ev.confirmation_execution:
            raise AuthorizationError(
                "protected confirmation execution is not covered by the "
                "registered evidence")
    elif auth_level == CONFIRMATION_LEVEL:
        # symmetric: AUTH-3 IS the scoped confirmation benchmark level;
        # issuing it for a development dispatch would be a contract
        # mismatch (AUTH-3 requires the confirmation roster + evidence)
        raise AuthorizationError(
            f"{CONFIRMATION_LEVEL} is the scoped confirmation benchmark "
            "level: it requires confirmation_execution coverage of a "
            "confirmation-split roster (development dispatches use "
            "AUTH-1/AUTH-2)")
    elif ev.roster_split == "confirmation":
        # sub-confirmation levels must sit on development-split evidence:
        # confirmation-covering evidence cannot back a development-level
        # dispatch either (roster split enforced at the authorization
        # boundary, complementing the exact roster_digest binding)
        raise AuthorizationError(
            "confirmation-split evidence cannot authorize a "
            f"development-level ({auth_level}) dispatch; roster split "
            "enforcement refused")
    untrusted = sorted(set(ev.certificate_refs) - TRUSTED_CERTIFICATE_REFS)
    if untrusted:
        raise AuthorizationError(
            f"untrusted certificate store entries: {untrusted}")
    if not ev.certificate_refs:
        raise AuthorizationError("empty certificate collection")
    # §3.3: bind execution authorization to the EXACT experiment
    # identity and authorization purpose
    if ev.experiment_id and ev.experiment_id != experiment_id:
        raise AuthorizationError(
            f"evidence is bound to experiment {ev.experiment_id!r}; "
            f"authorization for {experiment_id!r} refused (experiment "
            "identity binding)")
    if ev.auth_purpose and ev.auth_purpose != auth_level:
        raise AuthorizationError(
            f"evidence authorizes purpose {ev.auth_purpose!r}; "
            f"authorization at {auth_level!r} refused (purpose binding)")
    REVOCATIONS.check(ev.certificate_refs)
    if _AUTHORITATIVE_STATE is not None:
        _AUTHORITATIVE_STATE.consult(
            certificate_refs=ev.certificate_refs,
            evidence_identity=ev.evidence_identity())
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
            "roster_split": ev.roster_split,
            "evidence_identity": ev.evidence_identity(),
            "experiment_binding": ev.experiment_id or "(any)",
            "auth_purpose": ev.auth_purpose or "(any)",
            "dispatch_limits": dict(ev.dispatch_limits),
            "results_dependency": "none",   # no model results involved
        })
    return auth.with_checksum()


def register_trusted_execution_evidence(
        *, authoritative_state, experiment_id: str, auth_purpose: str,
        primitives, protocols, models,
        dataset_file, roster_file,
        parser_file, evaluator_file, interpreter_file, oracle_file,
        certificate_store, shared_core_acceptance_file,
        canary_evidence_file, breaker_evidence_file,
        witness_suite_file, mutation_report_file,
        ea13_scope_file=None, ea18_scope_file=None,
        dispatch_limits=None) -> ExecutionEvidence:
    """Order §3.3 — evidence-BACKED readiness (replaces caller-asserted
    readiness). Every readiness flag and identity below is DERIVED from
    digest-verified artifacts and the authoritative certificate store;
    caller-provided ACCEPTED strings or readiness Booleans are never
    consulted. Fail-closed on any missing/mismatched/tampered input."""
    import hashlib
    import json as _json
    import pathlib

    def _digest(path) -> str:
        p = pathlib.Path(path)
        if not p.is_file() or p.stat().st_size == 0:
            raise AuthorizationError(
                f"evidence artifact missing or empty: {p.name}")
        return hashlib.sha256(p.read_bytes()).hexdigest()

    def _load(path) -> dict:
        p = pathlib.Path(path)
        try:
            return _json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise AuthorizationError(
                f"evidence artifact unreadable: {p.name}: {e}") from e

    # -- applicable qualification certificates (authoritative, current) ---
    if authoritative_state is None:
        raise AuthorizationError(
            "trusted registration requires the authoritative "
            "qualification state (§3.2)")
    certs = []
    for ref in authoritative_state_expected_refs(certificate_store):
        cert = certificate_store.get(ref)
        if cert is None or not cert.is_valid():
            raise AuthorizationError(
                f"certificate {ref!r} not currently valid in the "
                "authoritative store")
        certs.append(cert)
    if not certs:
        raise AuthorizationError("no applicable certificates")
    certificate_digests = tuple(
        (c.certificate_id, c.digest_bindings()) for c in certs)

    # -- exact dataset and roster identities (recomputed from bytes) ------
    dataset_digest = _digest(dataset_file)
    roster_digest = _digest(roster_file)

    # -- actual parser/evaluator/interpreter/oracle identities ------------
    parser_digest = _digest(parser_file)
    evaluator_digest = _digest(evaluator_file)
    _digest(interpreter_file)
    oracle_digest = _digest(oracle_file)
    if evaluator_digest == oracle_digest:
        raise AuthorizationError(
            "oracle identity equals the evaluator (independence)")

    # -- shared-core acceptance: derived from the acceptance artifact ----
    sc = _load(shared_core_acceptance_file)
    sc_verdict = sc.get("verdict") or sc.get("gate") or ""
    if sc_verdict != "ACCEPTED":
        raise AuthorizationError(
            f"shared-core acceptance artifact says {sc_verdict!r} "
            "(caller-asserted ACCEPTED strings are never consulted)")

    # -- canary + circuit-breaker integration evidence ---------------------
    canary = _load(canary_evidence_file)
    if not canary.get("passed", False):
        raise AuthorizationError(
            "canary integration evidence not passing "
            f"({canary.get('failure_reason', 'no pass marker')})")
    breaker = _load(breaker_evidence_file)
    if not breaker.get("passed", False):
        raise AuthorizationError(
            "circuit-breaker integration evidence not passing")

    # -- witness + mutation qualification -----------------------------------
    wit = _load(witness_suite_file)
    if wit.get("summary", {}).get("failed", 1) != 0:
        raise AuthorizationError("witness suite has failures")
    mut = _load(mutation_report_file)
    if mut.get("summary", {}).get("escapes"):
        raise AuthorizationError("mutation campaign has escapes")

    # -- optional EA13/EA18 scope evidence ----------------------------------
    ea13 = _digest(ea13_scope_file) if ea13_scope_file else ""
    ea18 = _digest(ea18_scope_file) if ea18_scope_file else ""

    evidence = ExecutionEvidence(
        compat_revision=EAE_CONTRACT_REVISION,
        primitives=tuple(primitives), protocols=tuple(protocols),
        models=tuple(models),
        dataset_digest=dataset_digest, roster_digest=roster_digest,
        evaluator_identity=f"oracle@{oracle_digest[:16]}",
        certificate_refs=tuple(c.certificate_id for c in certs),
        certificate_digests=certificate_digests,
        shared_core_acceptance="ACCEPTED",
        shared_core_evidence_digest=_digest(shared_core_acceptance_file),
        ea13_scope_evidence=ea13, ea18_scope_evidence=ea18,
        canary_ready=True, circuit_breaker_ready=True,
        roster_split="development",
        dispatch_limits=dict(dispatch_limits or {}),
        experiment_id=experiment_id, auth_purpose=auth_purpose)
    register_execution_evidence(
        evidence,
        trusted_certificate_refs={c.certificate_id for c in certs},
        authoritative_state=authoritative_state)
    return evidence


def authoritative_state_expected_refs(certificate_store) -> list:
    """Certificate references applicable to the next registration: all
    currently-valid certificates in the trusted store."""
    return [c.certificate_id for c in
            certificate_store.snapshot().certificates if c.is_valid()]


def recheck_execution_authorization(auth: ExecutionAuthorization) -> None:
    """Time-of-check integrity: revocation after issuance fails closed.

    When an authoritative qualification state is bound (§3.2), every
    recheck consults the durable state — current certificate validity,
    durable revocations and evidence identity — so revocation between
    requests, during active inference, or across process restarts
    refuses dispatch even when the consumer's local set is empty."""
    if not auth.checksum_valid():
        raise AuthorizationError("authorization checksum drifted")
    refs = [auth.certificate_ref] + list(
        auth.payload.get("certificates", []))
    REVOCATIONS.check(refs)
    if _AUTHORITATIVE_STATE is not None:
        _AUTHORITATIVE_STATE.consult(
            certificate_refs=refs,
            evidence_identity=auth.payload.get("evidence_identity", ""))
        return
    ev = _REGISTERED_EVIDENCE
    if ev is None or auth.eae_revision != ev.compat_revision:
        raise AuthorizationError(
            "registered evidence no longer covers this authorization "
            "(stale authorization refused)")
    if ev.evidence_identity() != auth.payload.get("evidence_identity"):
        raise AuthorizationError(
            "registered evidence was replaced after issuance (stale "
            "authorization refused, §3.2)")
