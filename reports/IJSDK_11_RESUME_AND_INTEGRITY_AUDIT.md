# IJSDK_11_RESUME_AND_INTEGRITY_AUDIT — P0R Resume and Independent Baseline Audit

Mission: **IJ-SDK-1.1 — Benchmark Integrity Hardening & Cross-SDK Physical Qualification** (extends IJ-SDK-1.0)
Generated: 2026-11-27 (every remote fact re-queried on this date)
Audited HEAD: `c28a41bad410b66103b499eaaec4ee1b3a227b10` · Frozen source: `fe56f324daf4ae106908e0d0a0f16967afc9c463`
Branch: `mission/ij-sdk-1.0-cross-sdk-agentic-benchmark` · Tracking issue #7 · Draft PR #8

Evidence: `evidence/IJSDK/P0R/baseline_reconciliation.json` (machine-readable reconciliation),
`evidence/IJSDK/P0R/defect_reproductions_audited_c28a41b.json` (76 probes run against the audited bytes).

---

## 1. Verdict

| Question | Answer |
|---|---|
| Is the benchmark foundation trustworthy enough for the formal GPU matrix? | **No.** |
| Concerns D01–D07 | **Reproduced** — 75 of 76 probes against the audited commit; 1 suspected sub-issue not reproduced (counterevidence recorded) |
| Phase gates recorded PASS before this audit | 5 (P0, P1, P2, P3, P5) |
| Phase gates that survive this audit | **3** — P0 (point-in-time), P1 (scope narrowed), P2 (scope = development admission) |
| Phase gates reopened as FAIL | **P3**, **P5**, and the **P4 harness core** (a ledger row had marked it "done PASS") |
| Final acceptance gates G01–G20 satisfied | **0** — and 0 can even be mapped; their definitions are not in the repository |
| `IJSDK_FORMAL_BENCHMARK_ADMISSION_GO` | **NOT RUN** — the previous P5 PASS does not authorize the formal matrix |

All original results, phase reports and evidence files are preserved byte-for-byte (verified by SHA256 before and after the
reproduction run). Nothing below deletes history; stale ledger entries are corrected in place with the superseded value kept.

## 2. Live state reconciliation

| Item | Recorded | Live (2026-11-27) | Disposition |
|---|---|---|---|
| Local HEAD vs remote branch | `c28a41b` | identical; ahead 0 / behind 0 | consistent |
| Frozen source | `fe56f324` ancestor | still an ancestor of this branch **and** of the parent branch | consistent |
| Parent dependency PR #6 | head `fe56f324` | head **`06f25ab`** — advanced after the freeze | P0 statement was true at audit time; frozen source unaffected; PR #6 untouched |
| Sibling work | PRs #2/#4/#6 | PR **#9** (`codex/ij-slm-1.0`) opened and pushed twice during this audit | other workstation active; not touched |
| PR #8 | "stacked on PR #6" | base is the **default branch** `codex/ij0-tool-calling`, not the PR #6 branch | stacking is documentary only |
| PR #8 size | — | +514,777 / −127, 2,509 files, 92 commits | 79 commits are inherited parent work |
| **IJ-SDK-only review diff** | — | **`git diff fe56f324..c28a41b`: 80 files, +7,825 / −5** | this is the diff to review |
| PR #8 body, Issue #7 body | "P1 in progress; P2–P5 NOT_RUN" | stale against the mission state | rewritten at delivery |

## 3. Phase gates are not final acceptance gates

The mission order defines **P0–P19 phase gates** and **G01–G20 final acceptance gates**. These are different systems.

- The only gate list in the repository is the **parent Atlas** system (G00–G29, `atlas/gates.json`), which belongs to mission
  IJ-0.7.1. No IJ-SDK G01–G20 list exists anywhere in the repository.
- Therefore no phase gate can be mapped onto an acceptance gate, and **none is reported as satisfied**.
- The previous session did not overclaim here: its three final verdicts were honestly `NOT_RUN`.
- **Owner input needed:** the G01–G20 definitions (or confirmation of where they live). Until then the dashboard reports
  phase gates and acceptance gates in separate columns, with the acceptance column at 0 of 20 unmapped.

## 4. Phase gate dispositions

