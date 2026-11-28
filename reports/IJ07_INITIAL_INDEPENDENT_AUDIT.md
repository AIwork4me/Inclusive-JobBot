# IJ-0.7 IJ-0.6 独立基线审计

以 [PR #2](https://github.com/AIwork4me/Inclusive-JobBot/pull/2) 开放状态下的审阅提交 `d2e5b31aa1f0894638f7b648a4cf3591fbb71e6e` 建立 IJ-0.7 堆叠分支。默认分支仍指向 `0592c319ab341f70bda979874697386e33ccc680`。基线提交中保存的 72 项 Git blob 与 IJ-0.6 的 173 项制品均通过 SHA256 核验。GitHub 针对此精确 HEAD 返回 11 项成功检查，覆盖软件回归和固定输入 C++ 解析器。 [基线清单](../evidence/IJ07/baseline_manifest.json) · [精确 HEAD CI](../evidence/IJ07/baseline_ci.json)

## 从原始逐条记录重新推导

| 口径 | Vulkan | ROCm/HIP |
|---|---:|---:|
| 历史 V1 全量通过 | 433/500 | 432/500 |
| V2 全量语义轨迹通过 | 459/500 | 458/500 |
| V2 全量 PASS / FAIL / BLOCKED | 420 / 41 / 39 | 420 / 42 / 38 |
| 历史 V1 多工具通过 | 58/100 | 58/100 |
| V2 多工具语义轨迹通过 | 84/100 | 84/100 |
| V2 多工具 PASS / FAIL / BLOCKED | 77 / 16 / 7 | 77 / 16 / 7 |
| V2 全步骤正确字段 | 794/821 | 794/821 |
| V1 通过但工单 tags 为空 | 15 | 15 |
| 多工具持久业务状态证据不足 | 22 | 22 |

两后端关联同一批 500 个 Case ID。重新生成的 V2 全部 1,000 条结果和汇总与归档逐字节一致。两后端共同的 `tc-seq-0043` 完成两项查询，但最终回答引用了错误订单。22 条多工具状态证据不足案例中，15 条保留明确参数错误的 `FAIL`，其余 7 条为 `BLOCKED`。15 条空 tags 的解析前原文缺失，历史根因保留 `ROOT_CAUSE_UNVERIFIED`。 [原始证据身份](../evidence/IJ06/rescoring/summary.json)

## 解析器、Gateway、SDK 与岗位试验

- P4b 两个后端各有 146 条固定输入，119 条适用原生断言通过，27 条原生断言 `NOT_RUN`。严格参数和协议一致性分别为 146/146。原始 wire 分类各为 141 PASS、5 FAIL，5 条均为重复 JSON 键的预期拒绝。保留原始分类。 [解析器分层报告](IJ06_PARSER_ROOT_CAUSE_REPORT.md)
- Gateway 归档的 209 条软件回归全部通过，其中包含模拟 HTTP 和历史 wire 回放。岗位开发试验在每个后端各保存 6 条执行记录，覆盖 3 种结构化单据和两个实验组。Qwen3-8B 的参考臂另有 3 条 Vulkan 记录。完整六组岗位因果实验仍为 `NOT_RUN`。 [Gateway](IJ06_SECURE_GATEWAY_REPORT.md) · [岗位试验](IJ06_PURPOSE_BUILT_CAUSAL_ANALYSIS.md)
- AG-01 至 AG-12 均有历史逐门记录。P4b 的 AG-06 在 Vulkan 为 `FAIL`，ROCm/HIP 为 `PASS`。原始 b12359 正好相反。AG-11 四份记录均为 `BLOCKED`。单次结构化字段差异不足以归因到 GPU 后端。 [SDK 记录](IJ06_ANTIGRAVITY_QUALIFICATION.md)

## 本机与复现

实测 Windows 11 build 26200、Ryzen AI MAX+ PRO 395、16 核 32 线程、Radeon 8060S、驱动 32.0.22018.5、安装内存 128 GiB。Windows 在采集时报告约 95.8 GiB 可见内存。探针连接本地 b12359 Vulkan 服务器。 [本次硬件采集](../evidence/IJ07/environment/windows.json)

```powershell
.venv/Scripts/python.exe -m scripts.tools.audit_ij07_baseline --check
.venv/Scripts/python.exe benchmarks/tool_calling/generators/generate_dataset.py --check
```

G0 为 `PASS`。结果适用于归档审计。IJ-0.7 新推理、独立 holdout 及生产资格单独举证。
