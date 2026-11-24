# IJ-0.7 remaining qualification risks

| Scope | Gate | Required evidence |
|---|---|---|
| Historical business effect | G2 | V1 reproductions use in-memory tools and synthetic receipts. Database, confirmed writes, and SDK callbacks need a stateful run with explicit business inputs. |
| Independent full tests | G4–G6 | Both TC-V2 backend profiles failed. MULTITOOL first attempts passed 129/600 with the original wire limit. Complete the L0–L7 paired tracks and isolate any gains in the separate corrected multi-tool profile. |
| Causal closure | G7–G8 | Evaluate each failure at adjacent request and source layers. Investigate schema, prompt, precision and sampling contributions. Keep pre-fix and patched configurations distinct. |
| SDK qualification | G9 | Repeat AG-06 with paired structured output and preserved SDK/model messages. AG-11 needs complete trusted observation or isolation for the full SDK process tree. |
| Competitive comparisons | G10–G11 | Run the B/D/F/G TC-V2 batch runner on the frozen roster with shared declared budgets, then complete the matched multi-tool, planning and repeat panels. [Runbook](../benchmarks/competitive_slm/TC_V2_BATCH.md) |
| JobBot execution | G12 | Arm F is complete below the 99% target. Run JOB-V1 A–E on the same input, policy, budget and persisted state expectations. Quantify knowledge, specialized schema and SOP effects. [Model treatments](../benchmarks/job_productivity_v1/holdout/MODEL_ARMS.md) |
| Deployment | G13 | Repeat controlled backend and quantization measurements with TTFT, concurrency and peak memory. Physical energy and soak remain pending owner equipment and awake-window constraints. DX-M2 hardware is unavailable. |

The repository publishes synthetic records and hashes. Local source logs, raw
process paths, downloaded weights and engine binaries stay under ignored
directories. [Machine-owner blockers](../BLOCKERS.md)
