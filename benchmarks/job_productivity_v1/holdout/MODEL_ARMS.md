# JOB-V1 local model treatments A–E

The runner uses the unchanged JOB-V1 paired roster and common Gateway and SQLite oracle. The model receives the frozen operator message and attachments, plus any scheduled user corrections as separate user messages, before it may alter the synthetic world. Case metadata, private state, scopes and expected answers stay in the host.

| Treatment | Exposure and workflow | Model |
|---|---|---|
| A | Generic table lookup and open draft body. The model chooses each lookup and proposes the assessment. | MiniCPM5-2B Q8_0 |
| B | The same free trajectory with separate typed purchase-order, supplier, catalog, inventory and draft schemas. | MiniCPM5-2B Q8_0 |
| C | The model emits typed intake or clarification. The existing skill workflow sequences and executes authorized business tools. | MiniCPM5-2B Q8_0 |
| D | C plus the versioned job knowledge from the three existing skills. | MiniCPM5-2B Q8_0 |
| E | D's prompt, orchestration, permissions and policy. | Qwen3-8B Q8_0 |

Free trajectories can stage unsubmitted review drafts after calling the scoped sources and seeing their results on a prior turn. The Gateway verifies authorization and independently checks the proposed assessment against the observed business records before writing. The staged note is a model proposal. The independent oracle checks its source digest and resulting business state. A/B do not use the SOP to select lookups or fill arguments. C–E use the SOP only after a fully validated intake. Tools cannot submit reviews, reserve stock or create tickets.

The execution path is Vulkan-only and uses the archived P4b observer with exact binary/DLL identity, full Radeon offload, native model-template checks and PID-scoped GPU telemetry. Preflight reads only local artifacts. The source observer and wire transport preserve requests, raw sampled completions, model usage, error evidence, and observed tool calls. Resume requires the same source, pairing and launch identities. A completed checkpoint includes exact SQLite evidence. Transport, observer or telemetry omissions remain visible as `BLOCKED`.

```powershell
$env:PYTHONPATH = 'src'
python -m benchmarks.job_productivity_v1.holdout.run_models --arm A --runtime-root $RuntimeRoot --engine-dir $PinnedVulkanObserver --preflight-only
python -m benchmarks.job_productivity_v1.holdout.run_models --arm A --runtime-root $RuntimeRoot --engine-dir $PinnedVulkanObserver --case JOB-DOC-001 --case JOB-CUS-001 --case JOB-PRD-001 --output .runtime/job-v1-a-diagnostic
```

Use one output directory per arm and panel. Omit `--case` for the full roster, use `--panel repeat` for the frozen repeated cases and `--batch-size` to limit cases per launch. `--resume` resumes the exact run. The default model seed is 23001 for primary cases. Repeats use the prescribed seeds. Model calls use temperature zero, an 8K context and at most 1,536 output tokens per response within the shared 8,192-token case budget.

The common result tracks correctness and actual business completion separately. A/B free-trajectory argument accuracy is left unmeasured against the C–F normalized intake-field unit. No hosted model, SDK, real business source or live write is used. Synthetic wire tests exercise treatment behavior. Actual A–E inference and paired comparisons require separate measured runs.
