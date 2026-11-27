# IJEVAL_02R — Contract Hardening Report (IJ-EVAL-ASSURANCE-1.0, EA02-R)

Status: COMPLETE — gate `EA02R_EVALUATION_CONTRACT_INVARIANTS_GO` **GRANTED**
for the scope "evaluation-contract invariants EA-D01..EA-D06". This is NOT a
claim that the assurance system as a whole is qualified.
Date: 2026-11-28 · Addendum: `docs/IJEVAL_MISSION_ORDER_EA02R.md` (preregistered,
commit 35cad83) · Audited HEAD `3fff135` verified == remote before any change.

## Method

Every concern was **reproduced first** on the audited implementation
(`evidence/IJEVAL/EA02R/red_reproduction.json`, generator
`scripts/ij_eval_assurance/ea02r_red_repro.py --phase red`), then repaired,
then re-observed (`green_reproduction.json`). The red evidence is preserved
as a historical artifact of the audited state; re-running `--phase red`
against the hardened tree raises by design.

## Findings and repairs

| ID | Red observation (audited `3fff135`) | Repair | Green evidence |
|---|---|---|---|
| EA-D01 | REVOKED/UNQUALIFIED/PENDING all statistically eligible; PENDING+ELIGIBLE escaped the validator | Five eligibility authorities; formal ones require an actual `QualificationCertificate` from a `CertificateStore` bound by scope + dataset/parser/evaluator identity to the record's provenance; certificate is the authority, explicit record REVOKED blocks, no store → fail closed | REVOKED/UNQUALIFIED/PENDING formal-ineligible (diagnostic-eligible); `fail_closed_without_certificate: true` |
| EA-D02 | `from_legacy_boolean("False")` → **CORRECT** (truthiness inversion); `None`→INCORRECT; 0/1/lists coerced; unknown failure class → ordinary outcome | `type(x) is bool` everywhere; complete legacy-schema validation (contradictory metadata, unknown failure classes → `LegacyContractError`); adapter maps contract errors to separately-classified NOT_EVALUABLE; export validates the complete record | all non-Boolean probes raise; genuine True/False unaffected |
| EA-D03 | 5 illegal combinations escaped; string/int enum substitution accepted with 0 violations | 5 new validator rules + `ContractTypeError` at construction; cognitive/business invariants separated | state-space battery (below) |
| EA-D04 | evidence defaulted to VERIFIED (trust by omission) | default UNVERIFIED; versioned `VerifiedEvidence` envelope only via `verify_evidence()` (sha256 match + schema + trial/evaluator identity, with `basis`); validator cross-checks envelope vs provenance | default_evidence_state: UNVERIFIED |
| EA-D05 | no formal aggregation boundary; historical analyzer reads Booleans (EA00 R3) | `aggregate_semantic` boundary: typed records only, central validation, qualified/not_evaluable/quarantined/canary classification, fail-closed formal publication; `n02rr_analyze.py` marked DIAGNOSTIC-ONLY (docstring only; sealed artifacts untouched) | EA00 corruption regression at the actual entry point (below) |
| EA-D06 | live: direct exit 1 vs piped exit 0 (pipe masks BLOCKED) | `pubgate.py`: argv subprocess (no shell), exit code captured directly, finding-count verdict, malformed/truncated output fails closed, staged-identity binding pre/post, auditable receipts, gated `commit` | wrapper exists; 6 injected bypass modes all fail closed |

## Systematic state-combination validation (EA-D03)

`scripts/ij_eval_assurance/ea02r_state_space.py` +
`evidence/IJEVAL/EA02R/state_space_results.json`. Hypothesis confirmed
unavailable → stdlib exhaustive enumeration:

| Block | Dimensions | Combinations |
|---|---|---|
| Cognitive core (exhaustive) | execution × pipeline × parser × verdict × qualification × publication | 8,640 |
| Business (exhaustive) | business × safety × world × pipeline | 96 |
| Evaluator (exhaustive) | evaluator × disagreement × pipeline × verdict | 216 |
| Evidence (exhaustive) | evidence × envelope × provenance × marker × publication × safety | 360 |
| Malformed types | enum/bool field substitutions | 44 |

**Results: 9,312 generated · 2,958 valid · 6,354 invalid · 0 escaping invalid
combinations · 0 false rejections · 24/24 declared invariants exercised ·
44/44 malformed type injections rejected at construction.** The expected
validity rules were authored INDEPENDENTLY from the specification
(`model_illegal()`, 24 rules R01–R24) and never call the validator under
test; validator/model agreement is exact. Made permanent by
`tests/ij_eval_assurance/test_state_space.py`.

## EA00 injected-corruption regression at the aggregation entry point (EA-D05)

`tests/ij_eval_assurance/test_boundary.py::TestEA00CorruptionRegression`
(sealed corpus skipUnless present; runs against
`evidence/IJNANO/N02RR/trial_reconciliation.jsonl` + the two EA00 shapes
through the adapter):

- **Without certificate**: diagnostic_correct = **870**, not_evaluable = **2**,
  quarantined = 0, formal_publication = `BLOCKED_NO_CERTIFICATE_BOUND`.
- **With certificate** (identity-bound to ij_nano.n02r.suite /
  arms_v2.parse_response / n02r.scorer/contract-v2): qualified_eligible =
  **2,184**, correct = **870**, not_evaluable = 2, conditional accuracy =
  870/2184, formal_publication = ALLOWED (no unresolved critical rows).
- The contaminated **871/2186** headline is structurally unreachable (the
  injected True-verdict row can only be NOT_EVALUABLE; the injected
  False-verdict row can never enter the numerator).
- The sealed corpus file hash is unchanged before/after (INV07).

## Publication gate (EA-D06)

`scripts/ij_eval_assurance/pubgate.py` (`run` / `commit -m` / `verify`).
Injected and verified fail-closed: nonzero process exit, zero exit with
findings, truncated output, empty output, staged content changed mid-check,
missing / corrupt / incomplete receipts. The motivating incident (pipeline
masks BLOCKED exit) is pinned as a live regression test. Receipts are
written to `evidence/IJEVAL/EA02R/pubgate_receipts/`. No hooks installed
outside repository scope; no remote-protection claim made.

## Test totals

- `tests/ij_eval_assurance`: **68/68 OK** (contract 45 + state-space 5 +
  boundary 5 + pubgate 13... composed of the batteries above).
- `tests/ij_nano` (existing regression): **213/213 OK**.
- Full-tree sensitive scan: **0 findings**.
- Working-tree probe artifacts cleaned; sealed evidence untouched.

## Residual limitations

Recorded in `evidence/IJEVAL/EA02R/defect_ledger.json`
(`residual_limitations`): CertificateStore lifecycle is EA17 work (formal
paths fail closed until then); N02RR envelope transfer relies on the
qualified loader's verification (basis-tagged); state-space is exhaustive
per-block rather than full cross-product; pubgate is the local gate
authority, not remote enforcement.

## Reproduction

```bash
python -I scripts/ij_eval_assurance/ea02r_state_space.py
python -I scripts/ij_eval_assurance/ea02r_red_repro.py --phase green
python -I scripts/ij_eval_assurance/pubgate.py run
python -m unittest discover -s tests/ij_eval_assurance -q
python -I -m unittest discover -s tests/ij_nano -q
```
