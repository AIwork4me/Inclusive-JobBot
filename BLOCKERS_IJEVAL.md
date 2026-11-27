# BLOCKERS — IJ-EVAL-ASSURANCE-1.0

| ID | Description | Status | Impact |
|---|---|---|---|
| IJE-B-001 | No qualified end-to-end business Oracle exists anywhere in the repository (inherited IJN-B-002) | OPEN (inherited, narrowed by EAE scope) | Verdict F (business production qualification) cannot be granted by this mission alone; EA05 dual-path must treat business oracles as a separate qualification scope |
| IJE-B-002 | `jsonschema` pinned in `requirements.lock` but not installed in the active environment (inherited NA-D08 caveat) | OPEN | Schema-validation code paths run the limited-validator fail-closed branch; EAE contract validator must not silently depend on the full library |
| IJE-B-003 | `n02rr_analyze.py` has no statistical eligibility filter (EA00 §2.2 R3) | OPEN — to be closed by EA02 `eligible_for_semantic_statistics` + EA05 differential layer | Any future N02RR-style corpus containing REPLAY_ERROR / EVIDENCE_INCONSISTENT rows would contaminate headline statistics; sealed 1.2R corpus verified unaffected |
