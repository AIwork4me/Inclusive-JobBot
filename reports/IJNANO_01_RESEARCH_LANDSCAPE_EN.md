# IJ-NANO-1.0 — N01 Research Landscape (Subjects R01–R09)

- Generated: 2026-11-27 (N01)
- Scope: consolidation of the N01 primary-source verification sweeps into the
  research-landscape deliverable required by mission order §2
  (`docs/IJNANO_MISSION_ORDER_V1_1.md`). No new claims beyond the recorded
  sweeps; no web browsing; no cloning or execution of subject code.
- Authoritative inputs: `evidence/IJNANO/N01/research_catalog.json` and the
  four verification sweeps in `evidence/IJNANO/N01/agent_reports/`
  (R01_R04, R02_R08, R03_R05_R06, R07_R09).
- Status vocabulary: subject verification is VERIFIED / PARTIALLY_VERIFIED and
  every catalog marking is preserved verbatim — never upgraded (R01's paper
  venue remains "PARTIALLY_VERIFIED"; R05 remains "VERIFIED as paper; NO
  CODE"; LLGuidance remains "UNVERIFIED_FOR_WINDOWS"). Execution statuses
  (PASS / FAIL / BLOCKED / NOT_RUN) apply to runtime work: in N01 every
  reproduction, local-Windows check and business evaluation of a subject is
  **NOT_RUN by construction**. The only executed-and-PASS evidence referenced
  is the engine-level N02 probe evidence for llama.cpp b12359.
- Machine-readable companions: `evidence/IJNANO/N01/license_matrix.json`
  (licenses, per subject/component) and
  `reports/IJNANO_OPEN_SOURCE_REUSE_DECISION.md` (component-level decision).

## 1. Subject-by-subject evidence (R01–R09)

Each block records the ten mandatory fields: primary source; exact paper
identity; repository revision; license; model parameter counts; whether model
weights changed (runtime-only vs fine-tuned); evaluation method (LLM-judged vs
deterministic); experimental metric; reported result; reproduction
limitations. All numbers are as reported by the primary sources; none were
reproduced in N01.

### 1.1 R01 — effGen — VERIFIED (paper venue PARTIALLY_VERIFIED)

| Field | Verified value |
|---|---|
| Primary source | `https://github.com/ctrl-gaurav/effGen` — main @ `37de05a6b4ed01c90ee38b9c254a162927ca2ac2` (2026-10-01); release v1.3.0 (2026-10-01); PyPI `effgen`; 208 stars |
| Exact paper identity | arXiv:2602.00887 "EffGen: Enabling Small Language Models as Capable Autonomous Agents", v2 2026-06-14; Srivastava, Hussain, Wang, Lin, Wang (Virginia Tech). "Accepted to ICML 2026" claimed on arXiv; OpenReview record not independently confirmed — venue **PARTIALLY_VERIFIED** (kept verbatim) |
| License | Code Apache-2.0; no weight artifacts distributed; paper-text license not recorded in the sweep |
| Model parameter counts | 1–3B total: Qwen2.5-1.5B-Instruct, Qwen2.5-3B-Instruct, Gemma 3 1B. Larger arms: Qwen2.5-7B/14B/32B, Gemma 3 1B–27B, GPT-OSS 20B |
| Weights changed? | No — runtime-only; frozen open weights; no fine-tuning; no weight artifacts in the 1,993-file repo |
| Evaluation method | Deterministic matching; **no LLM judge**; McNemar p<0.05 on 13 benchmarks; CIs stated to exist in the appendix (unread) |
| Experimental metric | Average accuracy across 13 agent benchmarks; tokens/task; speedup |
| Reported result | 1.5B: EffGen 47.44 vs Raw 34.28 / LangChain 32.81 / AutoGen 33.57 / Smolagents 27.81; 3B: 56.80; 7B: 63.07; 32B: 70.97; up to 18x speedup vs Smolagents (1.5B); ~734 tokens/task vs LangChain 1,318; scaling ablation: prompt optimization worth 11.2% at 1.5B vs 2.4% at 32B, routing 3.6% at 1.5B vs 7.9% at 32B; 70–87% tool-error recovery claimed |
| Reproduction limitations | ~52 base runtime deps (torch, transformers, fastapi, docker, 3 Google SDKs) — contradicts the minimal-runtime thesis; appendix CIs unread; Windows local plausible but undocumented (UNVERIFIED); venue unconfirmed; marketing polish and candid changelog regressions noted in the sweep |

Mechanisms verified in code and paper: model-size-aware 5-stage prompt
optimization (35-template library); YAML tool-description compression (−32%
tokens vs JSON); complexity-aware ModelRouter (Cost/Latency policies);
WorkflowDAG decomposition; 3-tier memory (FAISS/Chroma); MCP/A2A/ACP;
retry/backoff with graceful degradation; loop detection
(`max_turns_without_progress=2`, stronger in code than paper);
`recover_lost_tool_calls=True` default (v1.3.0); local backends
(llama-cpp-python GGUF, Transformers, vLLM, MLX, any OpenAI-compatible
`base_url`). Reuse class: `RESEARCH_ONLY_FOR_REPRODUCTION` (E01 comparator).

### 1.2 R02 — PTC-Decoder — VERIFIED

| Field | Verified value |
|---|---|
| Primary source | `https://github.com/yuminghui/llm-tool-constrained-decoder` — dormant since 2026-07-19; single author; 3 stars |
| Exact paper identity | arXiv:2609.30836 "PTC-Decoder: Towards Intelligent SLMs on Offline Resource-Constrained Edge Devices", v1 2026-09-25, preprint, no venue; Yu, Mu, Wu |
| License | MIT (code) + CC BY 4.0 (benchmark data addendum); **paper text CC BY-NC-SA** (non-commercial) |
| Model parameter counts | 7 SLMs, all ≤2B total: Qwen3.5-2B (mission expectation CONFIRMED), Qwen3-1.7B, Qwen3-0.6B, Qwen3.5-0.8B, gemma-3-1b-it, gemma-4-E2B-it (2.3B effective dense PLE; repo mislabels "2.0B MoE"), DeepSeek-R1-Distill-Qwen-1.5B |
| Weights changed? | No — runtime-only; training-free constrained decoding; zero weight changes |
| Evaluation method | **LLM-judged** (DeepSeek-V4-flash, 0–5 scales; 20 samples human double-checked) |
| Experimental metric | Judge "Overall" score; external F1 on ToolAlpaca / Seal-Tools / API-Bank; token overhead |
| Reported result | Mean Overall +1.21 (p<0.01, 95% CI [+1.13, +1.29]); best Overall 3.12 on Qwen3.5-2B; weakest model +350%; Qwen3-1.7B +48%; external F1 38→53 / 33→68 / 31→50; ablation remove-TC −0.99; token overhead 2.07x; counterexample: Qwen3-1.7B F1 0.355 → 0.292 under constraint |
| Reproduction limitations | arXiv-only preprint, no venue; dormant single-author repo; judge availability dependency (DeepSeek-V4-flash); transformers-only implementation (torch 2.12, transformers 5.8.1) — NOT llama.cpp-compatible, no adapter exists; admitted negative case; 2.07x token overhead; tested on Jetson Orin NX / Ubuntu 22.04, Windows plausible-untested |

Mechanisms (all in code): Plan-to-Act (forced first `plan` tool call);
HuggingFace `LogitsProcessor` masking DFA-unacceptable tokens + forced EOS at
accept + PAD mask; `char_fsm` NFA→DFA; per-step dynamic constraints;
`json_schema_to_fsm` can constrain arguments structurally, but the paper's
evaluated config constrains tool names only, params free (paper/code scope
divergence; code ≥ paper). Reuse class: `REIMPLEMENT_CLEAN_ROOM` — the
DFA+mask+forced-EOS design must be re-expressed via llama.cpp per-request
`json_schema`/`grammar` (or XGrammar-2 structural tags).

### 1.3 R03 — TinyAgent — VERIFIED

| Field | Verified value |
|---|---|
| Primary source | `https://github.com/SqueezeAILab/TinyAgent` — MIT; dormant since 2024-09-04 (~6 commits, 503 stars); HF artifacts TinyAgent-1.1B/7B (+GGUF), TinyAgent-ToolRAG, TinyAgent-dataset, all cards MIT |
| Exact paper identity | "TinyAgent: Function Calling at the Edge", arXiv:2409.00608, EMNLP 2024 **Demo track** |
| License | MIT (code, weights, dataset) |
| Model parameter counts | TinyAgent-1.1B (TinyLlama-1.1B base) — the only 1–3B total model in the R01–R09 corpus; TinyAgent-7B (WizardLM-2-7B) |
| Weights changed? | **Yes — the headline rests on fine-tuned weights**: +66/+42 pts from LoRA tool fine-tuning (80K synthetic samples, GPT-3.5/GPT-4 generated, ~$500 data cost); runtime mechanisms add only ~1.2–1.9 pts (ToolRAG, also ~2x prompt reduction); 4-bit QAT ~+0.3 |
| Evaluation method | Deterministic — programmatic graph isomorphism on their 1K test set; **no LLM judge** |
| Experimental metric | Function-calling accuracy |
| Reported result | 1.1B: base 12.71% → +LoRA 78.89% → +ToolRAG 80.06% → +4bit 80.35%; 7B: 41.25% → 83.09% → 84.95% → 85.14%; baselines GPT-3.5-turbo 65.04%, GPT-4-turbo 79.08%; ToolRAG selects ~3.97 tools vs 6 naive (DeBERTa-v3-small multi-label classifier) |
| Reproduction limitations | Self-generated synthetic evaluation; demo-track paper; dormant repo; **all 16 shipped tools are macOS AppleScript — Windows requires a full tool-layer rewrite**; core (llama.cpp GGUF serving) is portable |

Reuse class: `RESEARCH_ONLY` — the weight-change headline is not transferable
to a frozen-weights runtime; ToolRAG is the mechanism study input for M02.

### 1.4 R04 — Automated SLM Harness Adaptation — VERIFIED (repo renamed)

| Field | Verified value |
|---|---|
| Primary source | `https://github.com/malusamoyo/slm-harness-adaptation` (renamed from `migration-analysis`, HTTP 301, same repo id `R_kgDOQizbnA`) — MIT; main @ `2d31e1791a68f89554aa81c97d58fd62a636f4f4` (2026-09-04); 30 stars; no releases/tags |
| Exact paper identity | arXiv:2607.08938 "Better Harnesses, Smaller Models: Building 90% Cheaper Agents via Automated Harness Adaptation", v1 2026-07-09, cs.SE preprint, no venue; Yang, Zhao, Wu, Kästner |
| License | MIT (+ MIT submodule `software-agent-sdk`, OpenHands SDK) |
| Model parameter counts | **3–8B ACTIVE / 8–30B TOTAL (MoE)**: gemma-4-26b-a4b, qwen3-coder-30b-a3b; plus ministral-3-8b dense; frontier baseline gemini-3.1-pro. No 1–3B total model — this subject is exactly the mission-order total-vs-active distinction case |
| Weights changed? | No — runtime-only; frozen cloud-served weights (Vertex AI / Bedrock); GEPA-style genetic/Pareto harness search with a Gemini meta-agent (gemini-3.1-pro-preview) inside the loop; dspy>=3.0.4 |
| Evaluation method | Deterministic objective task metrics; **no LLM judge for scoring**; 3-run averages, best-validation kept; no CIs; results described as "highly stochastic" |
| Experimental metric | Test-set average task success (20/20/60 train/val/test split per task); cost per task |
| Reported result | gemma-4-26b-a4b 31.4% → 80.2% ($0.043 → $0.071) vs frontier 89.7% ($1.735); qwen3-coder-30b-a3b 26.9% → 76.3%; ministral-3-8b 9.5% → 25.0%; 16/21 task–SLM pairs improved, 3 regressed; $20/run, $1,260 total; "optimization cost recovered after 13 runs on average" |
| Reproduction limitations | Cloud APIs + Docker + Python>=3.14 → **no Windows-native path**; figshare replication package not downloaded in the sweep; abstract rounding discrepancy (89.7% claimed vs 89.4% computed); no statistical significance on headline comparisons |

Reuse class: `RESEARCH_ONLY` — methodology input for the N10 optimizer design
(O0–O5 comparators).

### 1.5 R05 — Growing Harness — VERIFIED as paper; NO CODE

| Field | Verified value |
|---|---|
| Primary source | arXiv only: **no code found** (no repo link in the paper; searches return citation trackers only) |
| Exact paper identity | arXiv:2609.26760 "Grow the Harness, Not the Context: From Strategy-Free Scaffolds to Reusable Specialist Agents", v1 2026-09-22 / v2 2026-09-24, preprint; Li, Li, Zhao, Ye, Li, Xu, Gao (SIAT CAS, UCAS, SUSTech, UMacau) |
| License | Paper text CC BY 4.0; nothing else exists to license |
| Model parameter counts | gpt-oss-120b, gpt-oss-20b, Qwen3.5-4B (smallest — **no 1–3B model**); optimizer GPT-5.6-terra / GPT-5.4 (proprietary) |
| Weights changed? | No — runtime-only; strategy-free scaffold + failure-guided conversion of recurring deterministic control decisions (parsing, validation, state updates, error recovery, stopping) into reusable executable code; function-level traces; joint repair window; success-first held-out gate with rollback |
| Evaluation method | **LLM judge inherited from the BrowseComp-Plus benchmark only**; otherwise benchmark scores; means over 3 runs with bootstrap CIs; no independent validation (~3 citations) |
| Experimental metric | LLM-call reduction; inference cost; WebArena success rate |
| Reported result | LLM-call reduction 76.0–91.8%; inference cost −74.4–98.6%; best mean in 5/6 settings; WebArena 44.7–45.3% while a Tool-Calling scaffold collapses to 6.7% at 4B |
| Reproduction limitations | **Paper-only — nothing to run**; optimizer requires proprietary frontier models; no independent replication |

Reuse class: `RESEARCH_ONLY` — the principle ("compile repeated control
decisions into deterministic code") is the M-mechanism "Growing Harness" arm
E06; task-specific business logic stays separate from model-oriented runtime
logic per mission order §8.

### 1.6 R06 — Meta-Harness — VERIFIED

| Field | Verified value |
|---|---|
| Primary source | `https://github.com/stanford-iris-lab/meta-harness` — MIT; created 2026-04-15, pushed 2026-11-05, 1814 stars, active. Artifact `meta-harness-tbench2-artifact` exists with **NO license (all rights reserved) — UNLICENSED** |
| Exact paper identity | "Meta-Harness: End-to-End Optimization of Model Harnesses", arXiv:2603.28052 (preprint); Lee, Nair, Zhang, K. Lee, Khattab, Finn |
| License | Main repo MIT; TB2 artifact UNLICENSED (excluded from reuse); paper-text license not recorded |
| Model parameter counts | Deployed: GPT-OSS-120B/20B, Claude Opus 4.6 / Haiku 4.5 — frozen, ≥20B, parameter counts otherwise unstated; **no 1–3B model anywhere**. Held-out math models: GPT-5.4-nano/mini, Gemini-3.1-Flash-Lite, Gemini-3-Flash |
| Weights changed? | No — runtime-only; outer-loop search over single-file Python harness programs around frozen base models; proposer = Claude Code + Opus-4.6 (cloud) with filesystem access to prior candidates' code, scores and **raw execution traces** (ablation: raw traces > summaries); task-reward-only feedback |
| Evaluation method | Deterministic task reward; **no LLM judge**; but no seed sweeps, SDs or CIs; released code described as "minimally tested" |
| Experimental metric | Task score (points); context-token count |
| Reported result | Text classification +7.7 pts vs ACE with ~4x fewer context tokens; math harness found on GPT-OSS-20B transfers +4.7 pts average across five held-out models; TB2: Opus 76.4% (#2), Haiku 37.6% (#1) |
| Reproduction limitations | No Windows/local deployment story; TB2 assumes Linux sandboxes; statistical rigor absent; ecosystem adoption real (harness-forge, VideoHarness-RSI, HF spaces) but no independent replication; unlicensed TB2 artifact cannot be reused |

Reuse class: `RESEARCH_ONLY` — N10 optimizer methodology; the raw-trace
feedback > score-only feedback ablation is directly actionable.

### 1.7 R07 — MagenticLite — VERIFIED

| Field | Verified value |
|---|---|
| Primary source | Not a separate repo: next generation of `https://github.com/microsoft/magentic-ui` (PyPI `magentic_ui`, MIT), living on `main` (old 0.1 AutoGen line on branch `magentic-ui-0.1`); pushed 2026-11-16, ~10.1k stars; v0.2.1 (2026-05-21), PyPI 0.2.2 (2026-07-21), Python >= 3.12 |
| Exact paper identity | **None — blog announcement** (Microsoft Research AI Frontiers, May 2026), not a paper |
| License | MIT code + MIT weights; research-grade caveats (Fara card: commercial use without additional testing out of scope) |
| Model parameter counts | MagenticBrain ~14B (SFT+RL from Qwen3-14B, 32K ctx) + Fara1.5-9B (from Qwen3.5-9B, 262K ctx, vision-only). **No 1–3B model — "small" here means 9–14B**; other Fara sizes unverified beyond one blog sentence |
| Weights changed? | Yes (relative to base) — MagenticBrain is SFT+RL from Qwen3-14B; Fara1.5-9B from Qwen3.5-9B |
| Evaluation method | Not recorded in the sweep (no paper metrics verified) |
| Experimental metric | Not recorded in the sweep |
| Reported result | Not recorded in the sweep — design claims only: step-by-step incremental planning; active context management (curating/condensing what small models see); delegation to subagents; recovery; human-in-the-loop pauses; Quicksand QEMU-based sandboxed execution |
| Reproduction limitations | 27 base deps — a full web-app stack (playwright, fastapi, sqlmodel, quick-sandbox, ...), not an embeddable library; Windows x64 supported **via WSL2 only**; documented hosting assumes vLLM-class GPUs (48–96 GB); llama.cpp as a hosting path undocumented (endpoints are OpenAI-compatible `/v1/chat/completions`, protocol-verified) |

Reuse class: `RESEARCH_ONLY` — design-pattern reference for Layer B/C. Note:
0.2 is NOT built on AutoGen/Agent Framework; Magentic-One continues as
"Magentic orchestration" in Microsoft Agent Framework (`agent-framework`
PyPI 1.26.0, MIT).

### 1.8 R08 — Constrained-decoding infrastructure — VERIFIED

Three components; none are papers; all licenses verified.

| Component | Version / status | Dynamic (state-dependent) capability | Reuse class (verbatim) |
|---|---|---|---|
| llama.cpp GBNF + json_schema | MIT; stable v1.1.0 (2026-11-26), nightly b12811 upstream; **mission-pinned engine b12359 (v1.0.0)** | Per-request grammar; mid-generation switching only via internal grammar triggers (tool-call parsers; v1.1.0 lazy grammar + out-of-range trigger rejection); **no public per-token grammar-change API** | REUSE_DIRECTLY (pinned b12359; N02 probe evidence) |
| LLGuidance | MIT (Microsoft-backed); v1.9.1, active (2026-11-18); ~50 µs/token mask; full JSON-schema mask ~1.5 ms; coverage oneOf 68% / allOf 98% / pattern 99% / format 74%; no external $ref; lenient mode | Cheap per-request grammar creation; token-trie constraints at exact token boundaries | UNVERIFIED_FOR_WINDOWS (no win wheels confirmed); candidate via llama.cpp build flag (integration optional, default OFF) |
| XGrammar | Apache-2.0; v0.2.9 (2026-11-09), active; default structured backend for vLLM/SGLang/TensorRT-LLM/MLC-LLM; native Windows wheels | **XGrammar-2** (May 2026, ACM DOI 10.1145/3786335.3813124): `triggered_tags` structural DSL (mid-generation state-dependent switching by markers), cross-grammar cache (~50% reuse @ 50 tools), repetition compression 100x, up to 80x compilation speedup, batching + speculative decoding, fork/rollback states | REUSE_WITH_ADAPTER_CANDIDATE (reference design for M04 if llama.cpp-native path insufficient) |

Engine-behavior finding (executed evidence, N02 probe v2, PASS-recorded
there): **b12359 rejects backslash-escaped-quote GBNF literals**; char-class
form `["]` works. Also: llama.cpp request surface verified — `grammar` +
`json_schema` fields on both endpoints, `response_format` wrapper
`{"type":"json_schema","json_schema":{name,strict,schema}}`, `tools` +
`tool_choice` auto/any/named (named since v1.1.0) with `--jinja`, MCP stdio
servers. XGrammar v0.x compile-time token-mask precompute can cost
seconds-to-minutes; v0.2.9 added opt-in JIT compilation.

### 1.9 R09 — General-purpose agentic SDKs — VERIFIED

| SDK | License | Version | Base deps | Local / OpenAI-compatible | Notes | Reuse class (verbatim) |
|---|---|---|---|---|---|---|
| PocketFlow | MIT | 0.0.3 | **0** | bring-your-own client | 99 lines; Node/Flow + max_retries/wait/exec_fallback; no typed tools | REUSE_DIRECTLY (skeleton candidate) |
| Pydantic AI (`pydantic-ai-slim`) | MIT | 2.76.0 (2026-11-27) | 9 | first-class `OpenAICompatibleProvider`, vLLM, Ollama; weak-backend model profiles | typed tools, validated structured output, 9 documented retry layers | REUSE_WITH_ADAPTER (typed layer candidate) |
| smolagents | Apache-2.0 | 1.26.0 | 6 | **dedicated `LlamaCppModel`** + Transformers/Ollama/LiteLLM | CodeAgent (actions as code) — SLM-relevant; local executor "not a security boundary" | REUSE_WITH_ADAPTER (model client + loop patterns) |
| LangGraph | MIT | 1.2.24 | 6 (+langchain-core tree) | no model client at all (model-agnostic) | durable execution, interrupts, checkpointing | TECHNICALLY_UNSUITABLE_FOR_MINIMAL (dependency tree) |
| OpenAI Agents SDK | MIT | 0.26.0 | 14 | `set_default_openai_client(base_url=...)`; tracing must be disabled without an OpenAI key | guardrails, sessions, handoffs; native-Windows documented | RESEARCH_ONLY (B-arm comparator) |
| Google ADK | Apache-2.0 | 2.15.1 | 24 (heaviest; fastapi/uvicorn/google-auth/graphviz) | Ollama/vLLM/LiteLLM connectors | workflow agents, callbacks, eval suite | TECHNICALLY_UNSUITABLE_FOR_MINIMAL |
| DSPy | MIT | 3.5.0 | 14 | quickstart uses `ollama_chat/llama3.2:1b` (explicit 1B) | Signatures + optimizers (GEPA); LLM judge designed-in for offline tuning (build-time only) | RESEARCH_ONLY (N10 optimizer comparator) |

## 2. Required distinction tables

### 2.1 1–3B TOTAL parameters vs larger MoE with small ACTIVE counts

| Subject | Parameter regime | Models | Applicability to a 1–3B-total runtime |
|---|---|---|---|
| R01 effGen | **1–3B total included** | Qwen2.5-1.5B/3B, Gemma 3 1B | Direct evidence (strongest 1–3B corpus member) |
| R02 PTC-Decoder | **≤2B total (7 SLMs)** | incl. Qwen3.5-2B, Qwen3-1.7B, gemma-3-1b-it | Direct evidence incl. the mission's Qwen3.5-2B expectation (CONFIRMED) |
| R03 TinyAgent | **1.1B total** | TinyAgent-1.1B | Direct, but the headline is weight-fine-tuned (see 2.2) |
| R04 slm-harness-adaptation | **3–8B active / 8–30B total MoE** (+ one 8B dense) | gemma-4-26b-a4b, qwen3-coder-30b-a3b, ministral-3-8b | **Not 1–3B-total evidence**: small-active MoE gains do not transfer to small-total dense models |
| R05 Growing Harness | ≥4B | Qwen3.5-4B smallest; gpt-oss-20b/120b | No 1–3B evidence |
| R06 Meta-Harness | ≥20B (unstated) | GPT-OSS-120B/20B, Claude Opus 4.6/Haiku 4.5 | No 1–3B evidence |
| R07 MagenticLite | 9–14B | MagenticBrain ~14B, Fara1.5-9B | No 1–3B evidence ("small" = 9–14B) |

### 2.2 Runtime-only optimization vs weight fine-tuning

| Subject | Gain origin | Decomposition |
|---|---|---|
| R01 effGen | **Runtime-only** | Frozen open weights; no fine-tuning; no weight artifacts |
| R02 PTC-Decoder | **Runtime-only** | Training-free constrained decoding; zero weight changes |
| R03 TinyAgent | **Mixed — weights dominate** | +66/+42 pts from LoRA fine-tuning; ToolRAG +1.5–2 pts (plus ~2x prompt reduction); QAT ~+0.3 |
| R04 slm-harness-adaptation | **Runtime-only** | GEPA-style harness search over frozen cloud weights |
| R05 Growing Harness | **Runtime-only** | Optimizer is proprietary frontier models; base models frozen |
| R06 Meta-Harness | **Runtime-only** | Frozen ≥20B models; harness search offline |
| R07 MagenticLite | **Weights changed** | MagenticBrain = SFT+RL from Qwen3-14B; Fara1.5-9B from Qwen3.5-9B |

Mission consequence: only R01 and R02 provide runtime-only evidence at 1–3B
total; R03's runtime mechanisms are worth ~1.5–2 pts on top of fine-tuned
weights and must not be attributed to the runtime alone (mission order §8).

### 2.3 Job-specific specialization

| Subject | Specialization dimension | Carrier | Transfer to this mission |
|---|---|---|---|
| R01 effGen | General agent benchmarks; model-size-aware prompt tiers | Runtime prompts | No job-specific evidence; comparator only (E01) |
| R02 PTC-Decoder | Domain benchmark: 200-task expert-annotated remote-sensing workload | Evaluation only — the mechanism (DFA tool constraints) is domain-agnostic | Mechanism portable via clean-room reimplementation; evaluation must be rebuilt on mission business worlds |
| R03 TinyAgent | Fixed 16-tool macOS AppleScript suite; 80K synthetic tool-specific samples | **Weights (LoRA) + tool layer** | Not transferable; ToolRAG mechanism only (M02), with frozen weights per mission order §8 |
| R04 slm-harness-adaptation | Per-task-family harness search (21 task–SLM pairs) | Runtime harness configurations | Methodology for N10; O0–O5 comparators |
| R05 Growing Harness | Compiles task-specific recurring control decisions into deterministic code on a strategy-free scaffold | Runtime code (reusable specialists) | Principle adopted as mechanism arm E06; task-specific business logic kept separate from model-oriented runtime logic (mission order §8) |
| R06 Meta-Harness | Harness programs specialized per task family | Runtime code | N10 methodology only |

Cross-cutting: **no subject provides evidence for the mission's own business
domain**, and the catalog records "independently_verified_business_correctness:
none found for any subject".

### 2.4 LLM-judged vs deterministically verified results

| Subject | Scoring method | LLM judge | Statistical reporting | Deterministic? |
|---|---|---|---|---|
| R01 effGen | Deterministic matching, 13 benchmarks | No | McNemar p<0.05; CIs in appendix (unread) | Yes |
| R02 PTC-Decoder | DeepSeek-V4-flash judge, 0–5 scales; 20 samples human double-checked | **Yes** | +1.21, p<0.01, 95% CI [+1.13, +1.29] | No (judge-dependent) |
| R03 TinyAgent | Programmatic graph isomorphism, 1K test set | No | None recorded | Yes |
| R04 slm-harness-adaptation | Objective task metrics (Gemini only inside the optimizer loop, not scoring) | No | 3-run averages; no CIs; "highly stochastic" | Yes |
| R05 Growing Harness | Benchmark suite incl. BrowseComp-Plus | Inherited from benchmark only | 3-run means, bootstrap CIs | Partially |
| R06 Meta-Harness | Task-reward only | No | No seed sweeps / SDs / CIs; code "minimally tested" | Yes (weakly reported) |
| R07 MagenticLite | Not recorded in the sweep | — | — | Not recorded |

## 3. Component-level comparison: PocketFlow vs pydantic-ai-slim vs smolagents vs effGen

Mission-order §2 comparison across the ten mandated axes. "Not recorded"
means the verification sweep contains no primary-source statement on that
axis; it is not a finding of absence.

| Axis | PocketFlow 0.0.3 (MIT) | pydantic-ai-slim 2.76.0 (MIT) | smolagents 1.26.0 (Apache-2.0) | effGen v1.3.0 (Apache-2.0) |
|---|---|---|---|---|
| Native functionality | Graph primitives only: Node/Flow, conditional/batch/async, per-node `max_retries`/`wait`/`exec_fallback`; no model client, no typed tools | Typed tools, schema-validated structured output, 9 documented retry layers, `OpenAICompatibleProvider` with weak-backend profiles, vLLM/Ollama | Agent loop + CodeAgent (actions as code), dedicated `LlamaCppModel`, Transformers/Ollama/LiteLLM, tool calling | Full agent platform: 5-stage size-aware prompt optimization (35 templates), YAML tool compression (−32% tokens), ModelRouter, WorkflowDAG, 3-tier memory (FAISS/Chroma), MCP/A2A/ACP, loop detection, graceful degradation, local backends (llama-cpp-python GGUF, vLLM, MLX, OpenAI-compatible) |
| Required custom code | Highest of the four: model client, tools, typed layer, telemetry all mission-built | Medium: model client and validation given; orchestration/agent policy mission-built | Medium-low: agent loop given; sandboxing must be supplied (executor is not a security boundary) | Lowest nominally, but bound to its own stack; mission uses it as an E01 comparator, not a component |
| Dependency footprint | **0** | 9 | 6 | **~52** (torch, transformers, fastapi, docker, 3 Google SDKs) |
| Initialization cost | Trivial (99 lines, pure Python) | Moderate (imports + provider setup; no server) | Moderate (executor + local model setup) | Heavy (ML stack incl. vector-memory tiers; docker in deps) |
| Observability | None built-in; logging left to the embedder | Retry/validation outcomes surfaced through typed results; deeper telemetry not recorded | Not recorded beyond executor caveats | Internal retry/backoff, degradation and loop-detection events; telemetry surface not recorded |
| Security | No code-execution surface in the skeleton (nothing built in) | Schema validation reduces malformed-output surface; no sandbox claim recorded | **CodeAgent executes model-generated code; executor explicitly "not a security boundary"** — must sit behind a mission sandbox | Ships docker in deps; MCP/A2A/ACP external surfaces; no sandbox guarantee recorded |
| Maintenance effort | 99 lines — fork cost trivial, but all orchestration maintenance shifts to the mission | Daily-active upstream; 9 deps to track | Active upstream (HF); 6 deps to track | 1,993-file repo, 20+ releases, candid changelog admitting regressions; ~52 deps — heaviest if embedded (mission embeds nothing) |
| Commercial licensing | MIT — clean | MIT — clean | Apache-2.0 — clean | Apache-2.0 — clean but footprint-heavy for SDK embedding |
| Local Windows compatibility | Yes (pure Python; catalog-verified) | Yes (Windows wheels verified) | Pure Python, local-first; Windows not explicitly asserted in the sweep | Plausible-untested (OS-Independent, pure Python; undocumented) |
| Model-specific adaptation effort | None provided — all SLM adaptation is mission work | Lowest recorded: model profiles for weak backends target exactly the small-model failure surface | Low-medium: `LlamaCppModel` first-class; CodeAgent suits SLM action-as-code; profiles not recorded | Purpose-built for 1.5B–32B (size-aware prompting) but only within its own stack |

**Required disclaimer (mission order §2).** Dependency count is **not** a
complete framework-quality ranking. PocketFlow's near-zero footprint is
useful, but a framework that requires substantial custom orchestration can
carry a higher total engineering cost than a richer framework: with
PocketFlow, the model client, typed tool layer, validation-retry behavior and
observability all become mission-owned code that must be specified, tested
and hardened (N06A-R defect classes apply to it like any other code). The
dependency column is one factor among the ten axes above, not a ranking.

## 4. Honest conclusions

1. **Strongest 1–3B-total evidence: effGen (runtime-only).** 1.5B average
   47.44 vs 34.28 raw across 13 benchmarks with deterministic scoring and
   McNemar p<0.05 — but carried by a ~52-dependency stack whose footprint
   contradicts the minimal-runtime thesis, a PARTIALLY_VERIFIED venue, and
   unread appendix CIs. Reproduction as comparator E01 only.
2. **Second 1–3B evidence: PTC-Decoder, including Qwen3.5-2B** (mission
   expectation CONFIRMED; best Overall 3.12; p<0.01 with CI) — but the
   primary metric is **LLM-judged** (DeepSeek-V4-flash), the implementation
   is **transformers-only** (not llama.cpp-compatible; no adapter exists),
   token overhead is 2.07x, and an admitted counterexample exists
   (Qwen3-1.7B: constrained F1 0.292 < unconstrained 0.355). Usable as a
   clean-room mechanism (M04), not as code.
3. **TinyAgent's 1.1B headline (80.35%) rests on fine-tuned weights**
   (+66/+42 pts LoRA); its runtime mechanisms add only ~1.5–2 pts; all 16
   tools are macOS AppleScript. Not transferable evidence for a
   frozen-weights, Windows-local runtime.
4. **Growing Harness is paper-only** (no code; proprietary optimizer; judge
   inherited from a benchmark; ~3 citations, no independent validation). The
   principle — compile repeated control decisions into deterministic code —
   is adopted as mechanism arm E06, with zero reusable code.
5. **No independently verified business correctness exists anywhere in
   R01–R09** (catalog cross-cutting finding). Every subject evaluates on
   public agent benchmarks or self-constructed tasks; none measures the
   mission's business worlds. Formal business claims remain gated on the
   mission's own qualified Oracle (N05A) — status NOT_RUN in N01.
6. **Total-vs-active matters:** R04's 31.4% → 80.2% result is 3–8B-active /
   8–30B-total MoE evidence and must not be cited for 1–3B-total models;
   R06/R07 operate at ≥9B. Only R01, R02, R03 touch the 1–3B-total regime.
7. **License posture:** commercially clean set for embedding — llama.cpp
   (MIT), PocketFlow (MIT), pydantic-ai-slim (MIT), smolagents
   (Apache-2.0), XGrammar (Apache-2.0), effGen (Apache-2.0, footprint-heavy),
   PTC-Decoder code (MIT). Excluded or conditioned: Meta-Harness TB2
   artifact (UNLICENSED), PTC-Decoder paper text (CC BY-NC-SA,
   non-commercial), LFM3-1.7B weights (LFM Open License v1.0,
   revenue-conditioned — **research use unaffected, IJN-B-003**).
8. **Binding reuse decisions are deferred to N03 measured capabilities**
   (mission order: do not finalize model-specific execution policies before
   measuring the capabilities that justify them). The recorded component-level
   dispositions live in `reports/IJNANO_OPEN_SOURCE_REUSE_DECISION.md`.

## 5. Verdict and evidence index

`N01_RESEARCH_LANDSCAPE_VERIFIED` — documentation scope PASS: every claim
above carries its primary source (repo + revision / arXiv id + version /
license), catalog verification markings are preserved verbatim, and all four
distinction tables required by mission order §2 are present. Execution
statuses: subject reproductions, Windows-local validations and business
evaluations are NOT_RUN in N01 by construction; the only executed evidence
cited is the N02 engine probe for llama.cpp b12359.

Evidence index:

- `evidence/IJNANO/N01/research_catalog.json` — verified catalog (subjects R01–R09)
- `evidence/IJNANO/N01/agent_reports/R01_R04_verification.md` — R01, R04 sweep
- `evidence/IJNANO/N01/agent_reports/R02_R08_verification.md` — R02, R08 sweep
- `evidence/IJNANO/N01/agent_reports/R03_R05_R06_verification.md` — R03, R05, R06 sweep
- `evidence/IJNANO/N01/agent_reports/R07_R09_verification.md` — R07, R09 sweep
- `evidence/IJNANO/N01/license_matrix.json` — machine-readable license companion
- `reports/IJNANO_OPEN_SOURCE_REUSE_DECISION.md` — component-level decision record
