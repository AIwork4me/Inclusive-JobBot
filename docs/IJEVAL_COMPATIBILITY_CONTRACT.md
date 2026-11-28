# IJEVAL Compatibility Contract — v1.0.0 (N03 critical path)

Machine-readable artifact: `evidence/IJEVAL/COMPAT/contract_v1.0.0.json`
(generator `scripts/ij_eval_assurance/compat_contract.py`; conformance test
`tests/ij_eval_assurance/test_compat_contract.py`). Registry:
`src/eval_assurance/compat/contract.py`. This document is the versioned
human-readable spec; the JSON artifact (with per-interface implementation
digests) is the integration target for the IJ-NANO runner.

Status summary: **11 interfaces across the 10 required sections — 8
IMPLEMENTED, 1 PARTIAL, 2 PLANNED.** The conformance test fails if an
IMPLEMENTED entry cannot be imported with its declared symbols, or if a
PLANNED entry already exists (the contract never claims more than the
codebase delivers).

## Sections

| Section | Interface | Status | Notes |
|---|---|---|---|
| task_schemas | n02rr_cognitive_families | IMPLEMENTED | six N02RR families via the legacy adapter; N03 C01–C08 intake declared below |
| parser_interfaces | legacy_n02rr_adapter | IMPLEMENTED | production parsing stays in IJ-NANO `arms_v2`; EAE consumes typed results + receipts |
| oracle_interfaces | reference_oracle | **PLANNED** | EA03/EA05: independent truth tables/assertions from task specifications; no production comparator imports; disagreement → ORACLE_DISAGREEMENT |
| evidence_envelopes | verified_evidence | IMPLEMENTED | schema 1.1.0, creation-keyed, immutable |
| evidence_envelopes | verification_receipts | IMPLEMENTED | hashes actual artifact bytes; trial/experiment binding |
| qualification_issuance | qualification_authority | IMPLEMENTED | sole trusted issuance; digest-bound; evidence mandatory |
| certificate_lifecycle | certificate_store | IMPLEMENTED | trusted-flag + registry checksum; durable revocation; reissue requires requalification |
| runner_authorization | runner_authorization | IMPLEMENTED | see Authorization rule below |
| canary_integration | canary_scheduler | **PLANNED** | EA09: production-path controls, preregistered cadence |
| quarantine_recovery | boundary_quarantine | PARTIAL | quarantine + duplicate/critical blocking implemented; restart-safe recovery scope (EA10) planned |
| qualified_aggregation | aggregation_boundary | IMPLEMENTED | scope certification + roster reconciliation + snapshot recheck |

## Authorization rule (binding)

N03 — and any runner scope — is authorized **only** by
`eval_assurance.compat.authorization.authorize_runner(report, store,
snapshot)` returning `RunnerAuthorization.allowed=True`: a checksummed,
scope-bound object carrying scope, verdict, scope declaration, qualified
counts, coverage, certificate ids + digests, snapshot checksum and reasons,
serialized via `to_json()`. A bare PASS string or certificate object
authorizes nothing. Revocation between aggregation and authorization fails
closed; `ALLOWED_PARTIAL` authorizes only when the caller explicitly
accepts a partial scope.

## N03 Batch A intake (declaration, not a dataset)

- Primitives C01–C08; 160 development + 80 **protected confirmation** cases.
- Source of truth: the IJ-NANO mission's pinned, committed qualification
  package (taxonomy frozen at IJ-NANO `bae4c3d`, taxonomy digest
  `cb800bce…`, `evaluation/ij_nano/n03/taxonomy.json`). EAE **consumes**
  this package when it lands; it never builds a competing dataset.
- Confirmation protection: confirmation expectations are consumed only by
  the trusted qualification path (reference oracle + certificate issuance)
  and are never passed to parsers, model-facing prompts, runner
  configuration, or optimizer-visible structures.
- Independent reference implementations will be derived from the C01–C08
  task specifications, not copied from the production answer generator.

## Compatibility versioning

Any interface change that alters symbols, semantics or authorization rules
forks `CONTRACT_VERSION`, regenerates the evidence artifact, and invalidates
dependent runner integrations (INV07/INV08). The artifact records
per-interface `implementation_sha256` so the runner can pin the exact
integration target.
