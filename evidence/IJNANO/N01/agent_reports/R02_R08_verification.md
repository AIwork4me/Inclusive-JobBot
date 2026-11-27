# N01 primary-source verification — R02 PTC-Decoder, R08 constrained decoding infrastructure

- Verification agent report, 2026-11-27 (GitHub API, arXiv, HF, crates.io/PyPI; no cloning/execution)
- Status: agent-verified; to be folded into the landscape reports

## SUBJECT 1 — PTC-Decoder — VERIFIED

| Item | Verified value |
|---|---|
| Repo | https://github.com/yuminghui/llm-tool-constrained-decoder — MIT (code) + CC BY 4.0 (benchmark data addendum); single author, 3 stars, dormant since 2026-07-19 |
| Paper | arXiv:2609.30836 "PTC-Decoder: Towards Intelligent SLMs on Offline Resource-Constrained Edge Devices", v1 2026-09-25, preprint, no venue; Yu, Mu, Wu; paper text CC BY-NC-SA |
| Models | 7 SLMs all ≤2B incl. **Qwen3.5-2B (mission expectation CONFIRMED)**, Qwen3-1.7B, Qwen3-0.6B, Qwen3.5-0.8B, gemma-3-1b-it, gemma-4-E2B-it (2.3B effective dense PLE — repo mislabels "2.0B MoE"), DeepSeek-R1-Distill-Qwen-1.5B |
| Mechanisms | ALL in code: Plan-to-Act (forced first `plan` tool call), HF LogitsProcessor masking DFA-unacceptable tokens + forced EOS at accept + PAD mask, char_fsm NFA→DFA, per-step dynamic constraints, json_schema_to_fsm (can constrain arguments structurally — the paper's evaluated config constrains tool names only, params free: paper/code scope divergence, code ≥ paper) |
| Implementation | Pure HuggingFace transformers (torch 2.12, transformers 5.8.1) — NOT llama.cpp/GBNF; no adapter exists; conceptually portable to llama.cpp sampler chain / json_schema per-request |
| Edge claims | Jetson Orin NX 16GB, Ubuntu 22.04, CUDA 12.2; remote-sensing concurrent workload |
| Results | Own 200-task expert-annotated remote-sensing benchmark + ToolAlpaca/Seal-Tools/API-Bank. LLM-judge (DeepSeek-V4-flash): mean Overall +1.21 (p<0.01, CI [+1.13,+1.29]); weakest model +350%; Qwen3-1.7B +48%; best Overall 3.12 (Qwen3.5-2B); external F1 38→53/33→68/31→50; ablation remove-TC −0.99; **token overhead 2.07x**; Qwen3-1.7B counterexample (F1 0.355 → 0.292 constrained) |
| LLM judge | YES — DeepSeek-V4-flash 0–5 scales, 20 samples human double-checked |
| Gains | Runtime-only (training-free, zero weight changes) |
| Windows | Plausible but untested (pure Python; bitsandbytes Linux-first history) |
| Red flags | arXiv-only; dormant repo; judge availability dependency; admitted negative case; 2.07x token overhead |

## SUBJECT 2 — Constrained decoding infrastructure

### llama.cpp — VERIFIED (MIT)
- Current landscape: stable **v1.1.0 (2026-11-26)**, nightly line **b12811**; our pinned engine is **b12359** (v1.0.0) — N02 probes run against b12359.
- APIs: request fields `grammar` + `json_schema` (both endpoints), `response_format` incl. wrapper `{"type":"json_schema","json_schema":{name,strict,schema}}`; `tools` + `tool_choice` auto/any/named (named since v1.1.0) with `--jinja`; MCP stdio servers.
- Dynamic/state-dependent: grammar is per-request; mid-generation switching exists internally via grammar triggers in tool-call parsers; v1.1.0 added lazy grammar + out-of-range trigger rejection. **No public per-token grammar-change API** — dynamic behavior confined to built-in chat/tool-call paths (important for M04 design: state-dependent constraints must use per-request regeneration or structural-tag approaches).
- LLGuidance integrated but optional (`LLAMA_LLGUIDANCE`, default OFF).

### LLGuidance — VERIFIED (MIT, Microsoft-backed)
- v1.9.1 (crate + PyPI), active (2026-11-18). Token-trie traversal: constraints defined on characters, applied at exact token boundaries. ~50 µs/token mask, full JSON-schema mask ~1.5 ms, cheap per-request grammar creation.
- JSON-schema coverage: oneOf 68%, allOf 98%, pattern 99% (no lookarounds), format 74%; no external $ref; lenient mode. Windows wheels unverified.

### XGrammar — VERIFIED (Apache-2.0)
- v0.2.9 (2026-11-09), active. Default structured backend for vLLM/SGLang/TensorRT-LLM/MLC-LLM. Native Windows wheels (win_amd64/arm64).
- **XGrammar-2** (May 2026; ACM paper DOI 10.1145/3786335.3813124): Structural Tag DSL with `triggered_tags` (free text until trigger, then structure — i.e. mid-generation state-dependent switching by markers), cross-grammar cache (~50% reuse @ 50 tools), repetition compression 100x, up to 80x compilation speedup, batching + speculative decoding support, fork/rollback states.
- v0.x compile-time token-mask precompute can cost seconds-to-minutes; v0.2.9 added opt-in JIT compilation.

## Cross-subject note for IJ-NANO

PTC-Decoder is transformers-only and cannot be reused with llama.cpp directly;
its DFA+mask+forced-EOS design must be re-expressed via llama.cpp per-request
`json_schema`/`grammar` fields (or XGrammar-2 structural tags if we move
beyond llama.cpp). For M04 (dynamic constrained decoder) on b12359/Vulkan:
per-request grammar regeneration is the supported mechanism; XGrammar-2's
triggered_tags is the reference design for state-dependent constraints.
