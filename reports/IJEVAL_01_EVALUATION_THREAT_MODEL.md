# IJEVAL_01 — Evaluation Threat Model and Failure Model (IJ-EVAL-ASSURANCE-1.0, EA01)

Status: COMPLETE (gate `EA01_EVALUATION_FAILURE_MODEL_COMPLETE` claim)
Date: 2026-11-28 · Matrix: `evidence/IJEVAL/EA01/failure_mode_matrix.json`
(generator `scripts/ij_eval_assurance/ea01_failure_model.py`, 48 modes, 38
critical, all 27 pipeline layers covered)

## 1. Method

The evidence-to-verdict pipeline is modeled as the 27 layers of mission order
§3 (task specification → dataset generation → … → reward generation →
publication). Each layer was assessed against the 12 failure classes of the
order (accidental, common-mode, false positive, false negative, silent data
loss, corrupted evidence, version incompatibility, hidden-answer leakage,
reward hacking, unauthorized state effect, incorrect recovery,
malicious/malformed input). Every mode carries the mandatory FMEA
prioritization (severity 1–5, potential affected trial count, detectability,
recoverability, downstream contamination risk) and the five-part control
mapping (preventive control, detection mechanism, containment action,
regression test, qualification requirement).

The model is **evidence-anchored, not hypothetical**: 26 of the 48 modes cite
a historical realization from the EA00 inventory (RS01, IJE-D001/D002,
IJSDK-D01/D02/D03, EV02/04/05, PR-D01/04/08, ORC-1, ORC-V2-b, RS02, RS04,
RS07, HA-4/5, TC-V1-d, IJ06 parser, D-010, RC-11, J-3, A1-16 …). Modes
without a historical realization (chiefly L26 reward-hacking family) are
preregistered for EA16.

## 2. Top-priority findings (severity ≥ 4 ranked by contamination × detectability difficulty)

1. **FM for L23 "unevaluable rows enter semantic rates"** (IJE-D001/R3) — the
   hardest-to-detect critical class: the verdict *field* looks perfectly
   normal; only contract-level eligibility logic catches it. Realized
   historically in three missions (RS01; IJ06-RS-1/2; IJSDK-D02). Primary EAE
   answer: EA02 `eligible_for_semantic_statistics` as the single consumption
   path + EA09 in-flight NOT_EVALUABLE canaries.
2. **Common-mode evaluator defects (L03/L16)** — a second evaluator that
   merely calls the first (or shares its comparator) provides zero protection;
   AEVE judge agreement failures (alpha ≤ 0.211) and Atlas A1-16
   single-source ground truth are the historical proof. EA05 independence
   analysis with shared-component disclosure is mandatory, and the claimed
   independence scope must shrink when components are shared.
3. **Qualification-gate self-defects (L25, IJSDK-D01)** — a gate that reads
   PASS beside `all_negatives_rejected=false` certifies weakened oracles.
   EAE gates must be validated by *weakened-oracle batteries* (deliberately
   broken candidates MUST fail), not by positive controls alone.
4. **Exception masking (L13/L17, IJE-D001)** — broad `except` plus a boolean
   verdict field converts software failure into model failure. Typed status
   separation (INV01/INV02) is the only structural fix; labeling without
   consumption-side enforcement proved insufficient (EA00 §2.2 R3).
5. **Business-state non-verification (L18, IJSDK-D03)** — `final_state_hash`
  unread; unauthorized writes score PASS. INV09 requires safety verdict
  computed independently of text plausibility.
6. **Hidden-answer leakage (L02/L03)** — holdout overlap and expectation
  leakage into prompts/tools; both historically present or near-missed;
  EA06 leakage witnesses + EA13 enforced access boundaries.

## 3. Detectability ranking (drives EA09 canary design)

- **Low detectability, high impact** (must be covered by *proactive* controls
  because nothing in normal output signals them): expectation errors,
  common-mode reference defects, leakage, exception masking, unevaluable-row
  ingestion, substring-match false positives, qualification self-defects.
- **Medium**: transport error-shapes, applicability gaps, identity/version
  drift, resume contamination, denominator inflation.
- **High**: publication hygiene (already gated by `publish_check.py`).

EA09 preflight must therefore exercise: positive/negative golden witnesses,
evidence-integrity controls, production/reference agreement, and
deliberately-weakened-evaluator rejection — the four families that cover every
low-detectability critical mode.

## 4. Contamination-window policy input (for EA10)

Modes with delayed detection (L12/L13/L17/L23) contaminate *retroactively*
until the last trusted checkpoint; modes with immediate signals (L08
transport, L10 capture) contaminate only forward. The matrix's
`recoverability` field records whether original artifacts survive: all
historical catastrophes were recoverable *only* because raw artifacts were
preserved — making EA08's complete-capture requirement the highest-leverage
prevention in the model.

## 5. Residual limitations

- 48 modes is a curated set, not an exhaustive enumeration; EA07 mutation
  testing and EA14 fault injection will surface unanticipated classes, which
  must be folded back into this matrix (matrix is versioned, INV07 applies).
- Malicious-adversary modeling (beyond malformed inputs) is limited to the
  L26 reward-hacking family, per mission scope; a full red-team threat model
  of the EAE itself is out of scope for EA01.

## 6. Reproduction

```bash
python -I scripts/ij_eval_assurance/ea01_failure_model.py
```
