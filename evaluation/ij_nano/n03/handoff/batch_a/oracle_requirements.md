# Batch A independent Oracle requirements (C01–C08) — for EA05 qualification

Consumer: IJ-EVAL-ASSURANCE (PR #13). The reference path (Independent
Interpreter -> Reference Oracle) must derive verdicts WITHOUT importing
IJ-NANO production or dataset-builder code. What each primitive's Oracle
must implement, from the pinned public artifacts alone plus the case's
protected/dev expectation record:

- **C01**: label equality against the expectation label, with the catalog
  membership check against the case's public `intent_catalog`.
- **C02**: field-by-field comparison with declared normalization
  (ISO deadline; unknown flags consistent with nulls). Partial credit is
  NOT defined: all five fields must match (or declared-equivalent).
- **C03 formatting**: canonical line-set/sequence comparison after
  whitespace normalization; uppercase per instruction; zh cases never
  require uppercase (design constraint recorded in the build).
  **formfill**: single-field equality. **oneedit**: exact line equality.
- **C04**: id-set equality; when the instruction declares a sort, sequence
  equality with ties allowed only where the build declares tie freedom.
- **C05**: boolean equality (the build's predicates are recomputable from
  the public policy + facts; the Oracle SHOULD recompute rather than trust
  the stored expectation — this is the dual-path discriminator for C05).
- **C06**: id equality; tie sets accepted exactly where the case declares
  alternatives (stored in the expectation's `alternatives`).
- **C07**: catalog-name equality (verbatim, case-normalized).
- **C08**: tool-id equality; the Oracle should additionally verify the
  serving tool is the unique capability superset when consuming the
  protected construction record (double-derivation, matches the dataset
  verifier's algebra).

## Verdict contract

- Semantic verdict per trial: CORRECT / INCORRECT / NOT_EVALUABLE.
- Production/reference disagreement -> NOT_EVALUABLE + quarantine
  (never silently resolved to either side).
- The Oracle must not read model-facing prompt constructions; it consumes
  the raw response artifact + the case expectation + the public payload.
