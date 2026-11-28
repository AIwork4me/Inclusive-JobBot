# IJ-NANO-48H Final Report

Campaign clock 2026-11-28T04:34Z → 2026-11-30T04:34Z (48h, never
restarted). This report covers the executed program at H+9; the
campaign remains live for any late-released scopes until H+44, after
which final sealing per order §13.5. Detailed results live in the
companion reports; this document binds them to the evidence chain.

## Executed program (all seals clean, replays verified)

| Experiment | Slots | Result |
|---|---:|---|
| E1 cognitive atlas, dev split (A-RQ/B/C/D) | 1,920/1,920 | MiniCPM .4625 · LFM3 .4391 · Qwen .1750; heterogeneous per-primitive structure; language interaction (LFM3 +9.1pp ZH) |
| E2 harness-adapter atlas (W1/W2/W3 × 640) | 1,920/1,920 | vs W0: W1 −0.9pp (p=.47) · W2 −1.1pp (p=.40) · W3 +3.1pp (32/12, p=.004; CI crosses 0) — published adapter gains do NOT transfer to bare cognitive tasks under local GGUF chat inference |
| Adapter physical admission | battery | PASS (identity, scale-0 equivalence, scale-1 distribution-level change, no silent fallback, flag identity) |

## Primary scientific findings

1. **RQ2 dominates**: the frozen 1024-token chat budget kills
   reasoning-heavy tasks for every model (Batch C accuracies ≤3.75%;
   all EMPTY trials `finish_reason=length`). Apparent capability
   limitations are substantially protocol artifacts.
2. **RQ1 heterogeneity**: no model dominates; leadership flips by
   batch and by language. Per-primitive matrix delivered.
3. **RQ3/RQ4**: adapter effects on cognition are neutral-to-slightly-
   negative (one small positive discordant effect for W3); mechanics
   reproduce, gains do not transfer — classification LOCAL_REPRODUCTION.

## Assurance record

Zero unresolved integrity problems across 3,840 trials; every scope
consumed at its pinned EAE revision with released-checksum
reproduction; two production containment events handled honestly
(preflight canary defect with zero dispatches; EAE drill revocation
coordinated to requalification); the adapter admission battery found
and fixed two real defects (Windows path parsing; probe sensitivity)
before any adapter dispatch.

## Blocked scopes and resume commands

All blocked causes are recorded in `BLOCKERS_IJNANO_48H.md`. Resume:
confirmation (AUTH-3) awaits freeze decisions; E3/E4 await a sandbox
decision (docker/WSL install needs the owner) and asset acquisition;
E5/E6/E7 await EAE scope releases — the 2h checkpoints consume any
release automatically (pin extract → scope entry → checksum
verification → queue extension). If none arrive, the campaign ends at
H+48 with this report plus `IJNANO_48H_EXPERIMENT_COVERAGE.md` as the
final accounting.

## Evidence index

- Seals + per-trial compact records: `evidence/IJNANO/N03H/{AUTH2A_RQ,
  AUTH2B, AUTH2C, AUTH2D, AUTH2W}/`
- Final analyses: `evidence/IJNANO/N03H/atlas_analysis_final.json`,
  `coverage.json`, per-scope `analysis.json`
- Admission: `evidence/IJNANO/N03H/ADAPTER_ADMISSION/`
- Reports: executive, E1 atlas, E2 adapter effects, coverage,
  stability/resource, capability-to-runtime mapping, next investment
  (this directory), live status
- Reproduction: `python -m benchmarks.ij_nano.n03h.campaign run
  --scope <SCOPE>` per scope (each consumes its pinned EAE revision);
  analysis via `scripts/ij_nano/n03h/{atlas_analysis,coverage_report,
  render_atlas_report,analyze_campaign}.py`
