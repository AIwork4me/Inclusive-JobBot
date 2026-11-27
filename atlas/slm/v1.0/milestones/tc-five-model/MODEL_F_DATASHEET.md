# mistralai/Ministral-3-3B-Instruct-2512-GGUF TC-V3 datasheet

Exact architecture and parameter metadata are unavailable in the frozen source record.
The measured GGUF uses Q8_0 and has SHA256 `8c2b72eb5861304fcfd5e82f1eddd6efa4115737f4239fd216a028a8852413ef`.
Weight file size in bytes is 3652204704.
The source license metadata is `apache-2.0`. See the pinned source identity for revision details.
Measurements use gfx1151 via vulkan, an 8,192-token configured context, llama.cpp b12359-b1b770d90d94cad9e9ea5b993bdbc383a522fb28 and Antigravity SDK 0.1.24.
Exact runtime and template digests are in the [capability matrix](CAPABILITY_MATRIX.json).

## Native and SDK capability

| Track | Metric | PASS | FAIL | BLOCKED | NOT_RUN | Applicable | Full |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| direct_first | BUSINESS_FACT_CORRECTNESS | 340 | 5 | 55 | 0 | 400 | 500 |
| direct_first | OUTPUT_CONTRACT_COMPLIANCE | 111 | 389 | 0 | 0 | 500 | 500 |
| direct_first | EXECUTION_PROCESS_CORRECTNESS | 419 | 81 | 0 | 0 | 500 | 500 |
| direct_first | STRICT_END_TO_END_SUCCESS | 0 | 0 | 500 | 0 | 500 | 500 |
| direct_first | FIRST_TOOL_CHOICE | 478 | 22 | 0 | 0 | 500 | 500 |
| direct_first | REQUIRED_ACTION_COVERAGE | 460 | 40 | 0 | 0 | 500 | 500 |
| direct_first | EXACT_ACTION_SEQUENCE | 404 | 96 | 0 | 0 | 500 | 500 |
| direct_first | RESULT_DELIVERY | 410 | 0 | 40 | 0 | 450 | 500 |
| direct_first | RESULT_COMPREHENSION | 381 | 14 | 55 | 0 | 450 | 500 |
| direct_first | TERMINATION_CORRECTNESS | 385 | 102 | 13 | 0 | 500 | 500 |
| direct_first | QUALIFIED_BUSINESS_COMPLETION | 39 | 361 | 0 | 0 | 400 | 500 |
| direct_first | authorization | 50 | 0 | 0 | 0 | 50 | 500 |
| direct_first | entity_binding | 389 | 61 | 0 | 0 | 450 | 500 |
| direct_first | required_arguments | 389 | 61 | 0 | 0 | 450 | 500 |
| sdk_first | BUSINESS_FACT_CORRECTNESS | 265 | 59 | 76 | 0 | 400 | 500 |
| sdk_first | OUTPUT_CONTRACT_COMPLIANCE | 0 | 497 | 3 | 0 | 500 | 500 |
| sdk_first | EXECUTION_PROCESS_CORRECTNESS | 390 | 108 | 2 | 0 | 500 | 500 |
| sdk_first | STRICT_END_TO_END_SUCCESS | 0 | 0 | 500 | 0 | 500 | 500 |
| sdk_first | FIRST_TOOL_CHOICE | 465 | 35 | 0 | 0 | 500 | 500 |
| sdk_first | REQUIRED_ACTION_COVERAGE | 472 | 25 | 3 | 0 | 500 | 500 |
| sdk_first | EXACT_ACTION_SEQUENCE | 372 | 125 | 3 | 0 | 500 | 500 |
| sdk_first | RESULT_DELIVERY | 411 | 0 | 39 | 0 | 450 | 500 |
| sdk_first | RESULT_COMPREHENSION | 311 | 63 | 76 | 0 | 450 | 500 |
| sdk_first | TERMINATION_CORRECTNESS | 359 | 112 | 29 | 0 | 500 | 500 |
| sdk_first | QUALIFIED_BUSINESS_COMPLETION | 0 | 398 | 2 | 0 | 400 | 500 |
| sdk_first | authorization | 50 | 0 | 0 | 0 | 50 | 500 |
| sdk_first | entity_binding | 383 | 52 | 15 | 0 | 450 | 500 |
| sdk_first | required_arguments | 383 | 52 | 15 | 0 | 450 | 500 |
| sdk_repeat | BUSINESS_FACT_CORRECTNESS | 92 | 18 | 10 | 0 | 120 | 150 |
| sdk_repeat | OUTPUT_CONTRACT_COMPLIANCE | 0 | 150 | 0 | 0 | 150 | 150 |
| sdk_repeat | EXECUTION_PROCESS_CORRECTNESS | 127 | 23 | 0 | 0 | 150 | 150 |
| sdk_repeat | STRICT_END_TO_END_SUCCESS | 0 | 0 | 150 | 0 | 150 | 150 |
| sdk_repeat | FIRST_TOOL_CHOICE | 135 | 15 | 0 | 0 | 150 | 150 |
| sdk_repeat | REQUIRED_ACTION_COVERAGE | 147 | 3 | 0 | 0 | 150 | 150 |
| sdk_repeat | EXACT_ACTION_SEQUENCE | 119 | 31 | 0 | 0 | 150 | 150 |
| sdk_repeat | RESULT_DELIVERY | 132 | 0 | 3 | 0 | 135 | 150 |
| sdk_repeat | RESULT_COMPREHENSION | 106 | 19 | 10 | 0 | 135 | 150 |
| sdk_repeat | TERMINATION_CORRECTNESS | 119 | 27 | 4 | 0 | 150 | 150 |
| sdk_repeat | QUALIFIED_BUSINESS_COMPLETION | 0 | 120 | 0 | 0 | 120 | 150 |
| sdk_repeat | authorization | 15 | 0 | 0 | 0 | 15 | 150 |
| sdk_repeat | entity_binding | 123 | 12 | 0 | 0 | 135 | 150 |
| sdk_repeat | required_arguments | 123 | 12 | 0 | 0 | 135 | 150 |
| sdk_streaming | BUSINESS_FACT_CORRECTNESS | 267 | 62 | 71 | 0 | 400 | 500 |
| sdk_streaming | OUTPUT_CONTRACT_COMPLIANCE | 0 | 500 | 0 | 0 | 500 | 500 |
| sdk_streaming | EXECUTION_PROCESS_CORRECTNESS | 396 | 104 | 0 | 0 | 500 | 500 |
| sdk_streaming | STRICT_END_TO_END_SUCCESS | 0 | 0 | 500 | 0 | 500 | 500 |
| sdk_streaming | FIRST_TOOL_CHOICE | 465 | 35 | 0 | 0 | 500 | 500 |
| sdk_streaming | REQUIRED_ACTION_COVERAGE | 477 | 23 | 0 | 0 | 500 | 500 |
| sdk_streaming | EXACT_ACTION_SEQUENCE | 379 | 121 | 0 | 0 | 500 | 500 |
| sdk_streaming | RESULT_DELIVERY | 414 | 0 | 36 | 0 | 450 | 500 |
| sdk_streaming | RESULT_COMPREHENSION | 309 | 70 | 71 | 0 | 450 | 500 |
| sdk_streaming | TERMINATION_CORRECTNESS | 367 | 109 | 24 | 0 | 500 | 500 |
| sdk_streaming | QUALIFIED_BUSINESS_COMPLETION | 0 | 400 | 0 | 0 | 400 | 500 |
| sdk_streaming | authorization | 50 | 0 | 0 | 0 | 50 | 500 |
| sdk_streaming | entity_binding | 386 | 51 | 13 | 0 | 450 | 500 |
| sdk_streaming | required_arguments | 386 | 51 | 13 | 0 | 450 | 500 |

