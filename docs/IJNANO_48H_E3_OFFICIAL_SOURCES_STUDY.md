# IJ-NANO-48H E3 — Official Hugging Face Harness-Adapter Sources Study

Status: AUTH-0 source study (no physical execution, no assets acquired
yet). Compiled 2026-11-28 for the preregistered E3 reproduction design
(order section 7). Every fact below carries its source; uncertainties
are explicit. This document freezes the reproduction targets.

## 1. Published LFM3-1.7B results to reproduce (model cards, step 400)

| Adapter | Task set | Base | Adapter | Δ | Tool-call Δ |
|---|---|---:|---:|---:|---:|
| Pi | 150 SmolDataEnvs (data analysis) | 70.0% | 80.7% | +10.7 ± 6.7 | −37% |
| Pi | 40 traj2envs (repository) | 15.0% | 12.5% | −2.5 ± 11.1 | −6% |
| OpenCode | 150 SmolDataEnvs | 69.3% | 84.7% | +15.3 ± 6.6 | −43% |
| OpenCode | 40 traj2envs | 2.5% | 5.0% | +2.5 ± 4.9 | +33% |
| Hermes | 150 SmolDataEnvs | 62.0% | 78.0% | +16.0 ± 7.0 | −38% |
| Hermes | 40 traj2envs | 25.0% | 17.5% | −7.5 ± 10.8 | −36% |

Source: model cards `harness-hub/LFM3-1.7B-{pi,opencode,hermes}`
(step 400). Every card states the adapters do NOT improve on the
repository tasks; Hermes never reached traj2envs in training.

## 2. Task-set identities (order §7.1)

- **Data analysis (150)**: `FineEnvs/SmolDataEnvs-harbor-train` —
  Kaggle-derived data-analysis questions; agent receives data files in
  a sandbox and writes one answer graded by exact/numeric match.
  Selection rule stated by the cards: "tasks 1,000 and up, easy and
  medium, none of them seen in training".
- **Repository (40)**: `harness-hub/traj2envs-rl` — 270 tasks total
  (253 build / 11 repair / 6 extend; 243 from one source trace repo;
  259 carry teacher-written tests), 40 held out for evaluation.
  Repo2RLEnvs is migrating to Repo2RLEnv and will be archived.