| Phase | Gate | Recorded | Audited | Basis |
|---|---|---|---|---|
| P0 | `P0_REPOSITORY_BASELINE_FROZEN` | PASS | **PASS** (point-in-time) | Roster and frozen-source verification stand. |
| P1 | `P1_GFX1100_PHYSICAL_RUNTIME_GO` | PASS | **PASS, scope narrowed** | Vulkan arm is real (API check exit 0, smoke exit 0, 43/43 layers). Byte parity was shown on one prompt set only; per-check detail lived only in gitignored scratch (now published under `evidence/IJSDK/P1/detail/`); the run overwrote inherited parent evidence (E-12, repaired). |
| P2 | `P2_MODEL_IDENTITIES_AND_ADMISSION_FROZEN` | PASS | **PASS, scope = development admission** | Every mandatory model's live SHA256 matches its recorded identity. Admission is a 10-case smoke, not a ranking. The manifest cited as the passport was never committed (E-22). |
| P3 | `P3_SDK_ADMISSION_AUDITED` | PASS | **FAIL — reopened** | "All 10 arms pass C1/C2/C3" is contradicted by its own evidence (§6, E-13…E-16). |
| P4 | `P4_CROSS_SDK_HARNESS_GO` | NOT_RUN (ledger: core "done PASS") | **Harness core FAIL — reopened**; gate NOT_RUN | D04–D07 reproduce. The two ledgers contradicted each other. |
| P5 | `P5_EVALUATOR_SCOPE_QUALIFIED` | PASS | **FAIL — reopened** | Its own result reads `gate=PASS` beside `all_negatives_rejected=false` (§5). |
| P6–P19 | — | NOT_RUN | NOT_RUN | unchanged. |

## 5. Integrity concerns D01–D07, reproduced from the audited bytes

The reproduction tool extracts the harness and oracle packages at `c28a41b` into an empty scratch directory and probes them
there. It never imports the working tree for the audited run. The legacy qualifier's output is redirected to scratch, and every
file under `evidence/IJSDK` is hashed before and after: **49 files, byte-identical**.

| Defect | Probes | Reproduced | What was observed on the audited commit |
|---|---:|---:|---|
| **D01** Oracle qualification false-pass | 6 | 6 | Gate `PASS` with `all_negatives_rejected=false`, exit code 0 — matches the published summary exactly. N06/N07 "rejected" with no rule. N07's expected list admits `CORRECT_RESULT`; a duplicate write with a completion-style answer **is** `CORRECT_RESULT`. **8 of 16 intentionally weakened oracles still pass the battery.** |
| **D02** Semantic false positives | 16 | 16 | 不合格 satisfies `合格`; "not approved" satisfies "approved"; 100 inside 1100; expected 0, answered 120; a negated refusal is `CORRECT_REFUSAL`; wrong currency (美元), wrong scale (万元), wrong entity association and added false claims all give `CORRECT_RESULT`. |
| **D03** Final state not validated | 9 | 9 | `final_state_hash` is never read. An unauthorized write with no rejection event is `CORRECT_RESULT`. A blocked attempt plus an authorized change is reported as `UNAUTHORIZED_STATE_CHANGE`. No state replay exists. |
| **D04** Session contamination | 5 | 5 | Reused adapter, per-trial usage: `2 → 4 → 6` model calls (fresh: `2, 2, 2`). With a 2-call budget: fresh `[PASS, PASS, PASS]`, reused `[PASS, FAIL, FAIL]`. Tool registrations and the business world survive `reset_session`. |
| **D05** Budgets not enforced | 13 | 13 | 180 generated tokens against a budget of 100 (PASS). Every request asks for 1024 tokens. 1.6 s against a 1.0 s deadline. Failed attempts uncharged. Timeout, malformed and truncated responses **escape `run_task` as uncaught exceptions**. |
| **D06** Gateway order | 14 | 13 | **A write-denied action under a scheduled fault executed and changed state** (inventory 120 → 115) and returned data instead of a denial; under `malicious_content` the injected "you now have write permission" text rode on real data. No schema validation, idempotency, transaction or audit. |
| **D07** Evidence contract | 13 | 13 | A parsed Chat Completions body is labelled `model_generation`. No event or parent IDs. Tools correlated by position. Five stages neither emitted nor declared. Missing, duplicated, reordered and corrupted evidence all score `CORRECT_RESULT`. |
| **Total** | **76** | **75** | |

### 5.1 Not reproduced — counterevidence recorded

- **D06.07 (fault index off-by-one): NOT a defect.** I suspected from reading the source that `Fault.call_index` (documented
  1-based) fired on the wrong invocation. Execution shows `call_index=1` fires on the first invocation, exactly as documented.
  Closed as not a defect; the verification probe stays in the suite so the claim cannot quietly return.
- **D06.14 (concurrent dispatch): reproduced, low frequency.** With 2 threads over 200 runs: 0 anomalies. With 4 threads over
  1,500 runs: 32 runs (2.1%) applied the scheduled fault to 0 or 2 calls instead of 1. Real, but rare; reported with both numbers.

### 5.2 Root causes established at source level

