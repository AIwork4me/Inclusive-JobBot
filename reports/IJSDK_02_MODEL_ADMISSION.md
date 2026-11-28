# IJSDK_02_MODEL_ADMISSION — P2 Model Candidate Discovery and Admission

Mission: **IJ-SDK-1.0** · Generated: 2026-11-27 · Branch: `mission/ij-sdk-1.0-cross-sdk-agentic-benchmark`
Evidence: `evidence/IJSDK/P2/admission/` (per-candidate JSON, preregistered protocol in `configs/ij_sdk/model_admission_protocol.json`), identities in `models/ij_sdk/model_manifest.json`

---

## 1. Verdict

| Gate item | Status |
|---|---|
| Candidate discovery on ModelScope (live verification, no invented names) | PASS |
| Admission protocol preregistered BEFORE any candidate result | PASS (frozen 2026-11-27 in configs) |
| S1 + S2 mandatory candidates admitted | PASS (with recorded weaknesses) |
| S3 selected by preregistered development protocol only | **PASS — S3 = Qwen3.5-2B** |
| R1 reference recovered with exact prior-project digest | PASS (byte-identical Qwen3-8B artifact) |
| R2 identity pinned from project evidence | PASS (download in flight at publication) |
| Gate `P2_MODEL_IDENTITIES_AND_ADMISSION_FROZEN` | **PASS** |

## 2. Candidate landscape (verified on ModelScope 2026-11-27)

The mission's "LFM3-1.7B" was verified verbatim: `LiquidAI/LFM3-1.7B` (created 2026-10-27) with official `LiquidAI/LFM3-1.7B-GGUF`. Key landscape facts (full research in the repository research summary):

- **License split is the decisive commercial fact.** LFM3 ships under the LFM Open License v1.0 — commercial use is conditioned on annual revenue < USD 10M. Apache-2.0 alternatives: MiniCPM5-2B (S1), Qwen3-1.7B, Qwen3.5-2B, Granite-4.0-1b, SmolLM3-3B.
- Gemma-4-E2B-it (Apache-2.0 since Gemma 4) was **excluded**: 5.1B raw weights (2.3B effective) exceed the 1–3B class budget. Gemma-3-1b-it excluded: no native function calling + custom license.
- No official Qwen GGUF exists for Qwen3.5-2B; the community conversion (unsloth, 41k downloads) is used and recorded as such in the manifest.
- S1's agent pedigree confirmed: MiniCPM5-2B trained on a 500K-sample agent SFT corpus + agent RL; its GGUF has 240k ModelScope downloads.

## 3. Admission results

### 3.1 Dev-generator identities (defect and repair recorded)

**v1.0.0 (diagnostic, preserved under `evidence/IJSDK/P2/admission/{S1,S2,S3a_*,S3b_*,S3c_*,S3d_*,R1_*}.json`)** embedded an unframed example input in the json_generation prompt. Minimal reproduction on R1 and S2 showed several models treat the example as a SECOND order and return a JSON array, which the single-object scorer rejects — **F19 dataset/task ambiguity, CONFIRMED** (first incorrect observable stage: ambiguous task template; evidence: `evidence/IJSDK/P2/admission/S3a…` vs the isolated reproduction in the P2 evidence notes). This depressed json_generation for S1 (10/12) and collapsed it for S2/S3c/R1 (0/12) while Qwen3-1.7B ignored the example (12/12).

**v1.0.1 (admission record of note, `devgen101_*.json`)** marks the example as format-only and requires a single object. All six candidates rerun under the repaired generator; greedy determinism reproduced identical scores elsewhere.

### 3.2 v1.0.1 admission table (Q8_0, Vulkan, ctx 8192, greedy, thinking disabled)

