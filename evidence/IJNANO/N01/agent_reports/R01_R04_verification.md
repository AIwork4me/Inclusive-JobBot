# N01 primary-source verification — R01 effGen, R04 slm-harness-adaptation

- Verification agent report, 2026-11-27 (GitHub API, arXiv, PyPI; no cloning/execution)
- Status: agent-verified; to be folded into the landscape reports

## SUBJECT 1 — effGen — VERIFIED (minor caveats)

| Item | Verified value |
|---|---|
| Repo | https://github.com/ctrl-gaurav/effGen — Apache-2.0 (SPDX), main @ `37de05a6b4ed01c90ee38b9c254a162927ca2ac2` (2026-10-01), 208 stars |
| Release | v1.3.0 (2026-10-01); 20+ releases since v0.0.1 (2026-01-31); PyPI `effgen` exists; effgen.org |
| Paper | arXiv:2602.00887 "EffGen: Enabling Small Language Models as Capable Autonomous Agents", v2 2026-06-14; authors Srivastava, Hussain, Wang, Lin, Wang (VT) |
| Venue | "Accepted to ICML 2026" per arXiv comments; OpenReview record NOT independently confirmed (bot challenge) — PARTIALLY VERIFIED |

Mechanisms in code AND paper (1,993-file repo): model-size-aware 5-stage
prompt optimization (35-template library); YAML tool-description compression
(-32% tokens vs JSON); complexity-aware ModelRouter (Cost/Latency policies);
WorkflowDAG task decomposition; 3-tier memory (FAISS/Chroma); MCP/A2A/ACP;
retry/backoff + graceful degradation (70–87% tool-error recovery claimed);
loop detection (max_turns_without_progress=2, loop guard — stronger in code
than paper); recover_lost_tool_calls=True default (v1.3.0); local backends
(llama-cpp-python GGUF, Transformers, vLLM, MLX, any OpenAI-compatible
base_url — external llama-server works).

Models (paper Table 2): Qwen2.5-1.5B/3B/7B/14B/32B, Gemma 3 1B–27B, GPT-OSS
20B. **1–3B total: Qwen2.5-1.5B, Qwen2.5-3B, Gemma 3 1B.**

Gains (13 benchmarks, avg accuracy): 1.5B EffGen 47.44 vs Raw 34.28 /
LangChain 32.81 / AutoGen 33.57 / Smolagents 27.81; 3B 56.80; 7B 63.07; 32B
70.97. Up to 18x speedup vs Smolagents (1.5B); ~734 tokens/task vs LangChain
1,318. Scaling: prompt-optimization ablation costs 11.2% at 1.5B vs 2.4% at
32B (H01-relevant evidence); routing ablation 3.6% at 1.5B vs 7.9% at 32B.

**Runtime-only gains** (open frozen weights; no fine-tuning; no weight
artifacts in repo). **No LLM judge** (deterministic matching; McNemar
p<0.05; CIs in appendix — UNVERIFIED in detail). Windows: OS-Independent
classifier, pure-Python, plausible but undocumented — UNVERIFIED. Footprint:
~52 base runtime deps incl. torch, transformers, fastapi, docker, 3 Google
SDKs — heavy for SLM use. Red flags minor (marketing polish; candid
changelog admitting regressions; NAIRR compute).

## SUBJECT 2 — Automated SLM Harness Adaptation — VERIFIED (naming nuance)

| Item | Verified value |
|---|---|
| Repo | https://github.com/malusamayo/slm-harness-adaptation (renamed from `migration-analysis`, 301 → same repo id `R_kgDOQizbnA`) — MIT, main @ `2d31e1791a68f89554aa81c97d58fd62a636f4f4` (2026-09-04), 30 stars, **no releases/tags** |
| Paper | arXiv:2607.08938 "Better Harnesses, Smaller Models: Building 90% Cheaper Agents via Automated Harness Adaptation", v1 2026-07-09, cs.SE preprint, no venue |
| Authors | Chenyang Yang, Xinran Zhao, Tongshuang Wu, Christian Kästner |
| Artifacts | figshare replication package (not downloaded); submodule software-agent-sdk (OpenHands SDK, MIT; SSH URL needs HTTPS conversion) |

Method: GEPA-style genetic/Pareto search over harness candidates (dspy>=3.0.4);
meta-agent (gemini-3.1-pro-preview) edits prompts, examples, skills, dynamic
contexts, tools, hooks, condensers, custom agents on the OpenHands SDK.
20/20/60 train/val/test split per task; 3 optimization runs, best-validation
kept; $20/run, $1,260 total; "optimization cost recovered after 13 runs on
average". No CIs or formal significance on headline comparisons; results
"highly stochastic".

Models: **explicitly 3B–8B ACTIVE (8B–30B TOTAL)** — gemma-4-26b-a4b,
qwen3-coder-30b-a3b, ministral-3-8b dense; frontier baseline gemini-3.1-pro.
**No 1–3B total model.**

Gains (test-set avg): gemma-4-26b-a4b 31.4% → 80.2% ($0.043→$0.071) vs
frontier 89.7% ($1.735); qwen3-coder-30b-a3b 26.9% → 76.3%; ministral-3-8b
9.5% → 25.0%; 16/21 task-SLM pairs improved, 3 regressed.

**Runtime-only** (frozen cloud-served weights; Vertex AI/Bedrock; no local
stack; Docker/Linux-oriented; Windows unlikely without WSL). No LLM judge for
scoring (objective metrics); Gemini meta-agent inside the optimizer loop.
Red flags: repo/paper URL mismatch (benign rename); Python >=3.14 + Docker;
abstract rounding (89.7% recovery vs computed 89.4%).

## Cross-subject answers

- 1–3B total: effGen yes (1.5B/3B/Gemma-1B); harness-adaptation no.
- Runtime-only gains: both yes; effGen has the strongest 1.5B-class evidence.
- LLM judges: none for scoring in either.
- Windows-native local: effGen plausible-untested; harness-adaptation no.
- Commercial: effGen Apache-2.0; harness-adaptation MIT (+ MIT submodule).
