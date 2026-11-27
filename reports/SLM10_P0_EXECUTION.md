# IJ-SLM-1.0 P0 execution evidence

## Physical controls

| Candidate | SDK AG-04, observer on | SDK AG-12, observer on | SDK AG-04, observer off | TC-V3 development |
|---|---|---|---|---|
| MiniCPM5-2B | PASS | PASS | PASS | 9 trajectories, 24 native requests |
| LFM3-1.7B | PASS | PASS | PASS | 9 trajectories, 23 native requests |
| Qwen3.5-2B | FAIL | PASS | PASS | 9 trajectories, 24 native requests |

All three candidates recorded actual Radeon activity and live SDK callbacks for both TC-V3 SDK development tracks. The Direct runtime, the SDK with a provider JSON response, and the SDK with provider SSE each ran the same three development cases. The provider-JSON arm adapts a validated JSON completion to SSE for the real SDK consumer and captures both wire representations. Native provider SSE stays distinct.

The native observer records the actual rendered prompt, input token IDs, sampled token IDs, sampled bytes and final pre-parser bytes without requesting extra fields in the provider response. The private capture retains the original tokens. The portable copy omits prompt token IDs because local SDK prompts can include private paths. It binds the local originals by digest. The initial incremental observer package failed the properties probe with HTTP 500. A full rebuild of the server translation units recovered the live controls. [Physical evidence manifest](../evidence/IJSLM/p0/manifest.json)

## Root-cause evidence

- **MiniCPM5 Direct native tools.** Both Direct modes proposed the expected tool on the historical balance prompt when replayed with the pinned candidate and observer build. Replaying the actual AG-04 SDK request with controlled Direct decoding also produced the expected first lookup in both modes. The balance prompt and SDK order workflow differ. The historical failure and SDK capability gain remain UNVERIFIED.
- **Qwen3.5 AG-02.** One physical pilot retained 575,276 raw bytes from a 200 SSE reply ending with provider stop. The boundary raised GatewayError when event payloads exceeded the 512 KiB aggregate limit. Decoding the exact capture with the 1 MiB diagnostic aggregate accepted the response. Per-frame, terminal and tool validations stayed in force. Independent real SDK reruns passed with both configured budgets, with 55,107 bytes on the original limit and 25,775 bytes on the revised limit. The historical ValueError had no response capture and remains UNVERIFIED.
- **Qwen3.5 observation control.** With observation enabled, AG-04 ran both requested tools and then produced an empty terminal reply before proposing another tool on SDK retry. That run failed the original probe. The observer-off run passed. The baseline SDK reports have no fixed decoding seed. These observations leave the SDK behavior equivalence question open. The fixed-seed Direct controls remain in the manifest.
- **Planning boundary.** The 24 historical trajectories remain initial-plan diagnostics. A new LFM3 Radeon development runner sent a later user update in the same real SDK conversation. The first Acting-first runs produced markup as prose because the SDK provider request selected no tools. Explicit auto selection during execution recovered five real callbacks in each of the Native and SOP-assisted Acting-first runs. Each used the cache fallback and retained rejected out-of-scope calls. Neither completed the task. The Plan-first proposals failed schema or reference checks before execution. [Planning development seals](../evidence/IJSLM/planning-development/manifest.json)

## Scoped mechanical qualification

The registry binds source, evaluation contract, benchmark version, task families, workflows, dimensions, risks and required exhibits for each verifier. Nine components passed the synthetic independent witnesses, legal alternatives and component-specific held-out controls. Credentials apply to the frozen TC-V3 task contract. Native parser semantics, persisted state, conditional planning and D25 remain BLOCKED. Authorization covers denied release in the synthetic environment. [Registry](../atlas/slm/v1.0/mechanical_qualification_registry.json) · [Software qualification report](../evidence/IJSLM/qualification/tc-v3-mechanical.json)

The queue publishes assessment and execution counts from verified trial seals. It reserves each trial before sending any model request and retains interrupted reservations for reconciliation. Each hardware session binds its source, GPU launch, runtime, SDK, model, dataset, evaluator and evidence hashes. AG-11 remains BLOCKED. The three candidate preflights exercised only synthetic local scenarios. [TC-V3 freeze](../atlas/slm/v1.0/tc-v3/manifest.json)

## Formal physical progress

The seal-derived dashboard reports execution and assessment separately by candidate. It contains scoped component, SDK/Direct pairing, repeat, language, token and provider latency measurements. Early observations cover only the task families already sealed. The dashboard reports a separate strict end-to-end state and retains every failed or blocked observation. [Physical progress](../atlas/slm/v1.0/physical_progress.md) · [Formal session manifests](../evidence/IJSLM/tc-v3/)
