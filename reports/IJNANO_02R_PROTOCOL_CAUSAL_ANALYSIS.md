# IJ-NANO-1.2 N02R — Model × Protocol Causal Analysis

> **SUPERSEDED (IJ-NANO-1.2R, 2026-11-28) — QUANTITATIVE SECTIONS.**
> The offline re-score that filled 1,397 of the 2,184 slots of
> `ec5b95357e960f99` contained a loader defect (positional unpacking of the
> persisted stage dict): every re-scored trial was sealed `PARSE_INVALID`
> regardless of content (1,397/1,397 affected; 588 false negatives). All
> quantitative tables, rates, contrasts and recommendation candidates in
> THIS report that derive from `ec5b95357e960f99` are historical and
> superseded by
> `reports/IJNANO_02RR_QUANTITATIVE_EVIDENCE_RECONCILIATION.md`
> (corrected matrix: `evidence/IJNANO/N02RR/corrected_protocol_matrix.json`;
> row-level reconciliation: `evidence/IJNANO/N02RR/trial_reconciliation.jsonl`;
> root cause: `reports/IJNANO_02RR_OFFLINE_RESCORE_ROOT_CAUSE.md`).
> Preserved scopes: physical execution coverage, artifact integrity,
> source-level findings, probe audits, evaluator qualification. Gate
> `N02R_MODEL_PROTOCOL_BEHAVIOR_CHARACTERIZED` was re-granted by 1.2R only
> for the corrected comparison scopes.


- Mission order: `docs/IJNANO_MISSION_ORDER_V1_2.md` §3
- Gate: `N02R_MODEL_PROTOCOL_BEHAVIOR_CHARACTERIZED`
- Engine: llama.cpp b12359 (commit `b1b770d90`), Vulkan backend, RX 7900 XTX
- Weights: 10/10 SHA256 MATCH vs committed manifest (fresh verification:
  `evidence/IJNANO/N02R/identity_verification.json`)
- Experiment identity: `d792514db3a65810` (controller/arms/scorer/task-suite
  hashes + engine SHA + decoding plan; see `runs/d792514db3a65810/manifest.json`)
- Suite: 60 tasks (6 families × 10; CN/EN 30/30; 3 business worlds), hash
  `a4ad5a09cbc833fda533fa76f15ba7a485d56d6cc5af19c8e49544eb79d154fd`

**Status: COMPLETE — corrected experiment `ec5b95357e960f99` sealed
(2,184/2,184 unique logical slots; gate
`N02R_MODEL_PROTOCOL_BEHAVIOR_CHARACTERIZED` = PASS, scoped to the
applicable comparison scopes; see limitations §7). The v1 screen
(`36bfed1d55a9987b`) remains sealed as development/diagnostic evidence per
the integrity audit.**

## 1. Design

Arms P0–P7 (labels in `benchmarks/ij_nano/n02r/arms.py`): native chat,
chat+json_schema, chat+verified-thinking-off+json_schema, completion+
json_schema, completion+GBNF, native function calling, completion+compact
DSL, completion+enumerated action. Matched across arms: task semantics,
available information, entity identities, budget (primary 1024, panel
64–1024 on preregistered arms P0/P1/P2/P5 × 12 tasks), temperature 0,
seed 42, `cache_prompt`. Semantic scoring through the N05AR-qualified
evaluator (contract v2): exact tool/entity identity, typed slots, units,
no substring matching. Rendering verified via `/apply-template`
(differential use in thinking-kwarg verification).

GPU execution proof per model session: listening socket owned by the
launched PID + D-010 offload line (43/43 S1, 25/25 S2, 25/25 S3).

## 2. Probe false-positive audit (order §3.2) — CORRECTED SCORING

Original N02 protocol artifacts are preserved unchanged. The audit
re-runs the checks with corrected logic (`runs/*/probe_audit_*.json`):

| Check | v1 (N02) behavior | v2 (N02R) behavior | Result |
|---|---|---|---|
| empty final content | PASS when `completion_tokens` set (S2 passed with empty text) | PASS requires non-empty content | S1 PASS; S2, S3 **FAIL** — both burn the whole 16-token probe in reasoning; the v1 false positive is reproduced and removed |
| native tool call | name checked only | structural (valid JSON arguments + required slot) AND semantic (`sku == "SKU-1001"`) | PASS ×3 |
| SSE usage | chunk count only | content+reasoning stream channels reconciled with `usage`; reasoning-token attribution recorded UNAVAILABLE (b12359 has no breakdown field) | PASS ×3 |
| cancellation | client abort + health | client abort vs server termination distinguished; slot release proven by a follow-up generation completing with token accounting | PASS ×3 |
| rendered prompt | not captured | `/apply-template` render + SHA | PASS ×3 |
| raw evidence | partial | full raw JSON (trimmed) per trial in `results.jsonl` | delivered |

