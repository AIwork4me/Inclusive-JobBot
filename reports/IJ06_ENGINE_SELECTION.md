# IJ-0.6 engine selection

Production selection is `NOT_RUN`. The production configuration is disabled and has no default backend. The scoped parser candidate was tested separately from the original b12359 GPU artifacts. The development review workload ran on both original GPU backends. Vulkan passed more SDK gates on the original engine. ROCm passed more on P4b. The longest observed Vulkan review latency exceeded ROCm/HIP's longest, with three observations on each. These runs do not establish a production backend ordering.

Evaluate the same frozen candidate on the workload and context/concurrency matrix before selecting a default. Retain safety, correctness, reliability, business productivity, efficiency and maintainability in that order. [Performance report](IJ06_PERFORMANCE_REPORT.md) · [SDK report](IJ06_ANTIGRAVITY_QUALIFICATION.md)
