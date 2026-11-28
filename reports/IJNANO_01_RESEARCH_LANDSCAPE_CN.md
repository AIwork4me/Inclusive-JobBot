# IJ-NANO-1.0 — N01 研究全景（对象 R01–R09）

- 生成时间：2026-11-27 (N01)
- 范围：将 N01 主源核验扫描整合为任务令 §2
  （`docs/IJNANO_MISSION_ORDER_V1_1.md`）要求的研究全景交付物。不提出扫描记录
  之外的新主张；不进行网络浏览；不克隆或不执行任何对象代码。
- 权威输入：`evidence/IJNANO/N01/research_catalog.json` 以及
  `evidence/IJNANO/N01/agent_reports/` 下的四份核验扫描
  （R01_R04、R02_R08、R03_R05_R06、R07_R09）。
- 状态词汇：对象核验状态为 VERIFIED / PARTIALLY_VERIFIED，目录中的标注一律
  原样保留、绝不升级（R01 的论文发表场所保持 "PARTIALLY_VERIFIED"；R05 保持
  "VERIFIED as paper; NO CODE"；LLGuidance 保持 "UNVERIFIED_FOR_WINDOWS"）。
  执行状态（PASS / FAIL / BLOCKED / NOT_RUN）适用于运行时工作：在 N01 阶段，
  对任何对象的复现、本地 Windows 验证与业务评估**均按定义为 NOT_RUN**。唯一
  引用的已执行且 PASS 的证据是 llama.cpp b12359 的 N02 引擎探针证据。
- 机器可读配套文件：`evidence/IJNANO/N01/license_matrix.json`
  （逐对象/逐组件的许可证矩阵）与
  `reports/IJNANO_OPEN_SOURCE_REUSE_DECISION.md`（组件级复用决策）。

## 1. 逐对象证据（R01–R09）

每一小节记录任务令要求的十个字段：主源；论文确切身份；仓库版本；许可证；
模型参数量；模型权重是否改变（仅运行时 vs 微调）；评估方法（LLM 评审 vs
确定性判定）；实验指标；报告结果；复现局限。所有数值均为主源报告值，N01
阶段未复现其中任何一项。

### 1.1 R01 — effGen — VERIFIED（论文发表场所 PARTIALLY_VERIFIED）

| 字段 | 核验值 |
|---|---|
| 主源 | `https://github.com/ctrl-gaurav/effGen` — main @ `37de05a6b4ed01c90ee38b9c254a162927ca2ac2`（2026-10-01）；发布 v1.3.0（2026-10-01）；PyPI `effgen`；208 星 |
| 论文确切身份 | arXiv:2602.00887 "EffGen: Enabling Small Language Models as Capable Autonomous Agents"，v2 2026-06-14；Srivastava, Hussain, Wang, Lin, Wang（弗吉尼亚理工）。arXiv 声称 "Accepted to ICML 2026"；OpenReview 记录未能独立确认 —— 发表场所 **PARTIALLY_VERIFIED**（原样保留） |
| 许可证 | 代码 Apache-2.0；不分发任何权重工件；论文文本许可未在扫描中记录 |
| 模型参数量 | 1–3B 总量：Qwen2.5-1.5B-Instruct、Qwen2.5-3B-Instruct、Gemma 3 1B。更大规格：Qwen2.5-7B/14B/32B、Gemma 3 1B–27B、GPT-OSS 20B |
| 权重是否改变 | 否 —— 仅运行时；冻结开放权重；无微调；1,993 个文件的仓库中无权重工件 |
| 评估方法 | 确定性匹配；**无 LLM 评审**；13 个基准上 McNemar p<0.05；附录声称给出置信区间（未读） |
| 实验指标 | 13 个智能体基准的平均准确率；每任务 token 数；加速比 |
| 报告结果 | 1.5B：EffGen 47.44 对 Raw 34.28 / LangChain 32.81 / AutoGen 33.57 / Smolagents 27.81；3B：56.80；7B：63.07；32B：70.97；较 Smolagents（1.5B）最高 18 倍加速；每任务约 734 token，LangChain 为 1,318；规模消融：提示优化在 1.5B 价值 11.2%、32B 为 2.4%，路由在 1.5B 为 3.6%、32B 为 7.9%；声称工具错误恢复 70–87% |
| 复现局限 | 约 52 个基础运行时依赖（torch、transformers、fastapi、docker、3 个 Google SDK）—— 与最小运行时论点相矛盾；附录置信区间未读；Windows 本地"可信但未文档化"（UNVERIFIED）；发表场所未确认；扫描记录到营销润色与更新日志坦承回退 |

