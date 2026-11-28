"""EAE–runner compatibility contract (N03 critical path, v1.0.0).

The machine-readable interface registry the IJ-NANO runner integrates
against. Every IMPLEMENTED entry is verified by ``verify_contract()`` (and
by the conformance test battery) to import and expose the declared symbols;
PLANNED entries are asserted NOT to exist yet — the contract never claims
more than the codebase delivers.

Sections map 1:1 to the coordination order's required contract list.
Honest statuses: IMPLEMENTED / PARTIAL / PLANNED.
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass

CONTRACT_VERSION = "1.1.0"

#: N03 Batch A intake target (read-only pin; owned by the IJ-NANO mission —
#: EAE consumes, never rebuilds): C01-C08 taxonomy contracts frozen at
#: IJ-NANO commit bae4c3d, taxonomy digest cb800bce... (see evidence).
N03_BATCH_A = {
    "primitives": "C01-C08",
    "development_cases": 160,
    "protected_confirmation_cases": 80,
    "taxonomy_digest_prefix": "cb800bce",
    "taxonomy_owner": "IJ-NANO PR #11 (evaluation/ij_nano/n03/taxonomy.json)",
    "intake_status": "VERIFIED",      # EA02R intake: all digest checks
    #                                     passed at pinned d23de5a
    #                                     (evidence/IJEVAL/EA03_N03/
    #                                     intake_verification.json)
    "confirmation_protection": (
        "confirmation expectations are consumed only by the trusted "
        "qualification path (reference oracle + certificate issuance); "
        "they are never passed to parsers, model-facing prompts, runner "
        "configuration or optimizer-visible structures"),
}


@dataclass(frozen=True)
class Interface:
    section: str          # contract section (order's list)
    name: str
    module: str           # import path
    symbols: tuple[str, ...]
    status: str           # IMPLEMENTED | PARTIAL | PLANNED
    notes: str = ""


REGISTRY: tuple[Interface, ...] = (
    # -- supported task schemas -------------------------------------------
    Interface("task_schemas", "n02rr_cognitive_families",
              "eval_assurance.adapters.n02rr",
              ("n02rr_result_from_replay",), "IMPLEMENTED",
              "six N02RR families via the legacy adapter; N03 C01-C08 "
              "intake declared in N03_BATCH_A (PLANNED until the pinned "
              "package lands)"),
    # -- parser interfaces -------------------------------------------------
    Interface("parser_interfaces", "legacy_n02rr_adapter",
              "eval_assurance.adapters.n02rr",
              ("n02rr_result_from_replay", "n02rr_contract_error_result"),
              "IMPLEMENTED",
              "production parsing stays in IJ-NANO arms_v2; EAE consumes "
              "typed results and receipts, never raw strings"),
    # -- independent oracle interfaces --------------------------------------
    Interface("oracle_interfaces", "reference_oracle",
              "eval_assurance.reference.oracle",
              ("validate_ground_truth", "evaluate_response",
               "GroundTruthVerdict", "GroundTruthResult",
               "ResponseVerdict"), "IMPLEMENTED",
              "obligation A (ground-truth qualification) and obligation B "
              "(reference-path response evaluation, independent "
              "interpreter in eval_assurance.reference.interpreter) "
              "IMPLEMENTED over the pinned Batch A snapshot: 160/160 dev "
              "VALID, 597/597 mutations detected, 38/38 GT-D probes, "
              "40/40 response witnesses; imports no production "
              "comparators"),
    Interface("parser_interfaces", "reference_interpreter",
              "eval_assurance.reference.interpreter",
              ("parse_response",), "IMPLEMENTED",
              "independently authored minimum parser semantics of the "
              "pinned handoff (parser_semantics.md @ d23de5a); reference "
              "leg of the dual-path evaluation"),
    # -- evidence envelopes --------------------------------------------------
    Interface("evidence_envelopes", "verified_evidence",
              "eval_assurance.contracts.core",
              ("VerifiedEvidence", "verify_evidence",
               "validate_sha256_digest"), "IMPLEMENTED",
              "schema 1.1.0; creation-keyed, immutable mappings"),
    Interface("evidence_envelopes", "verification_receipts",
              "eval_assurance.evidence",
              ("VerificationReceipt", "issue_verification_receipt",
               "validate_receipt_for", "sha256_of_file"), "IMPLEMENTED",
              "hash computed from actual artifact bytes; trial/experiment "
              "identity binding"),
    # -- qualification issuance ----------------------------------------------
    Interface("qualification_issuance", "qualification_authority",
              "eval_assurance.qualification.store",
              ("QualificationAuthority", "validate_certificate"),
              "IMPLEMENTED",
              "sole trusted issuance; digest-bound; evidence mandatory"),
    # -- certificate verification and revocation -------------------------------
    Interface("certificate_lifecycle", "certificate_store",
              "eval_assurance.qualification.store",
              ("CertificateStore", "QualificationCertificate",
               "QualificationSnapshot"), "IMPLEMENTED",
              "trusted-flag + registry checksum; durable revocation; "
              "reissue requires requalified=True"),
    # -- runner authorization (v1.1.0 split) ---------------------------------
    Interface("runner_authorization", "execution_authorization",
              "eval_assurance.compat.execution_authorization",
              ("ExecutionAuthorization", "ExecutionEvidence",
               "issue_execution_authorization",
               "recheck_execution_authorization"), "IMPLEMENTED",
              "PRE-DISPATCH contract (schema 1.1.0): binds qualification "
              "evidence (scope, digests, certificates, shared-core "
              "acceptance, canary/circuit-breaker readiness, revocation, "
              "dispatch limits); NEVER depends on experiment results — "
              "consumed by the IJ-NANO runner at a pinned IJEVAL "
              "revision; fail-closed with no registered evidence"),
    Interface("runner_authorization", "publication_authorization",
              "eval_assurance.compat.authorization",
              ("RunnerAuthorization", "authorize_runner"), "IMPLEMENTED",
              "POST-EXECUTION contract (schema 1.0.0, unchanged "
              "semantics): consumes a qualified AggregationReport; NOT a "
              "pre-dispatch requirement (v1.1.0 separation)"),
    # -- canary integration -------------------------------------------------------
    Interface("canary_integration", "canary_scheduler",
              "eval_assurance.canary.scheduler", ("CanaryScheduler",),
              "PLANNED",
              "EA09: controls through the PRODUCTION evaluation path; "
              "cadence 25 trials / 5 min preregistered; canaries counted, "
              "never model observations"),
    # -- quarantine and recovery ----------------------------------------------------
    Interface("quarantine_recovery", "boundary_quarantine",
              "eval_assurance.statistics.boundary",
              ("aggregate_semantic", "AggregationReport"), "PARTIAL",
              "quarantine classification + duplicate/critical blocking "
              "IMPLEMENTED; restart-safe recovery scope (EA10) PLANNED"),
    # -- qualified aggregation -----------------------------------------------------------
    Interface("qualified_aggregation", "aggregation_boundary",
              "eval_assurance.statistics.boundary",
              ("aggregate_semantic", "publish_report",
               "AggregationReport"), "IMPLEMENTED",
              "scope certification + roster reconciliation + "
              "publication-time snapshot recheck"),
)


def verify_contract() -> list[str]:
    """Conformance check: every IMPLEMENTED entry imports with its symbols;
    every PLANNED entry must NOT be importable (honesty). Returns problems
    (empty == conformant)."""
    problems: list[str] = []
    for iface in REGISTRY:
        try:
            mod = importlib.import_module(iface.module)
        except ImportError as e:
            if iface.status == "IMPLEMENTED":
                problems.append(f"{iface.name}: cannot import "
                                f"{iface.module}: {e}")
            continue
        if iface.status == "PLANNED":
            problems.append(f"{iface.name}: declared PLANNED but "
                            f"{iface.module} exists — update the contract")
            continue
        for sym in iface.symbols:
            if not hasattr(mod, sym):
                problems.append(f"{iface.name}: {iface.module} lacks "
                                f"symbol {sym!r}")
    return problems


def contract_summary() -> dict:
    return {
        "contract_version": CONTRACT_VERSION,
        "sections": sorted({i.section for i in REGISTRY}),
        "interfaces": len(REGISTRY),
        "by_status": {
            s: sum(1 for i in REGISTRY if i.status == s)
            for s in ("IMPLEMENTED", "PARTIAL", "PLANNED")},
        "n03_batch_a": dict(N03_BATCH_A),
    }
