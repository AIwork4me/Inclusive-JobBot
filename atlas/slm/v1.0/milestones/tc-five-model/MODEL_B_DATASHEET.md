# LiquidAI/LFM3-1.7B TC-V3 datasheet

Lfm3ForCausalLM has 1,728,801,536 parameters in the frozen upstream source.
The measured GGUF uses Q8_0 and has SHA256 `8f6b24182258205e9e01e21f1f24a1f208c1e8115578825d202ce39976af20b6`.
Weight file size in bytes is 1846238496.
The source license metadata is `other`. See the pinned source identity for revision details.
Measurements use gfx1151 via vulkan, an 8,192-token configured context, llama.cpp b12359-b1b770d90d94cad9e9ea5b993bdbc383a522fb28 and Antigravity SDK 0.1.24.
Exact runtime and template digests are in the [capability matrix](CAPABILITY_MATRIX.json).

## Native and SDK capability

| Track | Metric | PASS | FAIL | BLOCKED | NOT_RUN | Applicable | Full |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| direct_first | BUSINESS_FACT_CORRECTNESS | 372 | 1 | 27 | 0 | 400 | 500 |
| direct_first | OUTPUT_CONTRACT_COMPLIANCE | 476 | 18 | 6 | 0 | 500 | 500 |
| direct_first | EXECUTION_PROCESS_CORRECTNESS | 455 | 39 | 6 | 0 | 500 | 500 |
| direct_first | STRICT_END_TO_END_SUCCESS | 0 | 0 | 500 | 0 | 500 | 500 |
| direct_first | FIRST_TOOL_CHOICE | 482 | 18 | 0 | 0 | 500 | 500 |
| direct_first | REQUIRED_ACTION_COVERAGE | 477 | 17 | 6 | 0 | 500 | 500 |
| direct_first | EXACT_ACTION_SEQUENCE | 455 | 39 | 6 | 0 | 500 | 500 |
| direct_first | RESULT_DELIVERY | 433 | 0 | 17 | 0 | 450 | 500 |
| direct_first | RESULT_COMPREHENSION | 395 | 18 | 37 | 0 | 450 | 500 |
| direct_first | TERMINATION_CORRECTNESS | 455 | 39 | 6 | 0 | 500 | 500 |
| direct_first | QUALIFIED_BUSINESS_COMPLETION | 361 | 39 | 0 | 0 | 400 | 500 |
| direct_first | authorization | 44 | 0 | 6 | 0 | 50 | 500 |
| direct_first | entity_binding | 407 | 29 | 14 | 0 | 450 | 500 |
| direct_first | required_arguments | 407 | 29 | 14 | 0 | 450 | 500 |
| sdk_first | BUSINESS_FACT_CORRECTNESS | 312 | 16 | 72 | 0 | 400 | 500 |
| sdk_first | OUTPUT_CONTRACT_COMPLIANCE | 398 | 102 | 0 | 0 | 500 | 500 |
| sdk_first | EXECUTION_PROCESS_CORRECTNESS | 357 | 143 | 0 | 0 | 500 | 500 |
| sdk_first | STRICT_END_TO_END_SUCCESS | 0 | 0 | 500 | 0 | 500 | 500 |
| sdk_first | FIRST_TOOL_CHOICE | 491 | 9 | 0 | 0 | 500 | 500 |
| sdk_first | REQUIRED_ACTION_COVERAGE | 491 | 9 | 0 | 0 | 500 | 500 |
| sdk_first | EXACT_ACTION_SEQUENCE | 350 | 150 | 0 | 0 | 500 | 500 |
| sdk_first | RESULT_DELIVERY | 425 | 0 | 25 | 0 | 450 | 500 |
| sdk_first | RESULT_COMPREHENSION | 350 | 17 | 83 | 0 | 450 | 500 |
| sdk_first | TERMINATION_CORRECTNESS | 318 | 182 | 0 | 0 | 500 | 500 |
| sdk_first | QUALIFIED_BUSINESS_COMPLETION | 218 | 182 | 0 | 0 | 400 | 500 |
| sdk_first | authorization | 49 | 0 | 1 | 0 | 50 | 500 |
| sdk_first | entity_binding | 302 | 99 | 49 | 0 | 450 | 500 |
| sdk_first | required_arguments | 302 | 99 | 49 | 0 | 450 | 500 |
| sdk_repeat | BUSINESS_FACT_CORRECTNESS | 99 | 8 | 13 | 0 | 120 | 150 |
| sdk_repeat | OUTPUT_CONTRACT_COMPLIANCE | 128 | 22 | 0 | 0 | 150 | 150 |
| sdk_repeat | EXECUTION_PROCESS_CORRECTNESS | 120 | 30 | 0 | 0 | 150 | 150 |
| sdk_repeat | STRICT_END_TO_END_SUCCESS | 0 | 0 | 150 | 0 | 150 | 150 |
| sdk_repeat | FIRST_TOOL_CHOICE | 150 | 0 | 0 | 0 | 150 | 150 |
| sdk_repeat | REQUIRED_ACTION_COVERAGE | 150 | 0 | 0 | 0 | 150 | 150 |
| sdk_repeat | EXACT_ACTION_SEQUENCE | 116 | 34 | 0 | 0 | 150 | 150 |
| sdk_repeat | RESULT_DELIVERY | 135 | 0 | 0 | 0 | 135 | 150 |
| sdk_repeat | RESULT_COMPREHENSION | 111 | 8 | 16 | 0 | 135 | 150 |
| sdk_repeat | TERMINATION_CORRECTNESS | 103 | 47 | 0 | 0 | 150 | 150 |
| sdk_repeat | QUALIFIED_BUSINESS_COMPLETION | 73 | 47 | 0 | 0 | 120 | 150 |
| sdk_repeat | authorization | 15 | 0 | 0 | 0 | 15 | 150 |
| sdk_repeat | entity_binding | 101 | 29 | 5 | 0 | 135 | 150 |
| sdk_repeat | required_arguments | 101 | 29 | 5 | 0 | 135 | 150 |
| sdk_streaming | BUSINESS_FACT_CORRECTNESS | 314 | 17 | 69 | 0 | 400 | 500 |
| sdk_streaming | OUTPUT_CONTRACT_COMPLIANCE | 402 | 98 | 0 | 0 | 500 | 500 |
| sdk_streaming | EXECUTION_PROCESS_CORRECTNESS | 359 | 141 | 0 | 0 | 500 | 500 |
| sdk_streaming | STRICT_END_TO_END_SUCCESS | 0 | 0 | 500 | 0 | 500 | 500 |
| sdk_streaming | FIRST_TOOL_CHOICE | 493 | 7 | 0 | 0 | 500 | 500 |
| sdk_streaming | REQUIRED_ACTION_COVERAGE | 493 | 7 | 0 | 0 | 500 | 500 |
| sdk_streaming | EXACT_ACTION_SEQUENCE | 352 | 148 | 0 | 0 | 500 | 500 |
| sdk_streaming | RESULT_DELIVERY | 426 | 0 | 24 | 0 | 450 | 500 |
| sdk_streaming | RESULT_COMPREHENSION | 354 | 18 | 78 | 0 | 450 | 500 |
| sdk_streaming | TERMINATION_CORRECTNESS | 317 | 183 | 0 | 0 | 500 | 500 |
| sdk_streaming | QUALIFIED_BUSINESS_COMPLETION | 220 | 180 | 0 | 0 | 400 | 500 |
| sdk_streaming | authorization | 47 | 0 | 3 | 0 | 50 | 500 |
| sdk_streaming | entity_binding | 303 | 93 | 54 | 0 | 450 | 500 |
| sdk_streaming | required_arguments | 303 | 93 | 54 | 0 | 450 | 500 |

