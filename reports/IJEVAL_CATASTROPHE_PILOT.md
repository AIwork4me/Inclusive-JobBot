# Early catastrophe prevention pilot (order section 4)

Date: 2026-11-28. Evidence: `evidence/IJEVAL/EABC/catastrophe_pilot.json`.
Scope: CPU-only INTEGRATED campaign — each fault is activated inside the
real pipeline (trusted evidence registration → execution authorization →
trial loop with canary cadence → dual-path evaluation → sealing →
qualified analysis → publication). This is NOT the EA14 stress campaign
(no 10k-trial claim).

## Result: 13/13 scenarios detected or contained, 0 escapes

| scenario | mechanism | latency (trials after activation) | publication |
| --- | --- | --- | --- |
| N02R dictionary unpacking (original defect) | dual-path disagreement | 11 | BLOCKED_CRITICAL_NOT_EVALUABLE |
| exception masking | software-error class | 1 | BLOCKED_CRITICAL_NOT_EVALUABLE |
| false-positive scoring (any-catalog-member) | canary (C01) | 15 | BLOCKED_INCOMPLETE_ROSTER |
| ground-truth corruption (coupled, production-side) | dual-path disagreement | 1 | BLOCKED_CRITICAL_NOT_EVALUABLE |
| unauthorized fields dropped | canary (C02) | 15 | BLOCKED_INCOMPLETE_ROSTER |
| evidence forgery (artifact tamper) | publication evidence-integrity boundary | — | BLOCKED_EVIDENCE_INTEGRITY |
| qualification issuance without tests | issuance refusal (authority) | 0 dispatched | n/a |
| authorization level mismatch | issuance refusal (purpose binding) | 0 dispatched | n/a |
| stale authorization | recheck refusal (evidence identity) | 0 dispatched | clean panel |
| revocation bypass | issuance refusal (authoritative state) | 0 dispatched | clean panel |
| direct analyzer bypass | untrusted-store refusal | — | clean panel |
| missing artifact | verify/tamper | — | BLOCKED_EVIDENCE_INTEGRITY |
| duplicate artifact | duplicate-trial rejection (denominator safe) | — | clean panel |

"Clean panel" = the fault targeted the authorization/analysis boundary,
so the trial panel itself was clean; the boundary refusal is the
containment.

## System improvements the pilot itself forced (honest findings)

1. **Canary payload completeness.** The first canary implementation
   passed an empty case payload, so family-detection (C03 formfill vs
   formatting) and catalog-dependent evaluator faults could not fire —
   the pilot's false-alarm pattern exposed it. Canaries now execute
   with the real case public payloads and stored expectations.
2. **Full-family sweep per checkpoint.** Rotating one family per
   cadence checkpoint leaves a family-local fault undetected for up to
   N_families × interval trials (measured escape: E01 at >200 trials).
   Every checkpoint now sweeps ALL families, bounding family-fault
   detection latency to one interval (25 trials / 5 minutes).
3. **Canary software-fault semantics.** A production-pipeline exception
   during a canary is a canary FAILURE (never a pass, never a model
   verdict).
4. **Sweep window integrity.** The contamination window clears only
   after an entire sweep passes (an early passing family cannot hide a
   later failing one).

## Guarantee claimed (within the tested scope)

Zero known critical injected defects escaped into qualified publication.
Every scenario either never dispatched (authorization-boundary
refusals), was detected within ≤15 trials of activation (canary or
dual-path), or was contained at the publication boundary
(evidence-integrity checks). All controls are permanent regressions in
`tests/ij_eval_assurance/test_wavec_continuous.py` and
`test_dualpath_waveb.py`.