| Concern | Cause (file, mechanism) |
|---|---|
| D01 | `qualify_oracle.py`: the gate expression ignores `all_negatives_rejected`; `critical_ok` only asks "is the verdict in a list", so a widened list hides a failure; `rules_fired` is recorded but never checked; no control taxonomy (a metamorphic control is filed as "negative"). |
| D02 | `business_oracle.py`: `answer_must_contain` is substring matching on a comma/space-stripped string; completion claims come from a contract flag, not the text. |
| D03 | `business_oracle.py`: trusts the harness-supplied `state_changes` list; "unauthorized" is inferred from the co-occurrence of `rejected_calls` and `state_changes`. |
| D04 | `adapters/b0_raw.py`: `reset_session` clears history and final answer only; `Usage` lives on the instance and is returned by reference. |
| D05 | `adapters/b0_raw.py`: `max_tokens` hard-coded to 1024; the deadline is a per-request socket timeout; only `HTTPError` is caught; `Budget` has no prompt, tool-duration or cancellation fields. |
| D06 | `gateway.py`: the fault branch runs **before** the unknown-tool and permission checks, and two fault kinds call the handler. |
| D07 | `contracts/events.py` + `b0_raw.py`: stage names overstate what is captured; no identifiers; no validator. |

## 6. Evidence and record integrity findings

| ID | Severity | Status | Finding |
|---|---|---|---|
| E-01 … E-03 | critical | reproduced | D01: contradictory gate, no attribution, 8 surviving weakened oracles |
| E-04 … E-05 | critical | reproduced | D02/D03: wrong answers accepted; final state never validated |
| E-06 … E-07 | high | reproduced | D04/D05: contamination; budgets and error handling |
| E-08 | critical | reproduced | D06: **fault injection grants permission** |
| E-09 … E-11 | high/medium | reproduced | D06/D07 remainder |
| E-12 | high | confirmed, **repaired** | **Inherited parent-mission evidence was overwritten.** Re-running inherited installers on this machine replaced `evidence/IJ0/model_identity.json` and `evidence/IJ0/rocm_runtime_install.json` (the 2026-11-24 gfx1151 records) and the timestamp of `models/model_manifest.json`. Originals restored from the frozen source; this machine's re-run preserved under `evidence/IJSDK/P1/`. |
| E-13 | high | confirmed | **`installed_artifacts.json` is invalid.** All eight entries are the DSPy environment's 27-package freeze; the other seven SDKs' dependency identities were never recorded — including no recorded proof B8 is the 1.26.0 release the SEC-01 control depends on. |
| E-14 | high | confirmed | **B1 (Antigravity) conformance is unsupported.** No tool round-trip in code or evidence; its chat check passed on a truthy `ChatResponse` object. |
| E-15 | medium | confirmed | No wire capture exists: `wire` is empty in all ten records although the report says otherwise. |
| E-16 | medium | confirmed | B4 ran model-generated Python through the default in-process executor, unsandboxed, on the host. |
| E-17 | medium | confirmed | No regression tests exist for the harness or the oracle; both landed in one commit, so the "4 defects fixed by differential testing" have no red state in history. |
| E-18 | medium | confirmed | Cross-arm confounds: B7 runs `openai 2.54.0`, every other arm `3.60.0`; B8 pulls in over 210 packages (211 by `pip freeze`) and depends on `openai-agents 0.26.0`. |
| E-19 | low | confirmed | Parent branch advanced; PR #9 opened. Neither touched. |
| E-20 | low | confirmed | G01–G20 are not defined in the repository (§3). |
| E-21 | low | **not reproduced** | Suspected fault-index off-by-one — counterevidence (§5.1). |
| E-22 | high | confirmed, **repaired** | **`models/ij_sdk/model_manifest.json` was never committed** — excluded by `.gitignore` rule `models/*`. The P2 report cites it as frozen evidence, but it existed only on this workstation. |

### 6.1 Root cause of E-13 (controlled counterfactual)

The committed install script's capture loop uses `Join-Path $root $name "Scripts\python.exe"` — the three-argument form that
**Windows PowerShell 5.1 does not support** (added in PowerShell 6). `Join-Path` fails, the interpreter path becomes null, and
the loop records nothing.

| Variant | Result |
|---|---|
| A — committed logic, PowerShell 5.1 | 0 keys written |
| B — same loop, nested `Join-Path` | 8 distinct lists: 39 / 36 / 26 / 43 / 52 / 211 / 1 / 27 packages |
| Published file | equals variant B's DSPy list **for every key** |

So the committed script cannot have produced the committed file. The file's signature (every entry equal to the *last*
environment's freeze) is what a stale-variable capture produces, which points to an unrecorded ad-hoc capture — that part is
inferred, not proven.

