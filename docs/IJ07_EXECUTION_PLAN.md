# IJ-0.7 execution plan

1. Freeze and independently audit IJ-0.6, record current Windows identities and exact GitHub checks, then publish the audit on the stacked branch.
2. Research all named model families, pin artifacts before loading, and run the ten admission checks in order. Use the official ONNX reference track when a model needs an implementation outside the common llama.cpp build.
3. Use the frozen 1.0.2 dataset and the existing replay semantics for historical diagnostics. Establish that the capture path preserves sampling before the four replay arms. Separate source-level capture from chat protocol, evaluator and persisted business state verdicts.
4. Freeze independent dataset templates, graphs, test identities, model configurations and repeat panels. Reuse the existing V2 evaluator, SQLite oracle, Gateway and job statistics where their contracts match. Run TC-V2, MULTITOOL-V1 and both AGENTIC-PLAN-V1 tracks with explicit case, resource and time budgets.
5. Register failures at their earliest observable boundary. Minimal counterfactuals use the development or historical split. Retain original failure rows and record repaired configurations under new identities.
6. Run paired model comparisons and JOB-V1 A–F, then publish performance, reliability and bilingual evidence-derived findings. Record each G0–G17 verdict and the seven mission decisions. Keep binaries, weights and sensitive private artifacts local.

No formal holdout starts until its freeze is verified. Benchmark runs resume on the same fingerprint and retain completed cases, failures and denominator. Historical tests, fixed parser fixtures, hosted software checks and new Radeon inference have separate evidence scopes.
