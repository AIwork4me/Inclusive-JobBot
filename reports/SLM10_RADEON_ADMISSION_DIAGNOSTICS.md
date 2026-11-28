# IJ-SLM-1.0 Radeon admission diagnostics

MiniCPM5-2B, LFM3-1.7B and Qwen3.5-2B completed serial CPU and Radeon diagnostics after the verified Q2 handoff. The Radeon proof binds the live server PID to full model offload and GPU activity. Each portable report carries the installed Antigravity SDK and harness identity, engine and weight digests, and sealed traces.

| Model | SDK probes passed / executed | SDK dependent tools | SDK structured response | Direct native call | Direct stream parity |
|---|---:|---|---|---|---|
| [openbmb/MiniCPM5-2B](../evidence/IJSLM/admission/A/report.json) | 11/11 | PASS | PASS | FAIL | FAIL |
| [LiquidAI/LFM3-1.7B](../evidence/IJSLM/admission/B/report.json) | 11/11 | PASS | PASS | PASS | PASS |
| [Qwen/Qwen3.5-2B](../evidence/IJSLM/admission/D/report.json) | 10/11 | PASS | PASS | PASS | PASS |

AG-11 remains BLOCKED for all three models. These runs used the local loopback provider. End-to-end process egress was not independently observed.

MiniCPM5-2B answered the nonstreaming Direct balance request in prose and produced no native tool call. Its streaming response for that request did propose the account lookup. The SDK dependent-tool probe uses a different task and tool contract. A matched causal comparison of that Direct failure remains open.

The Qwen3.5-2B streaming prose probe AG-02 returned an SDK execution failure after the loopback wire boundary rejected the provider exchange with a ValueError. The boundary had no response snapshot for this failure. The exact rejection condition and independent reproduction remain open.

## Matched plan-first diagnostics

The same four existing public tasks ran through Direct llama.cpp and the real SDK for each model. All 12 Direct trajectories have matching native pre-parser generation records. The SDK arm retains the provider wire payload and SDK results. Native pre-parser capture was not enabled for the SDK requests in this diagnostic. These SDK records cannot establish parser-stage causality. The public task, visible system instruction and scoring rule match. The SDK controls its effective request, wrapper prompts and transport. These scores replay the existing oracle and carry no new mechanical qualification credential.

| Model | Direct PASS / FAIL / BLOCKED | SDK PASS / FAIL / BLOCKED |
|---|---:|---:|
| openbmb/MiniCPM5-2B | 0/4/0 | 0/3/1 |
| LiquidAI/LFM3-1.7B | 0/1/3 | 0/2/2 |
| Qwen/Qwen3.5-2B | 0/3/1 | 0/4/0 |

## Formal status

The 36,550-trial independent core roster has zero recorded trials. Formal model admission, scope-specific mechanical qualification and acting-first planning are still open. Semantic evaluation remains BLOCKED until the applicable Judges qualify. The independent task rosters and full statistical, specialization, JobBot permissions, hardware migration and source-level retest deliverables remain open.

[Per-probe matrix](../atlas/slm/v1.0/sdk_admission_diagnostics.csv) · [GPU handoff](../evidence/IJ073/aeve/gpu_handoff.json)
