# Priority TC-V3 capability report

Verified Radeon execution covers **4,950 of 4,950** frozen A/B/D slots.

Wilson intervals use PASS and FAIL. The full denominator includes BLOCKED and NOT_RUN.
The machine-readable report contains the exact case, seed and scope joins, the four-way transition counts, and the intervals for paired differences. The strict column uses the original sealed verdict.
[Machine-readable paired report](../atlas/slm/v1.0/tc-priority-capability.json)

## Candidate A

| Capability | Track | Planned | PASS | FAIL | BLOCKED | NOT_RUN | 95% CI |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| BUSINESS_FACT_CORRECTNESS | direct_first | 500 | 372 | 0 | 78 | 50 | 99.0% to 100.0% |
| OUTPUT_CONTRACT_COMPLIANCE | direct_first | 500 | 474 | 26 | 0 | 0 | 92.5% to 96.4% |
| EXECUTION_PROCESS_CORRECTNESS | direct_first | 500 | 472 | 28 | 0 | 0 | 92.0% to 96.1% |
| STRICT_END_TO_END_SUCCESS | direct_first | 500 | 0 | 0 | 500 | 0 | Unavailable |
| FIRST_TOOL_CHOICE | direct_first | 500 | 483 | 17 | 0 | 0 | 94.6% to 97.9% |
| REQUIRED_ACTION_COVERAGE | direct_first | 500 | 481 | 19 | 0 | 0 | 94.1% to 97.6% |
| EXACT_ACTION_SEQUENCE | direct_first | 500 | 472 | 28 | 0 | 0 | 92.0% to 96.1% |
| RESULT_DELIVERY | direct_first | 500 | 431 | 0 | 19 | 50 | 99.1% to 100.0% |
| RESULT_COMPREHENSION | direct_first | 500 | 412 | 10 | 28 | 50 | 95.7% to 98.7% |
| TERMINATION_CORRECTNESS | direct_first | 500 | 456 | 44 | 0 | 0 | 88.4% to 93.4% |
| QUALIFIED_BUSINESS_COMPLETION | direct_first | 500 | 372 | 28 | 50 | 50 | 90.1% to 95.1% |
| BUSINESS_FACT_CORRECTNESS | sdk_first | 500 | 207 | 10 | 233 | 50 | 91.7% to 97.5% |
| OUTPUT_CONTRACT_COMPLIANCE | sdk_first | 500 | 184 | 316 | 0 | 0 | 32.7% to 41.1% |
| EXECUTION_PROCESS_CORRECTNESS | sdk_first | 500 | 117 | 383 | 0 | 0 | 19.9% to 27.3% |
| STRICT_END_TO_END_SUCCESS | sdk_first | 500 | 0 | 0 | 500 | 0 | Unavailable |
| FIRST_TOOL_CHOICE | sdk_first | 500 | 449 | 51 | 0 | 0 | 86.8% to 92.2% |
| REQUIRED_ACTION_COVERAGE | sdk_first | 500 | 488 | 12 | 0 | 0 | 95.9% to 98.6% |
| EXACT_ACTION_SEQUENCE | sdk_first | 500 | 116 | 384 | 0 | 0 | 19.7% to 27.1% |
| RESULT_DELIVERY | sdk_first | 500 | 419 | 0 | 31 | 50 | 99.1% to 100.0% |
| RESULT_COMPREHENSION | sdk_first | 500 | 239 | 28 | 183 | 50 | 85.3% to 92.6% |
| TERMINATION_CORRECTNESS | sdk_first | 500 | 107 | 393 | 0 | 0 | 18.0% to 25.2% |
| QUALIFIED_BUSINESS_COMPLETION | sdk_first | 500 | 2 | 398 | 50 | 50 | 0.1% to 1.8% |
| BUSINESS_FACT_CORRECTNESS | sdk_streaming | 500 | 210 | 12 | 228 | 50 | 90.8% to 96.9% |
| OUTPUT_CONTRACT_COMPLIANCE | sdk_streaming | 500 | 188 | 312 | 0 | 0 | 33.5% to 41.9% |
| EXECUTION_PROCESS_CORRECTNESS | sdk_streaming | 500 | 116 | 384 | 0 | 0 | 19.7% to 27.1% |
| STRICT_END_TO_END_SUCCESS | sdk_streaming | 500 | 0 | 0 | 500 | 0 | Unavailable |
| FIRST_TOOL_CHOICE | sdk_streaming | 500 | 449 | 51 | 0 | 0 | 86.8% to 92.2% |
| REQUIRED_ACTION_COVERAGE | sdk_streaming | 500 | 489 | 11 | 0 | 0 | 96.1% to 98.8% |
| EXACT_ACTION_SEQUENCE | sdk_streaming | 500 | 114 | 386 | 0 | 0 | 19.3% to 26.7% |
| RESULT_DELIVERY | sdk_streaming | 500 | 416 | 0 | 34 | 50 | 99.1% to 100.0% |
| RESULT_COMPREHENSION | sdk_streaming | 500 | 241 | 30 | 179 | 50 | 84.6% to 92.1% |
| TERMINATION_CORRECTNESS | sdk_streaming | 500 | 109 | 391 | 0 | 0 | 18.4% to 25.6% |
| QUALIFIED_BUSINESS_COMPLETION | sdk_streaming | 500 | 2 | 398 | 50 | 50 | 0.1% to 1.8% |
| BUSINESS_FACT_CORRECTNESS | sdk_repeat | 150 | 65 | 0 | 70 | 15 | 94.4% to 100.0% |
| OUTPUT_CONTRACT_COMPLIANCE | sdk_repeat | 150 | 51 | 99 | 0 | 0 | 26.9% to 41.9% |
| EXECUTION_PROCESS_CORRECTNESS | sdk_repeat | 150 | 37 | 113 | 0 | 0 | 18.5% to 32.1% |
| STRICT_END_TO_END_SUCCESS | sdk_repeat | 150 | 0 | 0 | 150 | 0 | Unavailable |
| FIRST_TOOL_CHOICE | sdk_repeat | 150 | 147 | 3 | 0 | 0 | 94.3% to 99.3% |
| REQUIRED_ACTION_COVERAGE | sdk_repeat | 150 | 147 | 3 | 0 | 0 | 94.3% to 99.3% |
| EXACT_ACTION_SEQUENCE | sdk_repeat | 150 | 35 | 115 | 0 | 0 | 17.3% to 30.7% |
| RESULT_DELIVERY | sdk_repeat | 150 | 128 | 0 | 7 | 15 | 97.1% to 100.0% |
| RESULT_COMPREHENSION | sdk_repeat | 150 | 72 | 6 | 57 | 15 | 84.2% to 96.4% |
| TERMINATION_CORRECTNESS | sdk_repeat | 150 | 23 | 127 | 0 | 0 | 10.4% to 22.0% |
| QUALIFIED_BUSINESS_COMPLETION | sdk_repeat | 150 | 0 | 120 | 15 | 15 | 0.0% to 3.1% |