## 7. Corrections applied in this commit

| What | Change | History kept |
|---|---|---|
| `evidence/IJ0/*`, `models/model_manifest.json` | restored to the frozen-source bytes | gfx1100 re-run at `evidence/IJSDK/P1/model_identity_gfx1100.json`; ROCm record already in `evidence/IJSDK/P1/rocm_runtime_install.json` (content-identical) |
| P1 detail evidence | 6 per-check files published under `evidence/IJSDK/P1/detail/` | new; previously exit codes only |
| `.gitignore` | re-includes `models/ij_sdk/model_manifest.json` | weights remain ignored (verified) |
| `models/ij_sdk/model_manifest.json` | live-verified SHA256 for all 10 files; S3b/S3c/S3d/R1/R2 `status: verified`; R2 revision pinned; admission scores derived from the v1.0.1 evidence cases | v1.0.0 scores under `dev_score_history`, old prose under `weaknesses_v1_0_0`, pre-download sizes under `file_expected_at_download` |
| `MISSION_STATE_IJSDK.json` | P3 → FAIL, P5 → FAIL, P4 harness core → FAIL; IJ-SDK-1.1 verdicts added (all `NOT_RUN`); acceptance-gate mapping recorded as not verifiable | previous values under `reopened_by` |
| `TASK_LEDGER_IJSDK.md` | stale duplicate rows marked superseded; reopened rows corrected; P0R rows added | original rows retained |

The original P5 evidence (`evidence/IJSDK/P5/differential_results.json`) and all five phase reports are untouched. They are
superseded, not rewritten: P5 by P5R, P3 by P4B.

## 8. Artifacts and environments (re-verified live)

| Item | Result |
|---|---|
| Mandatory models S1 MiniCPM5-2B, S2 LFM3-1.7B, S3 Qwen3.5-2B | Q8_0 SHA256 matches recorded identity; S1/S2 Q4_K_M also match |
| References R1 Qwen3-8B, R2 Qwen3-14B | match prior-project pins |
| Other candidates (S3a, S3b, S3c) | match admission evidence — 10 of 10 files |
| llama-server b12359 (cpu, vulkan, rocm) | all three binaries match the P1-recorded SHA256 |
| Qwen3.5-2B Q4_K_M | **not present locally** — needed for the P8A quantization decision |
| SDK environments | 8 isolated venvs (B2, B3/B4, B5, B6, B7, B8, B9, O1) + B1 in the shared project venv; true per-environment package lists are in the reconciliation record |

## 9. Authorization and next steps

**Formal GPU matrix: NOT authorized.** No substantial GPU time is spent on the formal matrix. The sequence is:

1. **P4A** — repair D01–D07, add regression tests, record red → green, publish `IJSDK_P4A_INTEGRITY_HARDENING.md`.
2. **P4B** — formal adapters B0–B9 on conformance-verified paths, ≥ 40 development cases, fixture controls then physical cases,
   CodeAgent isolation, supply-chain re-verification with digest pins, one-command runner.
3. **P5R** — two independent oracles, ≥ 500 controls, scope matrix.
4. **P6 → P7 → P8A → P8B** in order; each gate granted only on its own evidence.

GPU use before P8A is limited to adapter conformance and qualification cases (small, development data only).

### 9.1 Open items that need the owner

1. **G01–G20 definitions** — required before any acceptance gate can be reported.
2. **B8 trust decision** — SEC-01 is re-verified in P4B against authoritative sources; whether Microsoft Agent Framework stays an
   arm or drops to comparator is the owner's call and is recorded, not assumed.
3. **PR #8 base** — left on the default branch. Changing it to the PR #6 branch would shrink the review diff from 2,509 files
   to about 80 but changes the merge order; not done without authorization.

## 10. Reproduction

```powershell
# D01-D07 against the audited commit (writes only the --out file)
python -I scripts/tools/ij_sdk_integrity_repro.py `
    --source c28a41bad410b66103b499eaaec4ee1b3a227b10 `
    --out evidence/IJSDK/P0R/defect_reproductions_audited_c28a41b.json

# the same probes against the current tree, after repair
python -I scripts/tools/ij_sdk_integrity_repro.py --source WORKTREE `
    --out evidence/IJSDK/P4A/defect_reproductions_after_repair.json

# baseline reconciliation (live git + GitHub + disk + recorded evidence)
python -I scripts/tools/ij_sdk_p0r_reconcile.py
```

Recovery state if interrupted after this commit: HEAD is the P0R commit on the mission branch; nothing is running; the next
action is P4A (start with D06 — the gateway is the smallest module and its defect is the most severe).