代码与论文中均核验到的机制：模型规模感知的 5 阶段提示优化（35 模板库）；YAML
工具描述压缩（较 JSON 省 32% token）；复杂度感知 ModelRouter（Cost/Latency
策略）；WorkflowDAG 任务分解；三层记忆（FAISS/Chroma）；MCP/A2A/ACP；
带优雅降级的重试/退避；循环检测（`max_turns_without_progress=2`，代码强于
论文）；`recover_lost_tool_calls=True` 默认开启（v1.3.0）；本地后端
（llama-cpp-python GGUF、Transformers、vLLM、MLX、任意 OpenAI 兼容
`base_url`）。复用类别：`RESEARCH_ONLY_FOR_REPRODUCTION`（E01 对照组）。

### 1.2 R02 — PTC-Decoder — VERIFIED

| 字段 | 核验值 |
|---|---|
| 主源 | `https://github.com/yuminghui/llm-tool-constrained-decoder` — 自 2026-07-19 起休眠；单一作者；3 星 |
| 论文确切身份 | arXiv:2609.30836 "PTC-Decoder: Towards Intelligent SLMs on Offline Resource-Constrained Edge Devices"，v1 2026-09-25，预印本，无发表场所；Yu, Mu, Wu |
| 许可证 | MIT（代码）+ CC BY 4.0（基准数据附录）；**论文文本 CC BY-NC-SA**（非商业） |
| 模型参数量 | 7 个 SLM，全部 ≤2B 总量：Qwen3.5-2B（任务期望 CONFIRMED）、Qwen3-1.7B、Qwen3-0.6B、Qwen3.5-0.8B、gemma-3-1b-it、gemma-4-E2B-it（2.3B 有效稠密 PLE；仓库误标 "2.0B MoE"）、DeepSeek-R1-Distill-Qwen-1.5B |
| 权重是否改变 | 否 —— 仅运行时；免训练约束解码；零权重变更 |
| 评估方法 | **LLM 评审**（DeepSeek-V4-flash，0–5 分制；20 个样本人工双检） |
| 实验指标 | 评审 "Overall" 分；ToolAlpaca / Seal-Tools / API-Bank 外部 F1；token 开销 |
| 报告结果 | 平均 Overall +1.21（p<0.01，95% CI [+1.13, +1.29]）；Qwen3.5-2B 上最佳 Overall 3.12；最弱模型 +350%；Qwen3-1.7B +48%；外部 F1 38→53 / 33→68 / 31→50；消融 remove-TC −0.99；token 开销 2.07 倍；反例：Qwen3-1.7B 约束下 F1 0.355 → 0.292 |
| 复现局限 | 仅 arXiv 预印本、无发表场所；休眠的单作者仓库；评审模型可用性依赖（DeepSeek-V4-flash）；仅 transformers 实现（torch 2.12、transformers 5.8.1）—— 与 llama.cpp 不兼容、不存在适配器；论文自认负例；2.07 倍 token 开销；测试环境为 Jetson Orin NX / Ubuntu 22.04，Windows 可信但未测试 |

机制（全部在代码中）：Plan-to-Act（强制首个 `plan` 工具调用）；HuggingFace
`LogitsProcessor` 屏蔽 DFA 不可接受 token + 接受处强制 EOS + PAD 掩码；
`char_fsm` NFA→DFA；逐步动态约束；`json_schema_to_fsm` 可在结构上约束参数，
但论文评估配置仅约束工具名、参数放开（论文/代码范围分歧；代码 ≥ 论文）。
复用类别：`REIMPLEMENT_CLEAN_ROOM` —— DFA+掩码+强制 EOS 设计必须经由
llama.cpp 逐请求 `json_schema`/`grammar`（或 XGrammar-2 结构标签）重新表达。

### 1.3 R03 — TinyAgent — VERIFIED

| 字段 | 核验值 |
|---|---|
| 主源 | `https://github.com/SqueezeAILab/TinyAgent` — MIT；自 2024-09-04 起休眠（约 6 次提交，503 星）；HF 工件 TinyAgent-1.1B/7B（含 GGUF）、TinyAgent-ToolRAG、TinyAgent-dataset，模型卡均为 MIT |
| 论文确切身份 | "TinyAgent: Function Calling at the Edge"，arXiv:2409.00608，EMNLP 2024 **Demo track** |
| 许可证 | MIT（代码、权重、数据集） |
| 模型参数量 | TinyAgent-1.1B（TinyLlama-1.1B 底座）—— R01–R09 语料中唯一的 1–3B 总量模型；TinyAgent-7B（WizardLM-2-7B） |
| 权重是否改变 | **是 —— 头条结果依赖微调权重**：LoRA 工具微调贡献 +66/+42 点（80K 合成样本，GPT-3.5/GPT-4 生成，数据成本约 500 美元）；运行时机制仅贡献约 1.2–1.9 点（ToolRAG，另带来约 2 倍提示压缩）；4-bit QAT 约 +0.3 |
| 评估方法 | 确定性 —— 其 1K 测试集上的程序化图同构判定；**无 LLM 评审** |
| 实验指标 | 函数调用准确率 |
| 报告结果 | 1.1B：底座 12.71% → +LoRA 78.89% → +ToolRAG 80.06% → +4bit 80.35%；7B：41.25% → 83.09% → 84.95% → 85.14%；基线 GPT-3.5-turbo 65.04%、GPT-4-turbo 79.08%；ToolRAG 平均选择约 3.97 个工具，朴素方式为 6（DeBERTa-v3-small 多标签分类器） |
| 复现局限 | 自生成合成评估；Demo track 论文；休眠仓库；**全部 16 个内置工具为 macOS AppleScript —— Windows 需要完全重写工具层**；核心（llama.cpp GGUF 服务）可移植 |

