# Qwen/Qwen3.5-2B TC-V3 datasheet

Qwen3_5ForConditionalGeneration has 2,274,069,824 parameters in the frozen upstream source.
The measured GGUF uses Q8_0 and has SHA256 `1b04acba824817554f4ce23639bc8495ff70453b8fcb047900c731521021f2c1`.
Weight file size in bytes is 2012012800.
The source license metadata is `apache-2.0`. See the pinned source identity for revision details.
Measurements use gfx1151 via vulkan, an 8,192-token configured context, llama.cpp b12359-b1b770d90d94cad9e9ea5b993bdbc383a522fb28 and Antigravity SDK 0.1.24.
Exact runtime and template digests are in the [capability matrix](CAPABILITY_MATRIX.json).

## Native and SDK capability

| Track | Metric | PASS | FAIL | BLOCKED | NOT_RUN | Applicable | Full |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| direct_first | BUSINESS_FACT_CORRECTNESS | 394 | 0 | 6 | 0 | 400 | 500 |
| direct_first | OUTPUT_CONTRACT_COMPLIANCE | 300 | 200 | 0 | 0 | 500 | 500 |
| direct_first | EXECUTION_PROCESS_CORRECTNESS | 462 | 38 | 0 | 0 | 500 | 500 |
| direct_first | STRICT_END_TO_END_SUCCESS | 0 | 0 | 500 | 0 | 500 | 500 |
| direct_first | FIRST_TOOL_CHOICE | 463 | 37 | 0 | 0 | 500 | 500 |
| direct_first | REQUIRED_ACTION_COVERAGE | 494 | 6 | 0 | 0 | 500 | 500 |
| direct_first | EXACT_ACTION_SEQUENCE | 412 | 88 | 0 | 0 | 500 | 500 |
| direct_first | RESULT_DELIVERY | 444 | 0 | 6 | 0 | 450 | 500 |
| direct_first | RESULT_COMPREHENSION | 427 | 0 | 23 | 0 | 450 | 500 |
| direct_first | TERMINATION_CORRECTNESS | 411 | 89 | 0 | 0 | 500 | 500 |
| direct_first | QUALIFIED_BUSINESS_COMPLETION | 272 | 128 | 0 | 0 | 400 | 500 |
| direct_first | authorization | 33 | 0 | 17 | 0 | 50 | 500 |
| direct_first | entity_binding | 393 | 40 | 17 | 0 | 450 | 500 |
| direct_first | required_arguments | 393 | 40 | 17 | 0 | 450 | 500 |
| sdk_first | BUSINESS_FACT_CORRECTNESS | 316 | 38 | 46 | 0 | 400 | 500 |
| sdk_first | OUTPUT_CONTRACT_COMPLIANCE | 85 | 415 | 0 | 0 | 500 | 500 |
| sdk_first | EXECUTION_PROCESS_CORRECTNESS | 443 | 57 | 0 | 0 | 500 | 500 |
| sdk_first | STRICT_END_TO_END_SUCCESS | 0 | 0 | 500 | 0 | 500 | 500 |
| sdk_first | FIRST_TOOL_CHOICE | 449 | 51 | 0 | 0 | 500 | 500 |
| sdk_first | REQUIRED_ACTION_COVERAGE | 466 | 34 | 0 | 0 | 500 | 500 |
| sdk_first | EXACT_ACTION_SEQUENCE | 420 | 80 | 0 | 0 | 500 | 500 |
| sdk_first | RESULT_DELIVERY | 410 | 0 | 40 | 0 | 450 | 500 |
| sdk_first | RESULT_COMPREHENSION | 356 | 48 | 46 | 0 | 450 | 500 |
| sdk_first | TERMINATION_CORRECTNESS | 402 | 98 | 0 | 0 | 500 | 500 |
| sdk_first | QUALIFIED_BUSINESS_COMPLETION | 80 | 320 | 0 | 0 | 400 | 500 |
| sdk_first | authorization | 50 | 0 | 0 | 0 | 50 | 500 |
| sdk_first | entity_binding | 387 | 57 | 6 | 0 | 450 | 500 |
| sdk_first | required_arguments | 387 | 57 | 6 | 0 | 450 | 500 |
| sdk_repeat | BUSINESS_FACT_CORRECTNESS | 96 | 11 | 13 | 0 | 120 | 150 |
| sdk_repeat | OUTPUT_CONTRACT_COMPLIANCE | 22 | 128 | 0 | 0 | 150 | 150 |
| sdk_repeat | EXECUTION_PROCESS_CORRECTNESS | 129 | 21 | 0 | 0 | 150 | 150 |
| sdk_repeat | STRICT_END_TO_END_SUCCESS | 0 | 0 | 150 | 0 | 150 | 150 |
| sdk_repeat | FIRST_TOOL_CHOICE | 129 | 21 | 0 | 0 | 150 | 150 |
| sdk_repeat | REQUIRED_ACTION_COVERAGE | 141 | 9 | 0 | 0 | 150 | 150 |
| sdk_repeat | EXACT_ACTION_SEQUENCE | 121 | 29 | 0 | 0 | 150 | 150 |
| sdk_repeat | RESULT_DELIVERY | 126 | 0 | 9 | 0 | 135 | 150 |
| sdk_repeat | RESULT_COMPREHENSION | 108 | 14 | 13 | 0 | 135 | 150 |
| sdk_repeat | TERMINATION_CORRECTNESS | 121 | 29 | 0 | 0 | 150 | 150 |
| sdk_repeat | QUALIFIED_BUSINESS_COMPLETION | 21 | 99 | 0 | 0 | 120 | 150 |
| sdk_repeat | authorization | 15 | 0 | 0 | 0 | 15 | 150 |
| sdk_repeat | entity_binding | 118 | 17 | 0 | 0 | 135 | 150 |
| sdk_repeat | required_arguments | 118 | 17 | 0 | 0 | 135 | 150 |
| sdk_streaming | BUSINESS_FACT_CORRECTNESS | 316 | 40 | 44 | 0 | 400 | 500 |
| sdk_streaming | OUTPUT_CONTRACT_COMPLIANCE | 81 | 419 | 0 | 0 | 500 | 500 |
| sdk_streaming | EXECUTION_PROCESS_CORRECTNESS | 442 | 58 | 0 | 0 | 500 | 500 |
| sdk_streaming | STRICT_END_TO_END_SUCCESS | 0 | 0 | 500 | 0 | 500 | 500 |
| sdk_streaming | FIRST_TOOL_CHOICE | 449 | 51 | 0 | 0 | 500 | 500 |
| sdk_streaming | REQUIRED_ACTION_COVERAGE | 466 | 34 | 0 | 0 | 500 | 500 |
| sdk_streaming | EXACT_ACTION_SEQUENCE | 422 | 78 | 0 | 0 | 500 | 500 |
| sdk_streaming | RESULT_DELIVERY | 409 | 0 | 41 | 0 | 450 | 500 |
| sdk_streaming | RESULT_COMPREHENSION | 359 | 47 | 44 | 0 | 450 | 500 |
| sdk_streaming | TERMINATION_CORRECTNESS | 404 | 96 | 0 | 0 | 500 | 500 |
| sdk_streaming | QUALIFIED_BUSINESS_COMPLETION | 78 | 322 | 0 | 0 | 400 | 500 |
| sdk_streaming | authorization | 50 | 0 | 0 | 0 | 50 | 500 |
| sdk_streaming | entity_binding | 389 | 53 | 8 | 0 | 450 | 500 |
| sdk_streaming | required_arguments | 389 | 53 | 8 | 0 | 450 | 500 |

