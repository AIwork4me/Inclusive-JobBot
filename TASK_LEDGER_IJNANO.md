# IJ-NANO-1.0 Task Ledger

Mission-specific ledger (see `MISSION_STATE_IJNANO.json`). Earlier missions'
`TASK_LEDGER.md` / `TASK_LEDGER_IJSDK.md` are never edited by IJ-NANO.
Status vocabulary: `PASS`, `FAIL`, `BLOCKED`, `NOT_RUN`.

| Phase | Task | Progress | Status | Evidence |
|---|---|---|---|---|
| N00 | Read governing files on all mission lines: AGENTS.md, HANDOFF.md, MISSION_STATE.json (default + ij-slm branch), MISSION_STATE_IJSDK.json, TASK_LEDGER.md/TASK_LEDGER_IJSDK.md, BLOCKERS.md, DECISIONS.md | done | PASS | audit recorded in `reports/IJNANO_00_BASELINE_AND_DEPENDENCY_AUDIT.md` |
| N00 | Re-query live remote (gh api): PRs #2/#4/#6/#8/#9, issues #1/#3/#5/#7; compare against mission-order anchors | done | PASS | `evidence/IJNANO/N00/baseline_manifest.json` (mission_order_historical_anchors) |
| N00 | Audit previously unreported PR #9 (IJ-SLM-1.0): scope, stacking (on PR #6 head), GPU-priority claim, execution state | done | PASS | `evidence/IJNANO/N00/baseline_manifest.json` (gpu_lease_determination) |
| N00 | Verify physical GPU identity and running processes on this workstation | done | PASS | RX 7900 XTX (gfx1100), driver 32.0.21030.2001; no llama/python processes |
| N00 | Verify branch topology: fe56f324 ancestor of PR #8 head; PR #6 head not an ancestor of PR #8 head; PR #6 head ancestor of ij-slm | done | PASS | `evidence/IJNANO/N00/baseline_manifest.json` (ancestry_verified) |
| N00 | Verify on-disk assets: S1/S2/S3/R1/R2 GGUF weights, llama.cpp cpu/vulkan/rocm installs, admission evidence (digest source: models/ij_sdk/model_manifest.json @ base) | done | PASS (identities recorded; disk re-verification deferred to N02 by design) | `evidence/IJNANO/N00/baseline_manifest.json` (physical_assets_verified) |
| N00 | Dependency qualification: IJ-SDK P0/P0R/P1/P2 reusable scopes; P3/P4-core/P5 NOT inherited; P4A code REFERENCE_ONLY; IJ-SLM coordination; formal GPU matrix not authorized | done | PASS | `evidence/IJNANO/N00/dependency_qualification.json` |
| N00 | Isolation: dedicated worktree, branch `mission/ij-nano-1.0-slm-native-agentic-runtime` at `56c6c74b` (PR #8 head at audit), upstream tracking pushed normally, no rebase policy recorded | done | PASS | `evidence/IJNANO/N00/baseline_manifest.json` (ij_nano_isolation) |
| N00 | Commit verbatim mission order as preregistration + research protocol doc | done | PASS | `docs/IJNANO_MISSION_ORDER.md`, `docs/IJNANO_RESEARCH_PROTOCOL.md` |
| N00 | Mission state files created (this ledger, MISSION_STATE_IJNANO.json, BLOCKERS_IJNANO.md, HANDOFF_IJNANO.md) | done | PASS | files at repository root |
| N00 | Tracking Issue + Draft PR created on GitHub | done | PASS | issue #10, draft PR #11 (base: default branch; stacking documentary, mission-only diff `git diff 56c6c74...mission/ij-nano-1.0-slm-native-agentic-runtime`) |
| N00 | Gate `N00_RESEARCH_BASELINE_FROZEN` | done | PASS | `reports/IJNANO_00_BASELINE_AND_DEPENDENCY_AUDIT.md` §9 |

## N00R (2026-11-27, done)

| Phase | Task | Progress | Status | Evidence |
|---|---|---|---|---|
| N00R | Re-query PR #9 live state; confirm audited HEAD `364c7ca` (updated 10:23:34Z; local ref synced) | done | PASS | `evidence/IJNANO/N00R/gpu_identity_comparison.json` (ij_slm_published_identity) |
| N00R | Read IJ-SLM identity evidence: `atlas/slm/v1.0/environment.json`, `evidence/IJ073/aeve/gpu_handoff.json`, sealed IJSLM tc-v3 run manifest | done | PASS | same; 8060S / gfx1151 / driver 32.0.22018.5 / Ryzen AI MAX+ PRO 395 host |
| N00R | Independent local identity: PCI `VEN_1002&DEV_744C&SUBSYS_0E3B1002&REV_C8`, gfx1100, driver 32.0.21030.2001, i7-13700K/B760M, host UUID hash 16-prefix, Vulkan0 device report cross-checked against IJ-SDK P1 | done | PASS | `evidence/IJNANO/N00R/gpu_identity_comparison.json` (local_workstation_identity) |
| N00R | Verdict `CROSS_HOST_GPU_LEASE_CONFLICT_RESOLVED`; IJ-SLM lease untouched | done | PASS | same (comparison, verdict) |
| N00R | Local lease: reuse existing host-wide protocol `benchmarks/root_cause/gpu_lease.py`; probe `ACQUIRED_FREE` + clean release at 11:20:07Z; IJ-SDK-1.1 idle, no reservation | done | PASS | `evidence/IJNANO/N00R/lease_scope_decision.json` |
| N00R | Verdict `LOCAL_GPU_LEASE_AVAILABLE`; no mission-specific mutex created | done | PASS | same |
| N00R | Dependency scope correction: formal-matrix non-authorization scoped to IJ-SDK's unqualified benchmark/evaluator; physical admission/microbenchmarks/diagnostics proceed under own qualification; DEP-03 reference fixed (IJN-B-005 → IJN-B-003); `superseded_by_n00r` block added | done | PASS | `evidence/IJNANO/N00/dependency_qualification.json`, `evidence/IJNANO/N00R/lease_scope_decision.json` (dependency_scope_correction) |
| N00R | Blockers updated: IJN-B-001 CLOSED, IJN-B-002 narrowed to formal business claims; shared evaluation architecture adopted | done | PASS | `BLOCKERS_IJNANO.md` |
| N00R | N00R report | done | PASS | `reports/IJNANO_00R_RESOURCE_AND_DEPENDENCY_RECONCILIATION.md` |

## N00RR (2026-11-27, IJ-NANO-1.1, done)

| Phase | Task | Progress | Status | Evidence |
|---|---|---|---|---|
| N00RR | Reconcile HEAD against audited anchor `f3d5817f` (local == origin; clean tree; no completed work restarted) | done | PASS | `git rev-parse HEAD origin/mission/ij-nano-1.0-slm-native-agentic-runtime` (identical) |
| N00RR | Commit IJ-NANO-1.1 mission order verbatim (preregistration) | done | PASS | `docs/IJNANO_MISSION_ORDER_V1_1.md` |
| N00RR | Correct stale records: N01 catalog row (catalog was committed at `f3d5817`), N02 heading/progress, N06 Layer-A software progress split from the N06 gate, HANDOFF refresh | done | PASS | this file; `MISSION_STATE_IJNANO.json` |
| N00RR | Update PR #11 description (old GPU blocker -> N00R resolution + N02 PASS + scoped status) | done | PASS | PR #11 body |
| N00RR | IJ-SLM-1.0 remote advanced `364c7ca..a34aae7`; confirmed untouched | done | PASS | `git fetch` record in N00RR notes |

## N01 (2026-11-27, done)

| Phase | Task | Progress | Status | Evidence |
|---|---|---|---|---|
| N01 | Primary-source verification R01-R09 via four parallel research agents (papers, repos, licenses, models, mechanisms, statistics) | done | PASS (verification sweeps; consolidation pending) | `evidence/IJNANO/N01/agent_reports/{R01_R04,R02_R08,R03_R05_R06,R07_R09}_verification.md` |
| N01 | research_catalog.json (all subjects + cross-cutting answers; committed at `f3d5817`; ledger row corrected at N00RR) | done | PASS | `evidence/IJNANO/N01/research_catalog.json` |
| N01 | license_matrix.json (18 entries incl. MODEL-S2 LFM revenue-conditioned line, TB2 UNLICENSED, PTC paper CC BY-NC-SA) | done | PASS | `evidence/IJNANO/N01/license_matrix.json` |
| N01 | Landscape reports CN/EN (content-equivalent; per-subject evidence + 4 distinction tables + 10-axis component comparison + honest conclusions) | done | PASS | `reports/IJNANO_01_RESEARCH_LANDSCAPE_{EN,CN}.md` |
| N01 | Component-level reuse decision (6 components; capability-dependent bindings deferred to N02R/N03 with explicit change-triggers) | done | PASS | `reports/IJNANO_OPEN_SOURCE_REUSE_DECISION.md` |
| N01 | Gate `N01_RESEARCH_LANDSCAPE_VERIFIED` (documentation scope; all candidate validations NOT_RUN, preserved) | done | PASS | gate recorded in `MISSION_STATE_IJNANO.json` |

## N02 (2026-11-27, done)

| Phase | Task | Progress | Status | Evidence |
|---|---|---|---|---|
| N02 | Fresh SHA256 verification: 10/10 weight files MATCH committed manifest; 95 engine binaries hashed (cpu/vulkan/rocm) | done | PASS | `evidence/IJNANO/N02/identity_verification.json`, `benchmarks/ij_nano/verify_model_identities.py` |
| N02 | Engine provisioned via gitignored junctions (b12359 verified: `build 12359, commit b1b770d90`) | done | PASS | `.runtime/n02/make_junctions.ps1` (local); runtime/llama-cpp/README conventions |
| N02 | Admission smokes under host-wide lease (S1,S2,S3d,R1,R2; vulkan) — all 9/10, D-010 offload proof per model | done | PASS | `evidence/IJNANO/N02/admission/*.json`, `evidence/IJNANO/N02/session_record.json` |
| N02 | Protocol probe v3: health/socket, D-010 offload, generation+usage, native tool-call, chat json_schema (strict, 1024), GBNF charclass, escaped-quote engine record, /completion json_schema, SSE streaming, cancellation | done | PASS (S1/S3/R1/R2 overall PASS; S2 protocol-surface PASS + chat-path reasoning-burn model-behavior finding recorded) | `evidence/IJNANO/N02/protocol/*.json`, `benchmarks/ij_nano/n02_protocol_probe.py` |
| N02 | Gate `N02_PHYSICAL_MODEL_RUNTIME_QUALIFIED` (runtime/protocol scope only; ROCm comparator and Q4 sensitivity explicitly NOT_RUN) | done | PASS | `reports/IJNANO_02_PHYSICAL_RUNTIME_QUALIFICATION.md` |

## N06/N07 Layer A (software scope only; recorded separately from the N06 Runtime gate, which stays NOT_RUN)

| Phase | Task | Progress | Status | Evidence |
|---|---|---|---|---|
| N06 | Layer A execution-integrity core: BudgetController (D05), EventLog hash-chain+seal (D07), TypedTaskState complete-reset+epoch-abort (D04), SafeToolGateway fixed-order transactions (D06), checkpoint/cancellation | done (software) | PASS under unittest (software scope only; NOT a Runtime qualification) | `src/nanoagent/{core,gateway}/`, `tests/ij_nano/` |
| N06 | Layer A regression suite: 36 tests green (`python -I -m unittest discover -s tests/ij_nano -t .`); IJ-SDK suite unaffected (93 OK) | done | PASS | test run recorded in this row; rerun command in HANDOFF |
| N06A-R | IJ-NANO-1.1 adversarial hardening NA-D01..NA-D08 (red reproduction -> minimal repair -> green regression -> negative controls) | done | PASS (gate `NANOAGENT_LAYER_A_SOFTWARE_INTEGRITY_GO`, software scope; red 54 -> green 119/119 + IJ-SDK 93 OK) | `reports/IJNANO_06A_RUNTIME_INTEGRITY_HARDENING.md`, `evidence/IJNANO/N06A-R/{defect_ledger,regression_results}.json`, `evidence/IJNANO/N06A-R/{red_run,green_run}.txt` |
| N06/N07 | Layers B (context compiler, tool filtering, grammar, slot binding) and C (action graph, recovery, goal controller) | not started | NOT_RUN | — |

## N05A (2026-11-27, IJ-NANO-1.1, done)

| Phase | Task | Progress | Status | Evidence |
|---|---|---|---|---|
| N05A | Typed evaluation contracts for the 12 cognitive families (intent, goal, tool selection, action representation, entity reference, slot value, numeric value+unit, state interpretation, conditional branch, recovery action, stop/continue, clarification); expectations evaluator-side only, Responses carry no answers | done | PASS (software scope) | `src/nanoagent/eval/contracts.py` |
| N05A | Deterministic semantic comparators (closed-vocab folding, entity identity, dimension-checked unit registry, typed predicates, polarity handling); substring matching never primary | done | PASS | `src/nanoagent/eval/comparators.py` |
| N05A | Control battery: 17 positives + 24 single-defect negatives (16 reason codes) covering every mission-order control class; every negative fails for exactly its intended reason | done | PASS | `src/nanoagent/eval/controls.py`, `tests/ij_nano/test_n05a_battery.py` |
| N05A | Mutation tests: every scoring rule load-bearing (drop-one-rule mutants detected; substring/unit-blind/polarity-blind mutants demonstrated) | done | PASS | `tests/ij_nano/test_n05a_mutation.py` |
| N05A | Coverage published per family | done | PASS | `evidence/IJNANO/N05A/evaluator_coverage.json` |
| N05A | Gate `N05A_COGNITIVE_EVALUATOR_QUALIFIED` (scoped; explicitly NOT the business Oracle) | done | PASS | `reports/IJNANO_05A_COGNITIVE_EVALUATOR_QUALIFICATION.md` |

## N1.2R (2026-11-27, IJ-NANO-1.2 resume, done)

| Phase | Task | Progress | Status | Evidence |
|---|---|---|---|---|
| N1.2R | Reconcile HEAD against audited checkpoint `dfce2952` (local == origin, clean tree, no completed phase restarted) | done | PASS | `git rev-parse HEAD origin/mission/ij-nano-1.0-slm-native-agentic-runtime` (identical: dfce2952accb48c177bd4798cc23bd425c88a9ca) |
| N1.2R | Verify live git/GitHub identities (AIwork4me; gh auth active) and remote URL | done | PASS | `git config user.name/email`, `gh auth status` |
| N1.2R | Commit IJ-NANO-1.2 mission order verbatim (preregistration) | done | PASS | `docs/IJNANO_MISSION_ORDER_V1_2.md` |
| N1.2R | Verify preserved artifacts: N00/N00R/N00RR evidence, N01 closure, N02 admission evidence, N06A-R red/green, N05A qualification, raw S2 protocol artifact `overall: FAIL` | done | PASS | `evidence/IJNANO/{N00,N00R,N01,N02,N05A,N06A-R}/`, `evidence/IJNANO/N02/protocol/S2.json` |
| N1.2R | Physical preconditions observed: no llama-server running; GPU present (RX 7900 XTX, driver 32.0.21030.2001); model hashes + engine identity to be reverified fresh at first physical execution (N02R) per HANDOFF §4 | done | PASS | this row; N02R will record fresh hashes |

## N05AR (2026-11-27, IJ-NANO-1.2, done)

| Phase | Task | Progress | Status | Evidence |
|---|---|---|---|---|
| N05AR | Red reproduction of all seven source-review concerns (EV01-EV07) against the pre-repair evaluator (detached worktree at f62ddc2) BEFORE any implementation change | done | PASS (31/45 distinct red tests; 14 anchors green) | `evidence/IJNANO/N05AR/red_run.txt`, `tests/ij_nano/test_n05ar_ev_concerns.py` |
| N05AR | EV01 identity-keyed state predicates: missing/duplicate/contradictory detection, order independence, single-reason attribution | done | PASS | `src/nanoagent/eval/comparators.py` (eval_state_interpretation), controls `state.neg.*`, `state.pos.{multi,reordered}` |
| N05AR | EV02 undeclared arguments: ARGUMENT_UNDECLARED from response.args alone, optional-argument contract, duplicate raw-key PARSE_INVALID gate | done | PASS | `comparators.py` (eval_action_representation/eval_slot_value/_raw_reasons), `contracts.py` (SlotSpec.optional), controls `action.neg.{undeclared_arg,unauthorized_option,duplicate_raw_key}`, `action.pos.optional_arg` |
| N05AR | EV03 predicate semantics split: predicates_equivalent vs predicate_truth(world); eq/ne/gt/ge/lt/le boundaries, units, invalid types (no crash) | done | PASS | `comparators.py`, `controls.py` TRUTH_CONTROLS (12) |
| N05AR | EV04 identifier kinds: label folding scoped; tool/entity/action exact identity + declared alias contracts; collision negatives | done | PASS | `comparators.py` (identifier_matches), controls `tool.neg.underscore_space`, `entity.neg.case_variant`, `entity.neg.substring_trap` |
| N05AR | EV05 unit handling: UNIT_MISSING without public declaration; unit_publicly_declared contract; no coercion, non-finite rejected | done | PASS | `contracts.py` (SlotSpec.unit_publicly_declared), `comparators.py` (check_slot), controls `slot.{pos.public_unit,neg.unit_missing}` |
| N05AR | EV06 comparator-level mutants: 9 classes, harness + gate; all detected; retained rule-drop mutants re-verified 19/19 | done | PASS | `comparators.py` (MUTANTS/apply_mutant/clear_mutant), `qualification.py` (mutation_gate), `evidence/IJNANO/N05AR/coverage_matrix.json` |
| N05AR | EV07 reconciliation + strict validation: 19 declared = 19 tested codes; ARGUMENT_MISMATCH obsolete with disposition; construction-time validation; validate_control_battery + qualify_family_scope dataset rules | done | PASS | `contracts.py`, `qualification.py`, `evidence/IJNANO/N05AR/coverage_matrix.json` |
| N05AR | Gate `N05AR_COGNITIVE_EVALUATOR_INTEGRITY_GO` (scoped; NOT the business Oracle) | done | PASS | `reports/IJNANO_05AR_COGNITIVE_EVALUATOR_REQUALIFICATION.md`, `evidence/IJNANO/N05AR/defect_ledger.json` |
| N05AR | Publication check (order §10): fail-closed finding-count decision + synthetic scanner control | done | PASS | `scripts/tools/publish_check.py`, `tests/ij_nano/test_publish_check.py` (9 tests OK; repo-wide check PASS) |

## N02R (2026-11-27, IJ-NANO-1.2 order + addendum, in flight)

| Phase | Task | Progress | Status | Evidence |
|---|---|---|---|---|
| N02R | Source-level llama.cpp b12359 investigation (chat template, thinking config, reasoning parser, grammar activation, json-schema conversion, budget accounting, GBNF escaped-quote) | done | PASS | `evidence/IJNANO/N02R/source_level_findings.md`; lazy-grammar root cause identified at source level |
| N02R | Matched 60-task suite + P0-P7 arm harness + evaluator-v2 scorer + resumable GPU controller + analyzer | done | PASS | `benchmarks/ij_nano/n02r/{tasks,arms,scorer,controller}.py`, suite hash frozen |
| N02R | Identity reverification before physical execution (10/10 weights MATCH, engine hashed) | done | PASS | `evidence/IJNANO/N02R/identity_verification.json` |
| N02R | Probe audit §3.2 (empty-content gate, tool-call semantics, SSE reconciliation incl. reasoning channel, cancellation scope, /apply-template, escaped-quote decomposition F1-F7) | done | PASS | `runs/*/probe_audit_*.json`; S2 escaped-quote engine record corrected (construction error, not parser defect) |
| N02R | v1 main screen 3x8x60 @1024 (experiment 36bfed1d55a9987b) | done (executed 1440/1440; sealed) | DIAGNOSTIC (reclassified per addendum) | `runs/36bfed1d55a9987b/{results.jsonl,manifest.json,seal.json}` |
| N02R | Addendum committed verbatim | done | PASS | `docs/IJNANO_MISSION_ORDER_V1_2_N02R_ADDENDUM.md` (5ea13f6) |
| N02R | PR-D01 information-equivalence manifest (request-level, per family) | done | PASS (asymmetry reproduced) | `evidence/IJNANO/N02R/pr_d01_information_manifest.json` |
| N02R | PR-D02/D03/D04/D05 offline reproduction + repairs (arms_v2 parser v2, P5A/P5B, P7 applicability, P7S two-stage) | done | PASS (13 red -> 24/24 green) | `evidence/IJNANO/N02R/pr_concerns_red_run.txt`, `tests/ij_nano/test_n02r_pr_concerns.py`, `benchmarks/ij_nano/n02r/arms_v2.py` |
| N02R | PR-D06/D07/D08/D09 repairs (full identity binding, netstat socket-PID, NOT_CAPTURED telemetry, content-addressed artifacts) | done | PASS | `benchmarks/ij_nano/n02r/controller_v2.py`, run 7a1b9d7d manifest/sessions |
| N02R | PR-D10 denominator reconciliation (v1 plan 2,016 unique not 2,160; corrected plan 2,184 unique logical slots) | done | PASS | `scripts/ij_nano/n02r_analyze_v2.py`, analyzer denominators block |
| N02R | Evidence disposition for v1 trials (never modified) | done | PASS | `evidence/IJNANO/N02R/evidence_disposition.json` |
| N02R | Gate `N02R_PARSER_EVALUATOR_INTEGRATION_GO` (15/15 mandatory negatives, hashes bound) | done | PASS | `evidence/IJNANO/N02R/parser_evaluator_qualification.json` |
| N02R | Corrected experiment 7a1b9d7d160202d8: smoke 57/57; main 893 + panel 504 physically executed (crash at parser defect P6-slot trailing scan fixed; request renderers verified byte-identical) | done | PASS (physical source) | `runs/7a1b9d7d160202d8/` (sealed) |
| N02R | Offline re-score per addendum §11: 1397/1397 trials re-parsed and re-scored from hash-verified artifacts into new identity ec5b95357e960f99 (0 hash mismatches) | done | PASS | `scripts/ij_nano/n02r_rescore.py`, `runs/ec5b95357e960f99/manifest.json` (rescore block) |
| N02R | Final physical fill under ec5b95357e960f99: remaining 787 main slots executed; panel fully covered | done | PASS (2184/2184 unique slots; 2214 physical requests; seal.json) | `runs/ec5b95357e960f99/{results.jsonl,seal.json}` |
| N02R | Protocol matrix deliverable (scopes + T-set + contrasts + budget curves + denominators) | done | PASS | `evidence/IJNANO/N02R/protocol_matrix.json`, `scripts/ij_nano/n02r_analyze_v2.py` |
| N02R | Causal report (sections 5-7: matrix, T0-T3 trade-off, recommendation candidates, limitations) | done | PASS | `reports/IJNANO_02R_PROTOCOL_CAUSAL_ANALYSIS.md` |
| N02R | Gate `N02R_MODEL_PROTOCOL_BEHAVIOR_CHARACTERIZED` | done | PASS (scoped; limitations documented) | `MISSION_STATE_IJNANO.json` phase N02R |

## N02RR (2026-11-28, IJ-NANO-1.2R order, closed)

| Phase | Task | Progress | Status | Evidence |
|---|---|---|---|---|
| N02RR | Mission order committed verbatim (preregistration) | done | PASS | `docs/IJNANO_MISSION_ORDER_V1_2R.md` |
| N02RR | RS01 red reproduction of the rescore loader defect on the published witness artifact + exact impact count (1,397/1,397 affected; 588 verdict flips, all false negatives; 0 false positives) | done | PASS | `evidence/IJNANO/N02RR/rs01_red_reproduction.json`, `reports/IJNANO_02RR_OFFLINE_RESCORE_ROOT_CAUSE.md` |
| N02RR | RS01 repair: key-based schema-validated loader, ArtifactIntegrityError as separately classified evidence failure; `n02r_rescore.py` rewritten fail-closed (no silent appends) | done | PASS | `scripts/ij_nano/n02rr_replay_lib.py`, `scripts/ij_nano/n02r_rescore.py` |
| N02RR | RS02 P7S two-stage causal replay: stage-1 selection recomputed, stage-2 payload verified against ACTUAL selection (30/30 consistent; 23 wrong selections fail visibly; 5 stage-1 failures; total latency/tokens across stages) | done | PASS | `evidence/IJNANO/N02RR/trial_reconciliation.jsonl` (p7s_reconstruction fields) |
| N02RR | Replay integration qualification: 19 end-to-end controls red-to-green incl. the dictionary-unpacking mutant (rejected on every positive control) | done | PASS | `evidence/IJNANO/N02RR/replay_qualification.json`, `tests/ij_nano/test_n02rr_replay_qualification.py` |
| N02RR | Gate `N02R_OFFLINE_REPLAY_INTEGRITY_GO` | done | PASS | same |
| N02RR | RS03 evidence-chain reconstruction: 2,184/2,184 slots at all six evidence levels, 0 findings; roster + trial-id recomputation; source/destination manifest comparison; request-renderer AST equivalence (12 functions/9 constants) + identical chat-template fingerprints; session PID evidence | done | PASS | `evidence/IJNANO/N02RR/evidence_verification.json` |
| N02RR | Gate `N02R_QUANTITATIVE_EVIDENCE_RECONCILED` | done | PASS | same |
| N02RR | Corrected full-corpus re-score under immutable replay identity `6701a6a6a08b34d9` (no GPU): 588 CORRECTED_FALSE_NEGATIVE, 809 TELEMETRY_CORRECTED, 787 UNCHANGED_VALID (physical rows reproduced 787/787 payload-identical; source verdicts restored 1,397/1,397); 0 EVIDENCE_INSUFFICIENT / 0 PHYSICAL_REEXECUTION_REQUIRED | done | PASS | `evidence/IJNANO/N02RR/{manifest.json,trial_reconciliation.jsonl}` |
| N02RR | RS04-RS08 corrected analysis: paired McNemar + Newcombe CIs on intersected applicable tasks; corrected telemetry with sample counts (missing never zero); failure taxonomy with mechanism split; T-set recalc; budget-panel caveat (total-generation budget, NOT reasoning-budget) | done | PASS | `evidence/IJNANO/N02RR/corrected_protocol_matrix.json`, `scripts/ij_nano/n02rr_analyze.py` |
| N02RR | Scientific conclusion recovery (13 questions) + supersession notices on both N02R reports + PR #11 description corrected | done | PASS | `reports/IJNANO_02RR_QUANTITATIVE_EVIDENCE_RECONCILIATION.md` §8; notices in `reports/IJNANO_02R_*.md` |
| N02RR | Gate `N02R_MODEL_PROTOCOL_BEHAVIOR_CHARACTERIZED` re-granted for corrected comparison scopes | done | PASS (corrected scopes) | `MISSION_STATE_IJNANO.json` phases.N02R/N02RR |
| N02RR | Corrected headline: 870/2,184 semantic PASS (39.8%) vs 282/2,184 defective; withdrawn claims: reasoning improves all three models, thinking-off harms S2, 256-token reasoning-budget optimality; confirmed: DSL zero success, S3 thinking-control requirement | done | PASS (negative results preserved) | reconciliation report §8 |

## N03-PROGRESSIVE (2026-11-28, IJ-NANO-1.3S order, ACTIVE)

| Phase | Task | Progress | Status | Evidence |
|---|---|---|---|---|
| S0 | Mission order committed verbatim (preregistration) | done | PASS | `docs/IJNANO_MISSION_ORDER_V1_3S.md` (SHA256 c447831d…) |
| S0 | Repository reconciliation: PR #11 HEAD bc4555e == audited == remote; PR #13 remote HEAD 9963926 == audited (local +1 unpushed preregistration + in-flight EA-R hardening owned by concurrent IJEVAL session, left untouched) | done | PASS | this commit; `MISSION_STATE_IJNANO_N03_PROGRESSIVE.json` reconciliation block |
| S0 | Progressive execution plan + machine state: dependency graph, AUTH-0..3 levels, batch register, budgets, protocol candidates, canary policy, confirmation protection | done | PASS | `docs/IJNANO_N03_PROGRESSIVE_EXECUTION_PLAN.md`, `MISSION_STATE_IJNANO_N03_PROGRESSIVE.json` |
| S0 | Gate `N03_PROGRESSIVE_EXECUTION_PLAN_FROZEN` | done | GRANTED | this commit |
| B1 | Taxonomy contracts C01–C32 (definitions, witnesses, boundaries, failure taxonomy, EAE deps) | not started | PENDING | planned `evaluation/ij_nano/n03/taxonomy/` |
| B2 | Dataset build 640 dev + 320 confirmation (CN+EN, family splits) | not started | PENDING | planned `evaluation/ij_nano/n03/` |
| B3 | Independent dataset verification | not started | PENDING | planned `tests/ij_nano/n03/` |
| B4 | Runner + authorization controller + synthetic transport | not started | PENDING | planned `benchmarks/ij_nano/n03/` |
| B1 | Taxonomy contracts C01-C32 frozen: 17-field contract per primitive (definition, observable behavior, isolation label distinguishing isolated/diagnostic capability from agentic autonomy, public info, output contract, applicable protocols from corrected-N02RR vocabulary, independent ground truth, correct/incorrect witnesses, valid alternatives, boundary cases, difficulty dimensions, failure taxonomy, additional EAE deps) + JSON schema + dependency-free validator + 12 positive/negative tests; digest pinned in mission state | done | PASS (validator exit 0; 225/225) | `evaluation/ij_nano/n03/{taxonomy.json,taxonomy.schema.json}`, `scripts/ij_nano/n03/validate_taxonomy.py`, `tests/ij_nano/test_n03_taxonomy.py` |
| B1 | Gate `N03_TAXONOMY_CONTRACTS_FROZEN` | done | GRANTED (sha256 cb800bce6efc01723e1e34ad10e159d3a95c44ed8592a3c0112c17e74f23861c) | `MISSION_STATE_IJNANO_N03_PROGRESSIVE.json` taxonomy block |
| S0+ | Status report generator (deterministic render of mission state; four separate progress measures, per-primitive matrix, gate table); Lane A reconciliation updated to EA-R delivery 67af3dd | done | PASS | `scripts/ij_nano/n03/status_report.py`, `reports/IJNANO_N03_PROGRESSIVE_STATUS.md` |

## N03-D01/D02 + B2/B3 Batch A (2026-11-28, continuation order, ACTIVE)

| Phase | Task | Progress | Status | Evidence |
|---|---|---|---|---|
| D01 | Slot accounting corrected: hand-maintained per-primitive totals removed from mission state; all accounting generated from frozen case roster x model registry (S1/S2/S3 from N02R controller identities); consistency + negative tests (duplicate id, misclassified split, wrong case count) | done | PASS (720 Batch A slots, 0 errors; 238/238) | `scripts/ij_nano/n03/slot_accounting.py`, `evaluation/ij_nano/n03/model_registry.json`, `evidence/IJNANO/N03/dataset/slot_manifest.json`, `tests/ij_nano/test_n03_dataset.py` |
| D02 | Taxonomy schema conformance: dependency-free validator equivalence contract (14/14 mutants rejected incl. schema-tag drift caught by the harness itself); jsonschema unavailable in repo env so JSON Schema validation is explicitly NOT claimed; taxonomy identity unchanged cb800bce | done | PASS | `scripts/ij_nano/n03/schema_conformance.py`, `evidence/IJNANO/N03/dataset/schema_conformance.json` |
| B2 (A) | Batch A dataset C01-C08: 8 primitives x 3 families (2 dev + 1 conf, disjoint family identities), 160 dev + 80 confirmation cases, CN/EN 5:5 per family, difficulty 1-3, per-primitive output contracts, construction-semantics ground truth, protected confirmation architecture (local-only expectations + hash-only committed manifest + gitignored answer-bearing seed) | done | PASS (deterministic rebuild reproduces committed digests) | `evaluation/ij_nano/n03/dataset/*`, `evidence/IJNANO/N03/dataset/build_manifest.json` |
| B3 (A) | Batch A independent verification: 240/240 truth re-derivations (public-recomputation for C03/C04/C05/C06/C08; independently coded rule tables for C01/C02/C07 with declared dual-implementation limitation), mutation battery 240/240 detected 0 escaped, leakage scan clean, split/family integrity + language balance verified | done | PASS | `evaluation/ij_nano/n03/dataset/verify.py`, `evidence/IJNANO/N03/dataset/verification_report.json` |

## N03-B2/B3 Batches B-D + complete dataset (2026-11-28, continuation order 2)

| Phase | Task | Progress | Status | Evidence |
|---|---|---|---|---|
| B2 (B) | Batch B families C09-C16: JSON/nested/DSL distinct output representations, slot extraction, coref with rotating targets + attribute-agreement construction, numeric extraction, unit/currency arithmetic, tool-result comprehension | done | PASS | `evaluation/ij_nano/n03/dataset/families_b.py` |
| B2 (C) | Batch C families C17-C24: typed world engine (orderflow/devops/labflow) with equality preconditions + effects; plan validity by SIMULATION against goal predicate (reference plan = witness, not answer key); replanning from current state; error envelopes incl. nested-in-success; diagnosis-driven argument correction; condition-holding fallbacks | done | PASS | `evaluation/ij_nano/n03/dataset/families_c.py` |
| B2 (D) | Batch D families C25-C32: stop/continue, clarification (invalid-counts-as-missing), escalation thresholds, interference with graded decoys, declared ambiguity, cross-language paired cases (pair_id + canonical equality), grounded citations, declared-sufficiency abstention | done | PASS | `evaluation/ij_nano/n03/dataset/families_d.py` |
| B3 (full) | Complete-dataset verification: 960/960 truth re-derivations; mutation battery 960/960 detected 0 escaped; leakage scan clean; per-primitive family split integrity (cross-primitive family name reuse correctly allowed); C30 pair-language + canonical consistency | done | PASS | `evidence/IJNANO/N03/dataset/verification_report.json` |
| preserve | Batch A identity preserved: all 240 public records + 160 dev expectations bit-identical in the complete roster; file ORDER changed (dev C01-C32 then conf) so whole-file digests differ - documented, pinned d23de5a package unaffected | done | PASS | `evidence/IJNANO/N03/dataset/batch_a_preservation.json` |
| D01 (full) | Slot accounting complete: 32/32 primitives, 640/320 cases, 1920/960/2880 primary slots, complete=True, 0 errors | done | PASS | `evidence/IJNANO/N03/dataset/slot_manifest.json` |
| gate | `N03_DATASET_FROZEN` + `N03_DATASET_VERIFIED` granted (960 cases; 960/960 + 960/960) | done | GRANTED | `MISSION_STATE_IJNANO_N03_PROGRESSIVE.json` |
| handoff | Batch B/C/D qualification packages v1 (per-batch requirements.md: parser surface, oracle rule, mutation targets per primitive; component digests) | done | PASS | `evaluation/ij_nano/n03/handoff/batch_{b,c,d}/` |
