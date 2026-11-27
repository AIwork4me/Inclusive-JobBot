# AEVE Judge agreement and controlled bias

Primary split `qualification`. 53 GPU session manifests are pinned in the companion JSON.

| Judge | Planned | Recorded | Conclusive | Correct | Correct with gold citations | Abstained | Invalid |
|---|---:|---:|---:|---:|---:|---:|---:|
| Qwen | 807 | 807 | 806 | 662 | 547 | 1 | 0 |
| Gemma | 807 | 807 | 765 | 486 | 322 | 36 | 6 |
| Mistral | 807 | 807 | 609 | 389 | 192 | 192 | 6 |
| LFM | 807 | 807 | 634 | 391 | 256 | 54 | 119 |

Nominal Krippendorff agreement is 0.211 across 793 cases with overlapping decisions.

| Judge pair | Same-source conclusive pairs | First correct | Second correct |
|---|---:|---:|---:|
| LFM / Mistral | 486 | 305 | 292 |
| LFM / Gemma | 611 | 378 | 410 |
| LFM / Qwen | 633 | 391 | 530 |
| Mistral / Gemma | 596 | 379 | 388 |
| Mistral / Qwen | 609 | 389 | 504 |
| Gemma / Qwen | 764 | 486 | 622 |

The following groups describe the primary cases recorded so far. Counts on different cases can reflect case selection.

| Judge | Group | Planned | Recorded | Conclusive | Accuracy among conclusive |
|---|---|---:|---:|---:|---:|
| Qwen | language=en | 291 | 291 | 291 | 86.9% |
| Qwen | language=mixed | 225 | 225 | 224 | 85.7% |
| Qwen | language=zh | 291 | 291 | 291 | 74.6% |
| Qwen | injection=False | 672 | 672 | 671 | 85.2% |
| Qwen | injection=True | 135 | 135 | 135 | 66.7% |
| Gemma | language=en | 291 | 291 | 288 | 72.2% |
| Gemma | language=mixed | 225 | 225 | 222 | 61.7% |
| Gemma | language=zh | 291 | 291 | 255 | 55.3% |
| Gemma | injection=False | 672 | 672 | 632 | 66.5% |
| Gemma | injection=True | 135 | 135 | 133 | 49.6% |
| Mistral | language=en | 291 | 291 | 247 | 61.9% |
| Mistral | language=mixed | 225 | 225 | 167 | 69.5% |
| Mistral | language=zh | 291 | 291 | 195 | 61.5% |
| Mistral | injection=False | 672 | 672 | 484 | 63.0% |
| Mistral | injection=True | 135 | 135 | 125 | 67.2% |
| LFM | language=en | 291 | 291 | 218 | 72.0% |
| LFM | language=mixed | 225 | 225 | 195 | 65.1% |
| LFM | language=zh | 291 | 291 | 221 | 48.4% |
| LFM | injection=False | 672 | 672 | 539 | 62.7% |
| LFM | injection=True | 135 | 135 | 95 | 55.8% |

Paired controls have 224/224 captured responses.

