# IJ-EVAL-ASSURANCE — Wave B closure report (EA03–EA08)

Date: 2026-11-28. Scope: production/reference dual-path integration on
the pinned Batch A dev dataset (`d23de5a` snapshot in
`evidence/IJEVAL/EA03_N03/pinned/`). Certificate:
`512efb617a9cb4c8 (scope=semantic aggregation category; capability identity in protocol field — corrected from a capability-named scope that could never match the eligibility lookup)` (scope `N03_BATCH_A_DEV_CPU_DUALPATH`, registry
`evidence/IJEVAL/EA03_N03/certificates/registry.json`, generation 1).

## 1. What was delivered

| Gate | Status | Evidence |
| --- | --- | --- |
| EA03 independent ground truth | GRANTED (73521bb, re-verified this session after the comparator fix: 160/160 VALID, 38/38 GT-D probes, 597/597 mutations) | `ground_truth_qualification_dev160_v2.json`, `gt_mutation_coverage_dev160.json` |
| EA04 production Parser qualification | GRANTED (pinned `parser_semantics.md` @ `58aa790` blob-verified; tokenizer-first rule-table implementation; P-series fault controls) | `pinned/parser_semantics.md`, `faults.py`, campaign below |
| EA05 dual-path response evaluation | GRANTED (unresolved disagreement → NOT_EVALUABLE + quarantine; software/empty/invalid/missing-evidence all distinct classes) | `src/eval_assurance/dualpath.py`, `tests/.../test_dualpath_waveb.py` |
| EA06 independence + common-mode report | GRANTED with disclosed limitations (this report §3; supersedes the EA06 report's "not yet exercised" item) | `reports/IJEVAL_EA06_INDEPENDENCE_RISK.md` + §3 below |
| EA07 witness + mutation coverage | GRANTED with two justified equivalents | `dualpath_witnesses.json`, `production_mutation_campaign.json`, `rule_coverage_matrix.json` |
| EA08 end-to-end evidence qualification | GRANTED (6/6 controls) | `ea08_end_to_end.json` |

## 2. Control totals (original 500-control proposal reconciled)

| Category | Count | Reused from |
| --- | --- | --- |
| Ground-truth semantic controls (classes A–F) | 597 | EA03-A v2 (reused unchanged; truth rules) |
| GT-D preregistered probes | 38 | EA03-A v2 |
| Obligation-B response witnesses | 40 | EA03-B (reused; reference path) |
| **Dual-path witnesses (new, integrated path)** | **116** | this session, every dev family of C01–C08 |
| **Production-logic faults (new)** | **20** | this session (18 detected, 2 EQUIVALENT with recorded dataset-specific justifications: `P14_empty_list_not_explicit`, `E05_alternatives_ignored`) |
| **EA08 evidence-integrity controls (new)** | **6** | X01–X07 |
| Total | 817 | — |

The GT controls are NOT counted as substitutes for the new categories:
parser, response-evaluation, and evidence-integrity rules are covered by
the new controls mapped rule-by-rule in `rule_coverage_matrix.json`
(25 rule rows). No redundant witness inflation — equivalents are
declared, not faked as detections.

## 3. Independence and common-mode risk (update to the EA06 report)

Independent: the reference leg (interpreter + oracle) imports no
production code and no IJ-NANO code (test-enforced); the production leg
(parser + evaluator over STORED expectations) imports no reference code
(test-enforced); oracle and evaluator files are digest-distinct
(certificate-enforced).

Common-mode risks, honestly stated:

1. **Shared pinned spec authorship.** Production parser and reference
   interpreter are two implementations of the SAME
   `parser_semantics.md` text, both authored by this lane. Structural
   independence (tokenizer/rule-table vs function-tree) is enforced and
   disclosed; spec-level misreading would affect both legs. Mitigated
   by: GT-side independence (truth derives from public payloads), the
   20 production-logic faults being detected through disagreement, and
   the GT-D coupled-corruption probes.
2. **Empty-truth formatting limitation.** A C03 formatting case whose
   ground truth is an empty line list cannot be scored CORRECT under
   the pinned output contract (the only surface for an empty result is
   an empty response, which is EMPTY_OUTPUT by contract). 2/160 dev
   cases are affected; both paths agree; disclosed, not normalized
   away.
3. **Two equivalent mutants** (P14/E05) with dataset-specific
   justifications recorded in the campaign artifact; the controls stay
   active for future datasets.
4. **Single dataset source / author overlap** — carried over from the
   EA06 report unchanged.

## 4. Defect found and reconciled (IJE-WB-D01)

The dual-path formfill witnesses exposed a real reference-path defect:
`oracle._compare_typed` compared the interpreter's raw single-field
dict against the derived `{field, value}` record shape, scoring every
CORRECT formfill answer INCORRECT (all 20 dev formfill cases). Fixed
with exact `(field, value)` pair comparison on both legs; verified:
158/160 positive witnesses CORRECT (2 EMPTY_OUTPUT empty-truth cases,
agreed), full GT battery re-run with zero regression. Record:
`dualpath_reconciliation.json`. Prior reported numbers unchanged.

## 5. Scope boundaries (what these gates do NOT grant)

- No all-32 cognitive qualification (Batch A C01–C08 dev only).
- No physical-runner qualification (ExecutionAuthorization stays
  fail-closed until the Wave C chain registers evidence).
- No confirmation-split coverage (protected expectations are
  hash-committed only).
- The runner-side integration of the production leg happens through
  the pinned-revision consumer contract (coordination note on
  Issue #12).
