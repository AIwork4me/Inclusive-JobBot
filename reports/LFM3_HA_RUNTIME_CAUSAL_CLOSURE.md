# LFM3-HA-1.1 runtime causal closure

The existing Draft PR #9 is the release vehicle. Startup matched the reviewed SHA `15423d6e6c137ab52b8342a8150bbd261d80de1d`, verified the unchanged archived seals, rehashed the base, all adapter assets and runtime binaries, and checked the Radeon lease, controller and AG-11 window. The core stands at 8,250 of 36,550, including 1,650 Gemma observations. The prior 30 preflight captures, three admitted LoRA routes and five Extension BLOCKED observations retain their original identities and dispositions.

| Finding | Disposition | Evidence |
|---|---|---|
| Raw SDK action-phase suppression exists | FAIL | With model-output retries at zero the pinned harness emitted `none`. The one-setting loopback probe changed it to `auto` at one retry. Native SDK writer source is still needed for source-branch confirmation. [Action-phase root cause](LFM3_HA_SDK_ACTION_PHASE_ROOT_CAUSE.md) |
| Corrected SDK development executor records outcomes | PASS | On the 40 new trajectories, 81/81 provider requests linked to native generation and 18/18 phase-aware callbacks linked to proposals. Repetition and failed termination remain measurable. [Paired preflight](../evidence/IJSLM/lfm3-ha-1.1/action-phase-retest.json) |
| Original SDK and phase-aware exact-execution outcomes | FAIL | In the matched ten-case scope, Original was 1/10 and PhaseAware was 6/10. Direct was 10/10. [Action-phase root cause](LFM3_HA_SDK_ACTION_PHASE_ROOT_CAUSE.md) |
| Typed binder for archived cases | PASS | Five same-byte SDK replays and five real Radeon reruns. All 21 fresh callbacks bound. The unchanged business scorer returned four FAIL and one BLOCKED. [Typed binder](SDK_TYPED_CALLBACK_BINDER_QUALIFICATION.md) |
| Fixed guarded adapter admission | PASS | All three adapters retain the originally qualified one-token numeric and fixed read-only route. [Frozen admission](LFM3_HA01_RADEON_ADMISSION.md) |
| Four-token numeric repeatability | FAIL | The 16-cell factorial sealed. Each process configuration failed the expanded numerical criterion. [Cache and routing](LFM3_HA_CACHE_AND_ROUTING_ROOT_CAUSE.md) |
| Native unknown adapter rejection | FAIL | The pinned source constructs a scale-zero list for unknown-only overrides. Raw physical requests returned HTTP 200 and the measured logprobs retained unresolved state differences. [Cache and routing](LFM3_HA_CACHE_AND_ROUTING_ROOT_CAUSE.md) |
| AG-11 offline evidence | BLOCKED | Owner-assisted capture and independent review remain required. [Owner action](../AG11_OWNER_ACTION_REQUIRED.md) |
| DX-M2 hardware | NOT_RUN | Physical compiler, supported recurrent state and device runs remain pending. [NanoAgent handoff](LFM3_HA_NANOAGENT_HANDOFF.md) |

## Author reproduction

The author article and model card specify a correctness-gated efficiency coefficient of 0.1. The pinned TRL Harbor training example explicitly sets 0.3 in its example reward. The published exact run configuration is required to establish which value the historical sessions executed. The original article describes 150 SmolDataEnvs and 40 Repo2RLEnvs holdout tasks. Public metadata and the article do not bind a complete historical roster, dataset and image digests or the exact harness and reward source used by the 190 cases. The dashboard source listing returned an authentication error at recheck. [Author article](https://huggingface.co/blog/harness-hub/harness-adapters) · [Author card](https://huggingface.co/harness-hub/LFM3-1.7B-opencode) · [Pinned TRL example](https://github.com/huggingface/trl/blob/7d3c60afefbf3f4599e96031ccdf6888457bf1f2/examples/async_grpo_harbor/async_grpo_harbor.py)

| Reproduction lane | Status |
|---|---|
| `EXACT_AUTHOR_REPRODUCTION` | BLOCKED on historical protocol inputs and isolated runtime |
| `GGUF_PORTABILITY_REPRODUCTION` | NOT_RUN on the author tasks. JobBot artifact verification has its own scope. |
| `CURRENT_DATASET_APPROXIMATION` | NOT_RUN. Requires a separately identified snapshot and isolation. |
| `JOBBOT_TRANSFER_EVALUATION` | Separate development registration and measurement under the Radeon guard. |

The current SmolDataEnvs registry at `588744be728257abfb8d4984ec8fab2acbd1f7e1` lists 5,000 names and paths in version 2.0. The public Repo2RLEnvs dataset at `191a751bda511eada76f6a9a76513d143321a64a` lists a manifest and exposes a viewer train partition. Those current snapshots identify candidate material but do not bind the author's historical 190-case execution. A newer trajectories bucket explicitly describes Qwen3.8-27B evaluations. The external task contents and commands remain outside host execution pending verified isolation. [SmolDataEnvs](https://huggingface.co/datasets/FineEnvs/SmolDataEnvs-harbor-train/tree/588744be728257abfb8d4984ec8fab2acbd1f7e1) · [Repo2RLEnvs dataset](https://huggingface.co/datasets/harness-hub/traj2envs-rl/tree/191a751bda511eada76f6a9a76513d143321a64a) · [Newer trajectories bucket](https://huggingface.co/buckets/harness-hub/harness-adapters-trajectories/tree/README.md)