复用类别：`RESEARCH_ONLY` —— 权重变更型头条结果不可迁移到冻结权重运行时；
ToolRAG 是 M02 的机制研究对象。

### 1.4 R04 — 自动 SLM Harness 适配 — VERIFIED（仓库更名）

| 字段 | 核验值 |
|---|---|
| 主源 | `https://github.com/malusamayo/slm-harness-adaptation`（由 `migration-analysis` 更名，HTTP 301，同一仓库 id `R_kgDOQizbnA`）— MIT；main @ `2d31e1791a68f89554aa81c97d58fd62a636f4f4`（2026-09-04）；30 星；无发布/标签 |
| 论文确切身份 | arXiv:2607.08938 "Better Harnesses, Smaller Models: Building 90% Cheaper Agents via Automated Harness Adaptation"，v1 2026-07-09，cs.SE 预印本，无发表场所；Yang, Zhao, Wu, Kästner |
| 许可证 | MIT（+ MIT 子模块 `software-agent-sdk`，OpenHands SDK） |
| 模型参数量 | **3–8B 激活 / 8–30B 总量（MoE）**：gemma-4-26b-a4b、qwen3-coder-30b-a3b；另有 ministral-3-8b 稠密；前沿基线 gemini-3.1-pro。无 1–3B 总量模型 —— 本对象正是任务令"总量 vs 激活量"区分的实例 |
| 权重是否改变 | 否 —— 仅运行时；冻结云端权重（Vertex AI / Bedrock）；GEPA 式遗传/帕累托 harness 搜索，循环内含 Gemini 元智能体（gemini-3.1-pro-preview）；dspy>=3.0.4 |
| 评估方法 | 确定性客观任务指标；**评分无 LLM 评审**；3 次运行取平均，保留验证集最优；无置信区间；结果被描述为 "highly stochastic" |
| 实验指标 | 测试集平均任务成功率（每任务 20/20/60 训练/验证/测试划分）；单任务成本 |
| 报告结果 | gemma-4-26b-a4b 31.4% → 80.2%（$0.043 → $0.071）对前沿 89.7%（$1.735）；qwen3-coder-30b-a3b 26.9% → 76.3%；ministral-3-8b 9.5% → 25.0%；21 个任务–SLM 对中 16 个改善、3 个回退；$20/次运行、总计 $1,260；"平均 13 次运行后收回优化成本" |
| 复现局限 | 云 API + Docker + Python>=3.14 —— **无 Windows 原生路径**；figshare 复现包未在扫描中下载；摘要舍入不一致（声称 89.7% 对计算值 89.4%）；头条对比无统计显著性 |

复用类别：`RESEARCH_ONLY` —— N10 优化器设计的方法学输入（O0–O5 对照组）。

### 1.5 R05 — Growing Harness — VERIFIED as paper; NO CODE

| 字段 | 核验值 |
|---|---|
| 主源 | 仅 arXiv：**未找到代码**（论文无仓库链接；检索仅返回引用追踪站） |
| 论文确切身份 | arXiv:2609.26760 "Grow the Harness, Not the Context: From Strategy-Free Scaffolds to Reusable Specialist Agents"，v1 2026-09-22 / v2 2026-09-24，预印本；Li, Li, Zhao, Ye, Li, Xu, Gao（SIAT CAS、UCAS、SUSTech、UMacau） |
| 许可证 | 论文文本 CC BY 4.0；不存在其他可许可对象 |
| 模型参数量 | gpt-oss-120b、gpt-oss-20b、Qwen3.5-4B（最小 —— **无 1–3B 模型**）；优化器 GPT-5.6-terra / GPT-5.4（专有） |
| 权重是否改变 | 否 —— 仅运行时；无策略脚手架 + 以失败为引导，将重复出现的确定性控制决策（解析、校验、状态更新、错误恢复、停止）转化为可复用可执行代码；函数级轨迹；联合修复窗口；成功优先的保留集门控与回滚 |
| 评估方法 | **LLM 评审仅继承自 BrowseComp-Plus 基准**；其余为基准分数；3 次运行均值、bootstrap 置信区间；无独立验证（约 3 次引用） |
| 实验指标 | LLM 调用削减；推理成本；WebArena 成功率 |
| 报告结果 | LLM 调用削减 76.0–91.8%；推理成本 −74.4–98.6%；6 个设置中 5 个取得最佳均值；WebArena 44.7–45.3%，而 Tool-Calling 脚手架在 4B 处崩塌至 6.7% |
| 复现局限 | **仅论文 —— 无可运行对象**；优化器依赖专有前沿模型；无独立复现 |

