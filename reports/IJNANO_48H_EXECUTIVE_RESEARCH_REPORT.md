# IJ-NANO-48H Executive Research Report

Campaign: 2026-11-28T04:34Z → 2026-11-30T04:34Z (48h budget, clock
never restarted). This report covers the physically executed scope at
H+8.8 with all authorized scopes COMPLETE; remaining mission scopes
stayed BLOCKED pending qualification releases and are reported as
such. Evidence: every number below traces to a sealed, hash-bound run
record under `evidence/IJNANO/N03H/` (per-trial compact records,
seals, analyses, coverage).

## What was physically demonstrated

- **3,840 physically executed, sealed trials with zero unresolved
  integrity problems**: E1 cognitive capability atlas (1,920/1,920
  development slots: Batches A-RQ/B/C/D x MiniCPM5-2B / LFM3-1.7B /
  Qwen3.5-2B, chat protocol, temp 0, seed 42, frozen renderer, 1024
  -token budget) and E2 harness-adapter atlas (1,920/1,920: W1_pi /
  W2_opencode / W3_hermes x the same 640 development cases).
- Every trial: dual-path evaluation (independent production and
  reference legs), content-addressed raw artifacts, offline replay
  verification (1,920+1,920 replays match recorded verdicts),
  per-dispatch EAE revocation recheck, continuous canaries, persistent
  circuit breaker, per-trial actual-provider-request telemetry.
- Assurance events handled in production: a controller canary-leg
  defect caught at preflight with zero trials dispatched
  (requalification-only recovery exercised); a cross-batch
  certificate-confusion hazard closed by a release-checksum gate; the
  EAE drill-revocation incident (48H-B-006) coordinated to
  requalification closure.
- Adapter physical admission battery PASS on this host: byte-verified
  adapter identities, scale-0 output equivalence, scale-1 genuine
  distribution-level change (logprob deltas up to 10.7, reproduced
  across fresh processes), no silent fallback, identical cache policy.

## The 11 questions

1. **What has been physically demonstrated?** (above) — plus: a
   complete E1+E2 evidence chain on RX 7900 XTX / llama.cpp b12359
   Vulkan / Q8_0(+F16 LoRA) that is independently replayable.
2. **Which 2B model is strongest for which cognitive abilities?**
   SUPPORTED (heterogeneity): overall E1 accuracy MiniCPM5-2B .4625 >
   LFM3-1.7B .4391 > Qwen3.5-2B .1750, but leadership flips by batch:
   LFM3 leads B (C09-C16, .625), MiniCPM leads A/D, all collapse on C
   (C17-C24: .0375/.025/.0 — budget exhaustion, see Q9). Language
   interaction: LFM3 +9.1pp in Chinese; MiniCPM +3.1pp in English.
   Per-primitive matrix: `IJNANO_03_SLM_COGNITIVE_CAPABILITY_ATLAS.md`.
3. **Which Harness Adapter improves which capabilities?** SUPPORTED
   (negative-to-neutral transfer to bare cognitive tasks): on 640
   matched dev cases vs W0 (LFM3 original): W1_pi −0.9pp (21/27,
   p=.47), W2_opencode −1.1pp (22/29, p=.40) — not significant;
   W3_hermes +3.1pp marginal (32/12 discordant, McNemar p=.0037;
   Newcombe CI [−2.3, +8.6] crosses zero). The adapters' published
   gains live in harness interaction, not standalone cognitive
   accuracy — consistent with the separate-host 720-panel's direct
   Pi contrast (−1.7pp).
4. **Which published HF results were reproduced?** NOT_SUPPORTED as
   gains: the published +10.7/+15.3/+16.0pp SmolDataEnvs improvements
   are NOT reproducible as cognitive-atlas gains under local GGUF
   chat inference (different task family, quantization and runtime;
   classified LOCAL_REPRODUCTION, never claimed exact). What DOES
   reproduce: adapter loading/application mechanics, and the
   efficiency-oriented design intent (W3 shows the only positive
   paired movement; W1/W2 show no harm).