Thinking-kwarg verification (`runs/*/thinking_verification_*.json`): a
kwarg is only trusted when the rendered template CHANGES with the kwarg
(`/apply-template` differential — jinja silently ignores unknown context
keys) AND a behavioral check shows no `reasoning_content` with non-empty
content. Result: **`enable_thinking` verified effective on S1, S2 and S3**.

## 3. Causal analysis of the chat-path structured-output failure

Preserved original observation (S2): Chat+json_schema FAIL (reasoning
4,030 chars, empty content, finish `length` @1024) vs Completion+GBNF and
Completion+json_schema PASS.

**Finding: the failure is engine protocol semantics, not model weights.**

Source level (`evidence/IJNANO/N02R/source_level_findings.md`, pinned
commit): chat requests install the json_schema grammar **lazily** with
reasoning-state triggers; `grammar_should_apply()` in
`common/sampling.cpp` deliberately withholds the grammar while the
reasoning-budget state machine is inside the thinking block; the
reasoning budget defaults to unlimited; `max_tokens` is shared across
reasoning+content. `/completion` requests install grammars eagerly from
token 0 — hence their PASS.

Physical replication: the same signature (reasoning present, empty
content, `finish_reason: length`, completion_tokens == budget) reproduces
on **S1 and S3** chat arms, and the verified thinking-disabled counterfactual
(P2) eliminates it (validation smoke `runs/d792514db3a65810`: P1 empty/
truncated/reasoning on all models → P2 zero-empty, zero-truncated,
grammar-valid). Budget panel quantifies the burn-vs-budget relationship.

## 4. Escaped-quote GBNF — engine record corrected

Decomposition probes (identical on all three models):

| Grammar | Result |
|---|---|
| `root ::= "say \"hi\""` (mid-literal escapes) | ACCEPTED |
| `root ::= "\"sku" …` (literal starts with `\"`, rule-start) | ACCEPTED |
| `root ::= "a\":\"b"` (escapes with colon inside) | ACCEPTED |
| `root ::= "\"" …` (literal consisting only of `\"`) | REJECTED |
| `root ::= "{" "\"sku" …` (escaped-quote-start literal after another literal) | REJECTED |
| N02 reconstruction | REJECTED |
| char-class form `["]` | ACCEPTED |

**Disposition**: b12359's GBNF parser supports escaped quotes in general
(`parse_char` handles `\"`); the rejection is a narrow lexer quirk for
literals that consist of, or begin with, an escaped quote when adjacent to
a preceding literal. The original N02 grammar string was invalid
construction; "use [\"] char classes" remains the robust guidance. The
N02 engine-record note is corrected here and in the ledger.

## 5. Quantitative protocol matrix (corrected experiment ec5b95357e960f99)

Full data: `evidence/IJNANO/N02R/protocol_matrix.json` (analyzer
`scripts/ij_nano/n02r_analyze_v2.py`). Denominators: **2,184/2,184 unique
logical slots executed** (1,680 main + 504 panel-extra; 1,397 reused via
verified offline re-score of complete artifacts + 787 new physical trials;
2,214 physical requests incl. 30 two-stage P7S); 0 NOT_RUN, 0 BLOCKED, 0
missing artifacts; 106 arm-task combos per model excluded as INAPPLICABLE
by preregistered applicability (never counted as model failures). The v1
native-usability diagnostic scope (experiment 36bfed1d, 1,440 trials) is
reported separately within the matrix.

### 5.1 Information-matched causal scope (semantic correctness, Wilson 95% CI)

| Arm | S1 MiniCPM5-2B | S2 LFM3-1.7B | S3 Qwen3.5-2B |
|---|---|---|---|
| M-P0 chat free | 0.20 [.12,.32] | 0.23 [.14,.35] | 0.10 [.05,.20] |
| M-P1 chat+schema | 0.27 [.17,.39] | 0.25 [.16,.37] | 0.10 [.05,.20] |
| M-P2 chat+schema+thinking-off | 0.20 [.12,.32] | 0.20 [.12,.32] | 0.25 [.16,.37] |
| M-P3 completion+schema | 0.23 [.14,.35] | 0.10 [.05,.20] | 0.23 [.14,.35] |
| M-P4 completion+GBNF | 0.17 [.09,.28] | 0.12 [.06,.22] | 0.22 [.13,.34] |
| M-P6 completion+DSL | 0.00 | 0.00 | 0.00 |
| M-P7 completion+enumerated | 0.13 (n=40) | 0.13 (n=40) | 0.13 (n=40) |
| P5A business tools (n=30) | 0.23 | 0.20 | 0.17 |
| P5B record_answer (n=60) | 0.15 | 0.08 | 0.17 |
| P7S two-stage (n=10) | 0.10 | 0.00 | 0.00 |
| **T2 chat+schema+reasoning-budget 256** | **0.30 [.20,.43]** | **0.27 [.17,.39]** | **0.30 [.20,.43]** |

