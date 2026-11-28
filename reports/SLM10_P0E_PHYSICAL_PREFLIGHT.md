# P0-E Radeon development preflight

**Physical coverage is PASS.** The Radeon follow-up captured all 42 registered development trajectories. The scoped assessments recorded 8 PASS and 34 BLOCKED. It adds zero trials to the 36,550 core denominator. [Verified captures and findings](SLM11_PHYSICAL_FOLLOWUP.md#p0-e-preflight)

| Model | Direct native | SDK native | Total |
| --- | ---: | ---: | ---: |
| MiniCPM5-2B | 7 | 7 | 14 |
| LFM3-1.7B | 7 | 7 | 14 |
| Qwen3.5-2B | 7 | 7 | 14 |
| Total | 21 | 21 | 42 |

The controls cover one action, a pair of parallel reads, a recoverable source failure, a mid-task scope revision, a 12-step chain, a persisted draft with a confirmed release, and a persisted draft with denied authorization. Both draft arms bind the host's external event to the exact recorded draft. Stateful traces carry a final snapshot digest and a separate read-only SQLite reopen digest, including scope, drafts, decisions, releases and audit rows. The runner records physical provenance separately from the model's correctness, so a real failed model trajectory stays a real measurement.

The scripted transport controls exercised Direct and the real SDK integration against a software provider. Their evidence qualifies the software checks only. Physical calls must be attributed to the pinned llama.cpp and Antigravity 0.1.24 harness on the leased Radeon, with native completion, provider transport, SDK callback and SQLite capture references.

## Resume and review

Inspect the frozen 14-slot plan per model with the regular module entry point.

```sh
python -m benchmarks.slm10.p0e_radeon
```

Replay the completed evidence with `python -m benchmarks.slm10.physical_followup`. The physical captures cover the synthetic development controls. Formal Planning, MULTITOOL, D25 and production qualification require their own evidence. [Resume procedure](../HANDOFF.md)
