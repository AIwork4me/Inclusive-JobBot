# IJ-NANO-1.1 N05A — Independent Cognitive Evaluator Qualification

Date: 2026-11-27. Scope: SOFTWARE_ONLY (deterministic evaluator
infrastructure; no model, GPU or engine involved). Mission order:
`docs/IJNANO_MISSION_ORDER_V1_1.md` §5. Verdict: **PASS** for the gate
`N05A_COGNITIVE_EVALUATOR_QUALIFIED` in its declared scope. **This
qualification never grants end-to-end business Oracle qualification.**

## 1. What was built

- `src/nanoagent/eval/contracts.py` — typed evaluation contracts for the
  twelve families: intent, goal, tool selection, action representation,
  entity reference, slot value, numeric value and unit, state
  interpretation, conditional branch, recovery action, stop/continue,
  clarification. `Expectation` (evaluator-side ground truth) and `Response`
  (runtime output only) are distinct types; a structural test enforces that
  `Response` carries no expectation/answer/reason fields.
- `src/nanoagent/eval/comparators.py` — deterministic semantic comparisons:
  closed-vocabulary canonical folding for ids/labels (never substring
  matching as the primary method), identity comparison for entities, a
  closed unit registry with dimension-checked conversion (1.5 km == 1500 m;
  120 CNY != 120 USD), typed boolean/polarity handling, typed state
  predicates with operator (polarity) equality, non-finite rejection.
- `src/nanoagent/eval/controls.py` — the control battery: 41 controls
  (17 positives, 24 negatives) covering every mission-order control class:
  correct alternative representation, wrong entity, wrong polarity, wrong
  numeric value, invalid units, missing required slots, extra incorrect
  assertions, structurally valid but semantically incorrect actions,
  incorrect branch, invalid recovery, premature stop, unnecessary
  continuation, wrong clarification topics. Each negative is single-defect
  and declares exactly one reason code.
- `src/nanoagent/eval/evaluator.py` — the runtime-facing API is
  `evaluate(case_id, response)`; expectations, control classes and reason
  codes stay evaluator-side. `describe()` exposes only safe metadata.

## 2. Qualification results

- Battery: all 17 positives PASS; all 24 negatives FAIL for exactly their
  single declared reason (16 distinct reason codes).
  `tests/ij_nano/test_n05a_battery.py`.
- Mutation tests: a mutant evaluator that drops ANY scoring rule wrongly
  accepts at least one critical negative — every rule is load-bearing.
  Includes the substring-weakened entity mutant (accepts "C-9-vip" where
  "C-9" was expected), demonstrating why substring matching is forbidden as
  the primary correctness method; and unit-blind/polarity-blind mutants.
  `tests/ij_nano/test_n05a_mutation.py`.
- Coverage published per family: `evidence/IJNANO/N05A/evaluator_coverage.json`
  (12 families; per-family positive/negative counts and exercised reason
  codes). Qualifying suite run: `evidence/IJNANO/N05A/qualifying_run.txt`
  (128/128 Layer A tests OK — evaluator tests included; IJ-SDK suite
  unaffected, rerun in the same session).
- Rerun: `python -I -m unittest discover -s tests/ij_nano -t .` and
  `python -I benchmarks/ij_nano/n05a_publish_coverage.py`.

## 3. Scope limits (binding)

- The unit registry is closed and small (length, mass, time, currencies as
  non-convertible, dimensionless counts). N03 dataset construction may
  extend it; extending the registry is a recorded change, not silent.
- The battery qualifies the comparators and control discipline, not any
  specific dataset's difficulty or coverage of business worlds — the 640/320
  dataset requirements belong to N03.
- Deterministic only: no LLM judge anywhere in the evaluation path.
- Not the business Oracle: formal end-to-end business evaluation remains
  BLOCKED on the narrowed IJN-B-002 conditions.

## 4. Gate

`N05A_COGNITIVE_EVALUATOR_QUALIFIED` — PASS (software scope), recorded in
`MISSION_STATE_IJNANO.json` and `TASK_LEDGER_IJNANO.md`.
