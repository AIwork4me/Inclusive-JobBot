# IJ-SDK-1.0 Task Ledger

Mission-specific ledger (see `MISSION_STATE_IJSDK.json`). The shared
`TASK_LEDGER.md` remains owned by the active Atlas worker; IJ-SDK-1.0 appends
only non-conflicting entries there. Status vocabulary: `PASS`, `FAIL`,
`BLOCKED`, `NOT_RUN`.

| Phase | Task | Progress | Status | Evidence |
|---|---|---|---|---|
| P0 | Live remote audit: default branch, PR #6 (58 commits, HEAD fe56f324), PRs #2/#4, issues #1/#3/#5; stale HANDOFF "no remote" noted, not edited | done | PASS | `reports/IJSDK_00_BASELINE_AUDIT.md` |
| P0 | Stacked isolation: dedicated local worktree (path withheld from evidence), branch `mission/ij-sdk-1.0-cross-sdk-agentic-benchmark` frozen at `fe56f324`, upstream tracking unset | done | PASS | `evidence/IJSDK/P0/baseline_manifest.json` |
| P0 | Suite roster verification from frozen bytes: TC-V2 500(+120 dev), MULTITOOL-V1 600(+6 diag), AGENTIC-PLAN-V1 800 worlds dual-track = 1,600 trajectories, JOB-V1 600; total 3,300 = mission expectation | done | PASS | `evidence/IJSDK/P0/baseline_manifest.json` (suite_roster_verified) |
| P0 | Prior-mission gate/verdict audit: Atlas G01-G05+G14 BLOCKED, all verdicts BLOCKED/NOT_RUN; AEVE not inherited as PASS | done | PASS | `evidence/IJSDK/P0/reusable_assets.json` |
| P0 | Reusable asset inventory + known limitations L-01..L-14 frozen | done | PASS | `evidence/IJSDK/P0/known_limitations.json` |
| P0 | Gate P0_REPOSITORY_BASELINE_FROZEN | done | PASS | `reports/IJSDK_00_BASELINE_AUDIT.md` |
| P0 | Tracking Issue #7 + Draft PR #8 created (stacked on PR #6, base codex/ij0-tool-calling) | done | PASS | https://github.com/AIwork4me/Inclusive-JobBot/issues/7, https://github.com/AIwork4me/Inclusive-JobBot/pull/8 |
| P1 | gfx1100 hardware/software fingerprint (this machine) | in progress | NOT_RUN | - |
| P1 | llama.cpp b12359 reproduction on RX 7900 XTX (Vulkan + ROCm/HIP) | not started | NOT_RUN | - |
| P1 | Function calling, structured output, tool-result continuation, multi-call on gfx1100 | not started | NOT_RUN | - |
| P1 | Gate P1_GFX1100_PHYSICAL_RUNTIME_GO | not started | NOT_RUN | - |
