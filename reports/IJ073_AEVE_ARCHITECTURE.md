# AEVE 评价合同与复现入口

AEVE 对一个已发生的试次给出分维度判断。输入包含公开任务、实际生成、工具事件及可取得的业务事实。每个事件有来源及摘要。缺失的后续动作保留为空。原判、复算事实、AI 意见和最终资格各有独立字段。

## 数据与可见性

- 历史清点固定在审阅提交 `88786ed8f01e9faf37ae458e66a6d9e953daba44`，验证 Git 对象和可取得的归档成员摘要。同一物理试次的检查点、重复执行、软件 witness、变异和离线派生物有不同的来源记录。
- 输入 Schema、判断 Schema、阶段要求和每维适用分母见 [AEVE 合同目录](../evaluation/aeve/)。只有真正提供给被测对象的材料能进入起始目标或计划判断。阶段投影保留用于引用复核的来源 ID。
- 事实重算使用原始快照和审计事件。语义正确、业务状态正确和协议正确分别计数。发生确定性失败时，后续模型意见作为审查资料保留。
- 候选模型看不到私有 Oracle；Judge 的输入不含历史得分、参考标签或待评模型身份。正式语义投票按已通过封存 Gold 的家族分配，并排除待测家族。两位 Judge 分别评判，争议交给第三个可用家族。正式裁决还要求独立 Judge 检查被引用的原始事件是否支持断言。引证不足、家族不足和不可解争议各有独立原因。

## 资格与运行

资格输入由可执行的有界规则生成。开发、校准、封存资格分组以基础世界为单位，配对变体只出现在同一分组。主资格试验固定四个 Judge × 807 个封存包。模型回复中的置信表述不参与区间估计；Macro-F1 区间按基础世界聚类重采样。引用门槛同时核对来源集合和由独立规则确定的结论方向。[评价器冻结清单](../evaluation/aeve/qualification_freeze.json)

每次推理保存冻结请求、实际传输内容、原始回复、原生生成、GPU 进程计数和模型身份。物理资格只使用完整封存的会话。中断后已写入但缺少会话封印的尝试隔离保存，任务重新排队。多工作树和端口共用合作式 GPU 锁。无租约的第三方 GPU 程序不受此进程锁控制。

## 命令

在包含模型和引擎的原工作站，使用项目虚拟环境，在 PR 工作树根目录运行以下命令。PowerShell 使用 `$env:PYTHONPATH='.;src'`，Linux 软件复验使用 `PYTHONPATH=.:src`。

```text
python -m evaluation.aeve verify
python -m evaluation.aeve resume
python -m evaluation.aeve qualification --split qualification
python -m evaluation.aeve history-report
```

`resume` 从本地 SQLite 队列恢复，按批归档。全新检出通过 `--assets` 指向保有已登记权重、引擎和依赖的目录，通过 `--state` 指向现有队列，或用 `python -m evaluation.aeve restore` 从可移植归档恢复既有判定。恢复不会新造模型调用时间或人工记录。

在无模型的检出上，`verify` 复核软件冻结和封存材料。`qualification` 只统计可验证的真实历史调用。正式历史评分依赖足够家族通过 Gold，独立人工盲审还依赖全量适用历史评分及独立资格。后续正式物理试验须等到人工校准及 Benchmark Validity 放行。


## P0 entrypoint regressions

At 04dc9ab, `oracle_panel.py:20` supplied treatment keywords to `runner.py:14`, whose signature stopped at `constrained`. `python -m evaluation.aeve.controller seed-oracle` raised TypeError on the clarification arm. Commit 9056349 implemented the treatment and goal-track arguments. The portable A/B result has five paired treatment configurations and the expanded panel has 64 cells.

At the same revision, `controller.py:87` imported an absent gold loader. `python -m evaluation.aeve.controller seed-gold` raised ModuleNotFoundError before reserving a trial. Commit 7af37af supplied the generator, independent rule labels, split manifest and loader. The entrypoint regression uses a fresh SQLite directory for each command. It also checks duplicate reservations and the complete four-family qualification roster. [Recorded RED/GREEN commands and exits](../evidence/IJ073/aeve/entrypoint_regression.json)
