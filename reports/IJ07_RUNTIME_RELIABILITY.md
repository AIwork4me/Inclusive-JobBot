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

The true Antigravity SDK CPU control held the model, engine, SDK, callback
and structured oracle fixed. The original prompt passed one of three.
An explicit instruction to use the tool response's result string for
finish.status passed three of three. Substantial GPU runtime qualification
still requires the revised profile and trusted AG-11 egress observation.
 [SDK prompt control](../evidence/IJ07/antigravity/ag06_prompt_cpu_control.json)

MULTITOOL-V1 ran all 300 fixed repeats on Vulkan. For 100 prespecified cases,
22 passed every seed and 78 failed every seed. Both Pass@3 and Pass^3
were 22%. The raw case and GPU evidence includes the original 16-call
wire cap. [Multi-tool repeat panel](../evidence/IJ07/multitool/repeat-vulkan-full/reliability.json)
