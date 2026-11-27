# IJ-NANO-1.0 — N02 Physical Runtime and Model Identity Qualification

- Generated: 2026-11-27T12:10:00Z
- Scope: physical runtime admission and protocol qualification on this
  workstation (gfx1100 / RX 7900 XTX). **Runtime/protocol tests only — no
  business-correctness claim of any kind** (scope per
  `evidence/IJNANO/N00R/lease_scope_decision.json`).
- All GPU sessions held the host-wide lease
  (`benchmarks/root_cause/gpu_lease.py`; acquired/released records in
  session evidence).

## 1. Identity verification (fresh, not inherited)

`benchmarks/ij_nano/verify_model_identities.py` against the committed anchor
`models/ij_sdk/model_manifest.json` (itself SHA256-recorded):

- **10/10 weight files MATCH** (size + SHA256): S1 Q8_0/Q4_K_M, S2 Q8_0/Q4_K_M,
  S3a-d Q8_0, R1 Q8_0, R2 Q8_0.
- **95 engine binaries hashed** across cpu/vulkan/rocm (llama-server.exe +
  all DLLs per backend).
- Evidence: `evidence/IJNANO/N02/identity_verification.json`.
- Engine provisioned through gitignored junctions per repo conventions;
  binary self-reports `version: 1.0.0-dev (build 12359, commit b1b770d90)` —
  the pinned identity.

## 2. Admission smokes (IJ-SDK frozen dev-gen v1.0.1 families, reused tool)

Executed 2026-11-27T11:29–11:33Z under the lease, backend vulkan:

| Arm | Model | dev score | D-010 offload |
|---|---|---|---|
| S1 | MiniCPM5-2B Q8_0 | 9/10 | 43/43 layers |
| S2 | LFM3-1.7B Q8_0 | 9/10 | 25/25 layers |
| S3 | Qwen3.5-2B Q8_0 | 9/10 | 25/25 layers |
| R1 | Qwen3-8B Q8_0 | 9/10 | 37/37 layers |
| R2 | Qwen3-14B Q8_0 | 9/10 | 41/41 layers |

Evidence: `evidence/IJNANO/N02/admission/*.json` (self-redacted by the
tool: `model_path = <outside-repository>`),
`evidence/IJNANO/N02/session_record.json`.

## 3. Protocol probe (`benchmarks/ij_nano/n02_protocol_probe.py`, v3)

Checks: health + socket ownership, D-010 offload line, basic generation with
usage accounting, native tool-call protocol (Chinese business tool),
`response_format json_schema` (chat path, strict), GBNF grammar via
`/completion`, engine-behavior record for escaped-quote GBNF literals,
`json_schema` field on `/completion`, SSE streaming with usage,
mid-stream client cancellation + post-cancel health.

| Arm | overall | notes |
|---|---|---|
| S1 | **PASS** | all checks green |
| S2 | PASS on protocol surface; chat-path json_schema FAIL | see §4 — constrained output itself PASSes via GBNF and /completion json_schema |
| S3 | **PASS** | |
| R1 | **PASS** | |
| R2 | **PASS** | |

Engine-behavior records (all five arms):
- `gbnf_escaped_quote_literals = ENGINE_REJECTS` (HTTP 400, "failed to parse
  grammar"): **b12359 rejects backslash-escaped-quote literals in GBNF**;
  char-class form `["]` works. Recorded, excluded from scoring.
- `/completion json_schema` expects a JSON object, not a string (v2 → v3
  probe fix; both code versions in git history).

## 4. Model-behavior findings (inputs to N03 / Runtime Profiles)

1. **LFM3-1.7B (S2) reasoning burn on the chat path**: with
   `response_format json_schema` (strict) at max_tokens 1024, the model
   consumed the entire budget in `reasoning_content` (4,030 chars),
   `finish_reason=length`, empty `content`. The constraint applies; the
   thinking channel starves it. The same model produces grammar-constrained
   JSON directly via `/completion` (`{"action":"query","sku":"SKU-1001"}`)
   and passes `/completion json_schema`. **Runtime-profile implication**: a
   NanoAgent profile for S2 must budget or disable thinking on chat-path
   structured output, or route structured decisions through the
   completion-path constraint. Not tuned further here — recorded as a
   capability finding (feed C-primitives: C09/C10/C32 stress dimensions).
2. All five models answered native tool-call protocol, SSE streaming,
   cancellation-with-recovery and token accounting identically at the
   protocol level; per-model capability differences belong to N03
   measurement, not this qualification.

## 5. ROCm/HIP comparator

Preserved as a separately identified comparator (mission order §4.2): the
rocm backend is installed and hash-verified (§1) but was **NOT executed** in
this session; no ROCm result is mixed into any table above. Backend mixing
remains forbidden; a dedicated ROCm comparison run is scheduled when its
experimental identity is preregistered.

## 6. Verdict

`N02_PHYSICAL_MODEL_RUNTIME_QUALIFIED` — **PASS** for runtime admission and
protocol scope on S1, S2, S3, R1, R2 (vulkan, b12359, Q8_0 anchors), with:
- S2's chat-path structured-output limitation recorded as a model-behavior
  finding (not a qualification failure of the engine protocol);
- engine grammar-parser limitation recorded (escaped quotes);
- quantization sensitivity (Q4-class) and the ROCm comparator explicitly
  NOT_RUN in this scope.

Evidence index: `evidence/IJNANO/N02/` (identity_verification,
admission/*, protocol/*, session_record).