## Failure signature and compensation

Observed signature — Strict answer format fails more often than first tool selection.
HYPOTHESIS — Structured Output Contract. Run an independent online comparison and preserve provider output, typed values, and intervention attribution.
Trial and seal references are listed by metric in the [capability matrix](CAPABILITY_MATRIX.json).

## Resource envelope

| Track | Resource | Observed | P50 | P95 |
| --- | --- | ---: | ---: | ---: |
| direct_first | input_tokens | 500/500 | 497 | 819 |
| direct_first | output_tokens | 500/500 | 62 | 96 |
| direct_first | total_tokens | 500/500 | 556 | 892 |
| direct_first | model_requests | 500/500 | 2 | 3 |
| direct_first | provider_inference_ms | 500/500 | 1401.354 | 2205.669 |
| direct_first | end_to_end_wall_ms | 0/500 | NOT_RUN | NOT_RUN |
| direct_first | sdk_boundary_wall_ms_sum | 0/500 | NOT_RUN | NOT_RUN |
| direct_first | actual_tool_executions | 500/500 | 1 | 2 |
| direct_first | context_consumption | 0/500 | NOT_RUN | NOT_RUN |
| sdk_first | input_tokens | 497/500 | 2603 | 4015 |
| sdk_first | output_tokens | 497/500 | 68 | 132 |
| sdk_first | total_tokens | 497/500 | 2667 | 4096 |
| sdk_first | model_requests | 500/500 | 2 | 3 |
| sdk_first | provider_inference_ms | 497/500 | 3241.983 | 4939.496 |
| sdk_first | end_to_end_wall_ms | 0/500 | NOT_RUN | NOT_RUN |
| sdk_first | sdk_boundary_wall_ms_sum | 497/500 | 3342.75 | 5067.12 |
| sdk_first | actual_tool_executions | 497/500 | 1 | 2 |
| sdk_first | context_consumption | 0/500 | NOT_RUN | NOT_RUN |
| sdk_streaming | input_tokens | 500/500 | 2608 | 4009 |
| sdk_streaming | output_tokens | 500/500 | 68 | 133 |
| sdk_streaming | total_tokens | 500/500 | 2667 | 4106 |
| sdk_streaming | model_requests | 500/500 | 2 | 3 |
| sdk_streaming | provider_inference_ms | 500/500 | 2950.36 | 5136.815 |
| sdk_streaming | end_to_end_wall_ms | 0/500 | NOT_RUN | NOT_RUN |
| sdk_streaming | sdk_boundary_wall_ms_sum | 500/500 | 3008.6800000000003 | 5212.58 |
| sdk_streaming | actual_tool_executions | 500/500 | 1 | 2 |
| sdk_streaming | context_consumption | 0/500 | NOT_RUN | NOT_RUN |
| sdk_repeat | input_tokens | 150/150 | 2610 | 4005 |
| sdk_repeat | output_tokens | 150/150 | 66 | 133 |
| sdk_repeat | total_tokens | 150/150 | 2665 | 4087 |
| sdk_repeat | model_requests | 150/150 | 2 | 3 |
| sdk_repeat | provider_inference_ms | 150/150 | 3123.209 | 4866.5470000000005 |
| sdk_repeat | end_to_end_wall_ms | 0/150 | NOT_RUN | NOT_RUN |
| sdk_repeat | sdk_boundary_wall_ms_sum | 150/150 | 3238.33 | 4977.18 |
| sdk_repeat | actual_tool_executions | 150/150 | 1 | 2 |
| sdk_repeat | context_consumption | 0/150 | NOT_RUN | NOT_RUN |

The matrix records session-level GPU memory and the measured resource totals per verified outcome.
Strict D25, production job accuracy, planning depth, autonomy and NPU performance remain unqualified.

The publisher describes a 3.4B language model and a 0.4B vision encoder for the family. [Publisher model card](https://huggingface.co/mistralai/Ministral-3-3B-Instruct-2512-GGUF)
