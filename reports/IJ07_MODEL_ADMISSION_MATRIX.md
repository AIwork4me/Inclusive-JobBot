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

## 独立修正配置

第二轮在同一 Radeon 上使用加入拒绝补丁的 P4b 版本，并请求关闭思考。B、D、E、F、G 与参考 H 通过十项探针。A 的普通对话和严格 Schema 探针通过，原生工具输入的首轮与流式配对失败。初轮结果保持原样。E 的总参数量超出 3.5B，G 单列为有效计算规模组。共同后端的独立全量成绩待验证。 [第二轮数据](../evidence/IJ07/model_identity/admission_strict/)

C 的官方 ONNX INT4 模型通过 CPU 普通对话，以及 AMD 厂商 ID 约束、禁用 CPU 回退的 WebGPU 普通对话。CPU 与 WebGPU 的依赖探针均在取得账号前提出余额调用，结果为 `FAIL`。增量和整段解码在该样本一致。独立流式和完整工具回传仍未验证。 [独立 ONNX 对话](../evidence/IJ07/model_identity/aion_reference/) · [依赖工具探针](../evidence/IJ07/model_identity/aion_tools/)

显式规定工具顺序与逐步回传的对照中，CPU 与 AMD WebGPU 均正确完成账户查询。
三次生成的输入和输出 token 逐个一致。该对照只验证明确流程的一个样本。
 [配对原始摘要](../evidence/IJ07/model_identity/aion_tools/serial-comparison.json)
