# LFM3 cross-harness transfer development panel

The candidate freeze contains 60 synthetic cases, six in each of the ten
TC-V3 development families, and 480 paired trial slots across four weight
profiles and Direct or Original SDK. It uses fresh case and world IDs with
the existing TC-V3 scenario templates. Its oracle is a development oracle
derived by the generator. Admission of a final holdout requires new task
families, separate authoring and blind business review.
[Development matrix](../atlas/slm/v1.0/lfm3-harness-adapters/CROSS_HARNESS_TRANSFER_MATRIX.json)

The runtime factor treats the SDK's original model-visible requests as its
own arm. A modified tool schema, normalized result, changed system message
or other model-visible rewrite belongs to a separately registered
SDK_MATCHED_CONTEXT arm. In a matched weight comparison, both sides use the
same exact runtime and policy. Each trial must record the typed proposal,
provider completion, SDK callback, executed action, returned result and
terminal response. For action-phase failures, retain the point at which
native generation, parser, provider stream, callback, or execution stopped.
A callback mismatch blocks model-level attribution unless the available
trace proves that the proposed action itself was wrong.

The scoped SDK extension has documented callback-provenance failures.
Before dispatching these 480 trajectories, verify native and SDK parity
against positive and negative controls for this roster's action phases,
including parallel actions, changed scope and denials. Record the review
by scope. AG-03 admission covers a single read-only lookup. The candidate
freeze attributes zero physical trials and zero core trials.
[Callback mismatch evidence](SLM11_PHYSICAL_FOLLOWUP.md)

## Replayed SDK callback defect

Two archived Original LFM3 SDK Extension first replies were replayed with
Antigravity SDK 0.1.24 against a scripted loopback provider. The provider
retained the exact archived first response bytes and sent a synthetic
terminal reply. The original callback claim rejected both proposals
because the SDK supplied a float for a schema-declared integer. The
observed changes were `2048` to `2048.0` inside the nested rescan
configuration and `7` to `7.0` in the layout case. The arguments
otherwise matched at the claim boundary.

A trial-local witness converted only those known integer fields from
finite, exactly integral SDK floats to integers before matching. Both
callbacks then reached the sandbox. The strict production matcher did
not change. This recreates the callback defect with the real SDK and zero
new physical model trials. The 60-case transfer candidate uses string
references. It still requires its own Original SDK action-phase tests
across the declared families before dispatch.
[Callback replay evidence](../atlas/slm/v1.0/lfm3-harness-adapters/SDK_CALLBACK_REPLAY.json)

## Radeon action-phase preflight

Ten new scope-control worlds covered the same ten families at seed 7107
on Original LFM3, the pinned Radeon runtime and the cache-disabled admission
profile. The ten scripted-provider witnesses passed with the real SDK.
The physical panel used a separate namespace and recorded 30 trajectories.
It contributes zero registered M3 or core trials.

| Profile | Native requests captured | SDK or Direct linked actions | Execution process PASS/FAIL | Output contract PASS/FAIL |
|---|---:|---:|---:|---:|
| Direct | 22/22 | 13 | 10/0 | 10/0 |
| Original SDK | 10/10 | 0 | 1/9 | 1/9 |
| SDK_MATCHED_CONTEXT, tool choice only | 23/23 | 14 | 9/1 | 10/0 |

Original SDK sent all ten initial requests with tools present and
`tool_choice: "none"`. Nine generated a tool call as plain response text
with no structured call or callback. The single clarification case did
not require a tool. The fixed-adapter lookup admitted earlier took a
different SDK request path and carried `tool_choice: "auto"`. In the
single-field comparison, the host changed `none` to `auto` for
tool-bearing requests and left other request values intact. Structured
calls returned. A roundtrip case executed the same read twice and failed
its exact action path. Timing, cost and any adapter weight effect are
outside this preflight result.

Original SDK action-phase scope is FAIL on this bounded control. The
single-field arm remains a separate runtime experiment with a measured
execution failure. The frozen 480 development slots remain unexecuted.
Production and full independent qualification require their existing
scope and authorization evidence.
[Portable preflight](../atlas/slm/v1.0/lfm3-harness-adapters/SDK_ACTION_PHASE_PREFLIGHT.json)
