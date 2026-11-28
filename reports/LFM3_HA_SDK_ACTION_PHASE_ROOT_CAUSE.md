# LFM3 SDK action-phase causal diagnosis

The pinned Antigravity SDK 0.1.24 emitted `tool_choice: "none"` for a tool-bearing opening request when `model_output_retry.max_retries` was zero. Changing only that setting to one produced `"auto"`. The published real-SDK loopback probe held the model alias, prompt, single tool, allowlist, tool budget and output budget constant. Its provider was scripted and generated no model or GPU evidence. Separate controls changed the tool budget from four to three and the output budget from 768 to 1,536 with retries still zero. Both retained `"none"`. [Probe source](../benchmarks/slm10/ha11_retry_probe.py) · [Observed requests](../evidence/IJSLM/lfm3-ha-1.1/sdk-retry-probe.json)

| Path | Agent and tool policy | Request boundary |
|---|---|---|
| AG-03 single lookup | MINIMAL, explicit deny-all plus allow for lookup, one output retry | Fixed-route guard returns the SDK's original bytes. Native request carried `auto`. |
| Frozen TC-V3 SDK | MINIMAL, explicit deny-all plus per-tool allow, zero output retries | `sdk_trial.request_adapter` overlays `provider_profile`, including `auto`, fixed tool schemas and transport settings. |
| P0-E matched planner | MINIMAL with phase-specific registration and policy | `_Trial.sdk_phase` checks the SDK transcript. Its native arm preserves SDK tool choice and its matched arm uses `profile` and phase-specific offered tools. |
| Original SDK HA preflight | Frozen TC-V3 agent config, zero output retries | Historical scope harness replaced the TC-V3 request adapter with a fixed-route guard. The pinned harness's `none` reached the provider with tools present on all ten first requests. |
| ToolChoiceOnly HA preflight | Same agent and tool policy | Historical scope harness changed only effective `tool_choice` from `none` to `auto` for tool-bearing requests. |

The SDK Python path is `LocalOpenAIAgentConfig.create_strategy` → `LocalOpenAIConnectionStrategy._build_harness_config` and the superclass's retry-policy serialization in `local_connection.py` → the native `localharness` process. The OpenAI request is already populated when the JobBot wire boundary receives it. The matching public Python distribution packages the native executable separately. The exact internal branch assigning `tool_choice` remains **BLOCKED** on that source, while the externally controlled configuration trigger is verified. [SDK packaging](https://github.com/google-antigravity/antigravity-sdk-python/blob/main/pyproject.toml)

At the pinned provider, `tools/server/server-common.cpp` reads the effective `tool_choice` for chat configuration. The template parser generator enables its tool-call path when the supported template has tools and choice is enabled. The physical preflight linked requests to rendered prompts, sampled native output and provider responses. Original SDK generated plain-text tool syntax in nine cases with zero structured callbacks. ToolChoiceOnly recovered 14 executed actions in 23 native requests. The historical evaluator marked roundtrip and clarification termination FAIL. Roundtrip performed an extra identical read. Clarification had zero required actions and could meet the output shape while failing the exact clarification value. [Pinned parser generator](https://github.com/ggml-org/llama.cpp/blob/b1b770d90d94cad9e9ea5b993bdbc383a522fb28/common/chat-auto-parser-generator.cpp) · [Frozen preflight](../atlas/slm/v1.0/lfm3-harness-adapters/SDK_ACTION_PHASE_PREFLIGHT.json)

The new `SDK_MATCHED_CONTEXT_PhaseAware` adapter gives the trusted phase controller authority over the provider tool schemas and tool choice. It offers authorized synthetic reads in ACT and REPLAN, verifies the actual callback result before a replan, and stops provider routing after a terminal reply. PLAN, FINAL and CLARIFY expose no tools. OBSERVE is a host step. The diagnostic starts ACT under its public synthetic allowlist, and the model can stop without taking an action. The evaluator's hidden oracle is read after execution. [Phase policy](../src/model_gateway/phase_tool_policy.py) · [Diagnostic runner](../benchmarks/slm10/ha11_preflight.py)

## Radeon paired retest

Forty trajectories reused the ten historical scope prompts and worlds in fresh sessions at seed 7107. Runtime order rotated by task. All 81 provider responses linked to native generation. The prior 30 captures and the two captures in the interrupted config-copy attempt remain separate. The new panel contributes zero registered transfer or core trials. [Replayed run evidence](../evidence/IJSLM/lfm3-ha-1.1/action-phase-retest.json)

| Profile | Native requests | Linked actions | Exact execution | Exact termination |
|---|---:|---:|---:|---:|
| Direct | 22 | 13 | 10/10 | 10/10 |
| Original SDK | 10 | 0 | 1/10 | 0/10 |
| ToolChoiceOnly | 24 | 15 | 8/10 | 7/10 |
| PhaseAware | 25 | 18 | 6/10 | 5/10 |

Original SDK reproduced runtime policy suppression. ToolChoiceOnly repeated the same read in single and roundtrip. PhaseAware repeated single, roundtrip and both parallel reads, and proposed an extra distractor read in binding. All 18 phase-aware proposals linked to successful callbacks and recorded sandbox actions. Those extra reads and the parallel run's missing terminal reply are measured model and termination outcomes. The clarification response asked for the reference and passed shape validation, yet the frozen exact-value oracle required the literal `reference`. That is an exact-contract FAIL with semantic evaluation uncertainty. No native parser or callback fault accounts for the extra roundtrip read.

The phase-aware arm used the public tool definitions on the effective wire and a read-only scope. This is a model-visible treatment. Its score cannot isolate a change in tool choice from the other request changes. Direct and PhaseAware pass the bounded executor recording checks for development use. PhaseAware exact execution remains FAIL. The result supports full paired development measurement with failures retained and supports no production role qualification.
