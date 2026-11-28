# IJ-NANO-48H — E1 Cognitive Capability Atlas (development)

Chat protocol, temperature 0, seed 42, 1024-token generation budget, frozen renderer; 640 development cases x 3 models. Semantic accuracy counts CORRECT over model-evaluable outcomes only.

## Campaign provenance

| Batch | Experiment | Trials | Sealed |
|---|---|---:|---|
| A | `N03-AUTH2-DEVELOPMENT-BATCH-A-v2-RQ` | 480 | SEALED |
| B | `N03-AUTH2-DEVELOPMENT-BATCH-B-v1` | 480 | SEALED |
| C | `N03-AUTH2-DEVELOPMENT-BATCH-C-v1` | 480 | SEALED |
| D | `N03-AUTH2-DEVELOPMENT-BATCH-D-v1` | 480 | SEALED |

## Overall

| Model | n | Accuracy | EMPTY | INVALID | Mean latency | Mean completion tokens |
|---|---:|---:|---:|---:|---:|---:|
| LFM3-1.7B | 640 | 43.906% | 26.875% | 22.188% | 3.68 s | 629.2 |
| MiniCPM5-2B | 640 | 46.250% | 19.688% | 24.062% | 2.94 s | 530.6 |
| Qwen3.5-2B | 640 | 17.500% | 79.062% | 2.656% | 4.60 s | 939.9 |

## Per-primitive semantic accuracy

| Primitive | LFM3-1.7B | MiniCPM5-2B | Qwen3.5-2B |
|---|---:|---:|---:|
| C01 | 100.000% (20) | 100.000% (20) | 60.000% (20) |
| C02 | 0.000% (20) | 0.000% (20) | 0.000% (20) |
| C03 | 50.000% (20) | 40.000% (20) | 40.000% (20) |
| C04 | 0.000% (20) | 0.000% (20) | 10.000% (20) |
| C05 | 100.000% (20) | 100.000% (20) | 60.000% (20) |
| C06 | 100.000% (20) | 100.000% (20) | 95.000% (20) |
| C07 | 65.000% (20) | 100.000% (20) | 65.000% (20) |
| C08 | 15.000% (20) | 50.000% (20) | 15.000% (20) |
| C09 | 100.000% (20) | 70.000% (20) | 25.000% (20) |
| C10 | 100.000% (20) | 100.000% (20) | 10.000% (20) |
| C11 | 50.000% (20) | 100.000% (20) | 0.000% (20) |
| C12 | 95.000% (20) | 75.000% (20) | 10.000% (20) |
| C13 | 45.000% (20) | 50.000% (20) | 15.000% (20) |
| C14 | 100.000% (20) | 40.000% (20) | 0.000% (20) |
| C15 | 10.000% (20) | 0.000% (20) | 0.000% (20) |
| C16 | 0.000% (20) | 35.000% (20) | 10.000% (20) |
| C17 | 0.000% (20) | 5.000% (20) | 0.000% (20) |
| C18 | 0.000% (20) | 0.000% (20) | 0.000% (20) |
| C19 | 0.000% (20) | 0.000% (20) | 0.000% (20) |
| C20 | 0.000% (20) | 0.000% (20) | 0.000% (20) |
| C21 | 0.000% (20) | 0.000% (20) | 0.000% (20) |
| C22 | 0.000% (20) | 0.000% (20) | 0.000% (20) |
| C23 | 20.000% (20) | 25.000% (20) | 0.000% (20) |
| C24 | 0.000% (20) | 0.000% (20) | 0.000% (20) |
| C25 | 100.000% (20) | 100.000% (20) | 60.000% (20) |
| C26 | 50.000% (20) | 80.000% (20) | 0.000% (20) |
| C27 | 55.000% (20) | 100.000% (20) | 10.000% (20) |
| C28 | 0.000% (20) | 0.000% (20) | 25.000% (20) |
| C29 | 100.000% (20) | 60.000% (20) | 0.000% (20) |
| C30 | 0.000% (20) | 0.000% (20) | 0.000% (20) |
| C31 | 100.000% (20) | 50.000% (20) | 0.000% (20) |
| C32 | 50.000% (20) | 100.000% (20) | 50.000% (20) |

Cells show accuracy (trials). `—` = no evaluable evidence yet — never treated as zero.

## Language split (post-hoc, all 32 primitives)

| Model | EN accuracy | ZH accuracy |
|---|---:|---:|
| MiniCPM5-2B | .4781 (n=320) | .4469 (n=320) |
| LFM3-1.7B | .3937 (n=320) | .4844 (n=320) |
| Qwen3.5-2B | .1844 (n=320) | .1656 (n=320) |

Model x language interaction: LFM3-1.7B is markedly stronger in
Chinese (+9.1pp) while MiniCPM5-2B leans English (+3.1pp) —
deployment language choice matters at 2B scale. Post-hoc descriptive
split (not preregistered as a primary contrast).
