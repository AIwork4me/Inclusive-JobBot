# openbmb/MiniCPM5-2B TC-V3 datasheet

LlamaForCausalLM has 2,516,756,480 parameters in the frozen upstream source.
The measured GGUF uses Q8_0 and has SHA256 `c5415f8989bf88a8288f1b55a3cc371af53c07b0faa220a63bd7a990cfaba078`.
Weight file size in bytes is 2679710688.
The source license metadata is `apache-2.0`. See the pinned source identity for revision details.
Measurements use gfx1151 via vulkan, an 8,192-token configured context, llama.cpp b12359-b1b770d90d94cad9e9ea5b993bdbc383a522fb28 and Antigravity SDK 0.1.24.
Exact runtime and template digests are in the [capability matrix](CAPABILITY_MATRIX.json).

## Native and SDK capability

| Track | Metric | PASS | FAIL | BLOCKED | NOT_RUN | Applicable | Full |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| direct_first | BUSINESS_FACT_CORRECTNESS | 372 | 0 | 28 | 0 | 400 | 500 |
| direct_first | OUTPUT_CONTRACT_COMPLIANCE | 474 | 26 | 0 | 0 | 500 | 500 |
| direct_first | EXECUTION_PROCESS_CORRECTNESS | 472 | 28 | 0 | 0 | 500 | 500 |
| direct_first | STRICT_END_TO_END_SUCCESS | 0 | 0 | 500 | 0 | 500 | 500 |
| direct_first | FIRST_TOOL_CHOICE | 483 | 17 | 0 | 0 | 500 | 500 |
| direct_first | REQUIRED_ACTION_COVERAGE | 481 | 19 | 0 | 0 | 500 | 500 |
| direct_first | EXACT_ACTION_SEQUENCE | 472 | 28 | 0 | 0 | 500 | 500 |
| direct_first | RESULT_DELIVERY | 431 | 0 | 19 | 0 | 450 | 500 |
| direct_first | RESULT_COMPREHENSION | 412 | 10 | 28 | 0 | 450 | 500 |
| direct_first | TERMINATION_CORRECTNESS | 456 | 44 | 0 | 0 | 500 | 500 |
| direct_first | QUALIFIED_BUSINESS_COMPLETION | 372 | 28 | 0 | 0 | 400 | 500 |
| direct_first | authorization | 50 | 0 | 0 | 0 | 50 | 500 |
| direct_first | entity_binding | 422 | 20 | 8 | 0 | 450 | 500 |
| direct_first | required_arguments | 422 | 20 | 8 | 0 | 450 | 500 |
| sdk_first | BUSINESS_FACT_CORRECTNESS | 207 | 10 | 183 | 0 | 400 | 500 |
| sdk_first | OUTPUT_CONTRACT_COMPLIANCE | 184 | 316 | 0 | 0 | 500 | 500 |
| sdk_first | EXECUTION_PROCESS_CORRECTNESS | 117 | 383 | 0 | 0 | 500 | 500 |
| sdk_first | STRICT_END_TO_END_SUCCESS | 0 | 0 | 500 | 0 | 500 | 500 |
| sdk_first | FIRST_TOOL_CHOICE | 449 | 51 | 0 | 0 | 500 | 500 |
| sdk_first | REQUIRED_ACTION_COVERAGE | 488 | 12 | 0 | 0 | 500 | 500 |
| sdk_first | EXACT_ACTION_SEQUENCE | 116 | 384 | 0 | 0 | 500 | 500 |
| sdk_first | RESULT_DELIVERY | 419 | 0 | 31 | 0 | 450 | 500 |
| sdk_first | RESULT_COMPREHENSION | 239 | 28 | 183 | 0 | 450 | 500 |
| sdk_first | TERMINATION_CORRECTNESS | 107 | 393 | 0 | 0 | 500 | 500 |
| sdk_first | QUALIFIED_BUSINESS_COMPLETION | 2 | 398 | 0 | 0 | 400 | 500 |
| sdk_first | authorization | 50 | 0 | 0 | 0 | 50 | 500 |
| sdk_first | entity_binding | 99 | 203 | 148 | 0 | 450 | 500 |
| sdk_first | required_arguments | 99 | 203 | 148 | 0 | 450 | 500 |
| sdk_repeat | BUSINESS_FACT_CORRECTNESS | 65 | 0 | 55 | 0 | 120 | 150 |
| sdk_repeat | OUTPUT_CONTRACT_COMPLIANCE | 51 | 99 | 0 | 0 | 150 | 150 |
| sdk_repeat | EXECUTION_PROCESS_CORRECTNESS | 37 | 113 | 0 | 0 | 150 | 150 |
| sdk_repeat | STRICT_END_TO_END_SUCCESS | 0 | 0 | 150 | 0 | 150 | 150 |
| sdk_repeat | FIRST_TOOL_CHOICE | 147 | 3 | 0 | 0 | 150 | 150 |
| sdk_repeat | REQUIRED_ACTION_COVERAGE | 147 | 3 | 0 | 0 | 150 | 150 |
| sdk_repeat | EXACT_ACTION_SEQUENCE | 35 | 115 | 0 | 0 | 150 | 150 |
| sdk_repeat | RESULT_DELIVERY | 128 | 0 | 7 | 0 | 135 | 150 |
| sdk_repeat | RESULT_COMPREHENSION | 72 | 6 | 57 | 0 | 135 | 150 |
| sdk_repeat | TERMINATION_CORRECTNESS | 23 | 127 | 0 | 0 | 150 | 150 |
| sdk_repeat | QUALIFIED_BUSINESS_COMPLETION | 0 | 120 | 0 | 0 | 120 | 150 |
| sdk_repeat | authorization | 15 | 0 | 0 | 0 | 15 | 150 |
| sdk_repeat | entity_binding | 23 | 65 | 47 | 0 | 135 | 150 |
| sdk_repeat | required_arguments | 23 | 65 | 47 | 0 | 135 | 150 |
| sdk_streaming | BUSINESS_FACT_CORRECTNESS | 210 | 12 | 178 | 0 | 400 | 500 |
| sdk_streaming | OUTPUT_CONTRACT_COMPLIANCE | 188 | 312 | 0 | 0 | 500 | 500 |
| sdk_streaming | EXECUTION_PROCESS_CORRECTNESS | 116 | 384 | 0 | 0 | 500 | 500 |
| sdk_streaming | STRICT_END_TO_END_SUCCESS | 0 | 0 | 500 | 0 | 500 | 500 |
| sdk_streaming | FIRST_TOOL_CHOICE | 449 | 51 | 0 | 0 | 500 | 500 |
| sdk_streaming | REQUIRED_ACTION_COVERAGE | 489 | 11 | 0 | 0 | 500 | 500 |
| sdk_streaming | EXACT_ACTION_SEQUENCE | 114 | 386 | 0 | 0 | 500 | 500 |
| sdk_streaming | RESULT_DELIVERY | 416 | 0 | 34 | 0 | 450 | 500 |
| sdk_streaming | RESULT_COMPREHENSION | 241 | 30 | 179 | 0 | 450 | 500 |
| sdk_streaming | TERMINATION_CORRECTNESS | 109 | 391 | 0 | 0 | 500 | 500 |
| sdk_streaming | QUALIFIED_BUSINESS_COMPLETION | 2 | 398 | 0 | 0 | 400 | 500 |
| sdk_streaming | authorization | 50 | 0 | 0 | 0 | 50 | 500 |
| sdk_streaming | entity_binding | 96 | 210 | 144 | 0 | 450 | 500 |
| sdk_streaming | required_arguments | 96 | 210 | 144 | 0 | 450 | 500 |

