# Batch A dataset — known limitations (honest scope declaration)

1. **Dual-implementation independence for C01/C02/C07.** Truth for the
   construction-authored primitives is verified by separately coded rule
   tables plus a 240/240 mutation battery — not by recomputation from the
   public payload alone (which holds for C03/C04/C05/C06/C08). The rule
   tables were written from the same semantic contracts as the builders.
2. **Language asymmetry in C03.** Uppercase requirements are undefined for
   Chinese surfaces; zh formatting cases use in-stock / not-in-stock
   semantics without case transformation. This is a recorded design
   constraint, not silent scope reduction of the primitive.
3. **One confirmation family per primitive.** The 10 confirmation cases per
   primitive come from one dedicated family (family-level split). Broader
   confirmation-family coverage requires dataset growth beyond the frozen
   640/320 budget and is a future-scoped decision, not a silent change.
4. **C08 distractor quality.** Large inventories (32/64) include minted
   single-capability distractors ("handles X only"); retrieval difficulty
   is controlled by size and tag overlap, but no human-plausibility rating
   was applied.
5. **Boundary-case coverage.** At-threshold and tie cases exist (C04 ties,
   C05 thresholds, C06 declared ties) but are not exhaustive; the B3
   boundary battery grows with each batch.
6. **Reference models not pinned.** The 8B/14B S7C reference identities are
   NOT pinned in the model registry yet; they never contribute to the
   primary denominator.
7. **Trust boundary of confirmation protection.** Single-user OS with no
   OS-level sandbox: protection is directory separation + git exclusion +
   hash-only committed manifests + leakage tests. Strong isolation is not
   claimed (IJ-NANO-1.3S order section 6 requires this statement).
8. **No EA03–EA08 claims.** This package provides inputs FOR IJEVAL
   qualification. Nothing here grants any EA gate; that is the IJEVAL
   lane's independent decision.
