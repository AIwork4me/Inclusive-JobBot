# IJ-SLM-1.0 Tool Calling capability map

The current replay covers 4,014 of the 4,950 priority Radeon attempts and 4,014 of the 8,250 five-model TC-V3 attempts. The remaining core allocation is 32,536 of 36,550. The original strict TC-V3 verdict is BLOCKED on all 4,014 sealed attempts. Admission and dispatch for F and G are pending the priority cohort. [Formal dashboard](../atlas/slm/v1.0/physical_progress.md) · [Five-model passports](../atlas/slm/v1.0/tc-capability-passports.json) · [F/G admission evidence](../evidence/IJSLM/tc-v3-admissions/manifest.json)

## Native, SDK, and specialization

Each baseline row uses the matched first-attempt snapshot for the model and track. Metric entries report passes over observed PASS plus FAIL trials. The machine-readable matrix retains separate BLOCKED and NOT_RUN counts. A fact proof requires a scoped synthetic read, an exact business value, and source-linked delivery of what the model needed to answer. [Metric definitions and counts](../atlas/slm/v1.0/tc-capability-matrix.json)

| Model | First-attempt path | First tool choice | Business facts | Output contract | Verified execution | Scoped completion |
|---|---|---:|---:|---:|---:|---:|
| MiniCPM5-2B | Direct | 410/427 | 349/349 | 401/427 | 399/427 | 349/377 |
| MiniCPM5-2B | SDK provider JSON | 376/427 | 203/213 | 128/427 | 67/427 | 2/377 |
| MiniCPM5-2B | SDK provider SSE | 376/427 | 206/217 | 133/427 | 66/427 | 2/377 |
| LFM3-1.7B | Direct | 388/406 | 336/337 | 400/406 | 376/406 | 326/356 |
| LFM3-1.7B | SDK provider JSON | 397/406 | 278/294 | 348/406 | 266/406 | 196/356 |
| LFM3-1.7B | SDK provider SSE | 399/406 | 279/296 | 346/406 | 270/406 | 197/356 |
| Qwen3.5-2B | Direct | 346/383 | 327/327 | 215/383 | 345/383 | 209/333 |
| Qwen3.5-2B | SDK provider JSON | 332/383 | 249/287 | 76/383 | 326/383 | 74/333 |
| Qwen3.5-2B | SDK provider SSE | 332/383 | 249/289 | 73/383 | 325/383 | 72/333 |
| Ministral-3-3B-Instruct | All tracks | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |
| Gemma-4-E2B-it | All tracks | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |

- **MiniCPM5-2B** shows strong Direct first-tool selection and scoped completion in the observed cohort. In the SDK single-tool slice, 36 of 50 trials repeated a model proposal and executed the same action again. The historical guard suppressed callbacks in controlled read-only development tasks. Action State and termination remain hypotheses for native repeat and stop behavior. Host-protected callbacks have independent attribution. [Loss analysis](SLM10_SDK_CAPABILITY_LOSS_ROOT_CAUSE.md)
- **LFM3-1.7B** follows the first tool choice in both paths, with later argument and termination problems in SDK traces. Compact serialization returned exact JSON on 23 of 30 development tasks, compared with 19 of 30 SDK controls. Markdown directive removal is a separate next-decision intervention. The matched independent holdout remains NOT_RUN. [A/B evidence](SLM10_SDK_SPECIALIZATION_AB_TEST.md)
- **Qwen3.5-2B** follows the expected executed action on 326 of 383 SDK provider-JSON cases. The output contract passed 76 of 383. The SDK single-tool slice includes 34 exact values inside fences. A host Structured Output Contract can detect that failure. Native structured output and final grammar require new physical evidence before a compensation claim. [Loss analysis](SLM10_SDK_CAPABILITY_LOSS_ROOT_CAUSE.md)
- **Ministral and Gemma** require independent Radeon admission. Their registered weights and planned slots are available in the frozen roster. Native, SDK and specialized evidence will enter each passport after it seals. [Admission records](../evidence/IJSLM/tc-v3-admissions/manifest.json)

## Resource and deployment scope

The matched Pareto view uses the same model, case and seed on all three first-attempt paths. It compares scoped completion against median provider time and tokens. Session peak GPU memory is recorded alongside the comparison. Whole-task latency, native TTFT, energy and monetary cost require their own measurements. The cost matrix reports tokens, requests and available latency per proved business fact, strict output, verified execution and scoped completion. Every denominator is published separately. Across the full snapshot, 773 fenced answers passed business-fact verification and failed the output contract. [Matched Pareto matrix](../atlas/slm/v1.0/tc-quality-resource-pareto.json) · [Cost and evidence denominators](../atlas/slm/v1.0/tc-capability-matrix.json)

No model and adapter combination has role-level qualification. LFM3 with compact results is a candidate for read-only lookup tasks. MiniCPM5's Direct path warrants a separate matched comparison for tool execution roles. Qwen3.5's fact and format split warrants separate validation for structured handoffs. Document Review, Customer Service and Product Data Management need their own physical JOB-V2 comparisons before assignment. [Role hypotheses and risks](SLM10_MODEL_SPECIFIC_ADAPTER_GUIDE.md) · [Adapter controls and limits](SLM10_ADAPTER_QUALIFICATION.md)

## Remaining qualification

| Requirement | Physical or release disposition |
|---|---|
| Frozen TC-V3 | 4,014/8,250 published. D25 stays BLOCKED. |
| A0–A5 causal panel | 513/540 physical observations published, plus 144 SDK and guard controls. Ten slots are BLOCKED and 17 are NOT_RUN. Independent holdout NOT_RUN. |
| Adapter profiles | Six software-tested components. Real matched adapter qualification and factorial selection remain NOT_RUN. |
| SDK Extension | Independent software qualification passed for typed workflows, legal repeats, and producer links. Radeon execution NOT_RUN. |
| MULTITOOL-V2 | 7,500 planned across five models. The balanced 600-case revision passed software replay and follow-up defect probes. Formal dispatch remains BLOCKED. [Candidate manifest](../atlas/slm/v1.0/multitool-v2-candidate-0.3/manifest.json) |
| AGENTIC-PLAN-V2 | 20,800 planned across Plan-first, Acting-first and the SDK repeat panel. The 800-case source candidate replayed 2,300 synthetic worlds. Formal freeze and dispatch remain pending. [Planning roster](../docs/SLM10_PLANNING_ROSTER.md) |
| JOB-V2 and operational envelope | Physical job-role A/B, quantization, context, concurrency, hardware envelope and NPU deployment remain NOT_RUN. [NPU deployment requirements](SLM10_NPU_DEPLOYMENT_REQUIREMENTS.md) |
| Production autonomy | BLOCKED on D25, remaining semantic credentials and audited offline process egress. |

The core reserve is 8,250 TC-V3, 7,500 MULTITOOL-V2 and 20,800 AGENTIC-PLAN-V2 trials. The separate job, specialization, quantization, hardware and NPU experiments contribute zero to that denominator. [Frozen allocation](../atlas/slm/v1.0/execution_plan.json) · [Open gates](../BLOCKERS.md)