5. **Which results failed to reproduce, and why?** The adapter gains
   (Q4) and — on this scope set — nothing else was claimed upstream.
   Mechanism: (a) task-family mismatch (harness trajectories vs bare
   cognitive primitives), (b) Q8_0 base + F16 LoRA pairing is
   officially unevaluated upstream, (c) protocol budget: any
   reasoning-heavy benefit is masked by the frozen 1024-token budget.
6. **Does transfer work across harnesses?** BLOCKED (E4 requires the
   native-harness execution this host cannot sandbox — no docker/WSL;
   owner decision required).
7. **Does Runtime + Adapter co-design add benefits?** BLOCKED (E5
   scope not released; N06B/C runtime layers not built this
   campaign).
8. **Which configuration is most efficient?** SUPPORTED (partial,
   E1+E2 only): W0 LFM3-1.7B is the accuracy-per-token baseline to
   beat; no adapter improved accuracy, so the efficient E2
   configuration remains W0. For throughput, LFM3 has the lowest mean
   latency (2.1-3.2s/trial class). Full Pareto analysis needs the
   blocked E6 cohorts.
9. **Which gaps remain appropriate for Runtime engineering?**
   SUPPORTED (strongly): the dominant failure mode on C17-C24 is
   `finish_reason=length` budget exhaustion across ALL models (Batch C
   EMPTY rates 52/48/94%) — runtime-side budget policy, context
   management and answer-extraction are the highest-leverage fixes
   (Qwen3.5's 87.5% EMPTY in Batch B is the same mechanism).
10. **Which gaps remain appropriate for post-training?** PARTIAL:
    within-budget semantic errors (INCORRECT + INVALID_OUTPUT ~40% of
    evaluable outcomes) are the learnable residue; a learnability
    atlas (E7) needs its scope released — 0/8-style repeated-sampling
    evidence NOT_RUN.
11. **Next highest-value engineering investment?** Recommendation:
    a reasoning-budget and answer-extraction runtime layer (attacks
    the single largest measured failure bucket across all three
    models), then the E6 budget ladder to size it; adapter work
    should stay harness-scoped (their measured value is there).

## Verdicts

| Question | Verdict |
|---|---|
| 1 physical demonstration | SUPPORTED |
| 2 per-ability model ranking | SUPPORTED (heterogeneous) |
| 3 adapter capability effects | SUPPORTED (neutral-to-negative on cognition; W3 small positive) |
| 4 published reproduction | NOT_SUPPORTED (as gains) / mechanics reproduced |
| 5 failure mechanisms | SUPPORTED (task-family + quantization + budget) |
| 6 cross-harness transfer | BLOCKED |
| 7 runtime x adapter co-design | BLOCKED |
| 8 efficiency frontier | SUPPORTED (partial scope) |
| 9 runtime-addressable gaps | SUPPORTED (budget exhaustion dominant) |
| 10 post-training candidates | PARTIAL (E7 scope not released) |
| 11 next investment | RECOMMENDATION (runtime budget layer) |

## Honest boundaries

- All results are development-split; AUTH-3 confirmation (960 slots)
  is BLOCKED by design and NOTHING here is independently confirmed.
- E1's chat protocol is ONE preregistered configuration (1024-token
  budget, temp 0); the budget findings are protocol statements, not
  capability absolutes.
- E2 W0 evidence is reused from E1's LFM3 arms (identities verified:
  same protocol/renderer/sampling/roster); paired CIs reported on
  both discordant-pair and marginal bases.
- Vulkan temp-0 logprobs are not bitwise deterministic; adapter
  admission used distribution-level evidence (recorded).
- Attempt accounting: 3,840 physical attempts = 3,840 recorded trials;
  zero transport failures, zero quarantined benchmark trials, zero
  canary failures after the recorded preflight defect (which
  dispatched nothing).
