# IJ-NANO-1.2R — Quantitative Evidence Reconciliation (RS03–RS08)

- Mission order: `docs/IJNANO_MISSION_ORDER_V1_2R.md` §5–§8
- Supersedes: the quantitative sections of
  `reports/IJNANO_02R_PROTOCOL_CAUSAL_ANALYSIS.md` (see the supersession
  notice there). Historical values are not removed there; they are
  historical.
- Physical experiment (unchanged, sealed): `ec5b95357e960f99`
  (2,184 logical slots = 1,397 offline re-scores + 787 physical trials;
  sources `7a1b9d7d160202d8`, diagnostic `36bfed1d55a9987b`)
- Corrected replay identity: `6701a6a6a08b34d9`
  (`evidence/IJNANO/N02RR/manifest.json`; analysis-only, no GPU)
- Row-level evidence: `evidence/IJNANO/N02RR/trial_reconciliation.jsonl`
  (2,184 rows: original published verdict / original source verdict /
  corrected verdict / parser outputs / failure reasons / telemetry /
  source-evidence chain / change classification)
- Corrected matrix: `evidence/IJNANO/N02RR/corrected_protocol_matrix.json`
- Chain verification: `evidence/IJNANO/N02RR/evidence_verification.json`
  (gate `N02R_QUANTITATIVE_EVIDENCE_RECONCILED` = PASS)

**Status: COMPLETE. 870/2,184 corrected semantic PASS (39.8%) vs 282/2,184
(12.9%) as published under the defective re-score. No GPU re-execution was
required: every preserved artifact suffices (0 EVIDENCE_INSUFFICIENT,
0 PHYSICAL_REEXECUTION_REQUIRED).**

## 1. Evidence-chain verification (RS03)

All 2,184 logical slots verified at every level — hash field present →
artifact exists → SHA256 verified → contents schema-valid → physical
provenance verified → replay semantics valid: **2,184/2,184 at each level,
0 findings**. Roster membership: recomputed main+panel queue matches the
2,184 executed unique slots exactly (no missing/extra/duplicate slots);
every `trial_id` recomputes from the frozen identity. The 1,397 reused
trials retain full provenance: source row present, artifact hash equal,
artifact located in the sealed source run, and:

- **manifest comparison**: source vs destination identities are equal on
  every request-shaping field (models+SHA256+quant, engine exe+DLL SHA256,
  backend, GPU identity, suite hash, arm registry, applicability, budgets,
  decoding, cache policy, server profiles); the only differences are the
  two implementation hashes (`arms_v2`, `controller_v2`) — the parser-era
  fixes;
- **request-renderer source**: the two `arms_v2` eras (git blobs
  `8d2039d6` @ b0c7f44 vs `78d33b9c` @ 26445d6) are AST-identical over the
  complete request-rendering surface (12 functions, 9 constants:
  `build_request`, `info_block`, `_user_text`, schema/grammar/tool-schema
  builders, applicability and budget constants); the only differing
  functions are parser-side;
- **behavioral request identity** (source sufficiency): per-model/profile
  chat-template fingerprints (`/apply-template` rendered-prompt SHA256) are
  identical across the two experiments' verified physical sessions —
  the rendered prompts are byte-equal at the HTTP layer, not merely
  source-equal;
- session evidence: all six (model × profile) server sessions verified by
  netstat socket-owner PID with recorded health and offload lines.

## 2. Reconciliation outcome (mission §6)

| change classification | rows | meaning |
|---|---|---|
| CORRECTED_FALSE_NEGATIVE | **588** | published FAIL → corrected PASS (all offline-rescored) |
| CORRECTED_FALSE_POSITIVE | **0** | the defect could only fail trials |
| TELEMETRY_CORRECTED | **809** | verdict unchanged (already failing) but structure/telemetry repaired |
| UNCHANGED_VALID | **787** | physical rows — re-scored independently, verdict-identical |
| EVIDENCE_INSUFFICIENT | 0 | no artifact failed validation |
| PHYSICAL_REEXECUTION_REQUIRED | 0 | no GPU time spent or needed |

Independent consistency checks: corrected replay reproduces the 787 sealed
physical verdicts exactly (payload-identical, 787/787) and restores the
1,397 source-experiment physical verdicts exactly (1,397/1,397 — the
parser-era change is behaviorally inert on non-raising inputs, as the
function-level diff predicted).

## 3. Corrected protocol matrix (primary budget 1024, main scope)

Semantic accuracy / structural validity (n per cell in the matrix; Wilson
95% CIs included there):

