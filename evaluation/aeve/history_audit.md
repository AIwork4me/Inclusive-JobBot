# 历史证据适配器审计

审计输入固定在 `88786ed8f01e9faf37ae458e66a6d9e953daba44` 的 1,341 个证据文件。每个原始文件先与 Git tree 的大小及 blob 标识比对，再由适配器读取。5,500 个独立保留的原始试次检查点还逐个核验了发表的 SHA256。注册表的 sources 保存归档路径、组内位置及记录指纹。对于经规范化的早期格式，记录指纹覆盖适配器产生的记录，原始文件身份由 assets.json 单独绑定。

| 源码与最小复现 | 旧流程的表现 | 修正与独立回归 |
| --- | --- | --- |
| history_inputs.packet 和旧 intake 对一个含初始计划、读取、用户更新、最终答案的对话生成 D09 资料 | D09 可以读到未来观测和最终答案。先收集的更新标签还可能出现在触发它的工具调用之前。 | evidence_v2 按维度封存事件 ID。初始计划看不到执行数据，首次选工具看不到该次调用结果；仅在后续实际请求完整延续之前消息时插入新用户消息。test_decision_time_views_hide_later_changes_and_results 检查各阶段的确切事件序列。 |
| 原记录的请求未传工具，冻结任务在后续阶段有工具 | 用任务静态工具回填会在计划阶段引入未来才开放的能力。 | 原始请求优先，未声明工具对应空枚举。test_missing_plan_and_rejected_suggestion_remain_visible_without_an_execution 还检查被拒的提议只有 proposal，没有 action 或 observation。 |
| 用 17 个函数提议构成一次超出网关上限的回复，终端记录的 calls 为空 | 仅依靠执行轨迹会丢弃真实提议，造成“没有可评价输出”。 | first_decision 从实际 assistant 消息保留提议，并把执行证据留空。test_rejected_batch_preserves_proposal_but_never_synthesizes_observations 独立构造超限的 wire 回复。 |
| 同一 Case ID 分别出现在 ROCm 和 Vulkan 的离线评分文件 | 旧适配器采用共同父目录回填 run，合并了两个来源，出现评分相冲。 | 每条离线评分绑定其原始 run、Case ID 和独立评分来源。test_replay_link_requires_unique_original_identity 检查无歧义才能继承原始试次的语义判断。 |
| 一个 admission 对话的请求依次包含最初问题、先前一次工具回复、先前两次工具回复，随后从头启动 streaming 试验 | 逐条把 wire 请求登记成试次，将同一任务的多个连续回合计入物理分母。 | wire_episodes 仅对完整历史严格延长的请求做拼接。test_admission_groups_actual_continuations_but_separates_repeats 保留独立重试。 |
| 用 `{"unexpected":true}` 作为 Planning V1 的最终回答 | 旧适配器将能解析为 dict 等同于输出协议通过。 | history_scores.regrade 校验 disposition 与 facts 的键、类型及枚举，缺最终输出单列 NOT_RUN。test_parseable_wrong_final_contract_is_a_protocol_failure 同时检查两种输入。 |
| SDK 的系统消息中含带有运行模型别名的工作区目录 | 直接转发系统消息会泄漏生成模型身份。 | blind_content 在生成匿名展品 ID 前屏蔽环境路径和来源别名。test_blindness_removes_source_family_and_work_directory 使用合成目录独立验证。 |

物理输入共 17,458 个可评价的试次，36 个试次缺少可引用的决策材料。后者逐来源计数见 coverage.json。首次工具选择与参数维度仅评价第一次选择，后续依赖和恢复使用单独维度。软件控制、离线重放和物理试次的分母分别记账。nonphysical_evaluability.jsonl.gz 中的 source_trial_id 仅在原始身份唯一或产生派生记录的代码明确指定原始软件计划时填写。

在仓库根目录设置 `PYTHONPATH=.;src`，使用以下命令复验。

```powershell
python -m evaluation.aeve.history
python -m evaluation.aeve.history_supplement
python -m pytest -q tests/evaluator/test_aeve_history.py tests/evaluator/test_aeve_history_supplement.py
```

第一条命令在不提供本地原始运行目录时，从已公开的密封投影重建物理注册表及展品。原机器可追加 `--local-runs` 指向实际检查点父目录，以重新核验原始文件。第二条命令按独立的非物理分母重新运行适用的软件控制，保留其原始状态、目前的确定性复验和供 Judge 评估的观察事实。


## Physical dimension addendum

`python -m evaluation.aeve.history_dimensions` recomputes the 25-dimension inventory and addendum on a fresh checkout. The recorded 437,350 cells span all 17,494 physical trials. The 1,515 additional D04 cells require a real terminal answer and a clarification or missing-information duty in the initial brief. The addendum also records 2,115 budget results, 6,857 native protocol results, 1,091 authorization-state results and 107 strict-success vetoes from independently checked required layers. Each change retains the earlier status, source record and rule basis. An unsupported parser format or missing snapshot retains its unresolved classification. [Machine-readable per-dimension counts](../../evidence/IJ073/aeve/history/physical_addendum.json)