### 5.2 T-set causal analysis (thinking x grammar x budget; per addendum §10)

S2 (the original observation's model): T0 default 0.25 semantic / 0.27
structural / 0.73 empty-content; T1 thinking-off 0.20 / 0.47 / 0.53;
**T2 reasoning-budget-256 0.27 / 0.47 / 0.53**; T3 eager completion-schema
0.10 / 0.47 / 0.53; T3b eager GBNF 0.12 / 0.47 / 0.53.

- **T1 and T2 and T3 all eliminate truncation and raise structural success
  from 0.27 to 0.47** — they remove the lazy-grammar/budget starvation.
- **The trade-off is real and model-specific**: disabling thinking (T1)
  costs S2 semantic accuracy (0.25→0.20) while raising structure; bounding
  reasoning (T2) keeps the reasoning channel AND recovers content
  (S2 0.27 ≥ T0 0.25; S3 0.30 vs T0 0.10; S1 0.30 vs T0 0.27).
- S3 shows the largest chat-path deficit (T0 0.10, empty 0.90, truncation
  0.37) and the largest T1/T2 recovery (+0.15/+0.20 semantic).
- Eager completion constraints (T3) fix structure but reduce S2 semantic
  (0.10) — the plain-prompt transport loses the chat template's task
  framing for LFM3.

Causal claim (refined per addendum): the lazy-grammar mechanism and the
shared generation budget PERMIT reasoning to exhaust the completion
budget; model-specific reasoning behaviour determines how often this
occurs (S3 37% truncation vs S1 12% under T0) and how much reasoning
remains useful (T2 ≥ T1 on S2/S3). Model weights are NOT excluded as a
contributing factor; the protocol mechanism is confirmed necessary,
the model's reasoning propensity is the moderator.

### 5.3 Other matched contrasts

- Freeform vs constrained chat (M-P0 vs M-P1): no significant difference
  on any model (CIs overlap) — under matched information, the lazy
  schema constraint neither helps nor hurts chat arms at this budget.
- DSL (M-P6): 0/60 on all models — compact DSL output contracts are not
  usable for these 2B models without instruction tuning.
- Two-stage (P7S) underperforms single-shot structured output (0-0.10 vs
  M-P3 0.10-0.23) at this scale.
- Budget curves (64→512, panel arms): monotone degradation as budget
  shrinks for chat arms; full curves in `protocol_matrix.json`.

## 6. Model-specific protocol recommendation candidates

Candidates (for N03 confirmation, not final selections):

| Model | Primary candidate | Rationale (measured) | Secondary |
|---|---|---|---|
| S1 MiniCPM5-2B | Chat + json_schema + **reasoning budget ~256** (T2) | best semantic 0.30; structure 0.47; keeps reasoning channel | M-P1 (0.27) |
| S2 LFM3-1.7B | Chat + json_schema + **reasoning budget ~256** | only intervention ≥ T0 semantically (0.27) while fixing structure | avoid /completion transport (semantic drops to 0.10) |
| S3 Qwen3.5-2B | Chat + json_schema + thinking-off (M-P2) or reasoning budget (T2) | largest deficit under default (0.10); both recover to 0.25-0.30 | M-P3 (0.23) |

Cross-cutting: candidate-exposure in the prompt is REQUIRED for any
tool-selection semantics (PR-D01); native tool calling (P5A) performs on
par with schema arms and is the natural channel when tools exist;
record_answer-style structured answering (P5B) is viable but weaker;
DSL and two-stage protocols are not recommended at 2B scale.

## 7. Limitations

- Single execution per cell (temperature 0, seed 42); repeatability and
  seed variance are N03 scope, not claimed here.
- Reasoning-token attribution is UNAVAILABLE in b12359 usage; the
  reasoning channel is observed only as presence/character counts.
- 60-task mixed-family suite with exact-match semantic scoring; absolute
  rates are not business-accuracy claims.
- The empty-final-content metric counts content-channel emptiness; for
  tool-call arms (P5A/P5B) the answer legitimately lives in tool_calls.

