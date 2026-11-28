# Batch A critical mutation targets (C01–C08) — for EA07 qualification

Consumer: IJ-EVAL-ASSURANCE (PR #13). Each mutation below, injected into a
qualified evaluator/parser path, MUST be detected by the EAE controls
(differential verification, golden witnesses, canaries) — a mutation that
escapes into qualified statistics is a qualification failure for the
affected scope.

## Semantic-comparator mutations (per primitive)

- **M-C01a**: catalog-membership check replaced by substring containment
  (e.g. `shipping_status` accepted inside `shipping_status_delay`).
- **M-C01b**: label comparison made case-sensitive after the parser already
  normalized case (double normalization mismatch).
- **M-C02a**: `unknown_flags` ignored — missing deadline scored as CORRECT
  when the expectation records unknown.
- **M-C02b**: deadline string comparison skipping ISO normalization.
- **M-C03a**: line-set comparison replaced by substring presence of each
  expected line (order/format violations escape).
- **M-C03b**: uppercase requirement dropped (case-folding mutation).
- **M-C03c**: oneedit compared after stripping ALL whitespace (segment
  boundary corruption escapes).
- **M-C04a**: set equality replaced by subset check (extra ids escape).
- **M-C04b**: declared sort order ignored when comparing sequences.
- **M-C05a**: predicate boundary flipped at the threshold (`<=` -> `<`).
- **M-C05b**: policy limit read from a hardcoded constant instead of the
  case policy text.
- **M-C06a**: cheapest-qualifying argmax replaced by cheapest-overall.
- **M-C06b**: hard-constraint filter dropped for one attribute.
- **M-C07a**: action-name normalization that accepts paraphrases
  (`reset_password` ~= `password_reset`).
- **M-C08a**: candidate-list membership check dropped (hallucinated tool
  ids accepted when string-matching an expected alias).
- **M-C08b**: capability-superset uniqueness check dropped in the Oracle
  double-derivation.

## Cross-cutting (historical list, mandatory)

- Dictionary-unpacking/positional stage access (N02R defect class).
- Evaluator exception coerced to `semantic_correct=False`.
- Empty output scored as INCORRECT instead of EMPTY_OUTPUT.
- Boolean coercion of non-boolean fields.
- Duplicate trial ids both counted in one denominator.

## Expected controls

Each mutation must be (1) reproduced red in an isolated evaluator instance,
(2) caught by at least one independent control (reference-path
disagreement, golden witness, or canary), (3) represented in the permanent
regression corpus once repaired.