## Candidate B

| Capability | Track | Planned | PASS | FAIL | BLOCKED | NOT_RUN | 95% CI |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| BUSINESS_FACT_CORRECTNESS | direct_first | 500 | 372 | 1 | 77 | 50 | 98.5% to 100.0% |
| OUTPUT_CONTRACT_COMPLIANCE | direct_first | 500 | 476 | 18 | 6 | 0 | 94.3% to 97.7% |
| EXECUTION_PROCESS_CORRECTNESS | direct_first | 500 | 455 | 39 | 6 | 0 | 89.4% to 94.2% |
| STRICT_END_TO_END_SUCCESS | direct_first | 500 | 0 | 0 | 500 | 0 | Unavailable |
| FIRST_TOOL_CHOICE | direct_first | 500 | 482 | 18 | 0 | 0 | 94.4% to 97.7% |
| REQUIRED_ACTION_COVERAGE | direct_first | 500 | 477 | 17 | 6 | 0 | 94.6% to 97.8% |
| EXACT_ACTION_SEQUENCE | direct_first | 500 | 455 | 39 | 6 | 0 | 89.4% to 94.2% |
| RESULT_DELIVERY | direct_first | 500 | 433 | 0 | 17 | 50 | 99.1% to 100.0% |
| RESULT_COMPREHENSION | direct_first | 500 | 395 | 18 | 37 | 50 | 93.2% to 97.2% |
| TERMINATION_CORRECTNESS | direct_first | 500 | 455 | 39 | 6 | 0 | 89.4% to 94.2% |
| QUALIFIED_BUSINESS_COMPLETION | direct_first | 500 | 361 | 39 | 50 | 50 | 86.9% to 92.8% |
| BUSINESS_FACT_CORRECTNESS | sdk_first | 500 | 312 | 16 | 122 | 50 | 92.2% to 97.0% |
| OUTPUT_CONTRACT_COMPLIANCE | sdk_first | 500 | 398 | 102 | 0 | 0 | 75.8% to 82.9% |
| EXECUTION_PROCESS_CORRECTNESS | sdk_first | 500 | 357 | 143 | 0 | 0 | 67.3% to 75.2% |
| STRICT_END_TO_END_SUCCESS | sdk_first | 500 | 0 | 0 | 500 | 0 | Unavailable |
| FIRST_TOOL_CHOICE | sdk_first | 500 | 491 | 9 | 0 | 0 | 96.6% to 99.1% |
| REQUIRED_ACTION_COVERAGE | sdk_first | 500 | 491 | 9 | 0 | 0 | 96.6% to 99.1% |
| EXACT_ACTION_SEQUENCE | sdk_first | 500 | 350 | 150 | 0 | 0 | 65.8% to 73.9% |
| RESULT_DELIVERY | sdk_first | 500 | 425 | 0 | 25 | 50 | 99.1% to 100.0% |
| RESULT_COMPREHENSION | sdk_first | 500 | 350 | 17 | 83 | 50 | 92.7% to 97.1% |
| TERMINATION_CORRECTNESS | sdk_first | 500 | 318 | 182 | 0 | 0 | 59.3% to 67.7% |
| QUALIFIED_BUSINESS_COMPLETION | sdk_first | 500 | 218 | 182 | 50 | 50 | 49.6% to 59.3% |
| BUSINESS_FACT_CORRECTNESS | sdk_streaming | 500 | 314 | 17 | 119 | 50 | 91.9% to 96.8% |
| OUTPUT_CONTRACT_COMPLIANCE | sdk_streaming | 500 | 402 | 98 | 0 | 0 | 76.7% to 83.6% |
| EXECUTION_PROCESS_CORRECTNESS | sdk_streaming | 500 | 359 | 141 | 0 | 0 | 67.7% to 75.6% |
| STRICT_END_TO_END_SUCCESS | sdk_streaming | 500 | 0 | 0 | 500 | 0 | Unavailable |
| FIRST_TOOL_CHOICE | sdk_streaming | 500 | 493 | 7 | 0 | 0 | 97.1% to 99.3% |
| REQUIRED_ACTION_COVERAGE | sdk_streaming | 500 | 493 | 7 | 0 | 0 | 97.1% to 99.3% |
| EXACT_ACTION_SEQUENCE | sdk_streaming | 500 | 352 | 148 | 0 | 0 | 66.3% to 74.2% |
| RESULT_DELIVERY | sdk_streaming | 500 | 426 | 0 | 24 | 50 | 99.1% to 100.0% |
| RESULT_COMPREHENSION | sdk_streaming | 500 | 354 | 18 | 78 | 50 | 92.5% to 96.9% |
| TERMINATION_CORRECTNESS | sdk_streaming | 500 | 317 | 183 | 0 | 0 | 59.1% to 67.5% |
| QUALIFIED_BUSINESS_COMPLETION | sdk_streaming | 500 | 220 | 180 | 50 | 50 | 50.1% to 59.8% |
| BUSINESS_FACT_CORRECTNESS | sdk_repeat | 150 | 99 | 8 | 28 | 15 | 85.9% to 96.2% |
| OUTPUT_CONTRACT_COMPLIANCE | sdk_repeat | 150 | 128 | 22 | 0 | 0 | 78.8% to 90.1% |
| EXECUTION_PROCESS_CORRECTNESS | sdk_repeat | 150 | 120 | 30 | 0 | 0 | 72.9% to 85.6% |
| STRICT_END_TO_END_SUCCESS | sdk_repeat | 150 | 0 | 0 | 150 | 0 | Unavailable |
| FIRST_TOOL_CHOICE | sdk_repeat | 150 | 150 | 0 | 0 | 0 | 97.5% to 100.0% |
| REQUIRED_ACTION_COVERAGE | sdk_repeat | 150 | 150 | 0 | 0 | 0 | 97.5% to 100.0% |
| EXACT_ACTION_SEQUENCE | sdk_repeat | 150 | 116 | 34 | 0 | 0 | 70.0% to 83.3% |
| RESULT_DELIVERY | sdk_repeat | 150 | 135 | 0 | 0 | 15 | 97.2% to 100.0% |
| RESULT_COMPREHENSION | sdk_repeat | 150 | 111 | 8 | 16 | 15 | 87.3% to 96.6% |
| TERMINATION_CORRECTNESS | sdk_repeat | 150 | 103 | 47 | 0 | 0 | 60.9% to 75.5% |
| QUALIFIED_BUSINESS_COMPLETION | sdk_repeat | 150 | 73 | 47 | 15 | 15 | 51.9% to 69.1% |

