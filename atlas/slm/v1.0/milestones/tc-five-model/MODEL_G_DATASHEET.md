# google/gemma-4-E2B-it TC-V3 datasheet

Gemma4ForConditionalGeneration has 5,123,178,051 parameters in the frozen upstream source.
The measured GGUF uses Q8_0 and has SHA256 `c36d5e6be0d91124d8b995f5ad4e1ab0d307f6d95cdd08308820350dbd96ad15`.
Weight file size in bytes is 4967491520.
The source license metadata is `apache-2.0`. See the pinned source identity for revision details.
Measurements use gfx1151 via vulkan, an 8,192-token configured context, llama.cpp b12359-b1b770d90d94cad9e9ea5b993bdbc383a522fb28 and Antigravity SDK 0.1.24.
Exact runtime and template digests are in the [capability matrix](CAPABILITY_MATRIX.json).

## Native and SDK capability

| Track | Metric | PASS | FAIL | BLOCKED | NOT_RUN | Applicable | Full |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| direct_first | BUSINESS_FACT_CORRECTNESS | 367 | 33 | 0 | 0 | 400 | 500 |
| direct_first | OUTPUT_CONTRACT_COMPLIANCE | 0 | 500 | 0 | 0 | 500 | 500 |
| direct_first | EXECUTION_PROCESS_CORRECTNESS | 483 | 17 | 0 | 0 | 500 | 500 |
| direct_first | STRICT_END_TO_END_SUCCESS | 0 | 0 | 500 | 0 | 500 | 500 |
| direct_first | FIRST_TOOL_CHOICE | 483 | 17 | 0 | 0 | 500 | 500 |
| direct_first | REQUIRED_ACTION_COVERAGE | 500 | 0 | 0 | 0 | 500 | 500 |
| direct_first | EXACT_ACTION_SEQUENCE | 483 | 17 | 0 | 0 | 500 | 500 |
| direct_first | RESULT_DELIVERY | 450 | 0 | 0 | 0 | 450 | 500 |
| direct_first | RESULT_COMPREHENSION | 392 | 58 | 0 | 0 | 450 | 500 |
| direct_first | TERMINATION_CORRECTNESS | 483 | 17 | 0 | 0 | 500 | 500 |
| direct_first | QUALIFIED_BUSINESS_COMPLETION | 0 | 400 | 0 | 0 | 400 | 500 |
| direct_first | authorization | 50 | 0 | 0 | 0 | 50 | 500 |
| direct_first | entity_binding | 450 | 0 | 0 | 0 | 450 | 500 |
| direct_first | required_arguments | 450 | 0 | 0 | 0 | 450 | 500 |
| sdk_first | BUSINESS_FACT_CORRECTNESS | 339 | 50 | 11 | 0 | 400 | 500 |
| sdk_first | OUTPUT_CONTRACT_COMPLIANCE | 0 | 500 | 0 | 0 | 500 | 500 |
| sdk_first | EXECUTION_PROCESS_CORRECTNESS | 489 | 11 | 0 | 0 | 500 | 500 |
| sdk_first | STRICT_END_TO_END_SUCCESS | 0 | 0 | 500 | 0 | 500 | 500 |
| sdk_first | FIRST_TOOL_CHOICE | 500 | 0 | 0 | 0 | 500 | 500 |
| sdk_first | REQUIRED_ACTION_COVERAGE | 489 | 11 | 0 | 0 | 500 | 500 |
| sdk_first | EXACT_ACTION_SEQUENCE | 489 | 11 | 0 | 0 | 500 | 500 |
| sdk_first | RESULT_DELIVERY | 439 | 0 | 11 | 0 | 450 | 500 |
| sdk_first | RESULT_COMPREHENSION | 378 | 61 | 11 | 0 | 450 | 500 |
| sdk_first | TERMINATION_CORRECTNESS | 483 | 17 | 0 | 0 | 500 | 500 |
| sdk_first | QUALIFIED_BUSINESS_COMPLETION | 0 | 400 | 0 | 0 | 400 | 500 |
| sdk_first | authorization | 50 | 0 | 0 | 0 | 50 | 500 |
| sdk_first | entity_binding | 439 | 11 | 0 | 0 | 450 | 500 |
| sdk_first | required_arguments | 439 | 11 | 0 | 0 | 450 | 500 |
| sdk_repeat | BUSINESS_FACT_CORRECTNESS | 96 | 15 | 9 | 0 | 120 | 150 |
| sdk_repeat | OUTPUT_CONTRACT_COMPLIANCE | 0 | 150 | 0 | 0 | 150 | 150 |
| sdk_repeat | EXECUTION_PROCESS_CORRECTNESS | 141 | 9 | 0 | 0 | 150 | 150 |
| sdk_repeat | STRICT_END_TO_END_SUCCESS | 0 | 0 | 150 | 0 | 150 | 150 |
| sdk_repeat | FIRST_TOOL_CHOICE | 150 | 0 | 0 | 0 | 150 | 150 |
| sdk_repeat | REQUIRED_ACTION_COVERAGE | 141 | 9 | 0 | 0 | 150 | 150 |
| sdk_repeat | EXACT_ACTION_SEQUENCE | 141 | 9 | 0 | 0 | 150 | 150 |
| sdk_repeat | RESULT_DELIVERY | 126 | 0 | 9 | 0 | 135 | 150 |
| sdk_repeat | RESULT_COMPREHENSION | 106 | 20 | 9 | 0 | 135 | 150 |
| sdk_repeat | TERMINATION_CORRECTNESS | 133 | 17 | 0 | 0 | 150 | 150 |
| sdk_repeat | QUALIFIED_BUSINESS_COMPLETION | 0 | 120 | 0 | 0 | 120 | 150 |
| sdk_repeat | authorization | 15 | 0 | 0 | 0 | 15 | 150 |
| sdk_repeat | entity_binding | 126 | 9 | 0 | 0 | 135 | 150 |
| sdk_repeat | required_arguments | 126 | 9 | 0 | 0 | 135 | 150 |
| sdk_streaming | BUSINESS_FACT_CORRECTNESS | 338 | 50 | 12 | 0 | 400 | 500 |
| sdk_streaming | OUTPUT_CONTRACT_COMPLIANCE | 0 | 500 | 0 | 0 | 500 | 500 |
| sdk_streaming | EXECUTION_PROCESS_CORRECTNESS | 488 | 12 | 0 | 0 | 500 | 500 |
| sdk_streaming | STRICT_END_TO_END_SUCCESS | 0 | 0 | 500 | 0 | 500 | 500 |
| sdk_streaming | FIRST_TOOL_CHOICE | 500 | 0 | 0 | 0 | 500 | 500 |
| sdk_streaming | REQUIRED_ACTION_COVERAGE | 488 | 12 | 0 | 0 | 500 | 500 |
| sdk_streaming | EXACT_ACTION_SEQUENCE | 488 | 12 | 0 | 0 | 500 | 500 |
| sdk_streaming | RESULT_DELIVERY | 438 | 0 | 12 | 0 | 450 | 500 |
| sdk_streaming | RESULT_COMPREHENSION | 375 | 63 | 12 | 0 | 450 | 500 |
| sdk_streaming | TERMINATION_CORRECTNESS | 483 | 17 | 0 | 0 | 500 | 500 |
| sdk_streaming | QUALIFIED_BUSINESS_COMPLETION | 0 | 400 | 0 | 0 | 400 | 500 |
| sdk_streaming | authorization | 50 | 0 | 0 | 0 | 50 | 500 |
| sdk_streaming | entity_binding | 438 | 12 | 0 | 0 | 450 | 500 |
| sdk_streaming | required_arguments | 438 | 12 | 0 | 0 | 450 | 500 |

