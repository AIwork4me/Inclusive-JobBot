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
| N00 | Tracking Issue + Draft PR created on GitHub | done | PASS | numbers recorded in MISSION_STATE_IJNANO.json after creation |
| N00 | Gate `N00_RESEARCH_BASELINE_FROZEN` | done | PASS | `reports/IJNANO_00_BASELINE_AND_DEPENDENCY_AUDIT.md` §9 |

## N01 (opened, not started)

| Phase | Task | Progress | Status | Evidence |
|---|---|---|---|---|
| N01 | Verify R01 effGen, R02 PTC-Decoder, R03 TinyAgent, R04 slm-harness-adaptation, R05 Growing Harness, R06 meta-harness, R07 MagenticLite, R08 constrained decoding (GBNF/LLGuidance/XGrammar), R09 general-purpose frameworks | not started | NOT_RUN | — |
| N01 | Reuse-vs-rebuild classification with license matrix | not started | NOT_RUN | — |
| N01 | Landscape reports CN/EN + open-source reuse decision | not started | NOT_RUN | — |