## Candidate D

| Capability | Track | Planned | PASS | FAIL | BLOCKED | NOT_RUN | 95% CI |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| BUSINESS_FACT_CORRECTNESS | direct_first | 500 | 394 | 0 | 56 | 50 | 99.0% to 100.0% |
| OUTPUT_CONTRACT_COMPLIANCE | direct_first | 500 | 300 | 200 | 0 | 0 | 55.6% to 64.2% |
| EXECUTION_PROCESS_CORRECTNESS | direct_first | 500 | 462 | 38 | 0 | 0 | 89.7% to 94.4% |
| STRICT_END_TO_END_SUCCESS | direct_first | 500 | 0 | 0 | 500 | 0 | Unavailable |
| FIRST_TOOL_CHOICE | direct_first | 500 | 463 | 37 | 0 | 0 | 90.0% to 94.6% |
| REQUIRED_ACTION_COVERAGE | direct_first | 500 | 494 | 6 | 0 | 0 | 97.4% to 99.4% |
| EXACT_ACTION_SEQUENCE | direct_first | 500 | 412 | 88 | 0 | 0 | 78.8% to 85.5% |
| RESULT_DELIVERY | direct_first | 500 | 444 | 0 | 6 | 50 | 99.1% to 100.0% |
| RESULT_COMPREHENSION | direct_first | 500 | 427 | 0 | 23 | 50 | 99.1% to 100.0% |
| TERMINATION_CORRECTNESS | direct_first | 500 | 411 | 89 | 0 | 0 | 78.6% to 85.3% |
| QUALIFIED_BUSINESS_COMPLETION | direct_first | 500 | 272 | 128 | 50 | 50 | 63.3% to 72.4% |
| BUSINESS_FACT_CORRECTNESS | sdk_first | 500 | 316 | 38 | 96 | 50 | 85.6% to 92.1% |
| OUTPUT_CONTRACT_COMPLIANCE | sdk_first | 500 | 85 | 415 | 0 | 0 | 14.0% to 20.5% |
| EXECUTION_PROCESS_CORRECTNESS | sdk_first | 500 | 443 | 57 | 0 | 0 | 85.5% to 91.1% |
| STRICT_END_TO_END_SUCCESS | sdk_first | 500 | 0 | 0 | 500 | 0 | Unavailable |
| FIRST_TOOL_CHOICE | sdk_first | 500 | 449 | 51 | 0 | 0 | 86.8% to 92.2% |
| REQUIRED_ACTION_COVERAGE | sdk_first | 500 | 466 | 34 | 0 | 0 | 90.6% to 95.1% |
| EXACT_ACTION_SEQUENCE | sdk_first | 500 | 420 | 80 | 0 | 0 | 80.5% to 87.0% |
| RESULT_DELIVERY | sdk_first | 500 | 410 | 0 | 40 | 50 | 99.1% to 100.0% |
| RESULT_COMPREHENSION | sdk_first | 500 | 356 | 48 | 46 | 50 | 84.6% to 90.9% |
| TERMINATION_CORRECTNESS | sdk_first | 500 | 402 | 98 | 0 | 0 | 76.7% to 83.6% |
| QUALIFIED_BUSINESS_COMPLETION | sdk_first | 500 | 80 | 320 | 50 | 50 | 16.4% to 24.2% |
| BUSINESS_FACT_CORRECTNESS | sdk_streaming | 500 | 316 | 40 | 94 | 50 | 85.1% to 91.6% |
| OUTPUT_CONTRACT_COMPLIANCE | sdk_streaming | 500 | 81 | 419 | 0 | 0 | 13.2% to 19.7% |
| EXECUTION_PROCESS_CORRECTNESS | sdk_streaming | 500 | 442 | 58 | 0 | 0 | 85.3% to 90.9% |
| STRICT_END_TO_END_SUCCESS | sdk_streaming | 500 | 0 | 0 | 500 | 0 | Unavailable |
| FIRST_TOOL_CHOICE | sdk_streaming | 500 | 449 | 51 | 0 | 0 | 86.8% to 92.2% |
| REQUIRED_ACTION_COVERAGE | sdk_streaming | 500 | 466 | 34 | 0 | 0 | 90.6% to 95.1% |
| EXACT_ACTION_SEQUENCE | sdk_streaming | 500 | 422 | 78 | 0 | 0 | 81.0% to 87.3% |
| RESULT_DELIVERY | sdk_streaming | 500 | 409 | 0 | 41 | 50 | 99.1% to 100.0% |
| RESULT_COMPREHENSION | sdk_streaming | 500 | 359 | 47 | 44 | 50 | 84.9% to 91.2% |
| TERMINATION_CORRECTNESS | sdk_streaming | 500 | 404 | 96 | 0 | 0 | 77.1% to 84.0% |
| QUALIFIED_BUSINESS_COMPLETION | sdk_streaming | 500 | 78 | 322 | 50 | 50 | 15.9% to 23.7% |
| BUSINESS_FACT_CORRECTNESS | sdk_repeat | 150 | 96 | 11 | 28 | 15 | 82.5% to 94.2% |
| OUTPUT_CONTRACT_COMPLIANCE | sdk_repeat | 150 | 22 | 128 | 0 | 0 | 9.9% to 21.2% |
| EXECUTION_PROCESS_CORRECTNESS | sdk_repeat | 150 | 129 | 21 | 0 | 0 | 79.5% to 90.7% |
| STRICT_END_TO_END_SUCCESS | sdk_repeat | 150 | 0 | 0 | 150 | 0 | Unavailable |
| FIRST_TOOL_CHOICE | sdk_repeat | 150 | 129 | 21 | 0 | 0 | 79.5% to 90.7% |
| REQUIRED_ACTION_COVERAGE | sdk_repeat | 150 | 141 | 9 | 0 | 0 | 89.0% to 96.8% |
| EXACT_ACTION_SEQUENCE | sdk_repeat | 150 | 121 | 29 | 0 | 0 | 73.6% to 86.2% |
| RESULT_DELIVERY | sdk_repeat | 150 | 126 | 0 | 9 | 15 | 97.0% to 100.0% |
| RESULT_COMPREHENSION | sdk_repeat | 150 | 108 | 14 | 13 | 15 | 81.7% to 93.0% |
| TERMINATION_CORRECTNESS | sdk_repeat | 150 | 121 | 29 | 0 | 0 | 73.6% to 86.2% |
| QUALIFIED_BUSINESS_COMPLETION | sdk_repeat | 150 | 21 | 99 | 15 | 15 | 11.7% to 25.3% |
