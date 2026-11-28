# SDK typed callback binder qualification

The two archived Original LFM3 failures observed integers becoming floats for `read_asset.filters.profile.max_width` and `check_layout.page`. The pinned SDK's `LocalHarnessEventProcessor.handle_tool_call` reads both call ID and structured arguments. `_extract_tool_args` prefers the protobuf struct when present, and `struct_converter` returns the stored double. `ToolRunner.process_tool_calls` retains the call ID in its result envelope while invoking ordinary Python callbacks with kwargs. A new real-SDK loopback probe preserved the scripted provider ID and delivered page `7` as `7.0` at the tool runner. [SDK event processor](https://github.com/google-antigravity/antigravity-sdk-python/blob/main/google/antigravity/connections/local/event_processor.py) · [Frozen regression](../atlas/slm/v1.0/lfm3-harness-adapters/SDK_CALLBACK_REPLAY.json)

The explicit JobBot tool-runner adapter uses the SDK call ID before kwargs expansion. The binder validates the original provider JSON against the public schema and binds one pending call to the current trusted session, scope, authorization binding and observation revision. It returns separately retained wire, parsed, SDK and normalized arguments with conversion paths, and checks current authorization after matching. Actual dispatch uses the original proposal and applies the sandbox's existing policy.

Integer normalization requires an explicit integer schema, an exact integral value and an original integer within the binary64 safe-integer range. Floats for non-integer numeric arguments require exact agreement with the wire decimal. Ambiguous or absent callback IDs, duplicate and reused proposal IDs, stale context and revoked authorization fail closed. The regression controls cover nested arrays and records, null versus omission, fractional values, booleans, numeric strings and non-finite values. [Binder](../src/model_gateway/callback_binding.py) · [Software controls](../tests/regression/slm10/test_lossless_callback.py)

The original five Extension BLOCKED observations retain their original dispositions. A fresh scripted-provider replay fed each exact archived first response to the real SDK and generated an independent scripted terminal reply. Each of the five proposals bound and reached a synthetic sandbox. This replay establishes the callback mechanism for the MiniCPM5 layout and Qwen3.5 rescan and layout first replies independently of the two LFM3 instances. [Same-byte replay](../evidence/IJSLM/lfm3-ha-1.1/extension-scripted.json)

The versioned physical track `SDK_MATCHED_CONTEXT_TypedExtension` executed all five cases on Radeon. All 21 callbacks in the reruns bound and reached the sandbox. Binding scope passes for these replays. The unchanged workflow scorer observed four FAIL and one BLOCKED.

| Candidate | Case | Bound callbacks | Scoped outcome |
|---|---|---:|---|
| MiniCPM5 | Layout | 1 | FAIL, sandbox denied the proposed action |
| Original LFM3 | Rescan | 2 | FAIL, terminal answer mismatch |
| Original LFM3 | Layout | 1 | FAIL, sandbox denied the proposed action |
| Qwen3.5 | Rescan | 2 | FAIL, terminal answer mismatch |
| Qwen3.5 | Layout | 15 | BLOCKED, repeated tool calls and no terminal reply in the capture |

The typed binder restored evidence at the callback boundary. The two denied layout proposals remained denied. Repeat calls and terminal failure remain visible in the Qwen3.5 layout trace. [Physical replay](../evidence/IJSLM/lfm3-ha-1.1/extension-radeon.json)
