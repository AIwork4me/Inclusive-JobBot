# Atlas A1 阳性与负向控制

| 软件对照 | 通过 / 计划 | 实际路径 |
|---|---:|---|
| TC-V2 | 500/500 | 非流式 runner、Gateway、SQLite、冻结 Oracle |
| MULTITOOL-V1 | 600/600 | 批次 runner、仿真工具、适用时的 SQLite、冻结 Oracle |
| AGENTIC-PLAN-V1 Acting-first | 800/800 | runner、边界校验、内存 sandbox、冻结 Oracle |
| AGENTIC-PLAN-V1 Plan-first | 800/800 | 同一 runner 加必需的初始计划回合 |
| JOB-V1 | 600/600 | 已知结构化输入、Skill/Gateway、SQLite、冻结 Oracle。非执行终态有同源预期注入。 |

上述为确定性软件对照。完整 3,300 条对照基于冻结参考轨迹，独立作者的覆盖目前为一条手工零工具任务，双轨均通过。 [运行脚本](../scripts/tools/atlas_controls.py) · [终态记录](../evidence/IJ071/controls-reconciled.json.gz)

首轮多工具对账有 37 条 FAIL，均来自带草稿状态的案例。单例比较表明两次 Gateway 事务产生独立随机审计 UUID。修订对账用审计正文多重集，保留事件数量、授权、状态、参数及回执，投影随机事务身份和耗时字段。保留首轮结果和具名回归。 [原始结果](../evidence/IJ071/controls-draft-red.json.gz) · [回归](../tests/regression/test_atlas_controls.py)

新增 15 项规划回归覆盖错误工具、缺参与错误参数、未获取的 ID、错误时序、提前写、伪造确认、重复提交、错误事实和状态、虚报成功、冗余升级、格式变异以及等价工具与顺序。用户改约的现有多工具回归和完整 Mutation 分布仍需跨套件逐项做对照。 [回归](../tests/regression/test_atlas_negative_controls.py)

复现命令为 `python scripts/tools/atlas_controls.py --output .runtime/atlas-controls.json`。真实强模型 PC-S 尚未执行。 [强模型说明](ATLAS_PROMPT_CONTRACT_CAUSAL_ANALYSIS.md)
