# IJEVAL_00 — Historical Evaluation Audit (IJ-EVAL-ASSURANCE-1.0, EA00)

Status: COMPLETE (gate `EA00_EVALUATION_BASELINE_AUDITED` claim below)
Date: 2026-11-28 · Branch `mission/ij-eval-assurance-1.0-systemic-evaluation-integrity` · Base `bc4555e`

## 1. Audited repository and dependency identities

| Object | Identity at audit time | Verification |
|---|---|---|
| IJ-NANO HEAD (mission base) | `bc4555ecb6db989beefaeeba452c1c160283da2c` | local worktree == PR #11 remote head (gh) |
| PR #6 Atlas | `06f25ab50db9e8ef074d9fb804de3191d7eadb98` | gh pr view |
| PR #8 IJ-SDK | `56c6c74bf7216eb9cf65be4056c8db1964d23b05` | gh pr view == local IJSDK worktree HEAD |
| PR #9 IJ-SLM | `fb28ef2492388be237bdb2f835d261c819569551` | gh pr view |
| Default branch | `codex/ij0-tool-calling` @ `0592c31` | git |
| N02RR corrected replay identity | `6701a6a6a08b34d9` | manifest.json |
| Physical experiment | `ec5b95357e960f99`; source `7a1b9d7d160202d8`; diagnostic `36bfed1d55a9987b` | sealed manifests |

Scope corrections discovered during audit (important for later waves):
- The **Atlas/IJ-0.6–0.7.3 lineage lives in the IJSDK worktree** (stacked on the
  Atlas branch `fe56f324`), not in the default-branch checkout, which contains
  only the IJ-0 tool-calling era.
- **IJ-SLM has no separate working tree**; its evaluation-defect history is the
  IJ-NANO-lineage commit series already covered by the EV/NA-D/PR-D/RS families.
- No physical experiment was running at audit time (no python/llama-server
  processes; GPU idle) — branching was safe.

## 2. Historical defect inventory (deliverable §2.1)

`evidence/IJEVAL/EA00/historical_defect_inventory.json` — **67 records**:
EV01–EV07 (7), NA-D01–NA-D08 (8), PR-D01–PR-D10 (10), RS01–RS08 (8, grouped
as defined in the source ledgers), IJE-D001/D002 (2, discovered by this audit),
cross-mission 38 (IJ-0 TC-V1-a..g, IJ06/IJ07/Atlas/IJ073/IJ-SDK families).
Generator: `scripts/ij_eval_assurance/ea00_defect_inventory.py`;
cross-mission source: `evidence/IJEVAL/EA00/cross_mission_sweep.json`.

Coverage of the mandatory defect-family table (order §2.1): artifact loading
(RS01, NA-D02/D03), exception masking (RS01 mask at b0d57e9, IJE-D001),
semantic false negatives (RS01 588 rows, IJ06-RS-1 41/42), semantic false
positives (IJ06-RS-2 15, TC-V1-a 15/22, IJSDK-D02 16/16), state predicates
(EV01), predicate semantics (EV03), argument validation (EV02, PR-D04/D05),
identifier handling (EV04, IJ07-CJK), unit handling (EV05), parser ambiguity
(PR-D04/D05, IJ06 parser P4/P4b), duplicate keys (EV02, IJ06-PARSER-P4b),
protocol mismatch (PR-D02, IJ07-RC-11), tool exposure (PR-D01, IJSDK-E-18),
transaction state (NA-D01/D06/D07, IJSDK-D03/D06, ORC-V2-c), evidence identity
(PR-D06/D07/D08-9, HA-4/5, NA-D02/D03/D05), statistics (PR-D10, RS04–RS08,
IJ07-STAT discipline), telemetry (TEL-1, PR-D08/D09), coverage (HA-3/5, F19).

### 2.1 Headline findings requiring EAE design attention

