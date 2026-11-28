# LFM3-HA 720-trajectory transfer panel

The registered development comparison crosses four weight configurations with three execution paths and 60 tasks drawn from ten existing TC-V3 scenario families. It carries forward the original 480 Direct and Original SDK slots and adds 240 phase-aware SDK slots. Each task shares its world, schema contract and seed across weights. Weight order rotates in 15-task periods and runtime order is balanced within each period. Every SDK trajectory uses a fresh session. The panel adds zero core trials.

| Arm | Effective runtime |
|---|---|
| Direct | Native provider JSON with pinned tool schemas and sampling, cache and token limits |
| Original SDK | Real original SDK harness, legacy tool choice preserved, matched external provider limits and public tool schemas |
| Corrected SDK | `SDK_MATCHED_CONTEXT_PhaseAware` with the same external provider limits, phase-aware grants and typed callback binding |

The two SDK arms retain the real harness transcript and result wrapper. Phase-aware grants may reduce the exposed tool list. This difference belongs to the model-visible runtime treatment. The replay publishes matched weight differences, runtime differences, their interaction, exact arguments, output and termination, duplicate proposals, redundant executions and available provider costs.

## Protocol reconciliation

An initial diagnostic run sealed 270 trajectories before the effective budget audit showed that the SDK emitted a model-visible 65,535-token limit while Direct sent 768. Those sealed trials and the interrupted reservation are retained in the diagnostic archive. Their effective limits and cache controls do not satisfy the matched panel contract. The matched runner now checks the effective provider request before sealing and during replay. [Diagnostic seal manifest](../evidence/IJSLM/lfm3-ha-1.1/legacy-budget-diagnostic.json)

## First matched checkpoint

The first sealed period covers 15 of the 60 tasks across all 12 arms, with 180 verified trajectories. The table reports exact scoped completion at this interim checkpoint. Its paired effects are descriptive. [Checkpoint replay](../evidence/IJSLM/lfm3-ha-1.1/transfer-checkpoint-180.json)

| Weight | Direct | Original SDK | Phase-aware SDK |
|---|---:|---:|---:|
| Original | 12/15 | 0/15 | 6/15 |
| OpenCode | 13/15 | 0/15 | 4/15 |
| Pi | 13/15 | 0/15 | 8/15 |
| Hermes | 12/15 | 0/15 | 6/15 |