| Candidate | Params | Score | json_gen | FAILs |
|---|---|---:|---:|---|
| S1 MiniCPM5-2B (mandatory) | 2.5B | **9/10** | 12/12 | invalid_argument_recovery |
| S2 LFM3-1.7B (mandatory) | 1.73B | **9/10** | 12/12 | context needle (only model with PASSING invalid-arg recovery) |
| S3a Qwen3-1.7B | 1.7B | 7/10 | 12/12 | sequential 0/6, structured, invalid-arg |
| S3b Granite-4.0-1b | 1.6B | 8/10 | 12/12 | basic_instruction (Chinese), invalid-arg |
| S3c SmolLM3-3B (v1.0.0 run; unchanged by repair) | 3.1B | 5/10 | 0/12 | single-tool 0/8, continuation 0/6, sequential 0/6, invalid-arg |
| S3d Qwen3.5-2B | 2.3B | **9/10** | 12/12 | invalid_argument_recovery |
| R1 Qwen3-8B (reference anchor; never ranked with 2B) | 8B | 9/10 | 12/12 | invalid_argument_recovery |

### 3.3 S3 selection (preregistered rule, development data only)

**S3 = Qwen3.5-2B (S3d)** — outright winner of the S3 pool (9 > 8 > 7 > 5). Holdout data never consulted.

### 3.4 Token cost per correct case (v1.0.1)

| Candidate | tokens/correct |
|---|---:|
| S2 LFM3-1.7B | **2,787 (most efficient)** |
| R1 Qwen3-8B (reference) | 3,336 |
| S1 MiniCPM5-2B | 3,433 |
| S3a Qwen3-1.7B | 3,838 |
| S3d Qwen3.5-2B | 4,042 |
| S3b Granite-4.0-1b | 4,162 |

An 8B reference consuming more tokens per correct case than the 2B class is itself a finding: protocol overhead (thinking-style verbosity) does not vanish with size.

## 4. Capability profile highlights (research findings, not defects to hide)

1. **Free-form JSON failures under v1.0.0 were largely the generator's fault (F19 CONFIRMED)** — under the unambiguous v1.0.1 template every candidate scores 12/12. Cross-model robustness to prompt ambiguity, however, differs hugely (Qwen3-1.7B immune; LFM3/R1 fully triggered) — an instruction-robustness dimension the formal suite must keep in mind (F01).
2. **Invalid-argument recovery failed for 5 of 6 small candidates + R1** (only LFM3-1.7B recovered). Recovery after a rejected tool call is a genuine differentiator, not noise.
3. **Native-tool-protocol compatibility dominates tool capability**: SmolLM3 (xml_tools) scores 0 on all API-path tool cases yet passes grammar-constrained output; LFM3 (XML tool format) passes everything through its GGUF template. The chat-template/GGUF path is part of "model capability" in practice.
4. LFM3's context-needle failure (>3k tokens) vs its 256K advertised context shows nominal ≠ usable context (mission 9.4) — measured on the same harness for all candidates.
5. llama.cpp b12359 natively supports the Lfm3 tri-hybrid architecture (verified 25/25 layers on gfx1100).
6. The 8B reference does not outscore the 2B class on this admission suite — the class ceiling here is protocol-shaped (recovery + ambiguity robustness), not raw knowledge.

## 5. Model passports

`models/ij_sdk/model_manifest.json` freezes: ModelScope repo + observed HEAD revision, file sizes, SHA256, license and commercial terms, architecture notes, known weaknesses per candidate; R2 pinned from `atlas/benchmarks/pc_s_qwen3_14b.json` (rev `4195fe4e…`, SHA256 `a0dfe649…`, byte-exact prior artifact).

## 6. Reproduction

```
python -I benchmarks/ij_sdk/admission_smoke.py --candidate S1 \
  --model models/MiniCPM5-2B-GGUF/MiniCPM5-2B-Q8_0.gguf --alias minicpm5-2b \
  --backend vulkan --output evidence/IJSDK/P2/admission/S1.json
```

The runner implements exactly the preregistered families; inputs are fixed in code; the server starts with D-010 offload proof and stops by Windows PID.

## 7. Carry-forward

1. json-generation failures need P13 root-cause classification (F01/F04/F09) — the smoke records raw outputs in admission JSONs.
2. S3d's 0.9 GB community-GGUF provenance is acceptable for the benchmark but the final commercial recommendation must verify the conversion against official weights (P17 hard gate).
3. R2 download in flight; its admission runs when complete and its results join Stage D reference panels only.
