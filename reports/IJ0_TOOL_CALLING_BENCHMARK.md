# IJ-0 frozen tool-calling benchmark

Each arm ran the 500 frozen cases with MiniCPM5-2B Q8_0 on the physical Radeon GPU.
Tools were deterministic simulators operating on synthetic data.
The [IJ-0 acceptance thresholds](../docs/decisions/ADR-002-IJ0-TOOL-CALLING-ACCEPTANCE.md) were set after this benchmark began. The table is a diagnostic baseline.

- Dataset SHA256 `ce6bf6bf433baab69e511328faae42c34d6a245e44dfd432e2a30f94c84e6add`
- llama.cpp `b12359` at `b1b770d90d94cad9e9ea5b993bdbc383a522fb28`
- ModelScope revision `8cc1178b0a5cee98872ca3f2f88d49b3d3fa6f59`
- Model SHA256 `c5415f8989bf88a8288f1b55a3cc371af53c07b0faa220a63bd7a990cfaba078`
- Vulkan run `tc-test-d0cd7479ef414381875ca8d892ed4a61` at `1edf497cb96a217c45b4a5fc8d7653b6b6eda102` with Compute 96% peak engine activity and 3200.7 MiB peak process GPU memory.
  Excluded 5 out-of-range engine readings from the peak. Raw readings are preserved.
- ROCm run `tc-test-5d6fd88cfc16436d922c7bc75b752003` at `1edf497cb96a217c45b4a5fc8d7653b6b6eda102` with Compute 100%, Copy 9% peak engine activity and 3317.8 MiB peak process GPU memory.
  Excluded 41 out-of-range engine readings from the peak. Raw readings are preserved.

| Metric | Vulkan | ROCm |
|---|---:|---:|
| Frozen evaluator pass rate | 86.60% | 86.40% |
| Expected first-turn arguments correct | 96.90% | 96.90% |
| Invalid tool calls | 1.01% | 1.00% |
| Cases passed | 433 | 432 |
| Cases failed | 67 | 68 |
| Tool calls requested | 596 | 600 |
| Invalid tool calls (count) | 6 | 6 |
| Forbidden tool attempts | 7 | 7 |
| Unauthorized tool executions | 0 | 0 |
| Request errors | 0 | 0 |

| Category | Vulkan | ROCm |
|---|---:|---:|
| argument_types | 69/80 | 68/80 |
| error_recovery | 24/30 | 24/30 |
| sequential_multi_tool | 58/100 | 58/100 |
| single_tool | 100/100 | 100/100 |
| streaming_tool_call | 50/50 | 50/50 |
| thinking_separation | 30/30 | 30/30 |
| tool_result_round_trip | 80/80 | 80/80 |
| unauthorized_injection | 22/30 | 22/30 |

| Streaming comparison | Vulkan | ROCm |
|---|---:|---:|
| Identical tool names and raw argument strings | 50/50 | 50/50 |

The original 500-case scores can be compared descriptively with the new 90% task floor.
The new argument floor requires checking all required tool steps. The original first-turn
metric does not measure that requirement.

## Native parser fixtures

Fixture SHA256 `e1dd8382c633f5fb197a13cd95199596276f9043d06745395cea6ec5d3aacb0d`

- Vulkan recorded 6 FAIL, 20 PASS in `tc-fixtures-d7a1cda72c9f4f208b804ba8fa100f5a`.
  - `fx-valid-whitespace-between-tags` FAIL. Parsed calls differ from the fixed expectation.
  - `fx-invalid-duplicate-param` FAIL. Malformed structured tool call.
  - `fx-invalid-missing-close-param` FAIL. Malformed structured tool call.
  - `fx-invalid-unclosed-function` FAIL. Malformed structured tool call.
  - `fx-invalid-enum-outside-schema` FAIL. Parsed calls include an unapproved name, parameter or value.
  - `fx-invalid-unclosed-cdata` FAIL. Malformed structured tool call.
- ROCm recorded 6 FAIL, 20 PASS in `tc-fixtures-277dc6c5494a484aa1a7899c68b23313`.
  - `fx-valid-whitespace-between-tags` FAIL. Parsed calls differ from the fixed expectation.
  - `fx-invalid-duplicate-param` FAIL. Malformed structured tool call.
  - `fx-invalid-missing-close-param` FAIL. Malformed structured tool call.
  - `fx-invalid-unclosed-function` FAIL. Malformed structured tool call.
  - `fx-invalid-enum-outside-schema` FAIL. Parsed calls include an unapproved name, parameter or value.
  - `fx-invalid-unclosed-cdata` FAIL. Malformed structured tool call.

Assistant continuation supplies the fixed text. Successful replies carry a token trace showing that
the model sampled only EOS. Known native parser rejections are recorded as such.

## Scoring notes

- The frozen two-order cases require a single first-turn call for a randomly chosen order.
  A parallel lookup of both independent orders can fail this expectation while returning the requested facts.
- Argument accuracy covers the expected first-turn arguments present in the frozen definitions,
  including the loss of credit for missing calls.
- The simulator enforces an allowlist and validates arguments. These runs measure protections in
  the benchmark host with synthetic data.
- The frozen recovery score penalizes schema rejection of the unsupported warehouse even when
  the model subsequently lists supported warehouses. Report recovery and schema conformance separately.

### Ticket argument trace audit (v1)

The frozen scorer checks the first lookup, tool names and the final ticket ID for these cases.
This separate audit checks the later ticket subject, priority and tags against the fixed prompt.

- Vulkan: 15/22 frozen passes had mismatched ticket arguments.
  Case IDs `tc-seq-0001, tc-seq-0004, tc-seq-0012, tc-seq-0013, tc-seq-0017, tc-seq-0030, tc-seq-0031, tc-seq-0037, tc-seq-0041, tc-seq-0047, tc-seq-0073, tc-seq-0076, tc-seq-0082, tc-seq-0095, tc-seq-0100`.
- ROCm: 15/22 frozen passes had mismatched ticket arguments.
  Case IDs `tc-seq-0001, tc-seq-0004, tc-seq-0012, tc-seq-0013, tc-seq-0017, tc-seq-0030, tc-seq-0031, tc-seq-0037, tc-seq-0041, tc-seq-0047, tc-seq-0073, tc-seq-0076, tc-seq-0082, tc-seq-0095, tc-seq-0100`.

### Strict JSON trace audit (v1)

- Vulkan rejected 0/596 previously decoded argument objects under strict JSON rules.
- ROCm rejected 0/600 previously decoded argument objects under strict JSON rules.

## Evidence

- Vulkan run metadata, case traces, metrics and counters are in `evidence/IJ0/protocol/tool_calling_test_vulkan/`.
- ROCm run metadata, case traces, metrics and counters are in `evidence/IJ0/protocol/tool_calling_test_rocm/`.