| arm | S1 sem | S1 struct | S2 sem | S2 struct | S3 sem | S3 struct |
|---|---|---|---|---|---|---|
| M-P0 freeform chat | 0.533 | 0.717 | 0.567 | 0.600 | 0.317 | 0.317 |
| M-P1 chat+schema | 0.650 | 0.783 | 0.617 | 0.667 | 0.317 | 0.317 |
| M-P2 thinking-off | 0.567 | 1.000 | 0.550 | 1.000 | **0.617** | 1.000 |
| M-P3 completion+schema | 0.567 | 1.000 | 0.217 | 0.983 | 0.483 | 0.983 |
| M-P4 completion+GBNF | 0.467 | 1.000 | 0.300 | 0.967 | 0.400 | 1.000 |
| M-P6 DSL | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.083 |
| M-P7 enumerated | 0.275 | 0.900 | 0.250 | 0.925 | 0.250 | 1.000 |
| P5A native business tools | 0.567 | 0.633 | 0.600 | 0.733 | 0.367 | 0.500 |
| P5B record_answer | 0.500 | 0.667 | 0.200 | 0.333 | 0.350 | 0.633 |
| P7S two-stage | 0.200 | 1.000 | 0.000 | 0.500 | 0.000 | 1.000 |
| T2 reasoning-budget 256 | **0.700** | 1.000 | **0.683** | 1.000 | **0.650** | 1.000 |

(n: 60 per chat/completion arm, 40 for M-P7 [applicability], 30 for P5A
[applicability], 10 for P7S [structured_action only].)

## 4. Corrected empty-final-content and the reasoning-burn mechanism

The published matrix reported "empty final content" up to 1.00 by counting
**absent telemetry as empty output**. Corrected taxonomy (mechanism split;
content read from the artifacts):

| arm | S1 empty | S2 empty | S3 empty | of which budget-exhausted |
|---|---|---|---|---|
| M-P0 / M-P1 (default thinking) | 0.20/0.22 | 0.33/0.33 | 0.68/0.68 | **100%** |
| M-P2, T2, M-P3, M-P4, M-P6, M-P7, P7S | 0.00 | 0.00 | 0.00 | — |
| P5A / P5B | 0.17/0.25 | 0.20/0.45 | 0.13/0.08 | 100% |

Every empty final output in the default-thinking chat arms is a
`finish_reason=length` truncation with zero final content: the model spent
the entire generation budget on reasoning (S3: 41/60 trials at M-P0/M-P1).
Thinking-disabled (M-P2) and reasoning-budget (T2) arms have **zero**
empties on all three models. Empty-final-output is a reasoning-burn
phenomenon, not a refusal phenomenon.

## 5. Paired statistical comparisons (RS04)

Method: identical (model, task) instances at primary budget; intersected
applicable task IDs; exact two-sided McNemar on discordant pairs;
conservative Newcombe hybrid-score CI for the paired difference. **No
equivalence claims are made anywhere** — no practical-equivalence margins
were preregistered; nonsignificant results are reported as inconclusive,
not as parity. Significant results (p<0.05) in bold.

| model | contrast | paired n | rates | Δ | McNemar p |
|---|---|---|---|---|---|
| S1 | constrained vs freeform chat (M-P1−M-P0) | 60 | 0.65 vs 0.53 | +0.117 | **0.016** |
| S1 | enumerated vs JSON (M-P7−M-P3) | 40 | 0.275 vs 0.475 | −0.200 | **0.021** |
| S1 | DSL vs JSON (M-P6−M-P3) | 60 | 0.000 vs 0.567 | −0.567 | **<0.001** |
| S2 | chat vs completion transport (M-P1−M-P3) | 60 | 0.617 vs 0.217 | +0.400 | **<0.001** |
| S2 | DSL vs JSON | 60 | 0.000 vs 0.217 | −0.217 | **<0.001** |
| S2 | business tools vs record_answer (P5A−P5B) | 30 | 0.600 vs 0.100 | +0.500 | **<0.001** |
| S3 | thinking-off (M-P2−M-P1) | 60 | 0.617 vs 0.317 | +0.300 | **<0.001** |
| S3 | reasoning-budget (T2−M-P1) | 60 | 0.650 vs 0.317 | +0.333 | **<0.001** |
| S3 | chat vs completion (M-P1−M-P3) | 60 | 0.317 vs 0.483 | −0.167 | **0.021** |
| S3 | enumerated vs JSON | 40 | 0.250 vs 0.525 | −0.275 | **<0.001** |
| S3 | DSL vs JSON | 60 | 0.000 vs 0.483 | −0.483 | **<0.001** |
| S1 | reasoning-budget (T2−M-P1) | 60 | 0.700 vs 0.650 | +0.050 | 0.453 (inconclusive) |
| S2 | reasoning-budget (T2−M-P1) | 60 | 0.683 vs 0.617 | +0.067 | 0.424 (inconclusive) |
| S1 | thinking-off (M-P2−M-P1) | 60 | 0.567 vs 0.650 | −0.083 | 0.332 (inconclusive) |
| S2 | thinking-off (M-P2−M-P1) | 60 | 0.550 vs 0.617 | −0.067 | 0.455 (inconclusive) |
| S1 | native tools vs schema (M-P1−P5A) | 30 | 0.800 vs 0.567 | +0.233 | 0.065 (inconclusive) |
| S2/S3 | native tools vs schema | 30 | ≈equal | +0.03 | 1.0 (inconclusive) |
| S1/S2/S3 | two-stage vs single JSON (P7S−M-P3) | 10 | ≤0.2 vs 0.2–0.6 | −0.4/0.0/0.0 | 0.125 / no discordants (inconclusive) |

