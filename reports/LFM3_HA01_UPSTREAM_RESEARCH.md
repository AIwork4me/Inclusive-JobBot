# LFM3-HA-1.0 upstream research and admission inputs

## Scope and startup audit

The existing Draft PR #9 and its clean linked worktree agreed at the independently
reviewed commit `fb28ef2492388be237bdb2f835d261c819569551`. All 14 GitHub
checks at that revision succeeded. PRs #6, #8 and #11 are dependencies for
evaluation, cross-SDK comparison and NanoAgent exchange, respectively.
[Draft PR #9](https://github.com/AIwork4me/Inclusive-JobBot/pull/9)

The workstation reported Windows, AMD Ryzen AI MAX+ PRO 395, Radeon 8060S
(gfx1151), driver 32.0.22018.5 and 128 GiB installed RAM. The global physical
GPU mutex was available at the startup check. No matching benchmark controller,
llama-server, or AG-11 collector process was observed. This is a point-in-time
observation. The AG-11 capture still requires the workstation owner and an
independent review. The five cohort seal counts were each 1,650. The existing
core remains 8,250 sealed of 36,550 planned, with 28,300 complex-capability
trials outstanding. Gemma-4-E2B retains its full allocation.
[Core progress](../atlas/slm/v1.0/physical_progress.json) ·
[AG-11 owner procedure](../AG11_OWNER_ACTION_REQUIRED.md)

All nine Vulkan observer EXE/DLL hashes matched the sealed candidate B pilot.
The installed Antigravity SDK was 0.1.24. The frozen local Q8_0 base was
1,846,238,496 bytes and matched
`8f6b24182258205e9e01e21f1f24a1f208c1e8115578825d202ce39976af20b6`.
The archived publisher record pins the Liquid AI GGUF revision and
1,728,801,536 full-precision parameters. The live publisher endpoint did not
independently confirm availability of the exact historical GGUF revision during
this audit. [Frozen source identity](../evidence/IJ07/model_identity/B.json) ·
[Observer identity](../evidence/IJSLM/sdk-causal/pilot-B/report.json)

## LFM3 training and author evaluation

The November 6 article describes a planned mix of 550 SmolDataEnvs tasks and
230 trajectory-derived environments. The checkpoint cards provide realized
coverage. All three releases are step 400. Each has rank 32, alpha 64, ten
resolved target module names and 32,937,472 trainable adapter parameters
counted from the delivered tensors. The PEFT configs specify
`LiquidAI/LFM3-1.7B` and leave the training base revision unset.
[Original methodology](https://huggingface.co/blog/harness-hub/harness-adapters) ·
[Asset registry](../atlas/slm/v1.0/lfm3-harness-adapters/MODEL_ADAPTER_REGISTRY.json)

| Adapter | SmolDataEnvs reached | traj2envs reached | Main pass@1, base to LoRA | Change in calls on jointly solved main tasks | Repository pass@1, base to LoRA |
|---|---:|---:|---:|---:|---:|
| [OpenCode](https://huggingface.co/harness-hub/LFM3-1.7B-opencode/blob/a10630d0bff34b1a77f258174392a16662256993/README.md) | 550 | 107 | 69.3% to 84.7% | -43% (101) | 2.5% to 5.0% |
| [Pi](https://huggingface.co/harness-hub/LFM3-1.7B-pi/blob/38c0d399de8f787aac77316586b3b2a1370e899a/README.md) | 550 | 230 | 70.0% to 80.7% | -37% (99) | 15.0% to 12.5% |
| [Hermes](https://huggingface.co/harness-hub/LFM3-1.7B-hermes/blob/8d5c16bb28ef7aa630ac1f2981e4f72bb9399d43/README.md) | 474 | 0 | 62.0% to 78.0% | -38% (89) | 25.0% to 17.5% |

The 150 main tasks are easy and medium SmolDataEnvs holdouts with task numbers
1,000 and above. The 40 held-out repository tasks come from the 270-task
traj2envs release. The author-reported repository changes were +2.5, -2.5 and
-7.5 percentage points with paired intervals crossing zero in all three arms.
The exact 190 task IDs, image digests and per-trial results still need to be
reconciled against an author run manifest. Current dataset defaults alone do
not establish the historical split. The public cards describe one attempt per
task, at temperature 0.8, with base and adapted paired by task.
[SmolDataEnvs](https://huggingface.co/datasets/FineEnvs/SmolDataEnvs-harbor-train) ·
[traj2envs](https://huggingface.co/datasets/harness-hub/traj2envs-rl)

Training used eight rollouts per task, a learning rate of 1e-5, thinking
enabled with prior reasoning retained, 17 model calls and 600 seconds per
rollout. vLLM was configured for 131,072 total tokens. The article separately
reports up to 32,768 output tokens per turn and four micro-batches of up to
65,536 tokens each for the LFM3 trainer. It discarded rollouts more than four
policy versions stale. The authors cite vLLM commit
`fac2ce2eb3633c44a104a66dbb30d0e6c7f4493e` with backported LFM3 files,
Qwen3 Coder tool parsing and Qwen3 reasoning parsing. OpenCode was 1.19.5,
Pi requires the Chat Completions `openai-completions` provider, and Hermes
advertises a 64,000-token minimum. Exact training versions for Pi, Hermes and
the deployed plugins still need source corroboration. The published BF16/vLLM
results and future Windows Radeon results have distinct identities. The cards
state that the released GGUFs have no equivalent author re-evaluation.
[Original methodology](https://huggingface.co/blog/harness-hub/harness-adapters) ·
[Pi card](https://huggingface.co/harness-hub/LFM3-1.7B-pi) ·
[Hermes card](https://huggingface.co/harness-hub/LFM3-1.7B-hermes)

## Pipeline and boundaries

1. Harbor supplies the task environment, instruction and verifier. OpenEnv
   serves the episode, with a separate sandbox per rollout. The real harness
   constructs prompts, exposes its tools and turns tool results into follow-up
   model requests. A proxy records provider interactions. Trainer inputs reuse
   the model-visible tokens and account for the policy version that generated
   each rollout.
2. The vLLM worker serves the frozen model and named LoRAs. Independent trainer
   processes update only their adapter, publish updated versions and let an
   in-flight request complete on its original version. AsyncGRPO groups eight
   rollouts per task and learns from within-group reward variation. Groups
   with constant reward supply zero relative advantage.
3. The verifier reads the task outcome, with `correctness` preferred over
   `reward` in the authors' cards. The article reports an efficiency bonus
   of 0.1 times (1 - tool calls / 15), gated on correctness. Reproduction needs
   the pinned verifier and counter implementation for edge cases. SmolDataEnvs
   uses exact or numeric answer checking. The released repository environments
   were reconstructed from trajectory snapshots and tested against a reference,
   an empty or incomplete solution and verifier-integrity controls. Build
   tasks dominate the release, limiting coverage of recovery and replanning.
4. Safeagents is a response proxy that inspects model-proposed calls before
   the harness dispatches them. Its effects depend on the pinned rules and
   the tool and protocol shapes those rules understand. It supplements the
   sandbox. JobBot still needs independent business authorization, exact
   state verification and owner-controlled egress observation.

[TRL trainer](https://huggingface.co/docs/trl/en/async_grpo_trainer) ·
[Harbor training example](https://github.com/huggingface/trl/tree/7d3c60afefbf3f4599e96031ccdf6888457bf1f2/examples/async_grpo_harbor) ·
[Harbor](https://github.com/harbor-framework/harbor) ·
[OpenEnv](https://github.com/openenv/OpenEnv) ·
[Safeagents](https://github.com/huggingface/safeagents) ·
[Repo2RLEnv](https://github.com/huggingface/Repo2RLEnv)

The November 20 follow-up concerns Qwen3.8-27B. Its useful JobBot design inputs
are repository-family separation, reference and known-wrong trials, tamper and
replay controls, and repeated base-model difficulty screening. Its authors
reported mixed AutomationBench effects in a separate harness. That result
supports testing transfer on JobBot's own business expectations before
training or deploying a specialist. Candidate benefits include argument
binding and fewer redundant actions. Possible costs include premature stopping,
inappropriate shell-oriented behavior, and regressions under SDK request
rewrites or 8K context. [Follow-up methodology](https://huggingface.co/blog/harness-adapters-at-scale)

## GGUF provenance and commercial deployment

The released F16 GGUF and F32 PEFT files were downloaded at exact publisher
revisions. All six weights matched publisher LFS SHA256 and size. Each PEFT
config matched its Git blob and has a recorded SHA256. Each GGUF has 306
tensors across 153 A/B pairs. Every tensor maps to a weight of the frozen
`lfm3` base and matches the expected rank and dimensions. All 306 F16 tensors
per adapter are bitwise equal to a direct cast of their corresponding F32
PEFT tensors. The publisher conversion command and converter commit remain
unverified. [Publisher collection](https://huggingface.co/collections/harness-hub/lfm3-17b-harness-adapters) ·
[Tensor inventory](../atlas/slm/v1.0/lfm3-harness-adapters/ADAPTER_TENSOR_INVENTORY.json)

At the pinned upstream llama.cpp source, the loader checks architecture,
pairs A/B matrices, matches base tensor names and dimensions and allocates
adapter tensors with the matching base backend buffer where supported. The
graph applies the low-rank delta with alpha divided by rank and multiplied
by the configured scale. The loader has a CPU buffer fallback, so the
physical panel must inspect adapter placement and independently confirm
intervention through native numeric evidence.
[Loader](https://github.com/ggml-org/llama.cpp/blob/b1b770d90d94cad9e9ea5b993bdbc383a522fb28/src/llama-adapter.cpp) ·
[Graph](https://github.com/ggml-org/llama.cpp/blob/b1b770d90d94cad9e9ea5b993bdbc383a522fb28/src/llama-graph.cpp)

The base and six adapter repositories identify LFM Open License v1.0.
Liquid AI's full terms set the commercial threshold at USD 10 million or
more in annual revenue and define which entity and affiliates count. A
deployment review must establish the operator's eligibility or obtain a
commercial license, and check notice and redistribution obligations for any
derived weights. This run publishes artifact metadata only. The actual
organization eligibility decision remains open.
[Liquid AI license and full terms](https://www.liquid.ai/lfm-license)

## Gate disposition

Upstream methodology audit and adapter file identity are PASS at the scope
described above. Historical source/split reconstruction is BLOCKED pending
exact author and publisher evidence. Physical LoRA admission, author
reproduction, Antigravity transfer and JobBot qualification are NOT_RUN.
