# Capability compensation guide

## Model-specific evidence

| Model | Measured failure | Candidate component | Status |
| --- | --- | --- | --- |
| MiniCPM5-2B | 36 of 50 frozen SDK first-attempt single-tool tasks repeated a proposal and executed it again. | Compare trusted Action State, an immutable observation ledger, a bounded terminal controller and a duplicate execution guard as separate factors. | HYPOTHESIS for independent qualification |
| LFM3-1.7B | 361 of 400 scoped completions on Direct and 218 of 400 on first SDK in the paired baseline. | Compact Result Codec with a frozen 12-case, 24-trial independent experiment. | NOT_RUN in the physical holdout |
| Qwen3.5-2B | First SDK passed the output contract on 85 of 500 trials. | Remove only an unambiguous complete JSON fence after a validated terminal response. Separate grammar, constrained decoding and bounded retry experiments. | Offline software replay PASS. Physical treatment NOT_RUN. |
| Ministral-3-3B | 0 of 378 observed first SDK output-contract verdicts passed in the 381-trial published path slice. | The same host extraction control, recorded separately from the frozen model results. | Offline software replay PASS. Physical treatment NOT_RUN. |

[Paired baseline](../atlas/slm/v1.0/milestones/tc-priority/SDK_CAPABILITY_DELTA.md) · [SDK root-cause evidence](SLM10_SDK_CAPABILITY_LOSS_ROOT_CAUSE.md) · [Adapter registry](../atlas/slm/v1.0/sdk-adapter-profiles.json)

## Output-contract compensation

In the published snapshot, an offline replay identified 1,467 fenced answers across D and F with already proved business facts. The transform extracts the original object text and uses no oracle input. A separate scorer checks exact keys and types against the frozen contract. The replay records both hashes and a pointer to the exact original seal for each candidate.

| Model and path | Original PASS / observed | Offline output-contract PASS / observed | NOT_RUN slots |
| --- | ---: | ---: | ---: |
| Qwen3.5-2B SDK first | 85/500 | 321/500 | 0 |
| Ministral-3-3B SDK first | 0/378 | 221/378 | 119 |

Three sealed Ministral SDK-first output verdicts in that snapshot are BLOCKED. Raw answers, native outcome, tool calls, D25 and the frozen first-attempt seals retain their original outcomes. Ambiguous wrappers, duplicate keys, invalid objects and trailing prose fail the software extraction control. Resource overhead, safety in the live output boundary, grammar, schema-constrained decoding and bounded retry require separate measurements. [Replay and trial references](../atlas/slm/v1.0/tc-output-normalization-replay.json)

## Independent physical controls

- Compare the original and compact-result SDK on the same frozen LFM3 case, world and seed. Use exact paired discordance, token and request deltas, P50/P95 and complete safety and coverage dispositions. A small exploratory effect requires the registered independent validation rule. [Frozen holdout](../atlas/slm/v1.0/sdk-adapter-lfm3-holdout.json)
- For MiniCPM5, attribute repeated proposals, blocked callback reuse, consumed observations, action completion and final termination separately. Preserve legal retries, same tool on different entities, scope changes, observation expiration, write authorization and invalidation of prior approval. [Software guard controls](../tests/regression/slm10/test_sdk_adapters.py)
- Track MODEL_NATIVE, RUNTIME_CONSTRAINED, HOST_NORMALIZED and RETRY_ASSISTED as distinct intervention arms. Count terminal facts and schema, preservation of uncertainty, early stopping, extra fields and incorrect values. Record additional model requests and end-to-end latency on the same case and quality scope.

Independent holdout benefit and formal qualification are still open. All listed intervention work contributes zero core physical trials.