复用类别：`RESEARCH_ONLY` —— 其原则（"将重复控制决策编译为确定性代码"）
即 M 机制 "Growing Harness" 臂 E06；按任务令 §8，任务专属业务逻辑与面向模型
的运行时逻辑保持分离。

### 1.6 R06 — Meta-Harness — VERIFIED

| 字段 | 核验值 |
|---|---|
| 主源 | `https://github.com/stanford-iris-lab/meta-harness` — MIT；创建于 2026-04-15，最近推送 2026-11-05，1814 星，活跃。工件 `meta-harness-tbench2-artifact` 存在但**无许可证（保留所有权利）—— UNLICENSED** |
| 论文确切身份 | "Meta-Harness: End-to-End Optimization of Model Harnesses"，arXiv:2603.28052（预印本）；Lee, Nair, Zhang, K. Lee, Khattab, Finn |
| 许可证 | 主仓库 MIT；TB2 工件 UNLICENSED（排除出任何复用）；论文文本许可未记录 |
| 模型参数量 | 部署模型：GPT-OSS-120B/20B、Claude Opus 4.6 / Haiku 4.5 —— 冻结、≥20B、参数量未另行说明；**无任何 1–3B 模型**。保留集数学模型：GPT-5.4-nano/mini、Gemini-3.1-Flash-Lite、Gemini-3-Flash |
| 权重是否改变 | 否 —— 仅运行时；围绕冻结底座模型对外层循环搜索单文件 Python harness 程序；提议者 = Claude Code + Opus-4.6（云端），可访问此前候选的代码、分数与**原始执行轨迹**（消融：原始轨迹 > 摘要）；仅任务奖励反馈 |
| 评估方法 | 确定性任务奖励；**无 LLM 评审**；但无种子扫描、标准差或置信区间；发布代码被描述为 "minimally tested" |
| 实验指标 | 任务得分（点）；上下文 token 数 |
| 报告结果 | 文本分类较 ACE +7.7 点且上下文 token 约少 4 倍；在 GPT-OSS-20B 上发现的数学 harness 在五个保留集模型上平均迁移 +4.7 点；TB2：Opus 76.4%（第 2）、Haiku 37.6%（第 1） |
| 复现局限 | 无 Windows/本地部署路径；TB2 假设 Linux 沙箱；统计严谨性缺失；生态采用真实（harness-forge、VideoHarness-RSI、HF spaces）但无独立复现；无许可证的 TB2 工件不可复用 |

复用类别：`RESEARCH_ONLY` —— N10 优化器方法学；"原始轨迹反馈 > 仅分数反馈"
消融可直接采用。

### 1.7 R07 — MagenticLite — VERIFIED

| 字段 | 核验值 |
|---|---|
| 主源 | 非独立仓库：`https://github.com/microsoft/magentic-ui`（PyPI `magentic_ui`，MIT）的下一代，位于 `main`（旧 0.1 AutoGen 线在分支 `magentic-ui-0.1`）；最近推送 2026-11-16，约 10.1k 星；v0.2.1（2026-05-21）、PyPI 0.2.2（2026-07-21）、Python >= 3.12 |
| 论文确切身份 | **无 —— 博客发布**（Microsoft Research AI Frontiers，2026 年 5 月），非论文 |
| 许可证 | MIT 代码 + MIT 权重；研究级告诫（Fara 模型卡：未经额外测试的商业使用不在范围内） |
| 模型参数量 | MagenticBrain 约 14B（自 Qwen3-14B 经 SFT+RL，32K 上下文）+ Fara1.5-9B（自 Qwen3.5-9B，262K 上下文，仅视觉）。**无 1–3B 模型 —— 此处 "small" 指 9–14B**；其他 Fara 规格除一句博客外未核验 |
| 权重是否改变 | 是（相对底座）—— MagenticBrain 为 Qwen3-14B 的 SFT+RL；Fara1.5-9B 来自 Qwen3.5-9B |
| 评估方法 | 扫描中未记录（未核验到论文指标） |
| 实验指标 | 扫描中未记录 |
| 报告结果 | 扫描中未记录 —— 仅有设计主张：步进式增量规划；主动上下文管理（筛选/压缩小模型所见内容）；向子智能体委派；恢复；人机协同暂停；Quicksand 基于 QEMU 的沙箱执行 |
| 复现局限 | 27 个基础依赖 —— 完整 Web 应用栈（playwright、fastapi、sqlmodel、quick-sandbox 等），非可嵌入库；Windows x64 **仅支持 WSL2**；文档化部署假设 vLLM 级 GPU（48–96 GB）；llama.cpp 承载路径未文档化（端点为 OpenAI 兼容 `/v1/chat/completions`，协议已核验） |

