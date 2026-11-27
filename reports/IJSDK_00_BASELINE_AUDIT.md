# IJSDK_00_BASELINE_AUDIT — P0 Repository Audit and Research Isolation

Mission: **IJ-SDK-1.0 — Cross-SDK Agentic Capability Benchmark for 2B-class SLMs**
Generated: 2026-11-27 (live audit; every remote fact re-queried on this date)
Frozen source commit: `fe56f324daf4ae106908e0d0a0f16967afc9c463`
Research branch: `mission/ij-sdk-1.0-cross-sdk-agentic-benchmark`
Worktree: dedicated local checkout (path withheld from published evidence; see isolation note in §3)

Evidence: `evidence/IJSDK/P0/baseline_manifest.json`, `evidence/IJSDK/P0/reusable_assets.json`, `evidence/IJSDK/P0/known_limitations.json`

---

## 1. Verdict

| Item | Status |
|---|---|
| Repository identity and live remote state audited | PASS |
| All mandatory instruction sources read (AGENTS.md, HANDOFF.md, MISSION_STATE.json, BLOCKERS.md, TASK_LEDGER.md, DECISIONS.md, README.md, THIRD_PARTY_NOTICES.md, reports, evidence layout, issues, PRs) | PASS |
| Suite rosters verified against frozen bytes (counts + SHA-256) | PASS — 3,300 execution cases confirmed |
| Research isolation (stacked branch, worktree, no PR #6 interference) | PASS |
| Reusable asset inventory with qualification status | PASS |
| Gate `P0_REPOSITORY_BASELINE_FROZEN` | **PASS** |

One deliberate deviation from AGENTS.md is recorded in §7 (shared mission-state files).

## 2. Live repository state (re-queried 2026-11-27)

- Remote `https://github.com/AIwork4me/Inclusive-JobBot`, public, 166,073 KB, last push **2026-11-27T03:20:48Z**.
- Default branch `codex/ij0-tool-calling` @ `0592c319ab34`.
- **PR #6 is actively progressing**: branch `mission/ij-0.7.1-jobbot-agentic-capability-atlas-v1`, 58 commits, HEAD `fe56f324daf4` ("Freeze the Q1 truncation experiment and pin additional Judge families"), pushed 2026-11-27T03:20Z. The mission order's historical anchor `0e606b2fffc8` is the direct parent of the current tip — preserved in history, superseded as HEAD.
- Open PRs #2 (IJ-0.6) and #4 (IJ-0.7) are draft; issues #1, #3, #5 track prior missions.
- `HANDOFF.md` (2026-11-24) says "no remote — repository does not exist on GitHub". **This is stale**: the repository is published and active. We treat the live remote as authoritative and do not edit HANDOFF.md (owned by the active worker).

## 3. Isolation strategy (stacked branch)

The required research assets exist **only on the unmerged Atlas branch**:

| Suite/system | Default branch | Atlas branch (PR #6) |
|---|---|---|
| TC-V1 legacy tool-calling, engine_qualification | present | present |
| TC-V2, MULTITOOL-V1, AGENTIC-PLAN-V1/V2, JOB-V1, competitive_slm, root_cause, atlas_validity, ij06_sdk | absent | present |
| src/ (model_gateway, business_tools, skill_engine, sop_engine, audit) | absent | present |
| evaluation/aeve (AEVE evaluator) | absent | present |
| atlas/ (gates, verdicts, progress, workstreams) | absent | present |

Therefore, per mission order §3.2:

1. Frozen source commit = **Atlas branch tip `fe56f324daf4ae106908e0d0a0f16967afc9c463`** (contains all assets).
2. Separate worktree (dedicated local checkout; the absolute path is withheld from published evidence because it contains the local username — `scan_sensitive.py` enforces this) with branch `mission/ij-sdk-1.0-cross-sdk-agentic-benchmark`.
3. Documented parent dependency: PR #6 (branch `mission/ij-0.7.1-jobbot-agentic-capability-atlas-v1` @ `fe56f324`). The Draft PR for IJ-SDK-1.0 will declare this stacking; it merges only after/with PR #6 per owner decision.
4. Upstream tracking unset on the new branch — no accidental push to the Atlas branch.
5. PR #6 is never modified; no force-push anywhere; no merge without owner authorization.

## 4. Prior-mission state at source commit (what may and may not be inherited)

`MISSION_STATE.json` (updated 2026-11-26T17:02:32Z, phase IJ-0.7.3) and `atlas/gates.json` + `atlas/verdicts.json`:

- IJ-0.1–IJ-0.5: PASS (engine install, model identity, GPU proof — **on the previous gfx1151 machine**).
- IJ-0.TC: **FAIL** — pinned b12359 native parser 20/26 strict fixtures (B-009); frozen baseline 433/500 Vulkan, 432/500 ROCm; ADR-002 thresholds established; independent holdout NOT_RUN.
- IJ-0.AG: BLOCKED (B-008 checklist unavailable); read-only Antigravity loop smoke PASS both backends.
- Atlas gates: G00 PASS; **G01–G05, G14 BLOCKED**; G06–G13, G15–G29 NOT_RUN. All Atlas verdicts BLOCKED or NOT_RUN.
- Engine identity: llama.cpp official **b12359 (v1.0.0)** commit `b1b770d90d94…`; MiniCPM5 parser PR #24889 merge `c818263f…`; ROCm math libs from ROCm 10.0.0 wheels (D-009).
- Blockers open: B-004 (resumability), B-006 (no power meter), B-007 (soak power settings), B-009 (parser fixtures), B-010 (SDK egress isolation), B-011 (stateful write inputs), B-012 (MiniCPM5 sequential tools 25/100; TC-V2 first-pass < 90%).

**Consequence for IJ-SDK-1.0 (mission order §8):** the AEVE/Atlas evaluator is **not inherited as PASS**. Every evaluation scope claimed by this mission is independently qualified in P5 before formal benchmark conclusions. Historical witness tests and GPU results do not automatically qualify as cross-SDK evidence.

## 5. Suite roster verification (frozen bytes, counted 2026-11-27)

| Suite | Path | Verified count | SHA-256 (prefix) |
|---|---|---:|---|
| TC-V2 holdout | `benchmarks/tool_calling_v2/holdout/tc_v2_500.jsonl` | 500 | `34fae92ce5fe0ea14d69…` |
| TC-V2 dev | `benchmarks/tool_calling_v2/holdout/tc_v2_dev.jsonl` | 120 | `3cb578ba7cfc4c1e65fe…` |
| TC-V1 legacy (identity cross-check) | `benchmarks/tool_calling/datasets/tool_calling_500.jsonl` | 500 | `ce6bf6bf433baab69e51…` = HANDOFF identity ✓ |
| MULTITOOL-V1 | `benchmarks/multitool_v1/frozen/` (prompts/worlds 606 lines = 600 holdout + 6 diagnostic) | 600 | freeze `f6e4f5000bd8c894…` |
| AGENTIC-PLAN-V1 public | `benchmarks/agentic_planning_v1/datasets/holdout.jsonl` | 800 | `cb5f383b97f9600d…` |
| AGENTIC-PLAN-V1 private graphs | `benchmarks/agentic_planning_v1/task_graphs/holdout.jsonl` | 800 | `a5bf376de757ea5de1af…` |
| JOB-V1 | `benchmarks/job_productivity_v1/holdout/frozen/` (tasks/worlds/oracles) | 600 | freeze `7a04ed91976c8145…` |

Roster reconciliation with the mission order §9.2: TC-V2 500 ✓; MULTITOOL-V1 600 ✓; Planning Plan-first 800 + Acting-first 800 = dual-track protocol over the same 800 frozen worlds → 1,600 measured trajectories ✓ (mission note "the two planning tracks may share underlying worlds" confirmed by `datasets/protocol.json`); JOB-V1 600 ✓.
**Total: 3,300 execution cases — matches the frozen expectation exactly.**
Planning levels L0–L7 (100/level), 400 EN + 400 ZH, 14 domains; repeat panel 160 cases × 3 seeds. Previously exposed to MiniCPM5 and PC-S controls → treated as **legacy roster**, not fresh holdout (mission §9.2). The ≥1,200-case unseen holdout is authored in P6 with protected artifacts.

## 6. Reusable assets and their qualification status

Full inventory with statuses: `evidence/IJSDK/P0/reusable_assets.json`. Highlights:

- **Benchmark suites** (above): frozen, verified, reusable as regression/comparative rosters.
- **Runtime stack**: `src/model_gateway` (llama.cpp backend, OpenAI protocol, streaming, strict JSON, tool validation, authorization, execution policy, metrics), `src/business_tools` + skill/SOP engines + audit, `scripts/windows` launch/check scripts, `configs/llama_cpp` pinned engine profiles.
- **Evaluator**: `evaluation/aeve` — dimension rubrics, gold proof, adjudication, history controls. Status: **unqualified for our claims**; P5 re-derives.
- **Root-cause tooling**: failure ledger, GPU lease, generation capture, historical replay, performance probes.
- **SDK prior art**: `benchmarks/ij06_sdk` (qualify + wire-boundary capture), Antigravity read-only smoke evidence.
- **Reference-model anchors**: Qwen3-8B / Qwen3-14B PC-S control panels already measured on subsets (TC-V2 dev 56/100 & 66/100; MULTITOOL 28/120 & 45/120; Planning 4/320 & 35/320) → R1/R2 candidates (mission §5.2 "prefer reference models already represented in the existing project").
- **Model passports base**: `models/model_manifest.json` — MiniCPM5-2B GGUF (Apache-2.0) rev `8cc1178b…` with F16/Q8_0/Q4_K_M SHA-256s; BF16 rev `4e7a9471…`; GGUF-embedded chat template SHA-256 `cc945752…`.

**Not reusable:** all prior GPU measurements (different GPU: gfx1151 → this machine is gfx1100); AEVE/Atlas verdicts; witness tests as cross-SDK evidence.

## 7. Governance compliance and the one deviation

AGENTS.md non-negotiables adopted unchanged: PASS/FAIL/BLOCKED/NOT_RUN vocabulary; evidence bound to exact identities; no silent fallback; the model proposes and deterministic rules decide (fail-closed); local-only runtime; no system-level changes without the machine owner; `scan_sensitive.py` before every commit; small logical commits, normal pushes.

**Deviation (recorded, deliberate):** AGENTS.md asks every worker to update `MISSION_STATE.json` and `TASK_LEDGER.md` for finished work. Those files are under **active edit by the Atlas worker** (MISSION_STATE rewritten wholesale, last update 2026-11-26T17:02Z). The mission order §24.3 says to avoid conflicting edits to shared mission-state files and to use the mission-specific progress ledger as the source of truth. Resolution: IJ-SDK-1.0 maintains `MISSION_STATE_IJSDK.json` and `TASK_LEDGER_IJSDK.md` (added in this commit) and appends to shared files only where a non-conflicting entry is safe. This deviation is reversible if the owner prefers strict AGENTS.md behavior.

## 8. Known limitations carried into P1–P19

See `evidence/IJSDK/P0/known_limitations.json` (L-01…L-14). The most consequential:

1. **L-01**: no prior GPU evidence transfers — gfx1151 ≠ gfx1100. P1 qualifies Vulkan + ROCm/HIP from zero on the RX 7900 XTX.
2. **L-02/L-03**: pinned parser fixture failures and MiniCPM5's low sequential-tool capability are expected; E0 layer must separate parser failures (F08/F09) from model failures in every SDK arm.
3. **L-04**: AEVE stays out of claimed scopes until P5 qualification.
4. **L-06**: SDK egress isolation on Windows needs a process-level design (no machine policy changes); affected arms otherwise BLOCKED.
5. **L-07/L-08/L-09**: energy NOT_MEASURED; resumable queue mandatory; soak gates conditional on machine availability.

## 9. What P1 does next

Hardware/software fingerprint of **this** machine (RX 7900 XTX, gfx1100, driver 32.0.21030.2001, Windows 11 build 26300, i7-13700K, 32 GB RAM, 400 GB free — recorded 2026-11-27), then llama.cpp b12359 reproduction (official binaries; Vulkan; ROCm/HIP with the D-009 wheel fix), function-calling and structured-output qualification on the new GPU, with silent-CPU-fallback prevention per D-010. Deliverables: `reports/IJSDK_01_WINDOWS_GFX1100_QUALIFICATION.md` + `evidence/IJSDK/P1/*`.

Gate reached: **`P0_REPOSITORY_BASELINE_FROZEN` = PASS** (frozen at source commit `fe56f324`, evidenced by this report + the three P0 evidence files).
