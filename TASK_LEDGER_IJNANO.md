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

## N01 (in progress)

| Phase | Task | Progress | Status | Evidence |
|---|---|---|---|---|
| N01 | Primary-source verification R01-R09 via four parallel research agents (papers, repos, licenses, models, mechanisms, statistics) | done | PASS (verification sweeps; consolidation pending) | `evidence/IJNANO/N01/agent_reports/{R01_R04,R02_R08,R03_R05_R06,R07_R09}_verification.md` |
| N01 | research_catalog.json + license_matrix.json | not started | NOT_RUN | — |
| N01 | Landscape reports CN/EN + open-source reuse decision | not started | NOT_RUN | — |

## N02 (in progress)

| Phase | Task | Progress | Status | Evidence |
|---|---|---|---|---|
| N02 | Fresh SHA256 verification: 10/10 weight files MATCH committed manifest; 95 engine binaries hashed (cpu/vulkan/rocm) | done | PASS | `evidence/IJNANO/N02/identity_verification.json`, `benchmarks/ij_nano/verify_model_identities.py` |
| N02 | Engine provisioned via gitignored junctions (b12359 verified: `build 12359, commit b1b770d90`) | done | PASS | `.runtime/n02/make_junctions.ps1` (local); runtime/llama-cpp/README conventions |
| N02 | Admission smokes under host-wide lease (S1,S2,S3d,R1,R2; vulkan) — all 9/10, D-010 offload proof per model | done | PASS | `evidence/IJNANO/N02/admission/*.json`, `evidence/IJNANO/N02/session_record.json` |
| N02 | Protocol probe v3: health/socket, D-010 offload, generation+usage, native tool-call, chat json_schema (strict, 1024), GBNF charclass, escaped-quote engine record, /completion json_schema, SSE streaming, cancellation | done | PASS (S1/S3/R1/R2 overall PASS; S2 protocol-surface PASS + chat-path reasoning-burn model-behavior finding recorded) | `evidence/IJNANO/N02/protocol/*.json`, `benchmarks/ij_nano/n02_protocol_probe.py` |
| N02 | Gate `N02_PHYSICAL_MODEL_RUNTIME_QUALIFIED` (runtime/protocol scope only; ROCm comparator and Q4 sensitivity explicitly NOT_RUN) | done | PASS | `reports/IJNANO_02_PHYSICAL_RUNTIME_QUALIFICATION.md` |

## N06/N07 Layer A (software, in progress)

| Phase | Task | Progress | Status | Evidence |
|---|---|---|---|---|
| N06 | Layer A execution-integrity core: BudgetController (D05), EventLog hash-chain+seal (D07), TypedTaskState complete-reset+epoch-abort (D04), SafeToolGateway fixed-order transactions (D06), checkpoint/cancellation | done (software) | PASS under unittest | `src/nanoagent/{core,gateway}/`, `tests/ij_nano/` |
| N06 | Layer A regression suite: 36 tests green (`python -I -m unittest discover -s tests/ij_nano -t .`); IJ-SDK suite unaffected (93 OK) | done | PASS | test run recorded in this row; rerun command in HANDOFF |
| N06/N07 | Layers B (context compiler, tool filtering, grammar, slot binding) and C (action graph, recovery, goal controller) | not started | NOT_RUN | — |