复用类别：`RESEARCH_ONLY` —— Layer B/C 的设计模式参考。注：0.2 并非构建于
AutoGen/Agent Framework；Magentic-One 以 "Magentic orchestration" 之名延续于
Microsoft Agent Framework（`agent-framework` PyPI 1.26.0，MIT）。

### 1.8 R08 — 约束解码基础设施 — VERIFIED

三个组件；均非论文；许可证均已核验。

| 组件 | 版本/状态 | 动态（状态依赖）能力 | 复用类别（原样） |
|---|---|---|---|
| llama.cpp GBNF + json_schema | MIT；稳定版 v1.1.0（2026-11-26），上游 nightly b12811；**任务固定引擎 b12359（v1.0.0）** | 逐请求文法；中途切换仅经内部文法触发器（工具调用解析器；v1.1.0 增加惰性文法与越界触发器拒绝）；**无公开的逐 token 文法变更 API** | REUSE_DIRECTLY (pinned b12359; N02 probe evidence) |
| LLGuidance | MIT（微软支持）；v1.9.1，活跃（2026-11-18）；约 50 µs/token 掩码；完整 JSON-schema 掩码约 1.5 ms；覆盖率 oneOf 68% / allOf 98% / pattern 99% / format 74%；不支持外部 $ref；宽松模式 | 逐请求文法创建成本低；在精确 token 边界施加 token-trie 约束 | UNVERIFIED_FOR_WINDOWS（未确认 Windows wheels）；经 llama.cpp 构建开关候选（集成可选，默认关闭） |
| XGrammar | Apache-2.0；v0.2.9（2026-11-09），活跃；vLLM/SGLang/TensorRT-LLM/MLC-LLM 的默认结构化后端；原生 Windows wheels | **XGrammar-2**（2026 年 5 月，ACM DOI 10.1145/3786335.3813124）：`triggered_tags` 结构 DSL（按标记实现中途状态依赖切换）、跨文法缓存（50 工具时约 50% 复用）、重复压缩 100 倍、编译加速最高 80 倍、批处理 + 投机解码、fork/rollback 状态 | REUSE_WITH_ADAPTER_CANDIDATE（若 llama.cpp 原生路径不足，作为 M04 参考设计） |

引擎行为发现（已执行证据，N02 探针 v2，彼处记录为 PASS）：
**b12359 拒绝反斜杠转义引号的 GBNF 字面量**；字符类形式 `["]` 可用。另核验
llama.cpp 请求面：两个端点均支持 `grammar` + `json_schema` 字段、
`response_format` 包装 `{"type":"json_schema","json_schema":{name,strict,schema}}`、
`tools` + `tool_choice` auto/any/named（named 自 v1.1.0，需 `--jinja`）、MCP
stdio 服务器。XGrammar v0.x 编译期 token 掩码预计算可能耗时数秒至数分钟；
v0.2.9 增加可选 JIT 编译。

### 1.9 R09 — 通用智能体 SDK — VERIFIED

| SDK | 许可证 | 版本 | 基础依赖 | 本地/OpenAI 兼容 | 备注 | 复用类别（原样） |
|---|---|---|---|---|---|---|
| PocketFlow | MIT | 0.0.3 | **0** | 自带客户端 | 99 行；Node/Flow + max_retries/wait/exec_fallback；无类型化工具 | REUSE_DIRECTLY (skeleton candidate) |
| Pydantic AI (`pydantic-ai-slim`) | MIT | 2.76.0（2026-11-27） | 9 | 一等 `OpenAICompatibleProvider`、vLLM、Ollama；弱后端模型画像 | 类型化工具、经校验的结构化输出、9 层文档化重试 | REUSE_WITH_ADAPTER (typed layer candidate) |
| smolagents | Apache-2.0 | 1.26.0 | 6 | **专用 `LlamaCppModel`** + Transformers/Ollama/LiteLLM | CodeAgent（以代码为动作）—— 与 SLM 相关；本地执行器"非安全边界" | REUSE_WITH_ADAPTER (model client + loop patterns) |
| LangGraph | MIT | 1.2.24 | 6（+langchain-core 树） | 完全无模型客户端（模型无关） | 持久执行、中断、检查点 | TECHNICALLY_UNSUITABLE_FOR_MINIMAL (dependency tree) |
| OpenAI Agents SDK | MIT | 0.26.0 | 14 | `set_default_openai_client(base_url=...)`；无 OpenAI 密钥时必须关闭追踪 | 护栏、会话、交接；原生 Windows 有文档 | RESEARCH_ONLY (B-arm comparator) |
| Google ADK | Apache-2.0 | 2.15.1 | 24（最重；fastapi/uvicorn/google-auth/graphviz） | Ollama/vLLM/LiteLLM 连接器 | 工作流智能体、回调、评估套件 | TECHNICALLY_UNSUITABLE_FOR_MINIMAL |
| DSPy | MIT | 3.5.0 | 14 | 快速入门使用 `ollama_chat/llama3.2:1b`（明确 1B） | Signatures + 优化器（GEPA）；离线调优内置 LLM 评审（仅构建期） | RESEARCH_ONLY (N10 optimizer comparator) |

