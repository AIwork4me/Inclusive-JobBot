# TASK LEDGER — IJ-EVAL-ASSURANCE-1.0

| Task | Status | Evidence | Notes |
|---|---|---|---|
| Preregistration: mission order saved verbatim | DONE (0ab5c6b) | `docs/IJEVAL_MISSION_ORDER.md` | publish gate PASS (0 findings) |
| Branch + tracking issue #12 + Draft PR #13 | DONE | GitHub | base `codex/ij0-tool-calling`, from audited `bc4555e` |
| EA00 repository/state audit | DONE | this ledger + `MISSION_STATE_IJEVAL.json` | PR heads verified vs remote at start |
| EA00 §2.2 N02RR residual-risk reproduction | DONE (f081655) | `evidence/IJEVAL/EA00/n02rr_residual_risk_reproduction.json` | R1/R2/R3 reproduced; sealed corpus zero-risk rows; structural only |
| EA00 §2.1 historical defect inventory (EV/NA-D/PR-D/RS + cross-mission) | IN_PROGRESS | `evidence/IJEVAL/EA00/historical_defect_inventory.json` (pending) | IJ-NANO families swept; Atlas/IJ-SLM/IJ-SDK sweep running |
| EA00 audit report | PENDING | `reports/IJEVAL_00_HISTORICAL_EVALUATION_AUDIT.md` | after cross-mission sweep returns |
| EA01 threat model + FMEA matrix | PENDING | `reports/IJEVAL_01_EVALUATION_THREAT_MODEL.md`, `evidence/IJEVAL/EA01/failure_mode_matrix.json` | |
| EA02 typed evaluation contract | PENDING | `src/eval_assurance/contracts/` + tests | must carry the EA02.4 eligibility function that closes the §2.2 finding |
