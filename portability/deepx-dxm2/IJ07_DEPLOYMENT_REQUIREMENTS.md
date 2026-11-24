# IJ-0.7 DX-M2 deployment requirements

Physical DX-M2 execution is `NOT_RUN`. The reference workload is the pinned
MiniCPM5-2B Q8_0 text model and its native tool protocol. This specification
uses model configuration and local GGUF sizes. The hardware vendor describes
its DX-LLM runtime and compiler as well as multiple memory configurations.
Confirm availability, supported operator versions, and tool calls on the
specific board and compiler version. [DX-M2 SDK and board family](https://deepx.ai/products/dx-m2/)

## Model, storage and cache

- Dense Llama model, 2,516,756,480 total and 1,981,982,720 non-embedding
  parameters. All 42 transformer layers execute for every decoded token.
  Hidden size is 2,048. Attention uses 16 query heads and two KV heads at
  head size 128. [Official model architecture](https://github.com/OpenBMB/MiniCPM)
- The installed GGUF files are 5,039,006,688 bytes F16, 2,679,710,688 bytes
  Q8_0, and 1,561,318,368 bytes Q4_K_M. Record the independent compiled
  artifact size, working memory, and peak prefill memory at each precision.
  [Pinned model manifest](../../models/model_manifest.json)
- Uncompressed FP16 KV cache requires
  `2 × 42 × 2 × 128 × 2 = 43,008 bytes/token` per sequence. This is 336 MiB
  at 8,192 tokens and 5.25 GiB at 131,072 tokens. Add layout/paging,
  intermediate tensor and runtime overhead explicitly. The 8,192-token
  starting point is the tested Windows configuration. The 131,072-token
  figure is the model configuration limit.

## Runtime implementation

Support grouped-query causal attention and RoPE, RMSNorm, linear matmul and
quantized weight unpacking, SiLU with gated MLP, token gather, and final
logits. Demonstrate separate prefill and incremental decode, variable valid
sequence lengths and cache offsets, and stationary output under padded and
dynamic input shapes. Record hardware and CPU placement per operator and all
copy or dequantization impacts. Keep tokenizer, native prompt rendering,
sampling contract, parser and protocol/Gateway validation bound to explicit
versions. Equivalent CPU-assisted host placement must be identified in
the run configuration.

The CPU host owns authorization, confirmation, transaction logging, SQLite
state and offline egress controls. Parse EOS, stop strings and streaming tool
arguments using native parity fixtures. An NPU launch receipt and counters
must establish actual graph execution. Capture model prompts, token IDs and
parser input with instrumented diagnostic models.

## Acceptance

First compare frozen prompts, rendered template, CPU reference and native
wire fixtures. Run TC-V2 and its repeat panel under each supported precision
and context configuration using the same budgets. Admissions preserve ADR-002
thresholds and hard safety limits. Determine any allowed accuracy loss by a
predeclared paired comparison before the independent run. Extra resources may
merit a best-practice track with its own budget. Track tokens and model calls
per successful task, prefill/decode throughput, P50/P95, memory and energy
only when the instrumentation supports the measure. The existing JOB-V1
commercial goals include 99% first-pass success and the 15-second routine
P95 target. Their validation requires a sufficiently sized held-out run.
 [Physical acceptance plan](PHYSICAL_ACCEPTANCE_PLAN.md) · [ADR-002](../../docs/decisions/ADR-002-IJ0-TOOL-CALLING-ACCEPTANCE.md)
