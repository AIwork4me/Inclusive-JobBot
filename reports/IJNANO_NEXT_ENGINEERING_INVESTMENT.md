# IJ-NANO-48H Next Engineering Investment

Ranked by measured leverage from the sealed campaign evidence.

## 1. Reasoning-budget + answer-extraction runtime layer (recommended)

Evidence: EMPTY_OUTPUT via `finish_reason=length` is the dominant
failure bucket (38.6% of evaluable outcomes; Batch C 48-94% across ALL
models; Qwen3.5 87.5% even on classification-style Batch B). These are
protocol deaths, not capability deaths — the models spend the whole
1024-token budget reasoning and never emit an answer.

Investment: budget ladder measurement (E6 cohorts, pending scope),
adaptive budget policy, reasoning-stream answer extraction, and
budget-aware stopping in the runtime. Expected recovery: a large
fraction of the EMPTY bucket; Batch C's near-zero accuracies are the
upper bound of what is recoverable.

## 2. Structural-validity runtime assists

INVALID_OUTPUT ≈19% of evaluable outcomes concentrated in JSON/plan
families: schema-constrained decoding or one retry-with-format-feedback
in the runtime layer, no model change.

## 3. Language-aware model routing

LFM3 +9.1pp ZH vs EN; MiniCPM +3.1pp EN vs ZH: a trivial runtime router
captures several points of accuracy at zero model cost.

## 4. Keep adapters harness-scoped; co-design question stays open

E2: adapters did NOT improve bare-cognitive accuracy on this host
(−0.9 to +3.1pp; only W3 discordant-significant with marginal CI
crossing zero). Their published value is harness-interaction
efficiency — measure E3/E4/E5 there (all currently blocked: sandbox
for E3/E4, scope for E5). Do NOT spend post-training budget imitating
adapter gains on cognitive tasks.

## 5. Confirmation protection stays until the end

960 confirmation slots remain BLOCKED by design; once frozen
identities/policies exist post-campaign, they are the cheap next
evidence tier for any of the above.

## What NOT to invest in next

- Bigger models for this lane (E6 larger-model reference blocked on
  scope; 2B-lane questions dominate the roadmap).
- Multi-adapter merging (E8): no supporting evidence this campaign;
  the 27B super-adapter method transfers only after single-adapter
  harness value is demonstrated locally.
