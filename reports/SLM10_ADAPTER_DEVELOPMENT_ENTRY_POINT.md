# IJ-SLM-1.0 SDK adapter development entry point

The paired development runner uses the installed Antigravity SDK, a privately routed loopback wire boundary, existing provider normalization, and the synthetic TC-V3 read sandbox. Every arm gets fresh SDK directories, the same case and seed, a denied-by-default policy, explicit read-tool grants, bounded calls, cancellation, a deadline and zero automatic retries. The adapter sees an audited callback only after a unique SDK claim, a matching provider response, normal tool validation and a matching host result. Each provider request retains the normalized source and transformed digests, SDK and provider identifiers, callback source links and host processing time. [Implementation](../benchmarks/slm10/sdk_adapter_development.py) · [Profiles](../atlas/slm/v1.0/sdk-adapter-profiles.json)

The runner executes either the reference and one treatment or a plan audit. The supported treatments are Prompt Compiler, Compact Result Codec and Action State. Termination Policy and Structured Output Contract are post-capture observers with individual verdicts. The runner preserves original SDK output, provider output, callback audit and sandbox state. The fixture sandbox lacks the explicit immutable-read authority required by Duplicate Execution Guard. Host protection stays disabled in these runs.

The LFM3 holdout plan fixes twelve new synthetic public prompts over single, selection, roundtrip and dependency cases in English, Chinese and mixed language. The namespace and prompts are disjoint from the frozen TC-V3 development and formal holdout. The holdout uses the same fixture constructor and task families to test recurrence under changed wording and record identities. This design does not assess transfer to unrelated task families. It fixes both order-balanced arms at the same seed, with zero formal trial attribution. [LFM3 holdout plan](../atlas/slm/v1.0/sdk-adapter-lfm3-holdout.json)

From the repository root in the project Python environment, audit the holdout plan without starting inference.

```text
python -m benchmarks.slm10.sdk_adapter_development
```

When the registered Radeon slot is authorized and its controllers have exited, the physical holdout command takes the existing assets directory and a fresh output directory.

```text
python -m benchmarks.slm10.sdk_adapter_development --dispatch --assets <asset-root> --output <new-output-directory>
```

For other single-factor comparisons on existing synthetic development cases, add `--development` and choose `--candidate A|B|D` and `--treatment prompt_compiler|compact_result_codec|action_state`. The host checks for competing controllers and verifies the existing handoff, runtime version, binary and model hashes, SDK harness, Radeon launch and process-linked activity. The execution report preserves partial captures and publishes redacted evidence separately from private raw results. The profiler records the validated SDK-facing answer and provider answer individually, workflow and schema outcomes, model proposal and callback counts, and processing and request latency.

| Gate | Status | Scope |
|---|---|---|
| Independent plan and integration controls | PASS | Plan disjointness, read-only permission, correlated callbacks, request audit and four real SDK software fixtures over a scripted loopback provider. These fixtures carry no native model or GPU evidence. |
| Matched LFM3 holdout on Radeon | NOT_RUN | The sealed roster plans 24 physical trajectories. |
| Other adapter physical development and held-out comparisons | NOT_RUN | Requires separate matched outcome and overhead evidence. |
| Production qualification and factorial selection | BLOCKED | Requires physical qualification and independent controls in the intended role. |
