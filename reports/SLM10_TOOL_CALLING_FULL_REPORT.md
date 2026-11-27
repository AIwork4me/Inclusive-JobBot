# IJ-SLM-1.0 Tool Calling capability map

The current replay covers 4,950 of the 4,950 priority Radeon attempts and 6,210 of the 8,250 five-model TC-V3 attempts. The remaining core allocation is 30,340 of 36,550. The original strict TC-V3 verdict is BLOCKED on all 6,210 sealed attempts. The priority cohort is complete. This snapshot includes 1,260 F trials following its independent admission. G remains NOT_RUN. [Formal dashboard](../atlas/slm/v1.0/physical_progress.md) · [Five-model passports](../atlas/slm/v1.0/tc-capability-passports.json) · [F/G admission evidence](../evidence/IJSLM/tc-v3-admissions/manifest.json)

The five-model baseline also includes planned and observed denominators by model, track, task family, language and risk. Missing slot status, streaming verdict agreement and repeat-level reliability are recorded separately. [Five-model capability matrix](../atlas/slm/v1.0/tc-five-model-report.json)

## Native, SDK, and specialization

Each baseline row uses the matched first-attempt snapshot for the model and track. Metric entries report passes over observed PASS plus FAIL trials. The machine-readable matrix retains separate BLOCKED and NOT_RUN counts. A fact proof requires a scoped synthetic read, an exact business value, and source-linked delivery of what the model needed to answer. [Metric definitions and counts](../atlas/slm/v1.0/tc-capability-matrix.json)

| Model | First-attempt path | First tool choice | Business facts | Output contract | Verified execution | Scoped completion |
|---|---|---:|---:|---:|---:|---:|
| MiniCPM5-2B | Direct | 483/500 | 372/372 | 474/500 | 472/500 | 372/400 |
| MiniCPM5-2B | SDK provider JSON | 449/500 | 207/217 | 184/500 | 117/500 | 2/400 |
| MiniCPM5-2B | SDK provider SSE | 449/500 | 210/222 | 188/500 | 116/500 | 2/400 |
| LFM3-1.7B | Direct | 482/500 | 372/373 | 476/494 | 455/494 | 361/400 |
| LFM3-1.7B | SDK provider JSON | 491/500 | 312/328 | 398/500 | 357/500 | 218/400 |
| LFM3-1.7B | SDK provider SSE | 493/500 | 314/331 | 402/500 | 359/500 | 220/400 |
| Qwen3.5-2B | Direct | 463/500 | 394/394 | 300/500 | 462/500 | 272/400 |
| Qwen3.5-2B | SDK provider JSON | 449/500 | 316/354 | 85/500 | 443/500 | 80/400 |
| Qwen3.5-2B | SDK provider SSE | 449/500 | 316/356 | 81/500 | 442/500 | 78/400 |
| Ministral-3-3B-Instruct | Direct | 359/381 | 313/317 | 69/381 | 345/381 | 39/331 |
| Ministral-3-3B-Instruct | SDK provider JSON | 346/381 | 221/280 | 0/378 | 298/379 | 0/329 |
| Ministral-3-3B-Instruct | SDK provider SSE | 346/381 | 221/283 | 0/381 | 301/381 | 0/331 |
| Gemma-4-E2B-it | All tracks | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |

- **MiniCPM5-2B** shows strong Direct first-tool selection and scoped completion in the observed cohort. In the SDK single-tool slice, 36 of 50 trials repeated a model proposal and executed the same action again. The historical guard suppressed callbacks in controlled read-only development tasks. Action State and termination remain hypotheses for native repeat and stop behavior. Host-protected callbacks have independent attribution. [Loss analysis](SLM10_SDK_CAPABILITY_LOSS_ROOT_CAUSE.md)
- **LFM3-1.7B** follows the first tool choice in both paths, with later argument and termination problems in SDK traces. Compact serialization returned exact JSON on 23 of 30 development tasks, compared with 19 of 30 SDK controls. Markdown directive removal is a separate next-decision intervention. The matched independent holdout remains NOT_RUN. [A/B evidence](SLM10_SDK_SPECIALIZATION_AB_TEST.md)
- **Qwen3.5-2B** follows the expected executed action on 443 of 500 SDK provider-JSON cases. The output contract passed 85 of 500. The SDK single-tool slice includes 34 exact values inside fences. A host Structured Output Contract can detect that failure. Native structured output and final grammar require new physical evidence before a compensation claim. [Loss analysis](SLM10_SDK_CAPABILITY_LOSS_ROOT_CAUSE.md)
- **Ministral** passed independent Radeon and SDK admission. **Gemma** awaits its admission. Their registered weights and planned slots are available in the frozen roster. Native, SDK and specialized evidence will enter each passport after it seals. [Admission records](../evidence/IJSLM/tc-v3-admissions/manifest.json)

## Resource and deployment scope

The matched Pareto view uses the same model, case and seed on all three first-attempt paths. It compares scoped completion against median provider time and tokens. Session peak GPU memory is recorded alongside the comparison. Whole-task latency, native TTFT, energy and monetary cost require their own measurements. The cost matrix reports tokens, requests and available latency per proved business fact, strict output, verified execution and scoped completion. Every denominator is published separately. Across the full snapshot, 1,713 fenced answers passed business-fact verification and failed the output contract. [Matched Pareto matrix](../atlas/slm/v1.0/tc-quality-resource-pareto.json) · [Cost and evidence denominators](../atlas/slm/v1.0/tc-capability-matrix.json)

No model and adapter combination has role-level qualification. LFM3 with compact results is a candidate for read-only lookup tasks. MiniCPM5's Direct path warrants a separate matched comparison for tool execution roles. Qwen3.5's fact and format split warrants separate validation for structured handoffs. Document Review, Customer Service and Product Data Management need their own physical JOB-V2 comparisons before assignment. [Role hypotheses and risks](SLM10_MODEL_SPECIFIC_ADAPTER_GUIDE.md) · [Adapter controls and limits](SLM10_ADAPTER_QUALIFICATION.md)

## Remaining qualification

| Requirement | Physical or release disposition |
|---|---|
| Frozen TC-V3 | 6,210/8,250 published. D25 stays BLOCKED. |
| A0–A5 causal panel | 513/540 physical observations published, plus 144 SDK and guard controls. Ten slots are BLOCKED and 17 are NOT_RUN. Independent holdout NOT_RUN. |
| Adapter profiles | Six software-tested components. Real matched adapter qualification and factorial selection remain NOT_RUN. |
| SDK Extension | Independent software qualification passed for typed workflows, legal repeats, and producer links. Radeon execution NOT_RUN. |
| MULTITOOL-V2 | 7,500 planned across five models. The balanced 600-case revision passed software replay and follow-up defect probes. Formal dispatch remains BLOCKED. [Candidate manifest](../atlas/slm/v1.0/multitool-v2-candidate-0.3/manifest.json) |
| AGENTIC-PLAN-V2 | 20,800 planned across Plan-first, Acting-first and the SDK repeat panel. The 800-case source candidate replayed 2,300 synthetic worlds. Formal freeze and dispatch remain pending. [Planning roster](../docs/SLM10_PLANNING_ROSTER.md) |
| JOB-V2 and operational envelope | Physical job-role A/B, quantization, context, concurrency, hardware envelope and NPU deployment remain NOT_RUN. [NPU deployment requirements](SLM10_NPU_DEPLOYMENT_REQUIREMENTS.md) |
| Production autonomy | BLOCKED on D25, remaining semantic credentials and audited offline process egress. |

The core reserve is 8,250 TC-V3, 7,500 MULTITOOL-V2 and 20,800 AGENTIC-PLAN-V2 trials. The separate job, specialization, quantization, hardware and NPU experiments contribute zero to that denominator. [Frozen allocation](../atlas/slm/v1.0/execution_plan.json) · [Open gates](../BLOCKERS.md)
