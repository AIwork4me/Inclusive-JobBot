# IJEVAL ↔ IJ-NANO Execution contract v1.1.0 — integration instructions

**Contract:** `src/eval_assurance/compat/execution_authorization.py`
(schema `1.1.0`, `EAE_CONTRACT_REVISION = "1.1.0"`).
**Pinned IJEVAL revision:** the git commit recorded on Issue #12 for
this contract (the commit that introduces this file and
`contract_v1.1.0.json`). The consumer MUST pin that exact commit.

## What changed vs 1.0.0

- Authorization is SPLIT (qualification order §5):
  - **ExecutionAuthorization (this contract, new)** — pre-dispatch,
    binds the qualification evidence chain, requires NO
    AggregationReport, NO accuracy and NO completed model results.
    Fixes the startup circularity: the first physical benchmark is
    authorizable before any benchmark result exists.
  - **RunnerAuthorization (`compat/authorization.py`, schema 1.0.0,
    semantics unchanged)** — post-execution publication side only.

## Consumer integration (IJ-NANO PR #11, AUTH-0 runner)

The IJ-NANO `EAEExecutionAuthorizationProvider` already consumes this
shape (`benchmarks/ij_nano/n03/authorization.py`):

```python
provider = EAEExecutionAuthorizationProvider(
    pinned_revision="<pinned IJEVAL commit sha>",
    contract_module="eval_assurance.compat.execution_authorization")
auth = provider.issue_execution_authorization(RunRequest(
    experiment_id=..., dataset_digest=..., roster_digest=...,
    primitives=frozenset(...), protocols=frozenset(...),
    models=frozenset(...), eae_revision="<pinned IJEVAL commit sha>",
    auth_level="AUTH-1"))
gate = DispatchGate(provider)
physical = gate.authorize_physical(request)   # TEST_DOUBLE rejected here
```

Requirements on the consumer environment:

1. The IJEVAL repository checked out at the pinned commit with
   `<ijeval>/src` on `sys.path` (or installed from that checkout).
2. `request.eae_revision` must equal the provider's `pinned_revision`.
3. The EAE side must have REGISTERED evidence
   (`register_execution_evidence`) produced by its qualification
   pipeline — until then `issue_execution_authorization` raises and the
   gate stays closed (verified by
   `test_real_consumer_fail_closed_without_evidence`).

## What the EAE side binds before issuing (all fail-closed)

`compat_revision` match; dataset+roster digest match; primitive /
protocol / model scope coverage; `auth_level ∈ {AUTH-1, AUTH-2,
AUTH-3}`; confirmation execution requires AUTH-2 AND
evidence-confirmed confirmation coverage; non-empty certificates all in
the trusted store and none revoked; shared-core acceptance ACCEPTED;
canary + circuit-breaker readiness; dispatch limits recorded in the
payload. Checksum = sha256 over the canonical JSON of every bound
field; any field mutation invalidates it (controls 7/13).

## Verified by the 16 mandatory bypass controls

`tests/ij_eval_assurance/test_execution_authorization.py` — all 16
controls from order §6 pass, including the REAL consumer integration
(import of the actual IJ-NANO provider and `DispatchGate`, not a
conformance double): issue→validate→physical-gate→revoke→refuse, and
fail-closed behavior without registered evidence.

## Current honest status

No ExecutionEvidence is registered in production yet: shared-core
acceptance (EA09–EA14 chain), canary/circuit-breaker readiness and the
EA17 certificate for the Batch A scope are not complete. The contract
is published and consumer-verified, but it REFUSES physical dispatch
until that evidence exists. AUTH-1/AUTH-2 blockers are tracked in
`BLOCKERS_IJEVAL.md`.

## Trust model

Checksums bind fields against accidental drift and in-process
mutation; they are NOT a defense against a hostile process with code
execution (which could recompute them). Revocation is an explicit
registry re-checked at issue time and at every consumer recheck.
Single-user OS; no OS-level sandbox is claimed.
