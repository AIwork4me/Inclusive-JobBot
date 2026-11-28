# IJ-0.7.3 Q1 Judge failure ledger

The original Q1 qualification remains **FAIL**. The ledger audits all 3,228 sealed Radeon judgments, including successful controls. It links each row to its frozen packet hash, job, run, original classification, raw Judge text, and source-derived proof. The machine-readable summary retains the three headline Q1 metrics and reports the source audit alongside them.

| Judge | Strict citation accuracy | Source sufficiency among conclusive judgments | Sufficiency with only relevant exhibits |
|---|---:|---:|---:|
| Qwen3-14B | 67.9% | 608/806 | 519/806 |
| Gemma-4-E2B | 42.1% | 375/765 | 344/765 |
| Ministral-3-3B | 31.5% | 271/609 | 200/609 |
| LFM3-1.7B | 40.4% | 385/634 | 289/634 |

Source sufficiency requires the cited exhibits to establish the actual polarity under the source rule. A citation to an absent exhibit invalidates the claim. The focused column also flags exhibits outside the union of minimal proof sets. Such exhibits can include corroborating or contextual information. These diagnostics apply to the 26 synthetic templates. Free-text rationale entailment and generalization to unfamiliar tasks still need independent evaluation.

## Qwen3-14B

Macro-F1 was 0.816. Visible source records contradict 144 conclusive verdicts, and one judgment abstained on a determinate case. Four repeatable errors account for 90 incorrect PASS verdicts.

| Pattern | Count | Representative case and source discrepancy |
|---|---:|---|
| Dependency order | 25 | `c42c4ec19c19dd2ec5f6-a`. The rationale asserts lookup precedes read. The plan schedules read first. |
| Final protocol | 25 | `76a2ee5d562297fc27cc-a`. The rationale recognizes the JSON value. The Markdown fence breaks the bare-object contract. |
| Tool freshness | 20 | `80f52db6e63b030b35d8-a`. The selected archive is marked historical. The task requires a current source. |
| Recovery | 20 | `b6d7d38c16497e5d7dbc-a`. The trace selects publish. The observed timeout permits backup. |

The Qwen3-14B source audit found 81 sufficient judgments with a citation set different from the frozen one. The full proof still had to support the actual verdict. Another 198 conclusive judgments lacked sufficient citation support, including 76 conclusive judgments missing at least one exhibit from every minimal proof. The ledger records additional and missing evidence independently of polarity.

Qwen3-14B retained the same conclusive verdict for 71 of 75 pairs (94.7%). Two replanning cases passed in mixed Chinese and English and failed correctly in English. Two equivalent pending-delivery cases failed in Chinese and passed correctly in mixed language. For the full roster, the source contradicted 74/291 Chinese verdicts, 38/291 English verdicts and 32/225 mixed-language verdicts. The full-roster rates include differences in task mix. The four within-world flips establish a language-sensitive behavior on those cases.

## Gold and causal limits

Source rules read the visible task and exhibits only. The audit compares their results to Gold after recomputation. All 807 labels match the source interpretation. In 45 PASS packets the exact Gold citation set omits an exhibit required by the interpreted task. In 25 authorization cases, verifying the named approval issuer requires the policy in addition to the matching approved draft and action. In 20 wire-format cases, a syntactically valid object proves format and the verified observation establishes the requested count. By contrast, malformed JSON is a sufficient counterexample without the observation. The report retains 1,509 single-exhibit removals from minimal proof sets.

Several tasks leave scope for interpretation in the generic rubric. The D20 rubric emphasizes wire format while the visible task also requires a verified value. The D22 false-success rubric mentions terminal evidence, which can bias a Judge against an accurate pending-state answer. In D25, the final claim of a pending status is rebutted by the persisted state. The source replay checks only evidence present for the specific task. Cross-family approval policy and business-state assurance require stage-specific proofs in general history.

All 131 unusable Q1 replies returned HTTP 200 and ended at the Judge token limit. Those raw replies are traceable in the archive and are classified as output truncation. A schema-constrained reply can terminate before its object is complete. The output limit remains part of the Q1 identity.

The ledger preserves injection-tagged worlds. A Judge error on such a world alone cannot establish that the injected text caused it. The existing matched intervention captures supply the controlled comparison. [Meta-evaluation replay](IJ073_META_EVALUATION.md)

## Replay

Run with the project Python environment and the repository root and `src` on `PYTHONPATH`.

```text
python -m evaluation.aeve.q1_source_audit --output .runtime/q1_source_audit.json --ledger .runtime/q1_root_cause_ledger.jsonl.gz
```

[Frozen Q1 qualification](IJ073_JUDGE_QUALIFICATION.md) · [Source summary](../evidence/IJ073/aeve/q1_source_audit.json) · [Full ledger](../evidence/IJ073/aeve/q1_root_cause_ledger.jsonl.gz)