- **No published per-task ID manifest exists for either held-out
  subset** — the dataset repos + selection rule are the canonical
  identity. Local reproduction must derive and freeze its own task
  manifest and label the selection uncertainty (order §7.1 "Do not
  assume that the public training dataset name uniquely identifies the
  evaluation split").

## 3. Official inference configuration (what "official" means)

- vLLM serve `LiquidAI/LFM3-1.7B --enable-lora --max-lora-rank 32
  --lora-modules lfm3-harbor-<h>=harness-hub/LFM3-1.7B-<h>
  --enable-auto-tool-choice --tool-call-parser qwen3_coder
  --reasoning-parser qwen3 --trust-remote-code --max-model-len 131072`
- vLLM pinned at commit `fac2ce2eb3633c44a104a66dbb30d0e6c7f4493e`
  (+ three files from atmikshetty/vllm@5f67fbc)
- Sampling: one attempt per task, temperature 0.8; thinking mode ON
  for all LFM3 runs (earlier-turn reasoning stays in context)
- Harness versions: Pi 1.5.2, OpenCode 2.2.7 (Qwen article era) /
  1.19.5 (LFM3 cards era), Hermes Agent v0.22.6
- Adapters: LoRA r=32, α=64, all-linear layers; merged-into-base for
  Qwen evals, live LoRA serving for LFM3 evals
- Reward: task verifier correctness + tool-efficiency bonus
  `0.1 × (1 − calls/15)` on correct rollouts only
- GGUF pairing (officially published, explicitly **not re-evaluated**
  upstream): `LiquidAI/LFM3-1.7B-GGUF` Q8_0 base + per-adapter
  `LFM3-1.7B-harbor-<h>-lora-F16.gguf`; llama.cpp:
  `llama serve -m Q8_0.gguf --lora <h>-lora-F16.gguf -c 65536
  --port 8080 --alias lfm3-harbor-<h>`; Pi bridge:
  `pi install git:github.com/huggingface/pi-llama`; Pi requires
  `"api": "openai-completions"` in its config; Hermes needs ≥64,000
  tokens of context.

## 4. Verifier methodology (order §7.3 targets)

- Every task ships an oracle in `solution/` that must score full
  reward in the task's own image; images pinned by digest in
  `task.toml`.
- Trial retention: oracle passes twice; doing nothing / a stub /
  tampering with tests score 0; mutation testing prunes weak tests.
- safeagents reverse proxy checks every tool call; blocked calls
  replaced by a notice and the rollout scores 0 (plugin rules incl.
  `smoldataenvs.answer_source`, `traj2envs.solution_source`,
  `tamper.reward_write`, `tamper.test_files`).
- Qwen-era tooling: `openenv validate` (oracle_max, floor_gap,
  canary_floor, episode_determinism), 858/1,127 hub candidates passed.

## 5. Reproduction-fidelity classification (pre-declared)

Our lane executes llama.cpp b12359 Vulkan GGUF (Q8_0 base + F16 LoRA)
on RX 7900 XTX — NOT the official vLLM bf16/fp16 serving. Therefore:

- Native-harness episodes on the official held-out task families with
  matched sampling/steps: **SAME_TASK_DIFFERENT_RUNTIME** (order §7.2
  vocabulary), never claimed as EXACT_TASK_PROTOCOL_REPRODUCTION.
- The GGUF configuration itself is officially unevaluated upstream —
  our W0/W1-W3 GGUF panel is a **LOCAL_REPRODUCTION** of the
  published adapter deltas.
- Effective budgets (context, steps, tokens, tool parsers) are
  captured per episode (65,535-vs-768 lesson permanent).

## 6. Qwen3.8-27B context (E6 §10.3 study-only unless authorized)

Super-adapter = concatenation of three r=32 LoRAs along rank (PEFT
`combination_type="cat"` → r=96), applied as
`w·(ΔW_pi + ΔW_hermes + ΔW_opencode)` scaled ½ (chosen on TB2.1 →
"slightly optimistic"). Specialist gains up to +25.5pp (pi, SWE-bench
Pro hard 51: 39.2→64.7, p=0.002); efficiency −53…−72% tool calls.
27B high-precision results are NOT reproducible in 24GB VRAM; any
local 27B work is a separate resource configuration (order §10.3).

## 7. Uncertainties (explicit, per order §7.1)

1. Exact held-out task-ID manifests (150/40) are not published —
   selection-rule-derived manifests must be frozen locally and marked
   as inferred identities.
2. Effective per-rollout context budget for LFM3 evals (131,072 was
   the server max-model-len; rollout budget unstated).
3. Base-model git revisions unpinned upstream (`LiquidAI/LFM3-1.7B`).
4. Seeds unstated upstream.
5. GGUF pairing results are officially unevaluated (both directions:
   nothing to contradict, nothing to confirm).
6. Licenses: LFM3 adapters inherit LFM 1.0 (revenue-conditioned
   commercial terms — IJN-B-003 applies to any commercial framing).

Sources: primary article
[harness-adapters-at-scale](https://huggingface.co/blog/harness-adapters-at-scale);
LFM3 article
[harness-hub/harness-adapters](https://huggingface.co/blog/harness-hub/harness-adapters);
model cards
[pi](https://huggingface.co/harness-hub/LFM3-1.7B-pi),
[opencode](https://huggingface.co/harness-hub/LFM3-1.7B-opencode),
[hermes](https://huggingface.co/harness-hub/LFM3-1.7B-hermes);
datasets
[traj2envs-rl](https://huggingface.co/datasets/harness-hub/traj2envs-rl),
[agentic-coding-envs](https://huggingface.co/datasets/harness-hub/agentic-coding-envs);
[super-adapter](https://huggingface.co/harness-hub/Qwen3.8-27B-super-adapter);
[LFM3 collection](https://huggingface.co/collections/harness-hub/lfm3-17b-harness-adapters).
