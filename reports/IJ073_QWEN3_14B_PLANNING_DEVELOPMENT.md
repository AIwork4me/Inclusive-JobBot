# Qwen3-14B 条件规划双轨诊断

16 个不同任务覆盖 L0–L7 和中英文，每个任务配对 Native、Constrained 与给定目标、推断目标，共 64 个预注册请求。当前有 64/64 个已封存的物理请求。Oracle 判定 PASS 2，FAIL 62，BLOCKED 0，NOT_RUN 0。

冻结评分器先验证计划结构和 goal，再在固定的合成业务世界内执行可通过校验的计划。inferred 隐去顶层目标字段，评分器仍要求 goal 与合同标签逐字一致。语义等价的目标表述可能被拒绝。逐案数据另列标签是否出现在其余公开请求文本中。此面板无法给出自然语言目标理解准确率。

每格计划 1 次模型请求、0 次重试，输出上限 768 tokens。下表列出各任务的工具预算与上下文上限。已封存请求的 token 用量来自实际传输；工具记录来自固定世界中的软件执行。请求与重试计数以封存包为边界，未封存尝试不可核验。没有工具记录时保持未观测。每格仅一次，不估计跨任务总体成功率或重复可靠性。

| 任务 | 级别/语言 | 模式/目标 | 工具/上下文上限 | 实测上下文 | 传输 | Oracle | 字面目标 | 已执行调用 | 轨迹复核 | 校验/执行原因 | 原始证据 |
|---|---|---|---:|---:|---|---|---|---:|---|---|---|
| AP1-L0-001 | L0/en | native/provided | 0/4096 | 1671 | PASS | FAIL | PASS | — | NOT_RUN | invalid V2 schema | [卷内第 1 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L0-001 | L0/en | constrained/provided | 0/4096 | 1528 | PASS | FAIL | PASS | — | NOT_RUN | undefined terminal reference | [卷内第 2 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L0-001 | L0/en | native/inferred | 0/4096 | 1693 | PASS | FAIL | FAIL | — | NOT_RUN | incorrect public objective | [卷内第 3 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L0-001 | L0/en | constrained/inferred | 0/4096 | 1530 | PASS | FAIL | FAIL | — | NOT_RUN | incorrect public objective | [卷内第 4 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L0-002 | L0/zh | native/provided | 0/4096 | 2046 | FAIL | FAIL | NOT_RUN | — | NOT_RUN | incomplete_generation_or_transport | [卷内第 5 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L0-002 | L0/zh | constrained/provided | 0/4096 | 1402 | PASS | FAIL | PASS | — | NOT_RUN | undefined terminal reference | [卷内第 6 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L0-002 | L0/zh | native/inferred | 0/4096 | 1515 | PASS | FAIL | FAIL | — | NOT_RUN | invalid V2 schema | [卷内第 7 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L0-002 | L0/zh | constrained/inferred | 0/4096 | 1404 | PASS | FAIL | FAIL | — | NOT_RUN | incorrect public objective | [卷内第 8 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L1-002 | L1/en | native/provided | 3/4096 | 1890 | PASS | FAIL | PASS | — | NOT_RUN | invalid V2 schema | [卷内第 9 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L1-002 | L1/en | constrained/provided | 3/4096 | 1731 | PASS | FAIL | PASS | 1 | PASS | no enabled action | [卷内第 10 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L1-002 | L1/en | native/inferred | 3/4096 | 1866 | PASS | FAIL | FAIL | — | NOT_RUN | incorrect public objective | [卷内第 11 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L1-002 | L1/en | constrained/inferred | 3/4096 | 1723 | PASS | FAIL | FAIL | — | NOT_RUN | incorrect public objective | [卷内第 12 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L1-001 | L1/zh | native/provided | 3/4096 | 1642 | PASS | FAIL | PASS | — | NOT_RUN | invalid V2 schema | [卷内第 13 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L1-001 | L1/zh | constrained/provided | 3/4096 | 1536 | PASS | PASS | PASS | 1 | PASS | terminal | [卷内第 14 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L1-001 | L1/zh | native/inferred | 3/4096 | 1662 | PASS | FAIL | FAIL | — | NOT_RUN | invalid V2 schema | [卷内第 15 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L1-001 | L1/zh | constrained/inferred | 3/4096 | 1534 | PASS | FAIL | FAIL | — | NOT_RUN | incorrect public objective | [卷内第 16 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L2-001 | L2/en | native/provided | 4/4096 | 1931 | PASS | PASS | PASS | 2 | PASS | terminal | [卷内第 17 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L2-001 | L2/en | constrained/provided | 4/4096 | 1768 | PASS | FAIL | PASS | — | NOT_RUN | unbound reference, undefined terminal reference | [卷内第 18 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L2-001 | L2/en | native/inferred | 4/4096 | 1742 | PASS | FAIL | FAIL | — | NOT_RUN | invalid V2 schema | [卷内第 19 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L2-001 | L2/en | constrained/inferred | 4/4096 | 1653 | PASS | FAIL | FAIL | — | NOT_RUN | incorrect public objective | [卷内第 20 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L2-002 | L2/zh | native/provided | 4/4096 | 2032 | PASS | FAIL | PASS | — | NOT_RUN | invalid V2 schema | [卷内第 21 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L2-002 | L2/zh | constrained/provided | 4/4096 | 1765 | PASS | FAIL | PASS | — | NOT_RUN | unbound reference, undefined terminal reference | [卷内第 22 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L2-002 | L2/zh | native/inferred | 4/4096 | 2085 | FAIL | FAIL | NOT_RUN | — | NOT_RUN | incomplete_generation_or_transport | [卷内第 23 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L2-002 | L2/zh | constrained/inferred | 4/4096 | 1670 | PASS | FAIL | FAIL | — | NOT_RUN | incorrect public objective | [卷内第 24 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L3-002 | L3/en | native/provided | 5/4096 | 2147 | PASS | FAIL | PASS | 2 | PASS | no enabled action | [卷内第 25 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L3-002 | L3/en | constrained/provided | 5/4096 | 2053 | PASS | FAIL | PASS | — | NOT_RUN | unbound reference, undefined terminal reference | [卷内第 26 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L3-002 | L3/en | native/inferred | 5/4096 | 2135 | PASS | FAIL | FAIL | — | NOT_RUN | invalid V2 schema | [卷内第 27 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L3-002 | L3/en | constrained/inferred | 5/4096 | 2051 | PASS | FAIL | FAIL | — | NOT_RUN | incorrect public objective | [卷内第 28 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L3-001 | L3/zh | native/provided | 4/4096 | 2025 | PASS | FAIL | PASS | — | NOT_RUN | unbound reference, undefined terminal reference | [卷内第 29 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L3-001 | L3/zh | constrained/provided | 4/4096 | 1901 | PASS | FAIL | PASS | — | NOT_RUN | unbound reference | [卷内第 30 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L3-001 | L3/zh | native/inferred | 4/4096 | 2105 | FAIL | FAIL | NOT_RUN | — | NOT_RUN | incomplete_generation_or_transport | [卷内第 31 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L3-001 | L3/zh | constrained/inferred | 4/4096 | 1838 | PASS | FAIL | FAIL | — | NOT_RUN | incorrect public objective | [卷内第 32 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L4-001 | L4/en | native/provided | 6/4096 | 2222 | FAIL | FAIL | NOT_RUN | — | NOT_RUN | incomplete_generation_or_transport | [卷内第 33 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L4-001 | L4/en | constrained/provided | 6/4096 | 2222 | FAIL | FAIL | NOT_RUN | — | NOT_RUN | incomplete_generation_or_transport | [卷内第 34 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L4-001 | L4/en | native/inferred | 6/4096 | 2214 | FAIL | FAIL | NOT_RUN | — | NOT_RUN | incomplete_generation_or_transport | [卷内第 35 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L4-001 | L4/en | constrained/inferred | 6/4096 | 2140 | PASS | FAIL | FAIL | — | NOT_RUN | incorrect public objective | [卷内第 36 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L4-002 | L4/zh | native/provided | 7/4096 | 2245 | FAIL | FAIL | NOT_RUN | — | NOT_RUN | incomplete_generation_or_transport | [卷内第 37 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L4-002 | L4/zh | constrained/provided | 7/4096 | 2245 | FAIL | FAIL | NOT_RUN | — | NOT_RUN | incomplete_generation_or_transport | [卷内第 38 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L4-002 | L4/zh | native/inferred | 7/4096 | 2237 | FAIL | FAIL | NOT_RUN | — | NOT_RUN | incomplete_generation_or_transport | [卷内第 39 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L4-002 | L4/zh | constrained/inferred | 7/4096 | 2237 | FAIL | FAIL | NOT_RUN | — | NOT_RUN | incomplete_generation_or_transport | [卷内第 40 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L5-008 | L5/en | native/provided | 4/4096 | 2131 | PASS | FAIL | PASS | 2 | PASS | blocked call after denial | [卷内第 41 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L5-008 | L5/en | constrained/provided | 4/4096 | 2120 | PASS | FAIL | PASS | — | NOT_RUN | unbound reference, undefined terminal reference | [卷内第 42 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L5-008 | L5/en | native/inferred | 4/4096 | 2024 | PASS | FAIL | FAIL | — | NOT_RUN | incorrect public objective | [卷内第 43 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L5-008 | L5/en | constrained/inferred | 4/4096 | 2114 | PASS | FAIL | FAIL | — | NOT_RUN | incorrect public objective | [卷内第 44 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L5-005 | L5/zh | native/provided | 7/4096 | 1975 | PASS | FAIL | PASS | 2 | PASS | no enabled action | [卷内第 45 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L5-005 | L5/zh | constrained/provided | 7/4096 | 1971 | PASS | FAIL | PASS | — | NOT_RUN | unbound reference, undefined terminal reference | [卷内第 46 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L5-005 | L5/zh | native/inferred | 7/4096 | 1980 | PASS | FAIL | FAIL | — | NOT_RUN | invalid V2 schema | [卷内第 47 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L5-005 | L5/zh | constrained/inferred | 7/4096 | 1899 | PASS | FAIL | FAIL | — | NOT_RUN | incorrect public objective | [卷内第 48 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L6-005 | L6/en | native/provided | 17/6144 | 2345 | FAIL | FAIL | NOT_RUN | — | NOT_RUN | incomplete_generation_or_transport | [卷内第 49 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L6-005 | L6/en | constrained/provided | 17/6144 | 2345 | FAIL | FAIL | NOT_RUN | — | NOT_RUN | incomplete_generation_or_transport | [卷内第 50 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L6-005 | L6/en | native/inferred | 17/6144 | 2338 | FAIL | FAIL | NOT_RUN | — | NOT_RUN | incomplete_generation_or_transport | [卷内第 51 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L6-005 | L6/en | constrained/inferred | 17/6144 | 2338 | FAIL | FAIL | NOT_RUN | — | NOT_RUN | incomplete_generation_or_transport | [卷内第 52 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L6-012 | L6/zh | native/provided | 14/6144 | 2346 | FAIL | FAIL | NOT_RUN | — | NOT_RUN | incomplete_generation_or_transport | [卷内第 53 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L6-012 | L6/zh | constrained/provided | 14/6144 | 2264 | PASS | FAIL | PASS | — | NOT_RUN | unavailable tool or invalid argument keys | [卷内第 54 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L6-012 | L6/zh | native/inferred | 14/6144 | 2339 | FAIL | FAIL | NOT_RUN | — | NOT_RUN | incomplete_generation_or_transport | [卷内第 55 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L6-012 | L6/zh | constrained/inferred | 14/6144 | 2146 | PASS | FAIL | FAIL | — | NOT_RUN | incorrect public objective | [卷内第 56 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L7-004 | L7/en | native/provided | 10/6144 | 2343 | FAIL | FAIL | NOT_RUN | — | NOT_RUN | incomplete_generation_or_transport | [卷内第 57 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L7-004 | L7/en | constrained/provided | 10/6144 | 2343 | FAIL | FAIL | NOT_RUN | — | NOT_RUN | incomplete_generation_or_transport | [卷内第 58 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L7-004 | L7/en | native/inferred | 10/6144 | 2336 | FAIL | FAIL | NOT_RUN | — | NOT_RUN | incomplete_generation_or_transport | [卷内第 59 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L7-004 | L7/en | constrained/inferred | 10/6144 | 2336 | FAIL | FAIL | NOT_RUN | — | NOT_RUN | incomplete_generation_or_transport | [卷内第 60 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L7-005 | L7/zh | native/provided | 11/6144 | 2296 | FAIL | FAIL | NOT_RUN | — | NOT_RUN | incomplete_generation_or_transport | [卷内第 61 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L7-005 | L7/zh | constrained/provided | 11/6144 | 2296 | FAIL | FAIL | NOT_RUN | — | NOT_RUN | incomplete_generation_or_transport | [卷内第 62 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L7-005 | L7/zh | native/inferred | 11/6144 | 2288 | FAIL | FAIL | NOT_RUN | — | NOT_RUN | incomplete_generation_or_transport | [卷内第 63 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |
| AP1-L7-005 | L7/zh | constrained/inferred | 11/6144 | 2248 | PASS | FAIL | FAIL | — | NOT_RUN | incorrect public objective | [卷内第 64 行](../evaluation/aeve/results/sessions/ij073-1cfa81a033c948258551ab94896c9cf2/captures.jsonl.gz) |

## 配对分母

| 模式/目标 | 封存/预注册 | Oracle 通过/封存 | 双语均已封存的级别 |
|---|---:|---:|---:|
| native/provided | 16/16 | 1/16 | 8/8 |
| native/inferred | 16/16 | 0/16 | 8/8 |
| constrained/provided | 16/16 | 1/16 | 8/8 |
| constrained/inferred | 16/16 | 0/16 | 8/8 |

## 失败原因和实际检查分母

- blocked call after denial 出现在 1 个已封存请求中。
- incomplete_generation_or_transport 出现在 23 个已封存请求中。
- incorrect public objective 出现在 16 个已封存请求中。
- invalid V2 schema 出现在 9 个已封存请求中。
- no enabled action 出现在 3 个已封存请求中。
- unavailable tool or invalid argument keys 出现在 1 个已封存请求中。
- unbound reference 出现在 7 个已封存请求中。
- undefined terminal reference 出现在 8 个已封存请求中。

- 封存模型请求预算可核验 64/64，超限 0。
- 同一任务在封存包内的额外尝试预算可核验 64/64，超限 0。
- 上下文预算可核验 64/64，超限 0。
- 生成长度预算可核验 64/64，超限 0。
- 合成世界工具调用预算可核验 6/64，超限 0。

轨迹复核使用冻结世界重建初态，逐一重放实际记录的工具、参数和观测，并比较记录的终态。工具记录为空时没有可复核调用，终答与业务状态另行比较。未通过结构校验或传输失败的记录保留原始诊断。

[逐案预算、证据哈希及原因](../evidence/IJ073/oracle/planning_development.json) · [面板选择和请求构造](../evaluation/aeve/oracle_panel.py) · [冻结控制世界](../benchmarks/agentic_planning_v1/task_graphs/holdout.jsonl)
