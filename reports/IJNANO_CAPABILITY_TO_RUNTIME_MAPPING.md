# IJ-NANO-48H Capability-to-Runtime Mapping

Which measured capability gaps are addressable by Runtime engineering
vs post-training, from the sealed E1/E2 evidence (development split;
chat protocol with the frozen 1024-token budget).

## Measured failure buckets (3,840 trials)

| Bucket | Share of evaluable outcomes | Dominant location |
|---|---:|---|
| EMPTY_OUTPUT (budget exhaustion, `finish_reason=length` @1024) | 38.6% overall (Batch C: 48-94%; Batch B Qwen: 87.5%) | reasoning-heavy primitives C17-C24; Qwen everywhere |
| INVALID_OUTPUT (structural) | ~19% | JSON/plan formatting families |
| INCORRECT (semantic, within budget) | ~8% | spread |
| CORRECT | ~35% | classification-style families |

(Runtime-side numbers from `evidence/IJNANO/N03H/atlas_analysis_final.json`.)

## Runtime-addressable (with mechanism)

1. **Reasoning-budget management** — the single largest bucket.
   Mechanisms: measured budget ladder (E6, blocked on scope), answer
   extraction from reasoning streams, budget-aware stopping. Expected
   recovery: a large fraction of the 38.6% EMPTY bucket (Batch C
   collapse is protocol death, not capability death).
2. **Structural repair guidance** — INVALID_OUTPUT on JSON/plan
   families: schema-constrained decoding or retry-with-feedback in the
   runtime layer (no model change).
3. **Language routing** — LFM3 +9.1pp ZH / MiniCPM +3.1pp EN: a
   runtime router picks the model per language.

## Post-training candidates (learnable residue)

- Within-budget INCORRECT semantic errors and residual INVALID_OUTPUT
  after runtime repair — but the E7 repeated-sampling learnability
  evidence (0/8 vs 8/8 classification) is NOT_RUN (scope not
  released); treat as candidates, not conclusions.

## Adapter placement (from E2)

- Adapters moved bare-cognitive accuracy by −0.9 to +3.1pp (only W3
  discordant-significant; marginal CI crosses zero). Their value must
  be measured in harness-interaction scopes (E3/E4/E5 — blocked),
  NOT assumed for cognitive tasks. Runtime co-design (E5) remains the
  open question.

## Recommendation

Highest-leverage next engineering investment: a **reasoning-budget +
answer-extraction runtime layer**, sized by the E6 budget ladder once
released — it attacks the bucket that dominates every model's failure
profile on this protocol.