1. **Unrepaired critical defects in the live IJ-SDK evaluation stack**
   (`evaluation/ij_sdk/`, worktree at PR #8 head):
   - D01: the oracle *qualification gate itself* false-passes (reads PASS with
     `all_negatives_rejected=false`; 8/16 intentionally weakened oracles pass).
   - D02: `answer_must_contain` substring semantics → 16/16 semantic false
     positives (negation, substring numbers, wrong currency/entity).
   - D03: `final_state_hash` never read; unauthorized writes can score
     CORRECT_RESULT (direct INV09 violation surface).
   - D04–D07 partially repaired (46/76 integrity probes still reproduce).
   IJ-SDK formal GPU runs are already NOT authorized by that mission's own
   state file — consistent with this audit. EAE must treat IJ-SDK business
   verdicts as unqualified scope (no code changes on their branch; EA15
   adapter work happens here).
2. **LLM-judge scope stays quarantined**: AEVE judge families 0/4 admitted
   (J-1..J-6; alpha −0.120..0.211 vs 0.80). Confirms order §7.3: LLM judges
   never deterministic business truth; separate qualification scope.
3. **Ground-truth independence violations exist in Atlas planning**
   (A1-16 single-source world/witness/final co-generation) — exactly the
   EA03 §5.2 target.
4. **Every historical evaluator family that was ever quantified against a
   repaired reference exhibited false verdicts** (RS01 588 FN; IJ06-RS-1 41/42
   FN + 15 FP; IJ073-ORC 602 accepted mutations; B-IJ072-02). Uniform
   direction: unqualified evaluators err in BOTH directions; only differential
   verification + mutation gates caught them.

## 3. N02RR residual audit (deliverable §2.2)

Inspected: `scripts/ij_nano/n02rr_replay_lib.py`, `n02r_rescore.py`,
`n02rr_rescore.py`, `n02rr_analyze.py`, `n02rr_qualification_lib.py`.
Reproduced with production components (CPU, zero GPU):
`scripts/ij_eval_assurance/ea00_n02rr_residual_repro.py` →
`evidence/IJEVAL/EA00/n02rr_residual_risk_reproduction.json` (commit f081655).

| # | Finding | Status |
|---|---|---|
| R1 | Evaluator/replay exception coerced to `semantic_correct=False` (`n02rr_replay_lib.py:326-330`); classifiers label REPLAY_ERROR / EVIDENCE_INSUFFICIENT, verdict field does not | REPRODUCED |
| R2 | Causally impossible P7S two-stage response retains `semantic_correct=True`; only `failure_class=EVIDENCE_INCONSISTENT_STAGE2_TOOL` signals it | REPRODUCED |
| R3 | Production analyzer `n02rr_analyze.load_rows` has **no eligibility filter** (`r["sem"]=bool(verdict)`, line 86): injected headline moves 870/2184 → 871/2186; REPLAY_ERROR row counts as model FAIL, inconsistent row as PASS; paired() lines 143–148 and main() line 291 share the defect | REPRODUCED |
| — | Sealed corpus: **0** REPLAY_ERROR / EVIDENCE_INCONSISTENT / EVIDENCE_INSUFFICIENT rows → published 1.2R corrected headline (870/2,184) **not contaminated**; both risks structural/latent | VERIFIED |
| — | Repaired `n02r_rescore.py:118` seals the same coerced boolean into future experiment records | NOTED |

Answering the order's two §2.2 questions directly:
- *Can a downstream analyzer count a replay exception as a model failure?*
  **Yes — structurally.** `n02rr_analyze` does exactly that if such rows ever
  exist (they do not in the sealed corpus). The classification layer is honest;
  the consumption layer ignores it.
- *Can multi-stage causal inconsistency retain semantic_correct=True with only
  the failure classification indicating invalid evidence?* **Yes** (R2), and
  the analyzer ignores that classification too (R3).

Dispositions: no retroactive edit to sealed N02RR evidence (INV07); closure is
forward-looking via EA02 (`eligible_for_semantic_statistics` + typed verdict
NOT_EVALUABLE), EA05 differential layer, EA09 in-flight NOT_EVALUABLE canary
controls, EA10 circuit-breaker trigger. Tracked as IJE-D001/IJE-D002 +
blocker IJE-B-003.

## 4. Cross-mission evaluator inventory (deliverable)

| Evaluator | Location (worktree) | Qualified scope | Known defect exposure |
|---|---|---|---|
| Cognitive evaluator contract v2 (N05AR) | IJNANO `src/nanoagent/eval/{comparators,contracts,controls,qualification}.py` | cognitive families only; mutation-gated (9 mutant classes) | EV01–07 repaired; explicitly NOT the business Oracle |
| N02R scorer + parser v2 | IJNANO `benchmarks/ij_nano/n02r/{scorer,arms_v2}.py` | N02R families, gate N02R_PARSER_EVALUATOR_INTEGRITY_GO | PR-D01..05 repaired |
| N02RR replay engine | IJNANO `scripts/ij_nano/n02rr_replay_lib.py` | offline replay of sealed artifacts | IJE-D001/D002 (this audit) |
| TC-V1 frozen scorer | default branch `benchmarks/tool_calling/runner/evaluate.py` | frozen diagnostic only | TC-V1-a..g; superseded by V2 |
| Evaluator V2 + oracle + persisted holdout | IJSDK `benchmarks/tool_calling_v2/` | multitool workflow scoring, mutation battery | IJ06-RS-* repaired; RS-3 OPEN |
| Planning oracle v1→v2 differential | IJSDK `benchmarks/agentic_planning_*/oracle.py` | 800/800 worlds re-verified, 4 evidence paths | ORC-1..6 repaired; 235 cases non-alignable |
| AEVE judge framework | IJSDK `evaluation/aeve/` | 0/4 judge families admitted | J-*, HA-* ; LLM-judged scope BLOCKED |
| IJ-SDK business oracle + qualifier | IJSDK `evaluation/ij_sdk/{business_oracle,qualify_oracle}.py` | NONE (gate itself defective) | D01/D02/D03 NOT repaired |
| Publication gate | all branches `scripts/tools/publish_check.py` | repo-wide commit gate | exit-code history documented; count-based since d3dd82c |

## 5. Evaluator inventory → EAE control mapping (summary)

- Artifact loading/integrity → EA08 (validated loader is the *only* read path),
  EA07 mutant `mutant_unpack_last_stage` as permanent control.
- Exception masking → EA02 typed status (INV01/INV02), EA10 hard stop on
  unexpected evaluator exception.
- Substring/negation/unit/identifier semantics → EA04 parser qualification
  battery, EA05 independent assertions, EA07 mutants.
- Ground-truth independence → EA03 (executable witnesses, independent author).
- Denominators/telemetry/accounting → EA11 qualified analyzer consuming only
  `eligible_for_semantic_statistics` rows.
- Qualification-gate self-defects (IJSDK-D01) → EA02 central validator,
  EA10 revoked-certificate detection, EA18 bypass challenges.
- Leakage (HA-1/2/7, INV06) → EA03 leakage tests, EA08 identity binding,
  EA13 holdout protection.

## 6. Exact reproduction commands

```bash
python -I scripts/ij_eval_assurance/ea00_n02rr_residual_repro.py
python -I scripts/ij_eval_assurance/ea00_defect_inventory.py
```

Runtime junction required on a fresh worktree (untracked):
`cmd /c mklink /J runtime\llama-cpp\vulkan <IJNANO-worktree>/runtime/llama-cpp/vulkan`

## 7. Gate

`EA00_EVALUATION_BASELINE_AUDITED` — **claim: granted** on the scope audited
above (IJ-NANO full lineage + IJ-0/IJ-0.6–0.7.3/IJ-SDK cross-mission sweep of
the two available worktrees + §2.2 reproduction). Limitation: IJ-SLM PR #9
diff was inspected only through shared commit history, not a dedicated
checkout (its evaluation code is byte-identical to the IJ-NANO lineage it
preceded); residual risk recorded, not blocking, because the shared defect
families are fully represented in the audited ledgers.
