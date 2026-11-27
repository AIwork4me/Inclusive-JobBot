# NanoAgent five-model capability exchange

Use the [schema](CAPABILITY_EXCHANGE.schema.json) and [exchange](CAPABILITY_EXCHANGE.json) from the same PR #9 commit. Consumers pin that full Git SHA. The previous three-model exchange is preserved with its published SHA and manifest digest in the new exchange. The original [R0–R7 comparison contract](../MATCHED_BENCHMARK_CONTRACT.json) remains content-addressed.

The baseline covers all 8,250 frozen TC-V3 physical executions. Strict D25 remains BLOCKED. The exchange links the verified five-model matrix, first-attempt pairs, streaming agreement, repeat reliability, resource Pareto, raw trial seal inventory and per-model failure examples. SDK costs are same-case, same-seed SDK-first minus Direct-first. Missing whole-task latency remains unavailable.

- MiniCPM5 repeat proposals and termination remain separate targets for future independent interventions.
- The LFM3 compact-result holdout has 24 verified Radeon trajectories. The scoped finding is INDETERMINATE.
- Qwen3.5 and Ministral have 1,596 HOST_NORMALIZED counterfactual observations. The corresponding online replay and other structured output arms remain NOT_RUN. These entries preserve the frozen native and SDK results.

The scope of demonstrated capabilities remains the frozen synthetic tool-calling workload. All compensation choices listed here remain HYPOTHESIS. The exchange records zero additional core trials.

From the repository checkout, verify with `PYTHONPATH=src`.

```sh
python -m benchmarks.slm10.tc_five_model_milestone
python -m benchmarks.slm10.nanoagent_handoff
python -m benchmarks.slm10.nanoagent_five_model_handoff
```
