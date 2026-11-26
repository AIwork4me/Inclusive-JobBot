# AEVE Judge agreement and controlled bias

Primary split `development`. 8 GPU session manifests are pinned in the companion JSON.

| Judge | Planned | Recorded | Conclusive | Correct | Correct with gold citations | Abstained | Invalid |
|---|---:|---:|---:|---:|---:|---:|---:|
| Qwen | 404 | 12 | 12 | 11 | 10 | 0 | 0 |
| Gemma | 404 | 12 | 12 | 11 | 7 | 0 | 0 |
| Mistral | 404 | 36 | 30 | 21 | 11 | 5 | 1 |
| LFM | 404 | 0 | 0 | 0 | 0 | 0 | 0 |

Nominal Krippendorff agreement is -0.120 across 12 cases with overlapping decisions.

| Judge pair | Same-source conclusive pairs | First correct | Second correct |
|---|---:|---:|---:|
| LFM / Mistral | 0 | 0 | 0 |
| LFM / Gemma | 0 | 0 | 0 |
| LFM / Qwen | 0 | 0 | 0 |
| Mistral / Gemma | 9 | 3 | 8 |
| Mistral / Qwen | 9 | 3 | 9 |
| Gemma / Qwen | 12 | 11 | 11 |

The following groups describe the primary cases recorded so far. Counts on different cases can reflect case selection.

| Judge | Group | Planned | Recorded | Conclusive | Accuracy among conclusive |
|---|---|---:|---:|---:|---:|
| Qwen | language=en | 145 | 4 | 4 | 100.0% |
| Qwen | language=mixed | 113 | 3 | 3 | 100.0% |
| Qwen | language=zh | 146 | 5 | 5 | 80.0% |
| Qwen | injection=False | 336 | 10 | 10 | 90.0% |
| Qwen | injection=True | 68 | 2 | 2 | 100.0% |
| Gemma | language=en | 145 | 4 | 4 | 75.0% |
| Gemma | language=mixed | 113 | 3 | 3 | 100.0% |
| Gemma | language=zh | 146 | 5 | 5 | 100.0% |
| Gemma | injection=False | 336 | 10 | 10 | 90.0% |
| Gemma | injection=True | 68 | 2 | 2 | 100.0% |
| Mistral | language=en | 145 | 13 | 11 | 54.5% |
| Mistral | language=mixed | 113 | 11 | 9 | 77.8% |
| Mistral | language=zh | 146 | 12 | 10 | 80.0% |
| Mistral | injection=False | 336 | 28 | 23 | 69.6% |
| Mistral | injection=True | 68 | 8 | 7 | 71.4% |
| LFM | language=en | 145 | 0 | 0 | — |
| LFM | language=mixed | 113 | 0 | 0 | — |
| LFM | language=zh | 146 | 0 | 0 | — |
| LFM | injection=False | 336 | 0 | 0 | — |
| LFM | injection=True | 68 | 0 | 0 | — |

Paired controls have 0/224 captured responses.

Within-source translation comparisons control for the label-language correlation in these four baselines.
Synthetic attribution labels measure sensitivity to a claimed source. Actual own-family preference needs blinded model-authored examples.
Each treatment compares at most four source cases. Exact McNemar p-values are descriptive, with no multiplicity adjustment.
Primary coverage and agreement describe this archive snapshot. Admission uses the frozen qualification procedure.
