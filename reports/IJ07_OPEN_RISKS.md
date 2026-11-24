# IJ-0.7 remaining qualification risks

| Scope | Gate | Required evidence |
|---|---|---|
| Historical business effect | G2 | V1 reproductions use in-memory tools and synthetic receipts. Database, confirmed writes, and SDK callbacks need a stateful run with explicit business inputs. |
| Independent full tests | G4–G6 | Complete the 500-case TC-V2 on both backends, the 600-case multi-tool suite and 800-case L0–L7 with both tracks. Keep strict independent adjudication and full planned denominator. |
| Causal closure | G7–G8 | Evaluate each failure at adjacent request and source layers. Investigate schema, prompt, precision and sampling contributions. Keep pre-fix and patched configurations distinct. |
| SDK qualification | G9 | Repeat AG-06 with paired structured output and preserved SDK/model messages. AG-11 needs complete trusted observation or isolation for the full SDK process tree. |
| Competitive comparisons | G10–G11 | Use first trials on the exact same case roster and shared declared budgets, plus the frozen repeated panels. |
| JobBot execution | G12 | Run JOB-V1 A–F with the same unstructured input, policy, budget and persisted state expectations. Quantify knowledge, specialized schema and SOP effects. |
| Deployment | G13 | Repeat controlled backend and quantization measurements with TTFT, concurrency and peak memory. Physical energy and soak remain pending owner equipment and awake-window constraints. DX-M2 hardware is unavailable. |

The repository publishes synthetic records and hashes. Local source logs, raw
process paths, downloaded weights and engine binaries stay under ignored
directories. [Machine-owner blockers](../BLOCKERS.md)
