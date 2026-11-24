# MULTITOOL-V1

This freeze serves IJ-0.7 §6.2 and §9.4. The 600 original synthetic holdout cases contain 75 cases per category. Each category has 15 cases in each required-call band (2–3, 4–5, 6–10, 11–15 and 16–20), with five English, five Chinese and five mixed-language prompts per band. Six zero-call diagnostics exercise formatting and requests that require clarification. They have separate IDs and stay outside the 600-case and reliability denominators.

| Category | Synthetic task |
|---|---|
| MT-01 | Get concurrent-ready ambient and cold stock readings for depot names shared by similar references |
| MT-02 | Follow opaque references across route, dispatch and checkpoint services |
| MT-03 | Combine current stock with backlog or reconcile live and archived stock results |
| MT-04 | Follow the open main lane or a contingency lane according to checkpoint status |
| MT-05 | Submit an ordered nested set of grounded sensor readings and apply an inclusive load limit |
| MT-06 | Recover by one model-initiated retry or an independent mirror after a scheduled error |
| MT-07 | Apply a synthetic user's newly supplied or revised site constraint to the subsequent roster lookups |
| MT-08 | Resolve the current dispatch review, create a permitted unsubmitted draft, or stop safely when access is denied |

`frozen/manifest.json` identifies five frozen files and the SHA-256 of their canonical digest map. `prompts.jsonl` holds initial messages and tool allowlists. `tools.json` defines case-facing schema and operation descriptions. `worlds.jsonl` holds the synthetic service records, failure schedules, user events and draft grants. `oracles.jsonl` holds independent expectations for calls, dependencies, results, final JSON, and persisted state where applicable. `repeat_panel.json` preselects 100 holdout IDs ranked by salted SHA-256 within each category, depth and language stratum. Every depth band contributes 20 cases. The three frozen seeds are 48707, 65719 and 98123.

## Runtime and scoring contract

- Send `Case.model_input()` to the model. The returned payload contains the initial user message and JSON tool definitions. Keep the case metadata, world, model-run budgets and scorer outside model context. In MT-07, append the user message from `Scenario.take_events()` after the triggering tool result and before requesting the next assistant turn. Keep the event identity and its delivery turn for scoring.
- Execute the model's calls through one `Scenario` per attempt. Preserve raw argument strings, runtime results, turn and call identities. The simulator never advances the model's planned tools. Failure responses are keyed by tool, record and accepted attempt number, so independent call reorderings do not shift the error schedule. Timeout and HTTP 429/500 are synthetic response payloads. MT-06 recovery steps count toward required calls and stay within the first task attempt.
- Supply a fresh SQLite database path to MT-08 and collect `Scenario.snapshot()` before and after execution. Draft permission is enforced through the real Gateway and a synthetic grant. The runtime forbids live dispatch commits throughout this corpus. The scorer compares observed persisted SQLite state and transaction audit fields against the authored expectation.
- Pass the observed calls, exact final text, moderator deliveries and persisted snapshots to `score()`. The V2 evaluator accepts equivalent batching and ordering for independent calls and enforces later-turn availability for dependent calls. Use `required_steps` for complexity bands. A pass where `expected_outcome` is `expected_safe_stop` or `expected_clarification` represents correct handling of that task. Report those outcomes separately from business completion.
- Retain external reruns by frozen case ID and seed. `Pass@3` counts at least one successful run and `Pass^3` counts three successful runs. Keep additional diagnostics outside the preselected repeat panel. Full metrics and model-versus-runtime attribution require the model runner and telemetry for the report in IJ-0.7 §6.3–6.4.

## Verification

Run from the repository root with the environment that provides the project dependencies.

```powershell
$env:PYTHONPATH = 'src'
python -m benchmarks.multitool_v1.verify
python -m pytest tests/regression/ij07/test_multitool_v1.py -q
```

To regenerate a comparison copy, run `python -m benchmarks.multitool_v1.generate --output <new-directory>`. Verification checks the frozen bytes, strata, repeat panel and synthetic reference replay, including SQLite write evidence. The reference replay begins from the oracle and exists only to test the benchmark. Model qualification, GPU performance, and SDK execution remain `NOT_RUN` for this freeze. Template families repeat the same business domain and strict structured-answer format. Evaluation results describe generalization within those conditions.

## Local Radeon runner

`benchmarks.multitool_v1.run` verifies the exact P4b observer executable, DLLs, Q8_0 model and native template against the archived runtime identities. Live execution launches a private loopback server with full GPU offload, source-side generation capture and PID-bound GPU telemetry. The first-pass seed is 66007. The runner uses non-streaming requests, temperature zero, an 8K engine context and thinking disabled. The case allows at most 24 model turns and 32 proposals, with 1,536 output tokens per turn and a 600-second wall budget checked between model requests and before acting on responses.

```powershell
$env:PYTHONPATH = 'src'
python -m benchmarks.multitool_v1.run --backend vulkan --runtime-root $RuntimeRoot --engine-dir $PinnedObserver --preflight-only
python -m benchmarks.multitool_v1.run --backend vulkan --runtime-root $RuntimeRoot --engine-dir $PinnedObserver --case MT-01-001 --case MT-06-001 --case MT-07-001 --case MT-08-002 --output .runtime/multitool-diagnostic
```

Omitting `--case` selects the full primary panel. Use `--panel repeat` for the frozen repeat panel or `--panel controls` for the six zero-call controls. `--batch-size` limits additional attempts at each launch. Use `--resume` from the same source and runtime configuration to continue. Each assessed case has an atomic checkpoint with raw model requests and responses, observer traces, synthetic tool results and any SQLite snapshots. Missing transport, observer or GPU evidence is tracked as `BLOCKED`. Interrupted attempts are preserved independently of resumed verdicts. Raw artifacts remain local until machine-identifying information is reviewed. The runner measures real model execution in deterministic synthetic tool worlds, with no SDK or live business operations.

The original primary panel ran from commit `9d031fe95622bed88588f1c11a13d073748b26bf`.
Its fixed wire cap of 16 could reject a batch within the task's 32-proposal
budget. The current runner explicitly passes the task limit to the non-streamed
benchmark decoder. The archived IJ-0.6 gateway remains byte-verified.
Use a fresh output directory for that revised profile and keep
the original run on its pinned source. [Wire control](../../reports/IJ07_SOURCE_LEVEL_ROOT_CAUSE_MASTER_REPORT.md#rc-18-多工具预算和-wire-上限不一致)
