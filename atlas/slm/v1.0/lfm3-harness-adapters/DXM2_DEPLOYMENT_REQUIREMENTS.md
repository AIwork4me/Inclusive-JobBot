# LFM3 LoRA deployment requirements for DX-M2

`DX_M2_PHYSICAL_QUALIFICATION = NOT_RUN`.

DEEPX documents DX-M2 pre-optimized artifacts served through DX-LLM and a
DXNN SDK for the device. Public model listings establish an integration
surface. An exact LFM3 compiler target, dynamic LoRA support and a
reproducible LFM3 quantization and export package remain unverified.
[DX-M2](https://deepx.ai/products/dx-m2/) ·
[DXNN SDK](https://deepx.ai/products/dxnn-sdk/)

| Gate | Evidence to collect |
|---|---|
| Compiler identity | Pin board, driver, firmware, DXNN compiler, DX-LLM runtime, host OS and binary SHA256. Record exact import format, operator support and reason for each fallback. |
| LFM3 graph | Inspect short-convolution projections, convolution weights and state, attention and KV operations, the vendor compiler's static/dynamic shape support, and tensor precision across prefill and decode. Prove reset, reordering and session boundaries for recurrent/convolution state and KV cache. |
| Dynamic adapter | Require a supported linear LoRA kernel and measurable adapter placement. Test live reload, request routing, model/adapter hash pairing, concurrent sessions and wrong-adapter rejection. |
| Merged adapter | When dynamic LoRA is unavailable, merge into the pinned BF16/F16 base first. Compare unmerged and merged logits at the same dtype and input. Quantize the merged checkpoint separately. Pin calibration data and converter and build manifests. |
| Transport and policy | Compare native tools, typed arguments, JSON/SSE, parser terminals, callback delivery and cancellation at declared context and concurrency. Keep writes and approvals in the deterministic host policy. Verify separate local and egress identities. |
| Resource envelope | Measure TTFT, prefill/decode, peak host and device memory, cache pressure, sustained bandwidth where instrumented, latency, power and thermal throttling under the matched task set. |
| Quality retention | Use paired tool-call, planning and business probes after verifying text, tokenizer, prompt and policy identity. Check outputs, actions, persisted state and correct escalation. Charge costs of retries and failures to the cohort. |

Register original and adapted BF16/F16, Q8_0 and Q4_K_M base plus F16 LoRA,
high-precision merged, merged Q8 and merged Q4 as separate comparison
profiles. Add the vendor-specific target only once its supported precision,
activation and cache format are established. Export distinct artifact hashes
and test the Radeon and DX-M2 profiles on their respective hardware. Report
any CPU-executed operator and scope the outcome to that mixed placement.
Record energy only when instrumented. Preserve the current Radeon seals.
[Existing project NPU evidence contract](../../../../reports/SLM10_NPU_DEPLOYMENT_REQUIREMENTS.md)