## Failure signature and compensation

Observed signature — Repeated proposals and termination failures.
HYPOTHESIS — Action Ledger and Goal/Budget Controller. Measure proposals, caught duplicates and correct terminal answers separately. Include legitimate retries, entity changes, expired observations and changed authorization as negative controls.
Trial and seal references are listed by metric in the [capability matrix](CAPABILITY_MATRIX.json).

## Resource envelope

| Track | Resource | Observed | P50 | P95 |
| --- | --- | ---: | ---: | ---: |
| direct_first | input_tokens | 500/500 | 774 | 1247 |
| direct_first | output_tokens | 500/500 | 46 | 80 |
| direct_first | total_tokens | 500/500 | 823 | 1316 |
| direct_first | model_requests | 500/500 | 2 | 3 |
| direct_first | provider_inference_ms | 500/500 | 858.499 | 1439.767 |
| direct_first | end_to_end_wall_ms | 0/500 | NOT_RUN | NOT_RUN |
| direct_first | sdk_boundary_wall_ms_sum | 0/500 | NOT_RUN | NOT_RUN |
| direct_first | actual_tool_executions | 500/500 | 1 | 2 |
| direct_first | context_consumption | 0/500 | NOT_RUN | NOT_RUN |
| sdk_first | input_tokens | 500/500 | 3849 | 5825 |
| sdk_first | output_tokens | 500/500 | 80 | 114 |
| sdk_first | total_tokens | 500/500 | 3926 | 5924 |
| sdk_first | model_requests | 500/500 | 3 | 4 |
| sdk_first | provider_inference_ms | 500/500 | 2653.516 | 4502.982 |
| sdk_first | end_to_end_wall_ms | 0/500 | NOT_RUN | NOT_RUN |
| sdk_first | sdk_boundary_wall_ms_sum | 500/500 | 2765.81 | 4663.53 |
| sdk_first | actual_tool_executions | 500/500 | 2 | 4 |
| sdk_first | context_consumption | 0/500 | NOT_RUN | NOT_RUN |
| sdk_streaming | input_tokens | 500/500 | 3852 | 5847 |
| sdk_streaming | output_tokens | 500/500 | 83 | 112 |
| sdk_streaming | total_tokens | 500/500 | 3925 | 5941 |
| sdk_streaming | model_requests | 500/500 | 3 | 4 |
| sdk_streaming | provider_inference_ms | 500/500 | 2600.73 | 4578.669 |
| sdk_streaming | end_to_end_wall_ms | 0/500 | NOT_RUN | NOT_RUN |
| sdk_streaming | sdk_boundary_wall_ms_sum | 500/500 | 2698.7 | 4762.09 |
| sdk_streaming | actual_tool_executions | 500/500 | 2 | 4 |
| sdk_streaming | context_consumption | 0/500 | NOT_RUN | NOT_RUN |
| sdk_repeat | input_tokens | 150/150 | 3859 | 5851 |
| sdk_repeat | output_tokens | 150/150 | 77 | 115 |
| sdk_repeat | total_tokens | 150/150 | 3924 | 5949 |
| sdk_repeat | model_requests | 150/150 | 3 | 4 |
| sdk_repeat | provider_inference_ms | 150/150 | 2605.281 | 4833.009 |
| sdk_repeat | end_to_end_wall_ms | 0/150 | NOT_RUN | NOT_RUN |
| sdk_repeat | sdk_boundary_wall_ms_sum | 150/150 | 2726.27 | 4933.63 |
| sdk_repeat | actual_tool_executions | 150/150 | 2 | 4 |
| sdk_repeat | context_consumption | 0/150 | NOT_RUN | NOT_RUN |

The matrix records session-level GPU memory and the measured resource totals per verified outcome.
Strict D25, production job accuracy, planning depth, autonomy and NPU performance remain unqualified.
