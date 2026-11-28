# Atlas A1 提示合同因果分析

IJ-0.7 P0 在同一 system 消息同时要求初始计划和最终答案。运行器首轮拒绝调用工具或计划字段以外的响应。零工具场景仍需两轮。软件手工例可满足合同，一轮模型结果是否受指令竞争影响还需要 P0/P1 配对。 [请求](../benchmarks/agentic_planning_v1/contract.py#L45-L87) · [解析与切换](../benchmarks/agentic_planning_v1/runner.py#L151-L165)

对原始 1,600 条规划记录运行分层诊断，Acting-first 最终协议 69/800、执行层 190/800。Plan-first 协议及计划均为 0/800，执行层 110/800。两轨语义契约和业务结果均为 0/800，原始严格终态仍各为 0/800。执行层可在零工具场景通过，因此不得当作目标完成。安全层只报告已捕获轨迹中有无越权、重复、未确认写或可识别的虚报成功。 [新诊断](../evidence/IJ071/planning-diagnostic-layered.json) · [复评入口](../scripts/tools/atlas_replay_planning.py)

| 对照臂 | 一次只改变的变量 | 状态 |
|---|---|---|
| P0 | IJ-0.7 原合同 | 已有冻结历史结果，配对控制 NOT_RUN |
| P1 | Plan/Act/Final 阶段合同 | NOT_RUN |
| P2 | P1 加独立最小格式示例 | NOT_RUN |
| P3 | P1 加原生结构化输出约束 | NOT_RUN |
| P4 | P1 加语义等价的简明工具描述 | NOT_RUN |
| P5 | 显式预注册交互项 | NOT_RUN |

PC-S 使用本机已下载的 Qwen3-8B Q8_0。已冻结 100 条 TC-V2、120 条 MULTITOOL 和 160 条规划任务，规划每条运行双轨，共 540 次诊断试次。三套任务各自平衡中文和英文。权重、引擎与模板哈希已通过静态预检。采样配置及真实推理仍待执行，当前 PC-S 为 NOT_RUN。 [官方模型卡](https://huggingface.co/Qwen/Qwen3-8B) · [诊断 roster](../atlas/benchmarks/pc_s_roster.json) · [静态预检](../evidence/IJ071/qwen3-8b-runtime-preflight.json)