## 2. 必需的区分表

### 2.1 1–3B 总量参数 vs 小激活量的更大 MoE

| 对象 | 参数区间 | 模型 | 对 1–3B 总量运行时的适用性 |
|---|---|---|---|
| R01 effGen | **含 1–3B 总量** | Qwen2.5-1.5B/3B、Gemma 3 1B | 直接证据（1–3B 语料中最强） |
| R02 PTC-Decoder | **≤2B 总量（7 个 SLM）** | 含 Qwen3.5-2B、Qwen3-1.7B、gemma-3-1b-it | 直接证据，含任务的 Qwen3.5-2B 期望（CONFIRMED） |
| R03 TinyAgent | **1.1B 总量** | TinyAgent-1.1B | 直接，但头条结果依赖权重微调（见 2.2） |
| R04 slm-harness-adaptation | **3–8B 激活 / 8–30B 总量 MoE**（另有一个 8B 稠密） | gemma-4-26b-a4b、qwen3-coder-30b-a3b、ministral-3-8b | **非 1–3B 总量证据**：小激活 MoE 的增益不可迁移到小总量稠密模型 |
| R05 Growing Harness | ≥4B | Qwen3.5-4B 最小；gpt-oss-20b/120b | 无 1–3B 证据 |
| R06 Meta-Harness | ≥20B（未说明） | GPT-OSS-120B/20B、Claude Opus 4.6/Haiku 4.5 | 无 1–3B 证据 |
| R07 MagenticLite | 9–14B | MagenticBrain 约 14B、Fara1.5-9B | 无 1–3B 证据（"small" = 9–14B） |

### 2.2 仅运行时优化 vs 权重微调

| 对象 | 增益来源 | 分解 |
|---|---|---|
| R01 effGen | **仅运行时** | 冻结开放权重；无微调；无权重工件 |
| R02 PTC-Decoder | **仅运行时** | 免训练约束解码；零权重变更 |
| R03 TinyAgent | **混合 —— 权重主导** | LoRA 微调 +66/+42 点；ToolRAG +1.5–2 点（另带来约 2 倍提示压缩）；QAT 约 +0.3 |
| R04 slm-harness-adaptation | **仅运行时** | 对冻结云端权重的 GEPA 式 harness 搜索 |
| R05 Growing Harness | **仅运行时** | 优化器为专有前沿模型；底座模型冻结 |
| R06 Meta-Harness | **仅运行时** | 冻结 ≥20B 模型；harness 搜索离线进行 |
| R07 MagenticLite | **权重已改变** | MagenticBrain = Qwen3-14B 的 SFT+RL；Fara1.5-9B 来自 Qwen3.5-9B |

任务推论：仅 R01 与 R02 在 1–3B 总量上提供仅运行时证据；R03 的运行时机制在
微调权重之上仅值约 1.5–2 点，不可归功于运行时本身（任务令 §8）。

### 2.3 任务专属特化

| 对象 | 特化维度 | 载体 | 向本任务的迁移 |
|---|---|---|---|
| R01 effGen | 通用智能体基准；规模感知提示分层 | 运行时提示 | 无任务专属证据；仅作对照组（E01） |
| R02 PTC-Decoder | 领域基准：200 任务专家标注遥感负载 | 仅评估 —— 机制（DFA 工具约束）与领域无关 | 机制可经净室重实现移植；评估须在任务业务世界重建 |
| R03 TinyAgent | 固定 16 工具 macOS AppleScript 套件；80K 工具专属合成样本 | **权重（LoRA）+ 工具层** | 不可迁移；仅 ToolRAG 机制（M02），按任务令 §8 使用冻结权重 |
| R04 slm-harness-adaptation | 按任务族的 harness 搜索（21 个任务–SLM 对） | 运行时 harness 配置 | N10 方法学；O0–O5 对照组 |
| R05 Growing Harness | 在无策略脚手架上将任务专属重复控制决策编译为确定性代码 | 运行时代码（可复用专家） | 原则被采纳为机制臂 E06；任务专属业务逻辑与面向模型的运行时逻辑分离（任务令 §8） |
| R06 Meta-Harness | 按任务族特化的 harness 程序 | 运行时代码 | 仅 N10 方法学 |

横切结论：**没有任何对象为本任务自身的业务领域提供证据**，且目录记录
"independently_verified_business_correctness: none found for any subject"。

### 2.4 LLM 评审结果 vs 确定性判定结果