P7S two-stage causal reconstruction (RS02): all 30 P7S artifacts carry
both stages (or exactly one when stage-1 failed selection); the recomputed
stage-1 selection matches the stage-2 payload tool in **30/30 cases** —
the preserved evidence is causally consistent, and the 23 wrong stage-1
selections propagate into wrong final actions (TOOL_MISMATCH), i.e. they
are NOT hidden by correct-looking final responses. 5/30 trials never
reached stage 2 (selection failure). Mean total latency 0.664 s and total
prompt tokens 123.7 across both stages (n=30).

## 6. Resource telemetry (RS07), recovered from artifacts

Every mean carries its measured sample count; missing telemetry is
reported as missing, never as zero. The corrected replay reproduces the
source experiment's telemetry on all 1,397 reused trials (usage
1,397/1,397 — 1,034 with captured values, 363 with consistent
`NOT_CAPTURED` markers where llama-server omitted usage; latency
1,397/1,397). The `/completion` endpoint (M-P3/P4/P6/P7, P7S stage 2)
returned no usage object in this engine build (60 missing per completion
arm per model) — those cells have token means `None (n=0)`.

| arm | latency (mean, n) | completion tokens (mean, n) |
|---|---|---|
| S1 M-P1 vs M-P2 vs T2 | 2.85 s / 0.15 s / 1.44 s (60 each) | 505 / 16 / 239 |
| S2 M-P1 vs M-P2 vs T2 | 3.91 s / 0.23 s / 1.66 s (60 each) | 656 / 18 / 266 |
| S3 M-P1 vs M-P2 vs T2 | 4.32 s / 0.24 s / 1.53 s (60 each) | 871 / 20 / 279 |
| P5A (S1/S2/S3) | 2.22 / 2.72 / 1.42 s (30 each) | 371 / 449 / 260 |

Interpretation bounds: default-thinking chat spends 86–871 completion
tokens per trial (mostly reasoning, S3 burns 68% of trials to exhaustion
at budget 1024); thinking-off cuts latency ~15–20× and completion tokens
~30–50×; reasoning-budget-256 caps the burn while keeping final answers
(239–279 completion tokens including bounded reasoning).

## 7. Budget panel (RS: reasoning-budget caveat)

The budget curves vary the **total generation budget** (max_tokens /
n_predict: 64→1024) — this is NOT a reasoning-budget sweep; T2
(`--reasoning-budget 256`) is the only reasoning-budget condition, so
**no claim that 256 is optimal is made** (alternatives were never
compared). Total-budget findings that survive correction:

- thinking-off arms (M-P2) are budget-insensitive from 64 tokens up
  (S1/S3 ≈ 0.67 flat, S2 ≈ 0.58) — with reasoning excluded, answers are
  short;
- default-thinking arms collapse at small budgets (S3 M-P1: 0.000 at ≤256,
  0.317 at 1024) — reasoning starvation, consistent with §4;
- panel point estimates at 512 occasionally exceed 1024 (e.g. S1 M-P1
  0.667 vs 0.650): paired panel analysis at n=12 tasks shows these are
  within noise; treat as inconclusive.

## 8. The 13 questions (mission §8)

1. **Affected records**: 1,397 of 1,397 offline-rescored rows (588 verdict
   flips, 306 structural-only, 503 telemetry-only; 0 false positives).
2. **Failed→correct**: 588.
3. **Correct→incorrect**: 0.
4. **Corrected semantic accuracy**: table §3 (headline: corrected best arm
   per model: S1 T2 0.700, S2 T2 0.683, S3 T2 0.650 / M-P2 0.617).
