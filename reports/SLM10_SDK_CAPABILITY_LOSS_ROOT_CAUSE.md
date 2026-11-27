# SDK capability loss in frozen TC-V3

The offline v1.0 replay covers 4,014 sealed Radeon trials. It binds each reassessment to its unchanged trial identity and private capture digest. The original scores, D25 values and denominators remain in the seal. All three models completed the 50 SDK first-attempt single-tool tasks in this snapshot. [Matrix](../atlas/slm/v1.0/sdk-causal-matrices.json) · [Evidence manifest](../evidence/IJSLM/sdk-causal/manifest.json)

| Candidate | SDK single-tool tasks | Identical action proposed again | Identical action executed again | Verified delivery and correct value inside a JSON fence |
|---|---:|---:|---:|---:|
| MiniCPM5-2B | 50 | 36 | 36 | 32 |
| LFM3-1.7B | 50 | 22 | 22 | 0 |
| Qwen3.5-2B | 50 | 0 | 0 | 34 |

- MiniCPM5 repeats were already visible in the captured native generation after results reached the model. The parser preserved the observed proposals, and callback identifiers tied subsequent executions to the provider completions. For the 14 single-tool trials with frozen tool_result FAIL, the correct value was returned in a JSON fence.
- LFM3 produced identical action repeats on 22 single-tool trials. Twenty-three stop assessments failed. Four trials ended after four model requests and four callbacks with an empty final SDK answer and a last provider finish reason of tool_calls. Eleven trials contained late calls with incorrect arguments; the counts can overlap. The offline matrix counts exact action repeats separately from surplus calls to the same tool.
- All 34 Qwen3.5 single-tool tool_result failures recovered the expected value from a verified delivered result. The final JSON fence violated the response contract. All 50 single-tool stop assessments passed.

The SDK system message includes a GitHub-style Markdown instruction. The effective provider tool descriptions were normalized to the same frozen public tool contract. The observed provider completions and SDK-facing adapted bytes agreed on calls, text and finish reason for all 369 captured single-tool SDK requests in the snapshot. The native comparison covers the recognized forms with matching completion identifiers. The individual prompt, packaging and interaction effects are tested in the matched development controls. [Paired physical controls](SLM10_SDK_SPECIALIZATION_AB_TEST.md)

| Candidate | Complete SDK/Direct pairs | Median input token delta | Median output token delta | Median provider inference delta |
|---|---:|---:|---:|---:|
| MiniCPM5-2B | 427 | +3,211.0 | +28.0 | +1,954.1 ms |
| LFM3-1.7B | 406 | +2,731.0 | +0.0 | +758.0 ms |
| Qwen3.5-2B | 383 | +2,022.0 | +5.0 | +824.8 ms |

The deltas use paired SDK first attempt minus Direct first attempt. These pair sets include completed families from the frozen queue. Provider inference sums native prompt and generation time. The cost matrix uses requests and tokens per scoped read success. AG-11 remains BLOCKED. The earlier 512 KiB SSE cumulative-limit diagnosis remains proven on the captured bytes. The historical ValueError remains UNVERIFIED. [Component and cost matrices](../atlas/slm/v1.0/sdk-causal-matrices.json)