## Failure signature and compensation

Observed signature — Exact terminal output fails despite substantial correct tool execution.
HYPOTHESIS — Result Codec and Structured Output Contract. Use the matched case-level differences to select a candidate intervention, then test it on independent tasks.
Trial and seal references are listed by metric in the [capability matrix](CAPABILITY_MATRIX.json).

## Resource envelope

| Track | Resource | Observed | P50 | P95 |
| --- | --- | ---: | ---: | ---: |
| direct_first | input_tokens | 500/500 | 430 | 757 |
| direct_first | output_tokens | 500/500 | 66 | 138 |
| direct_first | total_tokens | 500/500 | 499 | 841 |
| direct_first | model_requests | 500/500 | 2 | 3 |
| direct_first | provider_inference_ms | 500/500 | 1066.368 | 2158.2490000000003 |
| direct_first | end_to_end_wall_ms | 0/500 | NOT_RUN | NOT_RUN |
| direct_first | sdk_boundary_wall_ms_sum | 0/500 | NOT_RUN | NOT_RUN |
| direct_first | actual_tool_executions | 500/500 | 1 | 2 |
| direct_first | context_consumption | 0/500 | NOT_RUN | NOT_RUN |
| sdk_first | input_tokens | 500/500 | 2545 | 4041 |
| sdk_first | output_tokens | 500/500 | 65 | 143 |
| sdk_first | total_tokens | 500/500 | 2612 | 4127 |
| sdk_first | model_requests | 500/500 | 2 | 3 |
| sdk_first | provider_inference_ms | 500/500 | 1570.55 | 2816.718 |
| sdk_first | end_to_end_wall_ms | 0/500 | NOT_RUN | NOT_RUN |
| sdk_first | sdk_boundary_wall_ms_sum | 500/500 | 1643.3899999999999 | 2889.23 |
| sdk_first | actual_tool_executions | 500/500 | 1 | 2 |
| sdk_first | context_consumption | 0/500 | NOT_RUN | NOT_RUN |
| sdk_streaming | input_tokens | 500/500 | 2546 | 4041 |
| sdk_streaming | output_tokens | 500/500 | 65 | 143 |
| sdk_streaming | total_tokens | 500/500 | 2613 | 4125 |
| sdk_streaming | model_requests | 500/500 | 2 | 3 |
| sdk_streaming | provider_inference_ms | 500/500 | 1566.663 | 2802.302 |
| sdk_streaming | end_to_end_wall_ms | 0/500 | NOT_RUN | NOT_RUN |
| sdk_streaming | sdk_boundary_wall_ms_sum | 500/500 | 1635.89 | 2875.86 |
| sdk_streaming | actual_tool_executions | 500/500 | 1 | 2 |
| sdk_streaming | context_consumption | 0/500 | NOT_RUN | NOT_RUN |
| sdk_repeat | input_tokens | 150/150 | 2536 | 4026 |
| sdk_repeat | output_tokens | 150/150 | 60 | 143 |
| sdk_repeat | total_tokens | 150/150 | 2597 | 4111 |
| sdk_repeat | model_requests | 150/150 | 2 | 3 |
| sdk_repeat | provider_inference_ms | 150/150 | 1505.999 | 2868.44 |
| sdk_repeat | end_to_end_wall_ms | 0/150 | NOT_RUN | NOT_RUN |
| sdk_repeat | sdk_boundary_wall_ms_sum | 150/150 | 1586.08 | 2937.7799999999997 |
| sdk_repeat | actual_tool_executions | 150/150 | 1 | 2 |
| sdk_repeat | context_consumption | 0/150 | NOT_RUN | NOT_RUN |

The matrix records session-level GPU memory and the measured resource totals per verified outcome.
Strict D25, production job accuracy, planning depth, autonomy and NPU performance remain unqualified.

The 2.3 billion figure is effective capacity. The source count includes per-layer embeddings. [Radeon admission](../../../../../reports/SLM11_GEMMA4_RADEON_ADMISSION.md)