| 对象 | 评分方法 | LLM 评审 | 统计报告 | 是否确定性 |
|---|---|---|---|---|
| R01 effGen | 确定性匹配，13 个基准 | 否 | McNemar p<0.05；附录置信区间（未读） | 是 |
| R02 PTC-Decoder | DeepSeek-V4-flash 评审，0–5 分制；20 样本人工双检 | **是** | +1.21，p<0.01，95% CI [+1.13, +1.29] | 否（依赖评审） |
| R03 TinyAgent | 程序化图同构，1K 测试集 | 否 | 未记录 | 是 |
| R04 slm-harness-adaptation | 客观任务指标（Gemini 仅在优化器循环内，不参与评分） | 否 | 3 次运行均值；无置信区间；"highly stochastic" | 是 |
| R05 Growing Harness | 基准套件含 BrowseComp-Plus | 仅继承自基准 | 3 次均值、bootstrap 置信区间 | 部分 |
| R06 Meta-Harness | 仅任务奖励 | 否 | 无种子扫描/标准差/置信区间；代码 "minimally tested" | 是（报告薄弱） |
| R07 MagenticLite | 扫描中未记录 | — | — | 未记录 |

## 3. 组件级对比：PocketFlow vs pydantic-ai-slim vs smolagents vs effGen

任务令 §2 要求的十轴对比。"未记录"指核验扫描中没有关于该轴的主源陈述；
不等于"不存在"。

| 轴 | PocketFlow 0.0.3 (MIT) | pydantic-ai-slim 2.76.0 (MIT) | smolagents 1.26.0 (Apache-2.0) | effGen v1.3.0 (Apache-2.0) |
|---|---|---|---|---|
| 原生功能 | 仅图原语：Node/Flow、条件/批处理/异步、节点级 `max_retries`/`wait`/`exec_fallback`；无模型客户端、无类型化工具 | 类型化工具、经校验的结构化输出、9 层文档化重试、带弱后端画像的 `OpenAICompatibleProvider`、vLLM/Ollama | 智能体循环 + CodeAgent（以代码为动作）、专用 `LlamaCppModel`、Transformers/Ollama/LiteLLM、工具调用 | 完整智能体平台：5 阶段规模感知提示优化（35 模板）、YAML 工具压缩（−32% token）、ModelRouter、WorkflowDAG、三层记忆（FAISS/Chroma）、MCP/A2A/ACP、循环检测、优雅降级、本地后端（llama-cpp-python GGUF、vLLM、MLX、OpenAI 兼容） |
| 所需自定义代码 | 四者中最高：模型客户端、工具、类型化层、遥测全部由任务自建 | 中：模型客户端与校验已有；编排/智能体策略自建 | 中低：智能体循环已有；须自备沙箱（执行器非安全边界） | 名义上最低，但绑定其自身技术栈；任务将其用作 E01 对照组而非组件 |
| 依赖足迹 | **0** | 9 | 6 | **约 52**（torch、transformers、fastapi、docker、3 个 Google SDK） |
| 初始化成本 | 极低（99 行，纯 Python） | 中（导入 + 提供方设置；无服务端） | 中（执行器 + 本地模型设置） | 高（含向量记忆层的 ML 栈；依赖含 docker） |
| 可观测性 | 无内建；日志留给嵌入方 | 重试/校验结果经类型化结果暴露；更深层遥测未记录 | 除执行器告诫外未记录 | 内部重试/退避、降级与循环检测事件；遥测面未记录 |
| 安全性 | 骨架无代码执行面（亦无内建防护） | 模式校验降低畸形输出面；未记录沙箱主张 | **CodeAgent 执行模型生成代码；执行器明确"非安全边界"** —— 必须置于任务沙箱之后 | 依赖含 docker；MCP/A2A/ACP 外部面；未记录沙箱保证 |
| 维护工作量 | 99 行 —— 分叉成本极低，但全部编排维护转移到任务方 | 上游每日活跃；需跟踪 9 个依赖 | 上游（HF）活跃；需跟踪 6 个依赖 | 1,993 文件仓库、20+ 次发布、更新日志坦承回退；若嵌入需跟踪约 52 个依赖 —— 最重（任务不嵌入任何部分） |
| 商业许可 | MIT —— 干净 | MIT —— 干净 | Apache-2.0 —— 干净 | Apache-2.0 —— 干净但对 SDK 嵌入而言足迹过重 |
| 本地 Windows 兼容 | 是（纯 Python；目录核验） | 是（Windows wheels 已核验） | 纯 Python、本地优先；扫描未明确断言 Windows | 可信但未测试（OS-Independent、纯 Python；未文档化） |
| 模型专项适配工作量 | 未提供 —— 所有 SLM 适配均为任务工作 | 记录中最低：面向弱后端的模型画像正对小模型失败面 | 中低：`LlamaCppModel` 一等公民；CodeAgent 适合 SLM 以代码为动作；画像未记录 | 为 1.5B–32B 量身打造（规模感知提示）但仅限其自身技术栈 |

