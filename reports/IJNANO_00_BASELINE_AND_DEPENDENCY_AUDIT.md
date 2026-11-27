# IJ-NANO-1.0 — N00 Baseline and Dependency Audit

- Generated: 2026-11-27T09:46:53Z
- Auditor: IJ-NANO-1.0 worker (independent session; no other mission worker
  was running on this workstation at audit time)
- Machine-readable evidence: `evidence/IJNANO/N00/baseline_manifest.json`,
  `evidence/IJNANO/N00/dependency_qualification.json`
- Mission order: `docs/IJNANO_MISSION_ORDER.md` (verbatim preregistration)

## 1. What was audited

All governing files on the default branch (AGENTS.md, HANDOFF.md,
MISSION_STATE.json, TASK_LEDGER.md, BLOCKERS.md, DECISIONS.md), the IJ-SDK
mission state in the sibling worktree (MISSION_STATE_IJSDK.json,
TASK_LEDGER_IJSDK.md), the IJ-SLM-1.0 branch state
(MISSION_STATE.json, physical_progress.json at the remote head), the live
remote via `gh api` (PRs #2, #4, #6, #8, #9; issues #1, #3, #5, #7), branch
ancestry, on-disk weights/engine assets, the physical GPU, and running
processes.

## 2. Remote state versus the mission order's anchors

| Anchor in mission order | Live state 2026-11-27 | Verdict |
|---|---|---|
| PR #6 HEAD `06f25ab5` | `06f25ab5` (updated 05:37Z) | still current |
| PR #8 HEAD `71660fbb` | `56c6c74b` (updated 07:56Z) | superseded by IJ-SDK-1.1 P4A checkpoint 1 (3 commits); anchor preserved in history |
| PR #8 frozen source `fe56f324` | `fe56f324` unchanged in MISSION_STATE_IJSDK.json | unchanged |
| not mentioned | **PR #9** `codex/ij-slm-1.0` "IJ-SLM-1.0 \| 2B-class Agentic Capability Atlas", head `350fb529` (updated 08:30Z) | new, audited below |

The mission order's dependency constraints (§4.2) were re-checked against
MISSION_STATE_IJSDK.json at the current PR #8 head: **P3 FAIL (reopened),
P4 harness core FAIL (reopened, P4A checkpoint 1 stopped by the operator),
P5 FAIL (reopened, P5R pending), formal GPU matrix NOT authorized.** The
blockers the order anticipated have not been resolved. Nothing from those
scopes is inherited as qualified.

## 3. PR #9 / IJ-SLM-1.0 (previously unreported dependency)

- Stacked on PR #6's current head `06f25ab` (ancestry verified).
- Scope: full capability atlas on the real Antigravity SDK and llama.cpp for
  the same three small models as IJ-NANO (MiniCPM5-2B, LFM3-1.7B,
  Qwen3.5-2B), 23,050 SDK + 13,500 direct-runtime trials planned (36,550
  formal trials required), plus model passports and a specialization study.
- Execution state at audit: `gpu_handoff: PASS`, Q2 sealed, arm-A
  direct-runtime mechanical trials already recorded in
  `physical_progress.json` (e.g. `A/direct_first/all/first_pass_mechanical`
  149/166 with Wilson intervals); semantic dimensions BLOCKED;
  `formal_trials_recorded: 0` in the 03:46Z state snapshot with trials
  landing afterwards.
- No IJ-SLM worktree or process exists on this workstation; its worker runs
  elsewhere.

**Determination: IJ-SLM-1.0 holds the GPU lease.** IJ-NANO respects it
(IJN-B-001). All IJ-NANO physical phases are BLOCKED; literature, protocol
and pure-software work proceed now.

## 4. Branch topology (verified)

```
codex/ij0-tool-calling (default) ── 0592c31
mission/ij-0.7.1-atlas (PR #6) ─── fe56f324 ── … ── 06f25ab (head)
                                     └─ mission/ij-sdk-1.0 (PR #8): P2…P5, P0R, P4A → 56c6c74 (head)
06f25ab ── codex/ij-slm-1.0 (PR #9) → 350fb529 (head)
mission/ij-nano-1.0-slm-native-agentic-runtime = 56c6c74 + IJ-NANO work (this branch)
```

Base selection rationale: the mission order names PR #6 and PR #8 as
dependencies; PR #8's head contains the complete required asset set
(digest-verified model manifest S1/S2/S3/R1/R2, gfx1100 engine/backend
qualification P1 PASS, admission tooling, Atlas datasets via ancestor
fe56f324, hardened-by-audit harness tests as reference). The newer Atlas
assets on the IJ-SLM line are documented as a coordination dependency, not a
source base, to avoid entangling with the active GPU mission. No rebase onto
moving parents; PR #6/#8/#9 branches are never modified.

## 5. Assets and identities verified

- Physical GPU: AMD Radeon RX 7900 XTX (gfx1100), driver 32.0.21030.2001 —
  matches IJ-SDK P1 environment evidence. The gfx1151 references in the
  default branch's AGENTS.md/HANDOFF.md belong to the previous workstation
  (IJ-SDK known-limitation L-01).
- Models on disk (sibling IJ-SDK worktree, outside git): S1 MiniCPM5-2B
  (apache-2.0), S2 LFM3-1.7B (**LFM Open License v1.0 — revenue-conditioned,
  IJN-B-003**), S3 Qwen3.5-2B (apache-2.0, community GGUF identity recorded),
  R1 Qwen3-8B, R2 Qwen3-14B (apache-2.0). Digest anchors:
  `models/ij_sdk/model_manifest.json` at the base commit; IJ-NANO re-verifies
  full SHA256 against disk at N02 and records fresh evidence.
- Engine: llama.cpp b12359 (build commit b1b770d9), cpu/vulkan/rocm installed;
  IJ-SDK P1 PASS on this machine (Vulkan primary, ROCm repaired via
  rocm-sdk-device-gfx1100==10.0.0).
- Datasets inherited via fe56f324 (roster verified by IJ-SDK P0): TC-V2 500
  (+120 dev), MULTITOOL-V1 600 (+6), AGENTIC-PLAN-V1 800 worlds dual-track,
  JOB-V1 600. Development material only — not unseen holdout.
- Environment constraints inherited: B-004..B-009 (no C++ toolchain, no power
  meter, soak/power owner decisions, missing SDK checklist, MiniCPM5 native
  parser fixture failures — the last directly informs M03/M04 design).

## 6. Dependency qualification summary

Full detail in `evidence/IJNANO/N00/dependency_qualification.json`.

| Dependency | Qualification | IJ-NANO action |
|---|---|---|
| Atlas datasets (PR #6 @ fe56f324) | roster verified PASS (IJ-SDK P0) | reuse as development material |
| Engine/backends on gfx1100 (IJ-SDK P1) | PASS | reuse config, re-verify at N02 |
| Model identities (IJ-SDK P2/P0R) | PASS | reuse after fresh SHA256 |
| SDK admission (IJ-SDK P3) | FAIL (reopened) | not inherited; arms BLOCKED |
| Harness core (IJ-SDK P4/P4A) | FAIL / NOT_RUN | REFERENCE_ONLY (D04-D07 = design requirements) |
| Oracle/evaluator (IJ-SDK P5/P5R) | FAIL / pending | not inherited; N05 BLOCKED for formal claims |
| IJ-SLM-1.0 (PR #9) | in flight, GPU holder | coordination only |
| Formal GPU matrix | not authorized | physical phases BLOCKED |

## 7. Isolation delivered

Dedicated worktree (path withheld from evidence), branch
`mission/ij-nano-1.0-slm-native-agentic-runtime` at `56c6c74b`, ordinary
non-force pushes, mission-only state files, no edits to other missions'
files. Tracking issue and draft PR recorded in MISSION_STATE_IJNANO.json.

## 8. Permitted while blocked

N01 literature investigation; research-protocol, statistical and dataset
design; pure-software NanoAgent development with unit tests (labelled
software-only). See dependency_qualification.json `permitted_now`.

## 9. Gate assessment

`N00_RESEARCH_BASELINE_FROZEN` — **PASS**. Conditions: live remote re-query
done (§2); dependency constraints re-verified (§2, §6); base commit selected
with recorded identity and ancestry (§4); state files created; mission order
committed as preregistration; GPU lease determined and respected (§3);
owner-input questions recorded (dependency_qualification.json
`owner_input_needed`).
