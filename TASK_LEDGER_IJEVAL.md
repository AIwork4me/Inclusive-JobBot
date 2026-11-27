# TASK LEDGER — IJ-EVAL-ASSURANCE-1.0

| Task | Status | Evidence | Notes |
|---|---|---|---|
| Preregistration: mission order saved verbatim | DONE (0ab5c6b) | `docs/IJEVAL_MISSION_ORDER.md` | publish gate PASS (0 findings) |
| Branch + tracking issue #12 + Draft PR #13 | DONE | GitHub | base `codex/ij0-tool-calling`, from audited `bc4555e` |
| EA00 repository/state audit | DONE | this ledger + `MISSION_STATE_IJEVAL.json` | PR heads verified vs remote at start |
| EA00 §2.2 N02RR residual-risk reproduction | DONE (f081655) | `evidence/IJEVAL/EA00/n02rr_residual_risk_reproduction.json` | R1/R2/R3 reproduced; sealed corpus zero-risk rows; structural only |
| EA00 §2.1 historical defect inventory (EV/NA-D/PR-D/RS + cross-mission) | DONE (6d7b24e) | `evidence/IJEVAL/EA00/historical_defect_inventory.json` (67 records) | incl. 38 cross-mission; IJSDK-D01/D02/D03 unrepaired |
| EA00 audit report | DONE (6d7b24e) | `reports/IJEVAL_00_HISTORICAL_EVALUATION_AUDIT.md` | gate claimed, IJ-SLM scope limitation noted |
| EA01 threat model + FMEA matrix | DONE (84c5ac2) | `reports/IJEVAL_01_EVALUATION_THREAT_MODEL.md`, `evidence/IJEVAL/EA01/failure_mode_matrix.json` | 48 modes / 38 critical / 27 layers |
| EA02 typed evaluation contract | DONE (e2467f4) | `src/eval_assurance/contracts/` + adapters + `docs/IJEVAL_RESULT_CONTRACT.md` | 27/27 tests; ij_nano suite 213/213 OK; IJE-D001/D002 closed at interface |
| EA02-R contract hardening (EA-D01..D06) | DONE | `reports/IJEVAL_02R_CONTRACT_HARDENING.md`, `evidence/IJEVAL/EA02R/` (red/green/state-space/defect ledger) | 68/68 + 213/213 tests; gate EA02R_EVALUATION_CONTRACT_INVARIANTS_GO granted; contract spec v1.1.0; pubgate replaces piped gate invocations |
| Wave B/C boundary hardening (EA-R01..R04) | DONE | `reports/IJEVAL_WAVEBC_HARDENING.md`, `evidence/IJEVAL/EABC/` | 95/95 + 213/213; authority issuance, byte-verified receipts, hardened publication chain, snapshot recheck |
| EA03 dataset qualification engine | PENDING | — | Wave B proper; N02R suite + N03 C01–C32 targets; issue through the trusted boundary |
