# Five-model TC-V3 physical measurement

All 8,250 frozen trials have replayable Radeon execution evidence. Physical coverage is PASS. Strict D25 remains BLOCKED for all 8,250 slots. Scoped completion uses cases where both paths have evaluable observations.

| Model | SDK first tool | Required coverage | Exact sequence | Execution | Output | Termination | Direct completion | SDK completion |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A | 449/500 | 488/500 | 116/500 | 117/500 | 184/500 | 107/500 | 372/400 | 2/400 |
| B | 491/500 | 491/500 | 350/500 | 357/500 | 398/500 | 318/500 | 361/400 | 218/400 |
| D | 449/500 | 466/500 | 420/500 | 443/500 | 85/500 | 402/500 | 272/400 | 80/400 |
| F | 465/500 | 472/500 | 372/500 | 390/500 | 0/500 | 359/500 | 39/398 | 0/398 |
| G | 500/500 | 489/500 | 489/500 | 489/500 | 0/500 | 483/500 | 0/400 | 0/400 |

[Paired results](PAIRED_RESULTS.json) · [Resource Pareto](QUALITY_RESOURCE_PARETO.md) · [Interactive report](report.html) · [中文报告](ENGINEERING_REPORT_ZH.md) · [Evidence](EVIDENCE_MANIFEST.json)

Reproduce from a repository checkout with `PYTHONPATH=src` and `python -m benchmarks.slm10.tc_five_model_milestone`.
