# IJ-0.7 模型运行时准入

有运行数据的候选固定 Q8_0 文件、b12359 二进制、温度 0、seed 7107 和 Vulkan。先启动 CPU 参考，再在 Radeon 8060S 检查实际 offload、同 PID GPU engine 和显存。三轮只读账户任务需要模型自行使用上一步返回的账号。此探针用于工程准入。

| ID | 权重哈希 | CPU 普通对话 | Radeon Vulkan | 普通对话 | 原生及依赖调用 / 回传 | 流式配对 | Schema 与异常输入 | 准入 |
|---|---|---|---|---|---|---|---|---|
| A MiniCPM5 | PASS | PASS | PASS 43/43 | PASS | PASS | PASS | FAIL | FAIL |
| B LFM3 | PASS | PASS | PASS 25/25 | PASS | PASS | PASS | FAIL | FAIL |
| C Aion | BLOCKED | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | BLOCKED |
| D Qwen3.5 | PASS | FAIL | PASS 25/25 | FAIL | PASS | PASS | FAIL | FAIL |
| E Granite | PASS | PASS | PASS 41/41 | PASS | PASS | PASS | FAIL | FAIL |
| F Ministral | PASS | PASS | PASS 27/27 | PASS | PASS | PASS | FAIL | FAIL |
| G Gemma | PASS | PASS | PASS 36/36 | PASS | PASS | PASS | FAIL | FAIL |
| H Qwen3-8B 参考 | PASS | PASS | PASS 37/37 | PASS | PASS | PASS | FAIL | FAIL |

对七个运行项，b12359 都把未知命名工具的对象型 `tool_choice` 当作 `auto`，返回 HTTP 200 和工具调用。A 和 D 的 JSON Schema 请求还耗尽 1,024 生成 token。D 的 CPU/Vulkan 普通对话在相同预算下未输出要求的纯文本。正式留出评测尚未运行。G1 初轮准入为 `FAIL`，G10 为 `NOT_RUN`。 [逐候选响应及 GPU 证据](../evidence/IJ07/model_identity/admission/)

C 的厂商 ONNX 格式存在，Windows Radeon 与 WebGPU 的实际编译、算子和执行证据尚未取得。正式竞争排名需至少四个通过准入且共同后端完整运行的模型家族。
