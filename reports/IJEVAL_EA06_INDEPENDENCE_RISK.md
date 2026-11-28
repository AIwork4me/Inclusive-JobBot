# EA06 — independence & common-mode risk report (N03 Batch A, EA03/EA05 legs)

Date: 2026-11-28. Scope: the reference path delivered for Obligation A
(ground truth) and Obligation B (response evaluation) at the pinned
IJ-NANO dataset revision d23de5a.

## 1. Independence claims (what is actually independent)

| Component | Independence basis |
| --- | --- |
| `reference/oracle.py` | Zero imports from IJ-NANO production/builder code (test-enforced `test_oracle_imports_no_ij_nano_code`). All truth recomputed from PUBLIC payloads under the pinned handoff contract. Stored expectations/construction metadata are cross-checked, never authoritative. |
| `reference/interpreter.py` | Independently authored from the pinned `parser_semantics.md` text (not from IJ-NANO parser code). |
| Pinned inputs | Consumed from `evidence/IJEVAL/EA03_N03/pinned/` (raw-file sha256 recorded and matched against the IJ-NANO handoff `package.json`), NOT from the mutable sibling worktree. |

## 2. Common-mode risks (residual, stated honestly)

1. **Shared corpus vocabulary.** The bilingual lexicons (C02 verbs /
   objects, C03 field phrases, C04 constraint grammar, C06 requirement
   phrases, C08 capability phrases, C01/C07 rule tables) were authored
   by reading the PUBLIC corpus. They generalize over the public
   surface, not over arbitrary language. Mitigation: class-F controls
   show unknown surfaces yield NOT_ESTABLISHED (never a fabricated
   VALID); the battery's class-D controls show changed public tasks are
   detected.
2. **Author overlap.** The same lane authors the rule tables and the
   mutation battery; the battery's tie probes deliberately use the
   oracle's own tables to construct the hardest balanced-ambiguity
   inputs (adversarial construction, disclosed in
   `_tie_text`). The GT-D probes were preregistered by the mission
   order (external source), which bounds self-grading.
3. **Single dataset source.** All 160 dev cases originate from one
   builder. The oracle validates the STORED answers against the PUBLIC
   payloads; a builder error that is consistent across both (e.g. a
   systematically wrong reading of an ambiguous instruction) would
   validate. Mitigation: GT-D probes inject exactly such coupled
   corruptions and all are detected because the oracle never trusts the
   stored side; residual risk is semantic misreading of the instruction
   itself, bounded by the bilingual counterexample batteries.
4. **Production-path dual evaluation is not yet exercised end-to-end**
   on physical trials (requires ExecutionAuthorization evidence chain).
   The reference leg is qualified; the production leg lives in the
   IJ-NANO runner (already integrated structurally at AUTH-0). Dual-path
   disagreement → NOT_EVALUABLE is enforced in the runner contract.

## 3. Controls executed (summary)

- 597 mutation controls across classes A–F, 0 escapes
  (`gt_mutation_coverage_dev160.json`).
- 38 GT-D preregistered probes, all detected.
- 40 Obligation-B witnesses (positive / negative-wrong /
  negative-malformed / empty / software-error), 0 failures.
- 21 authorization bypass controls (order §6) incl. real consumer
  integration, 0 escapes.

## 4. Disagreement policy

Reference-vs-production disagreement resolves to NOT_EVALUABLE and
quarantine (never silently to either side); software errors never
become model failures (EMPTY_OUTPUT is its own class). Both are
test-enforced.
