# IJ-0.7.3 Gold proof replay

The independent obligations reproduced the published labels for all 101 distinct packets in the discrepancy cohort. They confirmed 45 deficient Q1 Gold citation sets and the sufficiency of all 81 archived Qwen3-14B alternative citation sets. The two groups overlap in 25 packets. Of the alternatives, 38 include relevant evidence beyond the selected minimal proof and 3 include irrelevant evidence. A sufficient proof can carry either kind of extra evidence.

The audit enumerates minimal proofs from the positive obligations and independently sufficient counterexamples. It tests deletion of each exhibit from each minimal proof and reverses the decisive source facts in every packet. All 323 controls passed. Citation identity, sufficiency, extra evidence, rationale support and business polarity are recorded independently. The rationale check accepts structured claims bound to a cited obligation. Qualification of the archived free-text reasons remains NOT_RUN.

These seven registered synthetic templates support development and source replay. Zero-call routing on real historical workflows remains NOT_RUN. Q1 and Q2 use their original verdicts, citation criteria and thresholds. Q3 requires new task families and archival episodes under the formal freeze.

Run the replay from the Atlas worktree with the repository root and src on PYTHONPATH.

```text
python -m evaluation.aeve.gold_proof_report --replay evidence/IJ073/aeve/gold_proof.json --output .runtime/gold-proof-replay.json
```

[Per-case proof evidence](../evidence/IJ073/aeve/gold_proof.json) · [Q1 source ledger](../evidence/IJ073/aeve/q1_root_cause_ledger.jsonl.gz) · [Independent Q3 metrics](../evaluation/aeve/q3_metric_preregistration.json)
