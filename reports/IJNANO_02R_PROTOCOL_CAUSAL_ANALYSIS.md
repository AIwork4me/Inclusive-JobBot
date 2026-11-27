# IJ-NANO-1.2 N02R — Model × Protocol Causal Analysis

- Mission order: `docs/IJNANO_MISSION_ORDER_V1_2.md` §3
- Gate: `N02R_MODEL_PROTOCOL_BEHAVIOR_CHARACTERIZED`
- Engine: llama.cpp b12359 (commit `b1b770d90`), Vulkan backend, RX 7900 XTX
- Weights: 10/10 SHA256 MATCH vs committed manifest (fresh verification:
  `evidence/IJNANO/N02R/identity_verification.json`)
- Experiment identity: `d792514db3a65810` (controller/arms/scorer/task-suite
  hashes + engine SHA + decoding plan; see `runs/d792514db3a65810/manifest.json`)
- Suite: 60 tasks (6 families × 10; CN/EN 30/30; 3 business worlds), hash
  `a4ad5a09cbc833fda533fa76f15ba7a485d56d6cc5af19c8e49544eb79d154fd`

**Status: IN PROGRESS — main screen (3 models × 8 arms × 60 tasks @1024)
executing under the host-wide lease; budget panel and quantitative matrix
follow. Sections 2–4 are final (evidence sealed).**

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

## 5. Quantitative protocol matrix

TO BE FILLED from `runs/d792514db3a65810/protocol_matrix.json` (analyzer:
`scripts/ij_nano/n02r_analyze.py`) after the main screen and budget panel
complete: per model×arm semantic/structural rates with Wilson 95% CIs,
empty/truncation rates, latency, token accounting, per-family breakdown,
matched contrasts (chat-vs-completion transport, thinking on/off,
schema-vs-GBNF, schema-vs-native-tools, representation contrasts) and
budget-sensitivity curves.

## 6. Model-specific protocol recommendation candidates

TO BE FILLED after §5 (candidates, not predetermined solutions; derived
from measured contrasts with CIs and effect sizes).