## Failure signature and compensation

Observed signature — Output contract failures despite successful execution.
HYPOTHESIS — Structured Output Contract. Compare native, constrained, normalized and retry-assisted arms. Reject ambiguous values and forbid access to private expected answers.
Trial and seal references are listed by metric in the [capability matrix](CAPABILITY_MATRIX.json).

## Resource envelope

| Track | Resource | Observed | P50 | P95 |
| --- | --- | ---: | ---: | ---: |
| direct_first | input_tokens | 500/500 | 1016 | 1704 |
| direct_first | output_tokens | 500/500 | 95 | 141 |
| direct_first | total_tokens | 500/500 | 1122 | 1845 |
| direct_first | model_requests | 500/500 | 2 | 4 |
| direct_first | provider_inference_ms | 500/500 | 1548.861 | 2120.973 |
| direct_first | end_to_end_wall_ms | 0/500 | NOT_RUN | NOT_RUN |
| direct_first | sdk_boundary_wall_ms_sum | 0/500 | NOT_RUN | NOT_RUN |
| direct_first | actual_tool_executions | 500/500 | 1 | 2 |
| direct_first | context_consumption | 0/500 | NOT_RUN | NOT_RUN |
| sdk_first | input_tokens | 500/500 | 3041 | 4731 |
| sdk_first | output_tokens | 500/500 | 92 | 156 |
| sdk_first | total_tokens | 500/500 | 3105 | 4830 |
| sdk_first | model_requests | 500/500 | 2 | 3 |
| sdk_first | provider_inference_ms | 500/500 | 2437.002 | 3429.897 |
| sdk_first | end_to_end_wall_ms | 0/500 | NOT_RUN | NOT_RUN |
| sdk_first | sdk_boundary_wall_ms_sum | 500/500 | 2537.67 | 3575.05 |
| sdk_first | actual_tool_executions | 500/500 | 1 | 2 |
| sdk_first | context_consumption | 0/500 | NOT_RUN | NOT_RUN |
| sdk_streaming | input_tokens | 500/500 | 3033 | 4681 |
| sdk_streaming | output_tokens | 500/500 | 73 | 157 |
| sdk_streaming | total_tokens | 500/500 | 3097 | 4779 |
| sdk_streaming | model_requests | 500/500 | 2 | 3 |
| sdk_streaming | provider_inference_ms | 500/500 | 2388.238 | 3039.844 |
| sdk_streaming | end_to_end_wall_ms | 0/500 | NOT_RUN | NOT_RUN |
| sdk_streaming | sdk_boundary_wall_ms_sum | 500/500 | 2506.03 | 3127.9 |
| sdk_streaming | actual_tool_executions | 500/500 | 1 | 2 |
| sdk_streaming | context_consumption | 0/500 | NOT_RUN | NOT_RUN |
| sdk_repeat | input_tokens | 150/150 | 3106 | 5968 |
| sdk_repeat | output_tokens | 150/150 | 98 | 157 |
| sdk_repeat | total_tokens | 150/150 | 3263 | 6120 |
| sdk_repeat | model_requests | 150/150 | 2 | 4 |
| sdk_repeat | provider_inference_ms | 150/150 | 2470.603 | 3411.802 |
| sdk_repeat | end_to_end_wall_ms | 0/150 | NOT_RUN | NOT_RUN |
| sdk_repeat | sdk_boundary_wall_ms_sum | 150/150 | 2579.67 | 3563.56 |
| sdk_repeat | actual_tool_executions | 150/150 | 2 | 4 |
| sdk_repeat | context_consumption | 0/150 | NOT_RUN | NOT_RUN |

The matrix records session-level GPU memory and the measured resource totals per verified outcome.
Strict D25, production job accuracy, planning depth, autonomy and NPU performance remain unqualified.