5. **Corrected structural validity**: table §3 (constrained decoding arms
   ≈1.00; freeform chat 0.32–0.78; DSL 0.00–0.08).
6. **Corrected empty-final-content**: §4 — 0.00–0.25 (S1/S2), 0.68 (S3
   default-thinking), all budget-exhausted; 0.00 for thinking-off/T2/
   completion-constrained arms. Published values (up to 1.00) were
   telemetry-absence artifacts.
7. **Bounded reasoning improves all three models?** Point estimates yes
   (+5.0/+6.7/+33.3 pts), but statistically supported **only for S3**
   (p<0.001); S1/S2 inconclusive (p≈0.45). The previous blanket claim is
   withdrawn.
8. **Thinking-off harms S2, helps S3?** S3 help confirmed (+30.0 pts,
   p<0.001). S2 harm NOT supported (−6.7 pts, p=0.455, inconclusive).
   S1 inconclusive (−8.3, p=0.332).
9. **DSL zero semantic success?** Confirmed: 0/180 primary-budget trials
   across models (paired p<0.001 vs JSON); root cause is structural —
   models emit chain-of-thought/markdown instead of the DSL line
   (spot-verified in artifacts; the parser accepts clean DSL when
   produced).
10. **Two-stage inferior on matched tasks?** Direction consistent (S1
    −0.400, n=10, p=0.125; S2/S3 zero successes vs single-shot 0.217/0.483
    with no discordant pairs in P7S's favor). Evidence is directionally
    negative but statistically inconclusive at n=10; stage-1 wrong-tool
    selection is the dominant failure (23/25 selections wrong).
11. **Native function calling vs structured-answer recording?** P5A ≥ P5B
    everywhere; significant for S2 (+0.500, p<0.001); S1/S3 inconclusive
    (+0.03). Against chat+schema (M-P1): no significant difference on the
    P5A-applicable scope for any model (S1 +0.233, p=0.065; S2/S3
    ≈+0.03, p=1.0) — **native function calling is not disadvantaged**;
    the prior "chat+json_schema leads" ranking is not supported as a
    significant protocol effect.
12. **Conclusions changed**: (a) overall accuracy 12.9%→39.8% (defective→
    corrected); (b) "reasoning improves all three models" → only S3
    supported; (c) "thinking-off harms S2" → unsupported; (d) empty-
    content rates were telemetry artifacts, real mechanism is reasoning
    burn confined to default-thinking chat; (e) P5B/S2 collapse (0.100)
    and the S2 completion-transport collapse (0.217, p<0.001) are NEW
    model-specific findings; (f) DSL-zero and S3 thinking effects
    SURVIVE correction; (g) two-stage negativity survives directionally
    but is downgraded to inconclusive at n=10.
13. **Runtime Profile recommendations that remain justified**:
    - per-model: S1 chat+schema or T2; S2 chat+schema / T2 (avoid
      /completion transports and record_answer); S3 requires thinking
      control (T2 or thinking-off) — default-thinking S3 is unusable
      (0.317, 68% burn);
    - model-agnostic: never DSL at 2B scale; never record_answer as the
      structured channel for S2; two-stage decomposition not justified;
    - **withdrawn**: any claim that 256-token reasoning budget is
      optimal (untested); any ranking built on the defective matrix.

## 9. Failure taxonomy (corrected, primary budget, 1,680 main-scope rows)

SUCCESS 694; SEMANTIC_ERROR (true model semantic failures) 523;
STRUCTURAL_GENERATION_ERROR 248; EMPTY_FINAL_CONTENT_TRUNCATED 209 (100% of
empties are budget-exhausted; EMPTY_FINAL_CONTENT_STOPPED = 0);
TOOL_CALL_ONLY_UNPARSED 1; STAGE1_SELECTION_FAILED 5; plus the
2-stage-specific and evidence classes (0 artifact/replay/transport errors —
local server, 0 HTTP failures across all 2,209 physical requests;
2,209 = 2,184 trials + 25 P7S second stages, 5 P7S trials stopped at
stage 1).

## 10. Denominators

2,184 unique logical slots executed of 2,184 planned (main 1,680 + panel
504); applicability exclusions per model: M-P7 ×20, P5A ×30, P7S ×50,
P5A-panel ×6; physical requests 2,209 (25 P7S two-request trials + 5 stopped at stage 1);
inapplicable arm-task combinations are outside all denominators; paired
comparisons use only shared-applicable tasks (§5 ns).
