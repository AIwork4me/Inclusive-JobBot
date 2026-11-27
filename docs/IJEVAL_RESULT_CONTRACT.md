# IJEVAL Result Contract — Specification v1.0.0 (EA02)

Implementation: `src/eval_assurance/contracts/` (authority: code + tests
`tests/ij_eval_assurance/`). This document is the versioned specification.

## 1. Dimensions (order §4.1)

A single Boolean may never represent these (INV01/INV02):

| Dimension | Type | Values |
|---|---|---|
| Execution | `ExecutionStatus` | EXECUTED, NOT_RUN, BLOCKED, PARTIAL, CANARY_CONTROL |
| Evidence pipeline | `EvaluationStatus` | VALID, ARTIFACT_ERROR, TRANSPORT_ERROR, PARSER_ERROR, EVALUATOR_ERROR, REPLAY_ERROR, ORACLE_DISAGREEMENT, INVALID_DATASET, UNSUPPORTED_CONTRACT |
| Evidence integrity | `EvidenceIntegrity` | VERIFIED, REJECTED, MISSING (+ `evidence_invalid_reason`) |
| Parser | `ParserStatus` | PARSE_OK, MODEL_OUTPUT_INVALID, UNSUPPORTED_REPRESENTATION, PARSER_SOFTWARE_ERROR |
| Evaluator | `EvaluatorStatus` | OK, ERROR, DISAGREEMENT (+ `oracle_disagreement`) |
| Semantic | `SemanticVerdict` | CORRECT, INCORRECT, NOT_EVALUABLE, NOT_APPLICABLE |
| Business | `BusinessVerdict` | PASS, FAIL, NOT_VERIFIED, NOT_APPLICABLE (+ `business_world_valid`) |
| Safety | `SafetyVerdict` | SAFE, VIOLATION, NOT_VERIFIED, NOT_APPLICABLE |
| Qualification | `QualificationStatus` | QUALIFIED, UNQUALIFIED, REVOKED, PENDING |
| Publication | `PublicationEligibility` | ELIGIBLE, DIAGNOSTIC_ONLY, BLOCKED |

## 2. Invalid output vs evaluator failure (§4.2)

- **Case A** — model violates a qualified output contract:
  `ParserStatus.MODEL_OUTPUT_INVALID` + `SemanticVerdict.INCORRECT`.
  May enter model-failure statistics.
- **Case B** — parser/evaluator crashes or cannot interpret:
  `PARSER_SOFTWARE_ERROR` / `UNSUPPORTED_REPRESENTATION` /
  `EvaluationStatus ≠ VALID` → `NOT_EVALUABLE`. Never a model failure.
  (Closes IJE-D001: the N02RR replay-exception coercion.)

## 3. Legal combinations (§4.3) — enforced centrally

`validator.validate_result()` rejects (raises `ContractViolationError`),
before persistence/aggregation/publication:

- EVALUATOR_ERROR + CORRECT; REPLAY_ERROR + INCORRECT; TRANSPORT_ERROR +
  any qualified verdict; any non-VALID pipeline + qualified verdict.
- UNSUPPORTED_REPRESENTATION / PARSER_SOFTWARE_ERROR + qualified verdict.
- Missing mandatory provenance + qualified verdict (keys: experiment, trial,
  task, model, dataset, parser_version, evaluator_version).
- evidence_invalid_reason (e.g. EVIDENCE_INCONSISTENT_STAGE2_TOOL) +
  qualified verdict. (Closes IJE-D002.)
- Invalid/unverified business world + business PASS.
- Oracle disagreement + qualified conclusion or ELIGIBLE publication.
- Safety VIOLATION + business PASS or ELIGIBLE publication (INV09).
- UNQUALIFIED/REVOKED scope + ELIGIBLE publication.
- CANARY_CONTROL + ELIGIBLE publication; NOT_RUN/BLOCKED/PARTIAL +
  qualified verdict.

## 4. Legacy compatibility (§4.4)

- `from_legacy_boolean(semantic_correct, replay_error=, transport_error=,
  failure_class=, provenance=)` adapts N02RR-style records fail-closed:
  software/evidence failures map to NOT_EVALUABLE, never to False-as-failure.
- `to_legacy_boolean(result)` maps CORRECT→True, INCORRECT→False and
  **raises** `LegacyRepresentationError` for anything else. Consumers that
  need counts must use §5 instead of coercing.

## 5. Statistical eligibility (§4.5)

`eligible_for_semantic_statistics(result)` is the single authority. True
only when: EXECUTED (not canary) ∧ pipeline VALID ∧ evidence VERIFIED ∧ no
evidence-invalid marker ∧ parser ∈ {PARSE_OK, MODEL_OUTPUT_INVALID} ∧
evaluator OK ∧ no disagreement ∧ verdict ∈ {CORRECT, INCORRECT} ∧ complete
provenance. Analyzers consume this function only — per-row ad-hoc filtering
is forbidden (that exact freedom produced EA00 finding R3).

## 6. Evidence

- Contract tests + invalid-state mutation tests:
  `tests/ij_eval_assurance/test_contract_validator.py` (17 tests).
- Legacy + N02RR adapter closure tests:
  `tests/ij_eval_assurance/test_legacy_and_n02rr_adapter.py` (10 tests).
- Production-record reproduction feeding these shapes:
  `evidence/IJEVAL/EA00/n02rr_residual_risk_reproduction.json`.
- Result: 27/27 green (unittest discover, 2026-11-28).

## 7. Versioning

`CONTRACT_SPEC_VERSION = "1.0.0"`. Any semantic change to dimensions,
legality rules or eligibility forks the version and invalidates dependent
qualification certificates (INV07/INV08; enforced from EA17 onward).
