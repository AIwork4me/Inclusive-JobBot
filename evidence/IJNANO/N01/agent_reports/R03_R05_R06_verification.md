# N01 primary-source verification — R03 TinyAgent, R05 Growing Harness, R06 Meta-Harness

- Verification agent report, 2026-11-27 (GitHub API, arXiv, Hugging Face; no cloning/execution)
- Status: agent-verified; to be folded into reports/IJNANO_01_RESEARCH_LANDSCAPE_EN.md

## SUBJECT 1 — TinyAgent (SqueezeAILab) — VERIFIED (Windows caveat)

| Item | Verified value |
|---|---|
| Repo | https://github.com/SqueezeAILab/TinyAgent — exists, MIT, dormant since 2024-09-04 (~6 commits, 503 stars) |
| Paper | "TinyAgent: Function Calling at the Edge", arXiv:2409.00608, EMNLP 2024 **Demo track** |
| Authors | Erdogan, Lee, Jha, Kim, Tabrizi, Moon, Hooper, Anumanchipalli, Keutzer, Gholami (UC Berkeley / Squeeze AI Lab) |
| Artifacts | HF: TinyAgent-1.1B/7B (+GGUF), TinyAgent-ToolRAG, TinyAgent-dataset — all cards MIT |

Mechanisms in code: LLMCompiler-style parallel function calling (DAG plans);
ToolRAG (fine-tuned DeBERTa-v3-small multi-label classifier, ~3.97 tools
selected vs 6 naive); LoRA tool fine-tuning (80K synthetic train, GPT-3.5/GPT-4
generated, ~$500 data cost); 4-bit QAT with llama.cpp.

Models: TinyAgent-1.1B (TinyLlama-1.1B base) — **the only 1–3B total model**;
TinyAgent-7B (WizardLM-2-7B).

Gain decomposition (their 1K test set):
- 1.1B: base 12.71% → +LoRA 78.89% → +ToolRAG 80.06% → +4bit 80.35%
- 7B: base 41.25% → +LoRA 83.09% → +ToolRAG 84.95% → +4bit 85.14%
- Baselines: GPT-3.5-turbo 65.04%, GPT-4-turbo 79.08%
**Bulk of gain is fine-tuned weights (+66/+42 pts); runtime mechanisms add
~1.2–1.9 pts (ToolRAG also ~2x prompt reduction); QAT ~+0.3.**

Local/Windows: llama.cpp/LM Studio GGUF serving works; latency M3: 1.1B 4-bit
2.9 s / 0.68 GB. **All 16 shipped tools are macOS AppleScript** — Windows use
requires a full tool-layer rewrite. No LLM judge (programmatic graph
isomorphism). Red flags: self-generated synthetic eval, dormant repo,
demo-track paper.

## SUBJECT 2 — "Grow the Harness, Not the Context" — VERIFIED paper, NO CODE

| Item | Verified value |
|---|---|
| Exact title | "Grow the Harness, Not the Context: From Strategy-Free Scaffolds to Reusable Specialist Agents" |
| arXiv | 2609.26760, v1 2026-09-22 / v2 2026-09-24, preprint, CC BY 4.0 |
| Authors | Laizhen Li*, Jiarui Li*, Juanjuan Zhao, Kejiang Ye, Ye Li, Cheng-zhong Xu, Xitong Gao (SIAT CAS, UCAS, SUSTech, UMacau) |
| Code | **none found** (no repo link in paper; searches return trackers only) |

Method: strategy-free scaffold + failure-guided conversion of recurring
deterministic control decisions (parsing, validation, state updates, error
recovery, stopping) into reusable executable code; function-level traces;
joint repair window; success-first held-out gate with rollback.

Models: gpt-oss-120b, gpt-oss-20b, **Qwen3.5-4B (smallest — none in 1–3B)**;
optimizer GPT-5.6-terra / GPT-5.4 (proprietary). Results: LLM-call reduction
76.0–91.8%, inference cost −74.4–98.6%; best mean in 5/6 settings; WebArena
44.7–45.3% while Tool-Calling collapses to 6.7% at 4B. Means over 3 runs,
bootstrap CIs. LLM judge only inherited from BrowseComp-Plus benchmark.

No independent validation (~3 citations). License: paper CC BY 4.0 only.

## SUBJECT 3 — Meta-Harness (stanford-iris-lab) — VERIFIED

| Item | Verified value |
|---|---|
| Repo | https://github.com/stanford-iris-lab/meta-harness — MIT, created 2026-04-15, pushed 2026-11-05, 1814 stars |
| Paper | "Meta-Harness: End-to-End Optimization of Model Harnesses", arXiv:2603.28052 (preprint) |
| Authors | Yoonho Lee, Roshen Nair, Qizheng Zhang, Kangwook Lee, Omar Khattab, Chelsea Finn |
| Artifact | meta-harness-tbench2-artifact — exists, **NO license (all-rights-reserved)** |

What it does: outer-loop search over single-file Python harness programs
(prompting/retrieval/memory/orchestration) around a frozen base model;
proposer = Claude Code + Opus-4.6 with filesystem access to prior candidates'
code, scores and **raw execution traces** (ablation: raw traces > summaries);
task-reward-only feedback (**no LLM judge**).

Models: deployed GPT-OSS-120B/20B, Claude Opus 4.6 / Haiku 4.5 — **no 1–3B
model anywhere; param counts unstated; all base models frozen (pure
runtime/harness gains, zero weight changes)**. Held-out math models:
GPT-5.4-nano/mini, Gemini-3.1-Flash-Lite, Gemini-3-Flash.

Results: text classification +7.7 pts vs ACE with ~4x fewer context tokens;
math harness found on GPT-OSS-20B transfers +4.7 pts avg across five
held-out models; TB2 Opus 76.4% (#2), Haiku 37.6% (#1).

Reproducibility: code released but "cleaned-up… not tested beyond verifying
it runs"; no seed sweeps/SDs/CIs. Windows/local: not addressed; TB2 assumes
Linux sandboxes; proposer is a cloud coding agent. Ecosystem adoption real
(harness-forge, VideoHarness-RSI, HF spaces) but no independent replication.

## Cross-cutting (this report)

1. Only TinyAgent-1.1B is a 1–3B model; its headline rests on fine-tuned weights.
2. Meta-Harness and Growing Harness are pure runtime methods on frozen models
   but need large proprietary optimizers offline.
3. No LLM judges in-loop for TinyAgent/Meta-Harness; Growing Harness inherits
   one from a benchmark.
4. Code: TinyAgent MIT (macOS tools, dormant), Meta-Harness MIT (active);
   Growing Harness paper-only.
5. Windows: TinyAgent tool layer macOS-only; Meta-Harness assumes Linux.
