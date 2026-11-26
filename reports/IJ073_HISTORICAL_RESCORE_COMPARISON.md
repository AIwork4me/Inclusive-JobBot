# IJ-0 至 IJ-0.7.3 历史逐案复评分差异

逐试次文件采用 gzip 压缩的 JSONL。每行包含 Run ID、Case ID、Attempt ID、配置指纹、证据类型和来源。original_status 和 archived_dimensions 保存旧值，deterministic 保存本轮重算值，current 保存各维度当前可观测结果。物理正式判定存入 reviews.formal，非物理独立证据的正式判定存入 reviews.supplement，开发记录存入 reviews.development。

同义字段构成 comparisons 列。原有整体状态和 strict_sop_status 保持原实验含义，无法据此推定任一层级的表现。硬事实冲突及当前严格成功所需层级的否决保存在 vetoes。

| 可比维度 | 旧值 | 新值 | 试次 |
|---|---|---|---:|
| D23 | FAIL | FAIL | 721 |
| D23 | NOT_RUN | NOT_RUN | 1021 |
| D23 | PASS | PASS | 9463 |
| trace_status | FAIL | FAIL | 940 |
| trace_status | PASS | PASS | 286 |

缺少原有整体状态的试次有 2887 条，当前存在硬事实冲突或严格成功否决的试次有 0 条。只有归档事实和正式裁决进入 current。

逐试次数据中的 evidence_refs 指向该 Judge 输入内的事件；citations 提供原始响应所在卷、解压后的 JSONL 行号、尝试 ID 与 SHA256。裁决理由描述证据可支持的问题，缺失的后续业务动作保持未观测。

[逐试次数据](../evidence/IJ073/aeve/history/rescore.jsonl.gz) · [分母、状态计数及哈希](../evidence/IJ073/aeve/history/rescore_summary.json)
