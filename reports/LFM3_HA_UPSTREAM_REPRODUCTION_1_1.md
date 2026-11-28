# LFM3 original-harness reproduction status

**EXACT_AUTHOR_REPRODUCTION remains BLOCKED.** The public TRL recipe and
scheduled sweep name training job `6aedb4820e0338d1bb8107eb`. The three
step-400 adapter runs on the author dashboard carry that identifier in their
run names. The dashboard supplies checkpoint aggregates. The historical
per-task evaluation results, actual launch arguments and run-bound sandbox
digests remain unavailable. [Author dashboard](https://harness-hub-harness-adapters-rl.hf.space/) ·
[Published recipe](https://huggingface.co/spaces/trl-lib/trl-recipes/blob/9b49dba3bf66174fcedb7812f8e7db12b12027df/recipes/harness-adapters/LFM3-1.7B/recipe.yaml) ·
[Scheduled sweep](https://huggingface.co/spaces/trl-lib/trl-recipes/blob/9b49dba3bf66174fcedb7812f8e7db12b12027df/recipes/harness-adapters/scripts/eval_sweep.py)

## Reconstructed rosters

| Split | Source binding | Reconstructed tasks and image references |
|---|---|---|
| Repo2RLEnvs | The recipe pins `191a751bda511eada76f6a9a76513d143321a64a`. The launcher sorts task paths and takes 40 after skipping 230. | 40 task IDs with source TOML SHA256 and nine distinct referenced image digests. |
| SmolDataEnvs | The recipe leaves the revision unpinned. Public repository history places `0ee6ac78a21e2fc3544d9953e7a98204cd571f9c` immediately before the dashboard's November 6 run start. This revision is an inference. | Skip 1,000 sorted paths and retain the first 150 easy or medium entries. The 171 examined TOMLs yielded 43 easy and 107 medium. The recipe overrides their source image with a tag. Its resolved historical digest is missing. |

The pinned repository trees match the corresponding registry inventories.
The portable audit preserves the candidate IDs and the TOML digest for each
examined task through the cutoff. Zero executions are tied to an original
historical per-task receipt. [Reconstruction evidence](../evidence/IJSLM/lfm3-ha-1.1/author-recipe-audit.json) ·
[Evaluation launcher](https://huggingface.co/spaces/trl-lib/trl-recipes/blob/9b49dba3bf66174fcedb7812f8e7db12b12027df/recipes/harness-adapters/scripts/launcher_eval.py)

## Reward and runtime

The recipe's LFM3 training command passes `--tool-efficiency-weight 0.1`.
The launcher forwards that argument to the shared trainer. The trainer's
default is `0.3` and the parsed argument feeds the reward function. It adds
the weight times the clipped fraction `1 - tool_calls / 15` when verifier
correctness is at least one. A safeagents block gives reward zero in this
implementation. This traces the public recipe's effective coefficient. The
historical process argument receipt remains BLOCKED. [Training command](https://huggingface.co/spaces/trl-lib/trl-recipes/blob/9b49dba3bf66174fcedb7812f8e7db12b12027df/recipes/harness-adapters/LFM3-1.7B/train_hf_jobs.sh) ·
[Shared trainer](https://huggingface.co/spaces/trl-lib/trl-recipes/blob/9b49dba3bf66174fcedb7812f8e7db12b12027df/recipes/harness-adapters/scripts/async_grpo_harbor.py)

The recipe identifies vLLM and its LFM3 overlay commits, an OpenEnv commit
and the two guard plugin sources. The original OpenCode card identifies
1.19.5. The current shared evaluation launcher includes an OpenCode 2.2.7
fallback. The historical package lock, Pi and Hermes binaries, applied
patches and plugin file hashes still need run-bound corroboration. [Pinned OpenCode card](https://huggingface.co/harness-hub/LFM3-1.7B-opencode/blob/a10630d0bff34b1a77f258174392a16662256993/README.md) ·
[Published source audit](../evidence/IJSLM/lfm3-ha-1.1/author-recipe-audit.json)

## Execution status

This Windows workstation did not show Docker or Podman on PATH or a
configured WSL environment. The original harnesses need a verified
sandbox that excludes user directories, credentials, other worktrees
and external runtime egress. No job has been started in those harnesses.

| Lane | Configuration | Planned | Observed |
|---|---|---:|---:|
| EXACT_AUTHOR_REPRODUCTION | BF16/vLLM with run-bound author identity and original protocol | 1,140 | 0 |
| GGUF_PORTABILITY_REPRODUCTION | GGUF on Radeon with matched author harness and explicit hardware/runtime differences | 1,140 | 0 |
| CURRENT_DATASET_APPROXIMATION | Independently labeled run against a separately pinned reconstruction | Unregistered | 0 |
| JOBBOT_TRANSFER_EVALUATION | Matched synthetic JobBot workloads on Radeon | 720 | 720 |

A minimal isolated admission must pin the OpenCode 1.19.5 build, Pi
Chat Completions provider, Hermes source version and each plugin and tool
definition. Exercise paired Original and LoRA under the same harness.
Hermes requires at least 64,000 tokens in its documented setup. Record
whether an 8K launch is supported as its own compatibility result before
attempting that edge arm. Keep unavailable trials and their causes in the
denominator report. Bind every scored trajectory to a frozen oracle, task
world, seed, base and adapter, runtime and hardware identity.
