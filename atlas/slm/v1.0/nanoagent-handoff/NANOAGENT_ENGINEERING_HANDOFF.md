# NanoAgent engineering handoff

## Measurement scope

This first exchange covers the 4,950 frozen A/B/D TC-V3 trials on Radeon gfx1151. The [capability milestone](../milestones/tc-priority/README.md) documents the physical and statistical scope. Strict D25 and production authorization remain BLOCKED. The exchange introduces zero core trials.

PR #9 owns this physical baseline and intervention evidence. PR #11 owns NanoAgent components and their physical acceptance. PR #8 owns matched cross-SDK comparisons. PR #6 owns evaluation integrity and scope-specific credentials. Each consumer needs a credential applicable to its own runtime, tasks, hardware and assessment contract.

## Engineering use

- Use the [failure registry](MODEL_FAILURE_SIGNATURES.json) to locate the metrics and portable trials behind a design proposal. The [mapping](CAPABILITY_COMPONENT_MAPPING.json) states the invariant each proposed component must preserve and the experiment needed to measure its effect. All component proposals have HYPOTHESIS status.
- Pair R0–R7 under the [matched benchmark contract](MATCHED_BENCHMARK_CONTRACT.json). Keep eligibility and business quality equal when comparing model requests, user turns, latency or token costs. Pre-register sample size and the acceptance threshold before opening the qualification split. Use an independent holdout and preserve first attempts.
- Keep Radeon 8060S/gfx1151 and RX 7900 XTX/gfx1100 performance results in separate distributions. Use the same physical device for direct Antigravity versus NanoAgent latency and memory comparisons.
- Attribute model proposals, deterministic routing and SOP work, and human authorization to their actual sources. The host should reject scope and version mismatches before committing.

## Import and verification

Pin the commit containing this directory by full Git SHA in the consuming repository. The source Git SHA in the manifests identifies the reviewed PR #9 input baseline. Individual raw seal entries identify their own capture-source commit through the milestone evidence manifest.

From a remote checkout of the pinned commit, use the repository Python path conventions from the [reproduction guide](../milestones/tc-priority/REPRODUCTION_GUIDE.md). Run both commands to reconstruct the published exchange from portable physical evidence.

```sh
python -m benchmarks.slm10.tc_priority_milestone
python -m benchmarks.slm10.nanoagent_handoff
```

Validate the envelopes against [HANDOFF.schema.json](HANDOFF.schema.json). A patch version may correct publication metadata without changing a measurement. A minor version may add optional fields or scope-specific documents. A change to required fields, meaning, comparability or the evidence contract requires a new major version. Consumers should pin an exact version and verify the manifest digests.

## Decisions still open

Physical compensation benefit and resource overhead, the maximum reliable complexity and planning level, job quality, and NPU suitability require independent measurements. The [autonomy permission matrix](AUTONOMY_PERMISSION_MATRIX.json) states the host controls required for proposed or persisted operations. [Open risks](OPEN_RISKS.json)
