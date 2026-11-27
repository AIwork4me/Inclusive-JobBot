# N01 primary-source verification — R07 MagenticLite, R09 general-purpose SDKs

- Verification agent report, 2026-11-27 (GitHub API, PyPI JSON API, Microsoft/HF docs; no cloning/execution)
- Status: agent-verified; to be folded into the landscape reports

## SUBJECT 1 — MagenticLite — VERIFIED

- **Identity**: NOT a separate repo — it is the next generation of
  **microsoft/magentic-ui** (PyPI `magentic_ui`, MIT), living on `main` (old
  0.1 AutoGen line on branch `magentic-ui-0.1`). Repo description: "an
  experimental agent that works across the browser and local file system".
- **What it is**: small-model/harness co-designed agentic application
  (Microsoft Research AI Frontiers, blog May 2026): step-by-step incremental
  planning; active context management (curating/condensing what small models
  see); delegation to subagents; recovery; human-in-the-loop pauses;
  Quicksand QEMU-based sandboxed execution.
- **Models**: MagenticBrain ~14B (SFT+RL from Qwen3-14B, 32K ctx, MIT) +
  Fara1.5-9B (from Qwen3.5-9B, 262K ctx, vision-only, MIT). **No 1–3B
  model** — "small" here means 9–14B. Other Fara sizes unverified beyond a
  blog sentence.
- **Maintenance**: active (pushed 2026-11-16, ~10.1k stars); release v0.2.1
  (2026-05-21), PyPI 0.2.2 (2026-07-21), Python >= 3.12.
- **Windows**: PARTIAL — supported on Windows x64 **via WSL2 only** (QEMU/KVM
  sandbox); macOS ARM64 native. Endpoints: any OpenAI-compatible
  `/v1/chat/completions` (VERIFIED protocol-compatible); llama.cpp
  undocumented as a hosting path; documented hosting assumes vLLM-class GPUs
  (48–96 GB).
- **Commercial**: MIT code + MIT weights; research-grade caveats (Fara card:
  commercial use without additional testing out of scope).
- **Relation**: successor of Magentic-UI (app), not Magentic-One (pattern);
  0.2 is NOT built on AutoGen/Agent Framework. Magentic-One continues as
  "Magentic orchestration" in Microsoft Agent Framework
  (`agent-framework` PyPI 1.26.0, MIT).
- **Footprint**: 27 base deps — a full web-app stack (playwright, fastapi,
  sqlmodel, quick-sandbox, ...), not an embeddable library.

## SUBJECT 2 — Established agentic SDKs (all VERIFIED)

| SDK | License | Latest | Base deps | Local/OpenAI-compatible | Notes |
|---|---|---|---|---|---|
| Pydantic AI (`pydantic-ai-slim`) | MIT | 2.76.0 (2026-11-27) | 9 | first-class `OpenAICompatibleProvider`, VLLM, Ollama; model profiles for weak backends | richest retry architecture (9 documented layers); typed tools + validated structured output |
| LangGraph | MIT | 1.2.24 | 6 | no model client at all (model-agnostic) | durable execution, interrupts, checkpointing; pulls langchain-core |
| OpenAI Agents SDK | MIT | 0.26.0 | 14 | `set_default_openai_client(base_url=...)`; tracing must be disabled w/o OpenAI key | guardrails, sessions, handoffs; native-Windows documented |
| Google ADK | Apache-2.0 | 2.15.1 | 24 (heaviest; fastapi/uvicorn/google-auth/graphviz) | Ollama/vLLM/LiteLLM connectors | workflow agents, callbacks, eval suite |
| smolagents | Apache-2.0 | 1.26.0 | 6 | **dedicated `LlamaCppModel`** + Transformers/Ollama/LiteLLM | CodeAgent (actions as code) — SLM-relevant; local executor "not a security boundary" |
| PocketFlow | MIT | 0.0.3 | **0** | bring-your-own client | 99 lines total; Node/Flow with max_retries/wait/exec_fallback; no typed tools |
| DSPy | MIT | 3.5.0 | 14 | quickstart uses `ollama_chat/llama3.2:1b` (explicit 1B) | Signatures + optimizers (GEPA); **LLM-judge designed-in for offline tuning** |

### Ranked reuse recommendation (commercial, offline-first, minimal footprint, Windows + local server)

1. **PocketFlow** — the skeleton: 99 lines, 0 deps, MIT, pure Python;
   graph/conditional/batch/async + per-node retry with fallback already
   present. Forkable at trivial cost.
2. **Pydantic AI (slim)** — the typed interface layer: schema-validated tools
   and structured output with correction retries, nine-layer retry model,
   OpenAI-compatible provider with weak-backend profiles — exactly the
   small-model failure surface. 9 deps, daily-active.
3. **smolagents** — SLM agent-loop patterns + the only first-class
   `LlamaCppModel`; CodeAgent design; keep its executor behind our sandbox.

Runners-up: LangGraph (durability, but langchain-core tree), DSPy (offline
optimizer with 1B quickstart, but judge-dependent + 14 deps; build-time not
runtime), OpenAI Agents SDK (OpenAI-first defaults), Google ADK (footprint).

### Relevance to IJ-NANO architecture

- Layer A execution integrity maps cleanly onto PocketFlow's Node
  retry/fallback + our authoritative BudgetController/gateway.
- Layer B typed tools/structured output: adopt Pydantic AI patterns
  (validation-retry) rather than reinventing; evaluate `pydantic-ai-slim`
  as the typed layer in N04/E-arm comparisons.
- M04 dynamic constraints: XGrammar-2 `triggered_tags` is the reference
  design (see R02/R08 report); llama.cpp b12359 supports per-request
  grammar/json_schema only.
