# P0-E Radeon development preflight

**Physical coverage is NOT_RUN.** The registered follow-up is queued behind the frozen TC-V3 controller and the LFM3 paired holdout. It adds zero trials to the 36,550 core denominator.

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

The workstation follow-up already owns the order of scheduled runs. If interrupted, verify the output directories against the expected model, source identities, roster digest and task completion records before any retry. Publish redacted portable evidence for attributed captures. Physical execution coverage and the scoped software assessment remain separate from formal Planning, MULTITOOL, D25 and production qualification. [Resume procedure](../HANDOFF.md)
