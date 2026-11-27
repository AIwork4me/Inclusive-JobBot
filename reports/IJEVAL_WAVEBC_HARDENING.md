# IJEVAL Wave B/C — Trusted Assurance Boundary Hardening (EA-R01..EA-R04)

Status: COMPLETE for the four hardening concerns (addendum sections 2, 3, 8,
9 of `docs/IJEVAL_MISSION_ORDER_WAVE_BC.md`). These are foundations FOR Wave
B — no Wave B gate is claimed by this report.
Date: 2026-11-28 · Audited HEAD `9963926` verified == remote before changes.
Baselines preserved: ij_eval_assurance 68→95 tests, ij_nano 213/213, EA02-R
state-space results untouched.

## Method

Each concern reproduced red at `9963926`
(`evidence/IJEVAL/EABC/red_reproduction.json`, generator
`scripts/ij_eval_assurance/eabc_red_repro.py`), repaired, closed green
(`green_reproduction.json`), and pinned as a permanent battery
(`tests/ij_eval_assurance/test_wavebc_hardening.py`, 21 tests).

## Repairs

| ID | Red at `9963926` | Repair |
|---|---|---|
| EA-R01 | arbitrary `CertificateStore()` + `issue()` authorized formal eligibility (empty evidence, empty/identical reference identity, zero digest bindings) | `QualificationAuthority` is the only trusted issuance: gate evidence verified (files exist + non-empty), **actual sha256 digests computed from implementation bytes** (8 bindings), reference oracle must differ from the production evaluator, evidence refs mandatory; arbitrary stores are untrusted and never authorize; `validate_certificate` rejects incomplete/incompatible certificates; registries self-checksummed |
| EA-R02 | `"banana"` accepted as SHA256; untrusted identical digest pairs accepted; `VerifiedEvidence` directly constructible; envelope identity mutable | strict 64-hex syntax; creation-keyed `VerifiedEvidence`/`VerificationReceipt` (direct construction → `PermissionError`); read-only defensive-copy mappings; receipts hash **actual artifact bytes** bound to trial+experiment identity; N02RR adapter consumes receipts, not caller strings; three evidence classes documented (claimed / verified / qualified transfer) |
| EA-R03 | empty/unrelated/revoked-only stores → `ALLOWED`; zero qualified rows → `ALLOWED`; critical NOT_EVALUABLE didn't block; no roster/duplicate/scope enforcement | publication chain: trusted store ∧ currently-valid certificate **for the requested scope** ∧ qualified rows > 0 ∧ no critical NOT_EVALUABLE ∧ complete planned roster (or explicit `ALLOWED_PARTIAL` with `scope_declaration="partial"`, never full closure); duplicate trial ids quarantined; every planned slot reported |
| EA-R04 | report survived post-aggregation revocation; equivalent reissue immediately valid; corrupt registry crashed uncontrolled | immutable checksummed `QualificationSnapshot`; `publish_report` rechecks snapshot currency + per-certificate validity at publication time; durable revocation history with atomic persistence + registry checksum (corrupt/tampered → `CertificateError`); reissue of a revoked binding requires `requalified=True` with fresh gate evidence; RLock synchronization |

## EA00 corruption regression — hardened expectations

Re-run against the actual aggregation entry point
(`tests/ij_eval_assurance/test_boundary.py`), now with receipts computed
from the **actual sealed artifact bytes** (2,184 real hash verifications):

1. No trusted certificate: diagnostic truth only — **870 correct
   preserved**, 2 injections classified NOT_EVALUABLE-critical,
   `BLOCKED_NO_TRUSTED_CERTIFICATE`.
2. Certificate bound, contaminated scope: 870/2,184 qualified but the two
   unresolved critical evidence faults **block publication**
   (`BLOCKED_CRITICAL_NOT_EVALUABLE`) — contaminated rows can no longer be
   quietly dropped from a formal claim.
3. Sealed scope only (injections are not planned slots of the sealed
   experiment): **ALLOWED** with exact-roster reconciliation, conditional
   accuracy 870/2184, coverage 1.0, publication-time recheck passes.
4. One missing planned slot: `BLOCKED_INCOMPLETE_ROSTER`; declared partial:
   `ALLOWED_PARTIAL` / `scope_declaration="partial"`.

The 871/2186 headline remains structurally unreachable; the sealed corpus
hash is unchanged before/after (INV07).

## Trust boundary and threat model (EA-R01, documented honestly)

In-process Python cannot defend against a malicious caller that forges
`trusted=True` or monkeypatches the authority. The enforced boundary is
against **accidental misuse and untrusted data**: caller-built stores never
authorize, issuance without real gate evidence is impossible, digest
bindings come from actual bytes, and registries detect tampering. No
cryptographic signatures; no remote enforcement — neither implemented nor
claimed. Full lifecycle (signed receipts, scope hierarchies, multi-process
mutual exclusion) remains EA17 scope per the addendum.

## Test totals

- `tests/ij_eval_assurance`: **95/95 OK** (74 carried forward + 21 new).
- `tests/ij_nano`: **213/213 OK**.
- Full-tree sensitive scan: 0 findings (via pubgate receipts).

## Reproduction

```bash
python -I scripts/ij_eval_assurance/eabc_red_repro.py   # post-fix = green behavior
python -m unittest discover -s tests/ij_eval_assurance -q
python -I -m unittest discover -s tests/ij_nano -q
```

## Next

Wave B proper per the addendum: EA03 independent ground truth (N02RR + N03
families), EA04/EA05 dual-path independent evaluation, EA06/EA07 golden
witnesses + semantic mutation coverage, EA08 end-to-end evidence
qualification — all issuing through the now-trusted qualification boundary.
