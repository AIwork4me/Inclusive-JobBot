# IJ-NANO-1.0 — N01 Open-Source Reuse Decision (Component-Level, Provisional)

- Generated: 2026-11-27 (N01)
- Scope: the component-level reuse disposition required by mission order §2
  ("Make a component-level reuse decision rather than choosing an entire SDK
  prematurely") for the six components named in mission order §7: graph
  orchestration, schema validation, model transport, grammar construction,
  event persistence, state management.
- Grounding: every row cites the `reuse_class` value recorded in
  `evidence/IJNANO/N01/research_catalog.json` (quoted verbatim, never
  upgraded) and its verification sweep in
  `evidence/IJNANO/N01/agent_reports/`. No whole-SDK selection is made here.
- Status vocabulary: subject verification VERIFIED / PARTIALLY_VERIFIED
  preserved verbatim; execution statuses PASS / FAIL / BLOCKED / NOT_RUN —
  all candidate validations referenced below are **NOT_RUN in N01** (no
  subject code was cloned or executed), except the llama.cpp b12359 engine
  behaviors already PASS-recorded by the N02 probes.
- License gates applied up front: Meta-Harness TB2 artifact is UNLICENSED
  (excluded from any reuse); PTC-Decoder paper text is CC BY-NC-SA (mechanism
  study only, via clean-room reimplementation of the MIT code's mechanism);
  LFM3-1.7B weights are revenue-conditioned under the LFM Open License v1.0 —
  research use unaffected (IJN-B-003).

## 1. Decision rules (preamble)

Ten factors govern every disposition, with **no ranking among them**:

1. Native functionality fit.
2. Required custom code.
3. Dependency footprint.
4. Initialization cost.
5. Observability.
6. Security.
7. Maintenance effort.
8. Commercial licensing.
9. Local Windows compatibility.
10. Model-specific adaptation effort.

**Minimal dependency footprint is one factor among these ten — it is not a
ranking and not a proxy for total engineering cost.** Mission order §2
requires this to be stated explicitly: PocketFlow's small dependency
footprint is useful, but a framework requiring substantial custom
orchestration may have a higher total engineering cost. A near-zero-dependency
skeleton shifts model transport, typed validation, retry semantics and
observability onto mission-owned code that must be specified, tested and
hardened like any other component (N06A-R defect classes). Each disposition
below is therefore justified on the ten axes, never on dependency count
alone.

Additional rules:

- **Component-level only.** A disposition binds one component (e.g. schema
  validation), never an entire SDK. Adopting a pattern or adapter from a
  framework does not adopt the framework.
- **Evidence-bound.** Dispositions may not rest on unrecorded properties;
  where the sweep recorded nothing ("not recorded"), that is stated.
- **No premature binding.** Mission order §0/§2: do not finalize
  model-specific execution policies before measuring the cognitive
  capabilities that justify those policies. Final binding decisions that
  depend on N03 measured capabilities are explicitly deferred; this document
  records, per component: the candidate, the evidence, and **what measurement
  would change the decision**.
- **No heavier framework to maximize feature count** (mission order §7).

## 2. Component decision table

| # | Component | Candidate(s) and catalog `reuse_class` (verbatim) | Evidence basis | Provisional disposition (N01) | Deferred binding — what measurement changes it |
|---|---|---|---|---|---|
| 1 | Graph orchestration | **PocketFlow — REUSE_DIRECTLY (skeleton candidate)**; MIT; 0.0.3; 0 deps; 99 lines; Node/Flow with `max_retries`/`wait`/`exec_fallback`; graph/conditional/batch/async. Set aside: LangGraph — TECHNICALLY_UNSUITABLE_FOR_MINIMAL (dependency tree: 6 deps + langchain-core); its durable execution/checkpoints noted but out of minimal scope | R09 sweep (`agent_reports/R07_R09_verification.md`); commercial MIT clean; pure-Python Windows verified in catalog cross-cutting list | Fork PocketFlow as the Layer A skeleton at trivial cost; keep Layer C conditional-action-graph semantics mission-native on top of it; no state management is inherited (PocketFlow ships none) | N03 capability curves for planning depth, conditional branching, and stop-vs-continue: if measured SLMs require orchestration guarantees beyond Node/Flow primitives, the Layer C graph is specified first and the PocketFlow fork is re-scoped before any binding |
| 2 | Schema validation | **pydantic-ai-slim — REUSE_WITH_ADAPTER (typed layer candidate)**; MIT; 2.76.0; 9 deps; typed tools, validated structured output, 9 documented retry layers, `OpenAICompatibleProvider` with weak-backend profiles. Alternative in-house: the existing limited validator under NA-D08 audit | R09 sweep; weak-backend model profiles target exactly the small-model failure surface; Windows wheels verified | Evaluate `pydantic-ai-slim` as the typed layer in N04/E-arm comparisons behind an adapter boundary; NA-D08 verifies the actual schema subset of the in-house validator and rejects unsupported schemas at registration time | N03 slot-extraction / structured-action failure classes (which semantic constraints SLM outputs actually violate) + NA-D08 schema-subset verification decide whether a trusted standard validator is admitted or the in-house subset suffices |
| 3 | Model transport | **llama.cpp b12359 — REUSE_DIRECTLY (pinned b12359; N02 probe evidence)**; MIT; per-request `grammar` + `json_schema` on both endpoints, `response_format` json_schema wrapper, `tools` + `tool_choice` auto/any/named (named since v1.1.0, `--jinja`), MCP stdio. Patterns: **smolagents — REUSE_WITH_ADAPTER (model client + loop patterns)**; Apache-2.0; 1.26.0; only surveyed SDK with a first-class `LlamaCppModel` | R08/R09 sweeps; N02 probe evidence (engine identity and API surface PASS-recorded); engine caveat: b12359 rejects backslash-escaped-quote GBNF literals, use `["]` char classes | llama.cpp (pinned b12359) remains the sole model transport; adopt smolagents `LlamaCppModel` client/loop patterns through an adapter, not the SDK wholesale; executor never treated as a security boundary | N02R protocol arms A0–A7 (chat vs completion vs native tool-call causal results) and N03 protocol-sensitivity curves set the per-model default transport policy; a model profile may pin different request paths per capability, which changes the adapter, not the engine |
| 4 | Grammar construction | **llama.cpp b12359 GBNF + json_schema — REUSE_DIRECTLY (pinned)**; **XGrammar — REUSE_WITH_ADAPTER_CANDIDATE** (reference design for M04 if llama.cpp-native path insufficient; Apache-2.0; v0.2.9; native Windows wheels; XGrammar-2 `triggered_tags` = mid-generation state-dependent switching); **LLGuidance — UNVERIFIED_FOR_WINDOWS** (no win wheels confirmed; llama.cpp integration optional, default OFF); mechanism source: **PTC-Decoder — REIMPLEMENT_CLEAN_ROOM** (Plan-to-Act + per-tool DFA constraints re-expressed via llama.cpp per-request json_schema/grammar; transformers-only, no adapter exists) | R08 sweep (`agent_reports/R02_R08_verification.md`) + R02 sweep; engine constraints recorded: no public per-token grammar-change API — dynamic constraints must use per-request regeneration or structural-tag approaches; XGrammar v0.x compile-time precompute can cost seconds-to-minutes (v0.2.9 opt-in JIT) | Build grammar construction on llama.cpp per-request `json_schema`/`grammar` (GBNF authored with `["]` char classes); treat XGrammar-2 `triggered_tags` as the reference design for M04 dynamic constraints; keep LLGuidance unpinned until Windows wheels are confirmed; implement the PTC-Decoder mechanism clean-room for the M04 arm | N03 family "grammar-constrained action selection" + M04 state-dependency requirements decide whether per-request regeneration suffices on llama.cpp or an XGrammar adapter is actually built; LLGuidance re-enters only with verified Windows wheels |
| 5 | Event persistence | No third-party candidate carries a REUSE class in the catalog. Nearest recorded: LangGraph durable execution/checkpoints — TECHNICALLY_UNSUITABLE_FOR_MINIMAL (dependency tree) | R09 sweep; absence of a qualified candidate is itself the recorded finding | Mission-native append-only EventLog with the hardened canonical integrity envelope (NA-D02: envelope must cover trial/event/parent identity, sequence, timestamp, stage, kind, payload, previous hash; sealed evidence bound to an external manifest — a hash chain alone is not proof against a chain-rewriting adversary) | NA-D02/NA-D03 hardening and recovery results; only measured volume/performance pressure from the 3,600-slot pilot could reopen a store decision — no N03 cognitive result bears on this row |
| 6 | State management | No third-party candidate; PocketFlow intentionally ships none (bring-your-own store); MagenticLite's stack is RESEARCH_ONLY and not embeddable | R09/R07 sweeps | Mission-native transactional gateway per NA-D01: nested-aliasing repair, regression tests for nested dicts/lists, handler exception, cancellation, invalid commit, concurrent writes; durable transactional storage investigation for persistent job worlds | NA-D01 outcome plus persistent job-world requirements from N06B/C; measured N03 capability results do not change this row (it is an integrity component, not a capability-driven one) |

## 3. Research-only subjects (explicitly not component reuse)

| Subject | `reuse_class` (verbatim) | Role |
|---|---|---|
| effGen | RESEARCH_ONLY_FOR_REPRODUCTION (E01); mechanism study, not component reuse (footprint contradicts minimal-runtime thesis) | Comparator arm A9/E01 via its verified official implementation and native local model interface; ~52-dep footprint bars embedding |
| TinyAgent | RESEARCH_ONLY (weight-change headline not transferable; ToolRAG mechanism study for M02) | ToolRAG-style retrieval arm with frozen weights; gains from its LoRA weights must not be attributed to runtime mechanisms |
| slm-harness-adaptation | RESEARCH_ONLY (methodology for N10 optimizer design; O0–O5 comparators) | Optimizer methodology; 3–8B-active MoE results are not 1–3B-total evidence |
| Growing Harness | RESEARCH_ONLY (principle: compile repeated control decisions into deterministic code = M-mechanism 'Growing Harness' arm E06) | Principle only; paper has no code and needs proprietary optimizers |
| Meta-Harness | RESEARCH_ONLY (N10 optimizer methodology: raw-trace feedback > score-only feedback ablation is directly actionable) | Methodology only; TB2 artifact is UNLICENSED and excluded from reuse |
| MagenticLite | RESEARCH_ONLY (design-pattern reference for Layer B/C; not embeddable) | Design reference for incremental planning / context management / delegation / HITL; 27-dep web-app stack; WSL2-only |
| OpenAI Agents SDK | RESEARCH_ONLY (B-arm comparator) | B-arm comparator; OpenAI-first defaults; tracing must be disabled |
| DSPy | RESEARCH_ONLY (N10 optimizer comparator) | Offline optimizer comparator; LLM judge is build-time only, never runtime; 1B quickstart noted |
| Google ADK | TECHNICALLY_UNSUITABLE_FOR_MINIMAL | 24 base deps, heaviest surveyed |

## 4. Deferral record

Final binding for rows 1–4 is **deferred to N03 measured capabilities** per
mission order §0 ("Do not finalize model-specific execution policies before
measuring the cognitive capabilities that justify those policies") and §7
("Use N01 findings and measured N03 requirements to decide whether to reuse
or implement"). The measurements that can change each row:

| Measurement | Producing phase | Rows it can change |
|---|---|---|
| Protocol arms A0–A7 causal results (chat/completion/native tool-call, JSON Schema, GBNF, Action DSL, enumerated action) | N02R | 3 (transport default policy), 4 (grammar surface) |
| Twelve priority cognitive families (enumerated action selection, native tool-name selection, grammar-constrained action selection, compact DSL, slot extraction, entity resolution, context interference, tool inventory sensitivity, error recognition, invalid argument recovery, stop-vs-continue, conditional branching) | N03 | 1 (orchestration scope), 2 (validation subset), 4 (grammar mechanism sufficiency) |
| Schema-subset verification and unsupported-schema rejection behavior | N06A-R (NA-D08) | 2 |
| Transaction isolation, evidence and checkpoint integrity results | N06A-R (NA-D01/D02/D03) | 5, 6 (confirm mission-native path or reopen store search) |
| M04 state-dependent constraint requirements | N04 mechanism work | 4 (XGrammar adapter build/no-build) |

No row may be cited as a final architecture commitment before the producing
phase records its result; until then each disposition above is the recorded
candidate + evidence, per mission order §2's requirement that this be a
component-level decision record rather than a premature SDK choice.

## 5. Verdict

`N01_RESEARCH_LANDSCAPE_VERIFIED` (documentation scope): the component-level
reuse decision is recorded — PocketFlow skeleton (fork), pydantic-ai-slim
typed layer (adapter evaluation), llama.cpp b12359 pinned transport and
grammar surface, XGrammar as M04 reference design, mission-native event
persistence and state management — with every disposition grounded in the
catalog's `reuse_class` values and all capability-dependent bindings
explicitly deferred to N03. All candidate-specific runtime validations
remain NOT_RUN as of N01.
