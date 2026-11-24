# IJ-0.7 JobBot architecture decision record

Keep the SQLite Gateway as the execution boundary. It validates exact typed
arguments, caller and resource scope, workflow state and separately trusted
confirmation. Establish a direct fail-closed path for malformed requests,
uncertain outcomes and interrupted writes. Both development and qualification
must keep model proposals, tool outcomes, state transitions and the final
answer available for audit.

| Tier | Admission and route | Recovery and present evidence |
|---|---|---|
| 0. Deterministic rule | Structured input identifies the allowed operation and provides required typed fields. Use the same authorization and confirmation path. | Defer missing fields to clarification. The 3-case IJ-0.6 structured delivery-note rehearsal supports the local path in those fixtures. Operational coverage is unmeasured. |
| 1. Intent and field extraction | Small model proposes an intent and identifiers. Verify against schema and trusted records before selecting a workflow. | Ask for any absent or conflicting value. IJ-0.6 reported 3/3 correct draft or escalation cases on the defined development input. |
| 2. Native tool planning | Allow a tested small model to choose read-only tools within an approved task budget and enumerated resources. | Stop on undefined arguments, contradictory results, or misleading completion. The archived and fresh history includes improper tags and wrong entity attribution. More complex planning awaits the independent suite. |
| 3. Job knowledge and skill | Allow a versioned domain skill to retrieve policy and scoped records. Measure the incremental benefit on paired cases. | Escalate on missing evidence or policy conflict. JOB-V1 has authored oracle coverage and zero measured full-arm comparisons as of the freeze. |
| 4. SOP-controlled execution | For approved mutations, run the deterministic dependency graph, independently verify the effect and require human confirmation. | Keep idempotency and restore paths. Synthetic Gateway and draft tests validate software controls within their scope. |
| 5. Stronger model or human review | Route unresolved, high-risk, or long-chain tasks to an explicitly qualified local model or a human owner. | Record the transfer and remaining state. The 8B model supplies a comparable reference only after a complete matched evaluation. |

Radeon resource data from the pinned Q8_0 history supports engineering sizing
for that Windows configuration. The MiniCPM5 Q8_0 file is 2.68 GB before
runtime overhead. The 8,192-token FP16 KV estimate is 336 MiB. Re-estimate
context, concurrency, cache and quantization for each backend and task tier.
Coverage percentages and production budgets require independent user-facing
tasks and sampled workload distributions. [Historical replay](IJ07_HISTORICAL_REPRODUCTION.md)
 · [DX-M2 requirements](../portability/deepx-dxm2/IJ07_DEPLOYMENT_REQUIREMENTS.md)
