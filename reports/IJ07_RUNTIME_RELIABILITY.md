# IJ-0.7 runtime reliability stage report

Both Radeon backends completed all 500 historical cases for each parser build.
The archive contains 4,422 source-to-wire request correlations, with the
captured model identity and GPU process evidence for every session.
The exercise uses single concurrency and the frozen historical workload.
 [Coverage and identities](../evidence/IJ07/historical_replay/full/summary.json)

The native API fixture control and the competitive admission probe use
explicit engine identities. The local tool-choice patch passed the targeted
16-case CPU JSON/SSE comparison and the malformed-selection check on each
of seven live Vulkan admissions. Structured task reliability, SDK
network isolation, soak, and process recovery across all requested
concurrency settings remain open. [Root causes](IJ07_SOURCE_LEVEL_ROOT_CAUSE_MASTER_REPORT.md)
 · [Performance evidence](IJ07_GPU_PERFORMANCE.md)
