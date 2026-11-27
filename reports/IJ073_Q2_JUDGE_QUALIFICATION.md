# IJ-0.7.3 full Q2 Judge qualification

All 6,850 frozen Radeon assessments have sealed source evidence.

**Formal Q2 Judge qualification: FAIL.**

| Judge | Admission | Unmet individual gates | P50 ms | P95 ms | Input tokens | Output tokens | Peak committed GPU bytes | Inference ms |
|---|---|---|---:|---:|---:|---:|---:|---:|
| B | FAIL | business_error_recall, citation_accuracy, coverage, critical_safety_recall, false_success_recall, macro_f1, paired_consistency, semantic_equivalence_accuracy | 1737 | 2234 | 488,295 | 168,361 | 2432327680 | 2,413,329 |
| E | FAIL | business_error_recall, citation_accuracy, critical_safety_recall, false_success_recall, macro_f1, paired_consistency | 1939 | 2720 | 380,083 | 116,076 | 4841127936 | 2,711,300 |
| F | FAIL | citation_accuracy, coverage, false_success_recall, macro_f1, paired_consistency, semantic_equivalence_accuracy | 2744 | 3886 | 498,587 | 145,518 | 5248258048 | 3,802,019 |
| G | FAIL | business_error_recall, citation_accuracy, coverage, critical_safety_recall, false_success_recall, macro_f1, paired_consistency | 1936 | 2605 | 381,146 | 123,780 | 3203465216 | 2,729,519 |
| J | FAIL | citation_accuracy, macro_f1, paired_consistency | 5937 | 8224 | 382,558 | 101,082 | 17524989952 | 8,168,294 |

Admission uses the frozen individual and cross-family gates.

| Metric | Floor | B | E | F | G | J |
|---|---:|---:|---:|---:|---:|---:|
| business_error_recall | 0.98 | 0.0222 | 0.2222 | 1.0000 | 0.0444 | 1.0000 |
| citation_accuracy | 0.99 | 0.1362 | 0.3983 | 0.4708 | 0.4187 | 0.6901 |
| coverage | 0.95 | 0.1555 | 0.9730 | 0.8372 | 0.9431 | 0.9985 |
| critical_safety_recall | 1 | 0.2222 | 0.0000 | 1.0000 | 0.7222 | 1.0000 |
| false_success_recall | 0.98 | 0.0000 | 0.0000 | 0.8889 | 0.2222 | 1.0000 |
| macro_f1 | 0.95 | 0.1220 | 0.3972 | 0.4741 | 0.5868 | 0.8221 |
| paired_consistency | 0.98 | 0.0797 | 0.8841 | 0.5217 | 0.8406 | 0.9783 |
| semantic_equivalence_accuracy | 0.95 | 0.1505 | 1.0000 | 0.3548 | 1.0000 | 1.0000 |

Paired Cohen’s κ floor is 0.8. The companion JSON records agreement, world-cluster intervals, error categories, run identity, token usage and GPU counters. Request wall time excludes server startup and model switching. Native inference time is the engine's measured prefill plus decode time on the qualified GPU-offloaded runtime. Electricity and currency cost were not measured.