| Judge | Treatment | Conclusive pairs / planned | Improved | Degraded | Both correct with gold citations |
|---|---|---:|---:|---:|---:|
| Qwen | claim_other | 4 / 4 | 0 | 0 | 4 |
| Qwen | claim_own | 4 / 4 | 0 | 0 | 4 |
| Qwen | claim_unknown | 4 / 4 | 0 | 0 | 4 |
| Qwen | fact_changed | 4 / 4 | 0 | 0 | 4 |
| Qwen | injection | 4 / 4 | 0 | 0 | 4 |
| Qwen | irrelevant_turn | 4 / 4 | 0 | 0 | 4 |
| Qwen | json_key_order | 4 / 4 | 0 | 0 | 4 |
| Qwen | long_equivalent | 4 / 4 | 0 | 0 | 4 |
| Qwen | markdown | 4 / 4 | 0 | 0 | 4 |
| Qwen | observation_order | 4 / 4 | 0 | 0 | 4 |
| Qwen | prompt_paraphrase | 4 / 4 | 0 | 0 | 4 |
| Qwen | repeat | 4 / 4 | 0 | 0 | 4 |
| Qwen | translation | 4 / 4 | 0 | 0 | 4 |
| Gemma | claim_other | 4 / 4 | 0 | 0 | 1 |
| Gemma | claim_own | 4 / 4 | 0 | 0 | 1 |
| Gemma | claim_unknown | 4 / 4 | 0 | 0 | 1 |
| Gemma | fact_changed | 4 / 4 | 2 | 2 | 0 |
| Gemma | injection | 4 / 4 | 0 | 0 | 0 |
| Gemma | irrelevant_turn | 4 / 4 | 0 | 0 | 1 |
| Gemma | json_key_order | 4 / 4 | 0 | 0 | 0 |
| Gemma | long_equivalent | 4 / 4 | 0 | 0 | 1 |
| Gemma | markdown | 4 / 4 | 0 | 0 | 1 |
| Gemma | observation_order | 4 / 4 | 0 | 0 | 1 |
| Gemma | prompt_paraphrase | 4 / 4 | 0 | 0 | 0 |
| Gemma | repeat | 4 / 4 | 0 | 0 | 1 |
| Gemma | translation | 4 / 4 | 1 | 0 | 0 |
| Mistral | claim_other | 4 / 4 | 0 | 0 | 0 |
| Mistral | claim_own | 4 / 4 | 0 | 0 | 0 |
| Mistral | claim_unknown | 4 / 4 | 0 | 1 | 0 |
| Mistral | fact_changed | 4 / 4 | 1 | 1 | 0 |
| Mistral | injection | 4 / 4 | 1 | 1 | 0 |
| Mistral | irrelevant_turn | 4 / 4 | 1 | 1 | 0 |
| Mistral | json_key_order | 4 / 4 | 0 | 0 | 0 |
| Mistral | long_equivalent | 4 / 4 | 0 | 1 | 0 |
| Mistral | markdown | 4 / 4 | 1 | 1 | 0 |
| Mistral | observation_order | 4 / 4 | 1 | 1 | 0 |
| Mistral | prompt_paraphrase | 4 / 4 | 0 | 1 | 0 |
| Mistral | repeat | 4 / 4 | 0 | 0 | 0 |
| Mistral | translation | 4 / 4 | 1 | 0 | 0 |
| LFM | claim_other | 4 / 4 | 0 | 0 | 0 |
| LFM | claim_own | 4 / 4 | 0 | 0 | 0 |
| LFM | claim_unknown | 4 / 4 | 0 | 0 | 0 |
| LFM | fact_changed | 4 / 4 | 2 | 2 | 0 |
| LFM | injection | 3 / 4 | 0 | 0 | 0 |
| LFM | irrelevant_turn | 4 / 4 | 0 | 0 | 0 |
| LFM | json_key_order | 3 / 4 | 0 | 0 | 0 |
| LFM | long_equivalent | 4 / 4 | 0 | 0 | 0 |
| LFM | markdown | 4 / 4 | 0 | 0 | 0 |
| LFM | observation_order | 3 / 4 | 0 | 0 | 0 |
| LFM | prompt_paraphrase | 4 / 4 | 0 | 0 | 0 |
| LFM | repeat | 4 / 4 | 0 | 0 | 0 |
| LFM | translation | 4 / 4 | 0 | 0 | 0 |

Within-source translation comparisons control for the label-language correlation in these four baselines.
Synthetic attribution labels measure sensitivity to a claimed source. Actual own-family preference needs blinded model-authored examples.
Each treatment compares at most four source cases. Exact McNemar p-values are descriptive, with no multiplicity adjustment.
Primary coverage and agreement describe this archive snapshot. Admission uses the frozen qualification procedure.
