# IJ-NANO-1.2 N05A-R — Targeted Cognitive Evaluator Requalification

- Mission order: `docs/IJNANO_MISSION_ORDER_V1_2.md` §2
- Audited baseline: `dfce2952` (evaluator v1); red reproduced at `f62ddc2`
- Gate: `N05AR_COGNITIVE_EVALUATOR_INTEGRITY_GO` — **PASS** (software scope)
- Evidence: `evidence/IJNANO/N05AR/{red_run.txt,green_run.txt,defect_ledger.json,coverage_matrix.json}`
- Tests: `tests/ij_nano/test_n05ar_ev_concerns.py` (45 tests), retained
  `test_n05a_battery.py` / `test_n05a_mutation.py` updated to contract v2

## 1. What this is and is not

This requalification hardens the N05A cognitive evaluator against seven
source-review concerns (EV01–EV07). It remains a **cognitive evaluator
integrity** gate only: it never grants end-to-end business Oracle
qualification (blocker IJN-B-002 stays open for formal business claims).
The original N05A qualification evidence is preserved unchanged under
`evidence/IJNANO/N05A/`.

## 2. Method: reproduce red, then repair

Every concern was reproduced **before** any implementation change: the
final regression suite was executed against the pre-repair implementation
(detached worktree at `f62ddc2`). Result — `red_run.txt`:

| Concern | Distinct red tests | Defect demonstrated |
|---|---|---|
| EV01 state predicates | 6 | missing predicates accepted; duplicates/contradictions misattributed; valid reorder rejected |
| EV02 undeclared arguments | 5 | unknown/unauthorized args accepted; no optional contract; duplicate raw keys undetected |
| EV03 predicate semantics | 7 | no world-truth channel; threshold-vs-threshold; TypeError crash on `"thirty" <= 30` |
| EV04 identifier collisions | 6→4 sites | `adjust_stock`≡`adjust space`, `ORD-1042`≡`ord-1042` merged by blanket folding |
| EV05 missing units | 2 | scalar silently inherited hidden expected unit |
| EV06 mutation testing | 1 | no comparator-level mutants existed |
| EV07 coverage | 6 | 16 declared vs 14 tested codes; malformed inputs accepted |

**31 of 45 tests red; 14 anchors green** (behaviour that was already
correct and must remain so — e.g. leading-zero and fullwidth-Unicode
identifiers stay distinct, label folding survives for closed
vocabularies, explicit-unit quantity comparison unchanged).

## 3. Repairs (contract v2)

1. **EV01** — `eval_state_interpretation` now keys claims by exact
   `(entity_id, property)` identity: `MISSING_PREDICATE` for unclaimed
   required predicates (suppressed to a single `ENTITY_MISMATCH` when the
   defect is a wrong-entity substitution on the same property),
   `DUPLICATE_PREDICATE` for a second claim on one identity (including
   `eq`/`ne` contradictions — one-claim-per-identity contract),
   `EXTRA_ASSERTION` for out-of-scope or redundant claims; order-independent.
2. **EV02** — `ARGUMENT_UNDECLARED` is emitted from `response.args`
   alone (both `action_representation` and `slot_value`); `SlotSpec.optional`
   declares permitted optional arguments; a strict raw-JSON gate rejects
   duplicate object keys (`PARSE_INVALID`) before family evaluation; the
   `extra_assertions` channel is no longer the only guard.
3. **EV03** — split into `predicates_equivalent` (expression equivalence:
   exact operator identity + unit-aware threshold equality; cross-operator
   rewriting such as `ge 5 ≡ gt 4` is explicitly outside the contract) and
   `predicate_truth(pred, world)` (truth against an independently supplied
   world observation, unit-aware, boundary-exact). Invalid value types
   return `TYPE_MISMATCH` instead of raising `TypeError`. A claimed
   threshold is never evidence of the observed business value.
4. **EV04** — `identifier_matches` scopes folding to closed-vocabulary
   **labels** only (intent, goal types, enums, branches, recovery actions,
   decisions, clarification topics). Tool / entity / action identifiers
   compare by exact identity unless an explicit alias contract declares
   accepted variants (matched exactly). The v1 folded-entity and
   folded-tool "alternative representation" positives became collision
   negatives (`entity.neg.case_variant`, `tool.neg.underscore_space`).
5. **EV05** — `SlotSpec.unit_publicly_declared` is the only channel
   through which a bare scalar may inherit a unit (and only when the
   public task/schema declares it); otherwise `UNIT_MISSING`. Numeric
   strings and non-finite values stay `TYPE_MISMATCH` — no coercion.
6. **EV06** — `apply_mutant`/`clear_mutant` swap **real comparator
   functions** (handlers, `check_quantity`, `check_slot`,
   `identifier_matches`, `_OPS`, `_raw_reasons`; dispatch resolves through
   module globals at call time). Nine mutant classes; the qualification
   gate (`qualification.mutation_gate`) runs battery + predicate-truth
   controls against each; **all nine detected** with named witnesses
   (`coverage_matrix.json`). The retained v1-style rule-drop mutants were
   re-verified against the v2 rule set: 19/19 load-bearing.
7. **EV07** — reason-code contract reconciled: 19 declared = 19 tested
   (`PARSE_INVALID` controls added); `ARGUMENT_MISMATCH` declared
   **obsolete** with an explicit disposition record (subsumed by the seven
   precise codes). `Expectation`/`Quantity`/`SlotSpec`/`StatePredicate`
   validate at construction; `validate_control_battery` rejects malformed
   batteries; `qualify_family_scope` enforces the per-N03-family dataset
   rules: executable positive witness, critical negative controls, semantic
   mutations, valid alternative responses where applicable, and a versioned
   evaluator scope identity.

## 4. Qualification results

- Battery: **60 cases** (20 positive + 40 negative); all 40 negatives fail
  for **exactly** their single declared reason; every declared reason code
  carries ≥1 negative control (19/19 reconciled).
- Truth controls: 12/12 agree with hand-computed outcomes (operator
  boundaries, units, invalid types, unknown identities).
- Comparator mutants: 9/9 detected (witnesses and channels in
  `coverage_matrix.json`; `flip_inequality_ops` is caught through the
  predicate-truth channel — battery equivalence semantics do not apply
  ordering operators by design).
- Regression: `tests/ij_nano` **173/173 OK**; parent `tests/ij_sdk`
  **93 OK** (unaffected).
- Gate `N05AR_COGNITIVE_EVALUATOR_INTEGRITY_GO`: **PASS**.

## 5. Known limitations

- Software scope only, deterministic comparators; no model, GPU or
  business execution is involved or implied.
- Semantic-equivalence rules are the explicitly documented ones (exact
  operator identity + value equality; declared alias contracts). No
  general logical-equivalence reasoning is claimed.
- `qualify_family_scope` validates dataset-scope declarations
  structurally; the execution of a new family's controls is verified when
  that family's battery is actually run (same pattern as N05A).
- The v1→v2 behaviour changes (entity/tool exact identity) are recorded in
  `defect_ledger.json` §EV04; N03 dataset authors must not emit folded
  identifiers and may declare alias contracts where a task legitimately
  admits variants.
