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
| N03 coordination: compatibility contract v1.0.0 | DONE | `docs/IJEVAL_COMPATIBILITY_CONTRACT.md`, `evidence/IJEVAL/COMPAT/contract_v1.0.0.json` | 11 interfaces / 10 sections; RunnerAuthorization machine-readable; conformance-enforced |
| N03 Batch A intake verification | DONE | `evidence/IJEVAL/EA03_N03/intake_verification.json` | pinned d23de5a; canonical public digest 93c58566 verified; 240/160/80 structure verified; protected manifest digest-verified without content access |
| EA03 independent oracles C01–C08 | PENDING | `src/eval_assurance/reference/oracle.py` (spec: IJNANO handoff/batch_a/oracle_requirements.md) | C03-C08 recomputable; C01/C02/C07 adjudication; disagreement -> NOT_EVALUABLE |
| Execution/Publication authorization split | PENDING | compat v1.1.0 | 16 bypass controls per order section 6 |

## 2026-11-28 — EA03-A v2 / EA05-B reference / compat v1.1.0 (DONE)

| item | result |
| --- | --- |
| GT-D01..GT-D05 probes | 38/38 detected |
| Corrected qualification (dev 160) | 160 VALID / 0 INVALID / 0 AMBIGUOUS / 0 NOT_ESTABLISHED |
| Mutation battery classes A-F | 597 applicable, 0 escapes |
| Reconciliation vs historical 133/27 | 27 NE->VALID, 0 silent removals, 0 correction requests |
| Obligation B witnesses | 40/40 (positive/negative/empty/software-error) |
| Authorization bypass controls | 16/16 incl. real consumer integration |
| Tests | ij_eval_assurance 150/150; repo 306/307 (1 pre-existing env failure) |

## 2026-11-28 — Wave B closure (EA03–EA08) + auth-semantics correction

| item | result |
| --- | --- |
| AUTH semantics correction (order §3.1) | CONFIRMATION_LEVEL AUTH-2→AUTH-3 per frozen IJ-NANO-1.3S contract; mismatch reproduced red at 9c73bbf; symmetric enforcement + roster_split binding; controls 15-corrected + 17; contract artifact v1.1.1 |
| Production leg (EA04) | production/parser.py + production/evaluator.py implementing pinned parser_semantics.md (blob-verified @ 58aa790); tokenizer/rule-table structure, stored-expectation typed comparison |
| Dual-path integration (EA05) | src/eval_assurance/dualpath.py; disagreement→NOT_EVALUABLE+quarantine; EMPTY/INVALID/software/MISSING_EVIDENCE all distinct; content-addressed artifacts + offline replay; duplicate rejection preserves originals; crash-safe exact resume |
| Dual-path witnesses (EA07) | 116/116 passed through the actual integrated path (every dev family; kinds incl. extra-field, missing-field, flags-flip, multiline, dup-key, fenced) |
| Production-logic mutations (EA07) | 20 faults: 18 detected, 2 EQUIVALENT with dataset-specific justifications, 0 escapes |
| EA08 evidence controls | 6/6 (duplicate, resume, replay, tamper, missing-vs-empty, receipts) |
| GT battery re-run after IJE-WB-D01 fix | 160/160 VALID, 38/38 probes, 597/597 mutations, 40/40 obligation-B — zero regression |
| Coverage matrix | 25 rule rows; 817 total controls vs original 500-proposal, categories reconciled (GT reuse ≠ substitution) |
| Certificate | 512efb617a9cb4c8 (scope=semantic aggregation category; capability identity in protocol field — corrected from a capability-named scope that could never match the eligibility lookup) (N03_BATCH_A_DEV_CPU_DUALPATH) via real QualificationAuthority, persisted registry |
| Tests | ij_eval_assurance 168+18 new = full suite green at commit time (see pubgate receipt) |

## 2026-11-28 — Wave C + catastrophe pilot

| item | result |
| --- | --- |
| §3.2 authoritative qualification state | durable checksummed revocation+evidence-generation file; consult() pre-dispatch; restart-safe; tamper-fail-closed; 11/11 revocation scenarios as permanent controls |
| §3.3 trusted ExecutionEvidence | register_trusted_execution_evidence derives every flag from digest-verified artifacts; caller ACCEPTED/booleans rejected; experiment-identity + auth-purpose binding; evidence identity → stale-authorization refusal |
| §3.4 EA09 canary | full-family sweep per checkpoint (pilot-forced fix); cadence preflight/before-change/25-trials-or-5min/after-resume/before-seal/before-publication; CANARY_CONTROL never in denominators |
| §3.5 EA10 breaker | durable, restart-safe, in-flight accounting, contamination quarantine, evidence preservation, requalification-only recovery |
| §3.6 EA11 analyzer | dual-path session → typed records → formal boundary; verified envelopes; roster reconciliation; partial scopes; final-boundary revocation recheck; tamper blocking |
| Catastrophe pilot (order §4) | 13/13 detected/contained, 0 escapes; latencies: N02R 11, exception masking 1, false-positive 15, GT corruption 1; 2 system fixes forced by the pilot (canary payload completeness, full-family sweep) |
| Tests | 196/196 ij_eval_assurance at commit time |