## Failure signature and compensation

Observed signature — Reduced scoped completion through SDK.
HYPOTHESIS — Compact Result Codec. Use the frozen 12-task holdout. Keep the model, tools, world, seed and evaluation contract paired.
Trial and seal references are listed by metric in the [capability matrix](CAPABILITY_MATRIX.json).

## Resource envelope

| Track | Resource | Observed | P50 | P95 |
| --- | --- | ---: | ---: | ---: |
| direct_first | input_tokens | 494/500 | 536 | 819 |
| direct_first | output_tokens | 494/500 | 56 | 111 |
| direct_first | total_tokens | 494/500 | 594 | 897 |
| direct_first | model_requests | 500/500 | 2 | 3 |
| direct_first | provider_inference_ms | 494/500 | 736.171 | 1574.412 |
| direct_first | end_to_end_wall_ms | 0/500 | NOT_RUN | NOT_RUN |
| direct_first | sdk_boundary_wall_ms_sum | 0/500 | NOT_RUN | NOT_RUN |
| direct_first | actual_tool_executions | 494/500 | 1 | 2 |
| direct_first | context_consumption | 0/500 | NOT_RUN | NOT_RUN |
| sdk_first | input_tokens | 500/500 | 3375 | 4772 |
| sdk_first | output_tokens | 500/500 | 71 | 130 |
| sdk_first | total_tokens | 500/500 | 3449 | 4885 |
| sdk_first | model_requests | 500/500 | 3 | 4 |
| sdk_first | provider_inference_ms | 500/500 | 1766.336 | 2773.454 |
| sdk_first | end_to_end_wall_ms | 0/500 | NOT_RUN | NOT_RUN |
| sdk_first | sdk_boundary_wall_ms_sum | 500/500 | 1874.02 | 2887.55 |
| sdk_first | actual_tool_executions | 500/500 | 2 | 4 |
| sdk_first | context_consumption | 0/500 | NOT_RUN | NOT_RUN |
| sdk_streaming | input_tokens | 500/500 | 3364 | 4886 |
| sdk_streaming | output_tokens | 500/500 | 71 | 129 |
| sdk_streaming | total_tokens | 500/500 | 3435 | 5005 |
| sdk_streaming | model_requests | 500/500 | 3 | 4 |
| sdk_streaming | provider_inference_ms | 500/500 | 1754.11 | 2778.991 |
| sdk_streaming | end_to_end_wall_ms | 0/500 | NOT_RUN | NOT_RUN |
| sdk_streaming | sdk_boundary_wall_ms_sum | 500/500 | 1849.7800000000002 | 2897.89 |
| sdk_streaming | actual_tool_executions | 500/500 | 2 | 4 |
| sdk_streaming | context_consumption | 0/500 | NOT_RUN | NOT_RUN |
| sdk_repeat | input_tokens | 150/150 | 3366 | 4647 |
| sdk_repeat | output_tokens | 150/150 | 72 | 130 |
| sdk_repeat | total_tokens | 150/150 | 3435 | 4752 |
| sdk_repeat | model_requests | 150/150 | 3 | 4 |
| sdk_repeat | provider_inference_ms | 150/150 | 1732.469 | 2617.7780000000002 |
| sdk_repeat | end_to_end_wall_ms | 0/150 | NOT_RUN | NOT_RUN |
| sdk_repeat | sdk_boundary_wall_ms_sum | 150/150 | 1832.53 | 2718.83 |
| sdk_repeat | actual_tool_executions | 150/150 | 2 | 3 |
| sdk_repeat | context_consumption | 0/150 | NOT_RUN | NOT_RUN |

The matrix records session-level GPU memory and the measured resource totals per verified outcome.
Strict D25, production job accuracy, planning depth, autonomy and NPU performance remain unqualified.