**必需声明（任务令 §2）。** 依赖数量**不是**完整的框架质量排名。PocketFlow
近零足迹有用，但需要大量自定义编排的框架可能比功能更全的框架承担更高的总
工程成本：采用 PocketFlow 后，模型客户端、类型化工具层、校验重试行为与可
观测性全部转为任务自有代码，必须同样经历规格化、测试与加固（N06A-R 的缺陷
类别对它与其他代码一视同仁）。依赖列只是上述十轴之一，不是排名。

## 4. 诚实结论

1. **最强 1–3B 总量证据：effGen（仅运行时）。** 1.5B 在 13 个基准上平均
   47.44 对原始 34.28，确定性评分且 McNemar p<0.05 —— 但由约 52 依赖的技术
   栈承载（与最小运行时论点矛盾）、发表场所 PARTIALLY_VERIFIED、附录置信区
   间未读。仅作为对照组 E01 复现。
2. **第二份 1–3B 证据：PTC-Decoder，含 Qwen3.5-2B**（任务期望 CONFIRMED；
   最佳 Overall 3.12；p<0.01 带置信区间）—— 但主指标为 **LLM 评审**
   （DeepSeek-V4-flash），实现**仅限 transformers**（不兼容 llama.cpp、不存
   在适配器），token 开销 2.07 倍，且存在自认反例（Qwen3-1.7B：约束 F1
   0.292 < 无约束 0.355）。只能作为净室机制（M04）使用，不可作代码复用。
3. **TinyAgent 的 1.1B 头条（80.35%）依赖微调权重**（LoRA +66/+42 点）；
   其运行时机制仅贡献约 1.5–2 点；全部 16 个工具为 macOS AppleScript。对冻
   结权重、Windows 本地的运行时不构成可迁移证据。
4. **Growing Harness 仅有论文**（无代码；专有优化器；评审继承自基准；约
   3 次引用、无独立验证）。其原则 —— 将重复控制决策编译为确定性代码 —— 被
   采纳为机制臂 E06，可复用代码为零。
5. **R01–R09 中不存在任何经独立验证的业务正确性**（目录横切发现）。所有对
   象均在公开智能体基准或自建任务上评估；无一测量本任务的业务世界。正式业
   务主张仍受任务自有的合格 Oracle（N05A）门控 —— N01 阶段状态 NOT_RUN。
6. **总量 vs 激活量重要：** R04 的 31.4% → 80.2% 是 3–8B 激活 / 8–30B 总量
   MoE 证据，不得引用于 1–3B 总量模型；R06/R07 在 ≥9B 运行。仅 R01、R02、
   R03 触及 1–3B 总量区间。
7. **许可证态势：** 可商业嵌入的干净集合 —— llama.cpp（MIT）、PocketFlow
   （MIT）、pydantic-ai-slim（MIT）、smolagents（Apache-2.0）、XGrammar
   （Apache-2.0）、effGen（Apache-2.0，足迹重）、PTC-Decoder 代码（MIT）。
   排除或附条件：Meta-Harness TB2 工件（UNLICENSED）、PTC-Decoder 论文文本
   （CC BY-NC-SA，非商业）、LFM3-1.7B 权重（LFM Open License v1.0，收入条件
   型 —— **研究使用不受影响，IJN-B-003**）。
8. **约束性复用决策推迟至 N03 实测能力**（任务令：在测量支撑某策略的能力
   之前，不得最终确定模型专属执行策略）。已记录的组件级处置见
   `reports/IJNANO_OPEN_SOURCE_REUSE_DECISION.md`。

## 5. 判定与证据索引

`N01_RESEARCH_LANDSCAPE_VERIFIED` —— 文档范围 PASS：上述每个主张均携带其主源
（仓库 + 版本 / arXiv 编号 + 版本 / 许可证），目录核验标注原样保留，任务令
§2 要求的四张区分表全部在位。执行状态：对象复现、Windows 本地验证与业务评
估在 N01 按定义为 NOT_RUN；唯一引用的已执行证据是 llama.cpp b12359 的 N02
引擎探针。

证据索引：

- `evidence/IJNANO/N01/research_catalog.json` —— 已核验目录（对象 R01–R09）
- `evidence/IJNANO/N01/agent_reports/R01_R04_verification.md` —— R01、R04 扫描
- `evidence/IJNANO/N01/agent_reports/R02_R08_verification.md` —— R02、R08 扫描
- `evidence/IJNANO/N01/agent_reports/R03_R05_R06_verification.md` —— R03、R05、R06 扫描
- `evidence/IJNANO/N01/agent_reports/R07_R09_verification.md` —— R07、R09 扫描
- `evidence/IJNANO/N01/license_matrix.json` —— 机器可读许可证配套文件
- `reports/IJNANO_OPEN_SOURCE_REUSE_DECISION.md` —— 组件级决策记录
