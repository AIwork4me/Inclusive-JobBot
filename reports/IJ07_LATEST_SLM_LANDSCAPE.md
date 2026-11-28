# IJ-0.7 小模型调研

核查日期为 2026-11-24。模型卡描述厂商公布的能力。项目实测采用同一台 Windows Radeon 8060S、Q8_0 文本配置和公用 b12359 运行时，详见 [准入矩阵](IJ07_MODEL_ADMISSION_MATRIX.md)。[候选清单](../configs/ij07/model_candidates.yaml) 固定官方权重仓库版本、模板哈希和各 GGUF 转换件的 ModelScope 版本及本地 SHA256。

| 候选 | 厂商资料与可比范围 | 授权与运行时路径 |
|---|---|---|
| MiniCPM5-2B | 2026-09-07 发布。Llama 稠密架构，2.52B 总参数、1.98B 非嵌入参数，131,072 上下文，支持中英及思考开关。原生 XML 工具语法。厂商另外发布 SFT、Midtrain 和 Base 权重，视为独立配置。 | Apache-2.0。b12359 专用 MiniCPM5 parser，项目另有 P4b。 [OpenBMB](https://github.com/OpenBMB/MiniCPM) |
| LFM3-1.7B | 1.73B、262,144 上下文、128K 词表。厂商报告 24 层，结合门控短卷积、滑窗和全局注意力，支持中英及多轮工具调用。 | LFM Open License v1.0。第 5 条对商业用途设年营收门槛。运行仅限本次技术研究。使用厂商 Q8_0 GGUF；已核对 b12359 的 LFM3 loader。 [模型卡](https://huggingface.co/LiquidAI/LFM3-1.7B) · [许可证](https://huggingface.co/LiquidAI/LFM3-1.7B-GGUF/blob/main/LICENSE) · [官方运行说明](https://docs.liquid.ai/deployment/on-device/llama-cpp) |
| Aion-1.0-Instruct-2.3B | 2.29B、32,768 上下文、200,029 词表。Microsoft 提供原生模板和自定义 `AionInstructForCausalLM`。 | MIT。固定官方 ONNX WebGPU 的外部权重、ONNX 图和模板清单。b12359 未找到对应 architecture/converter 注册。当前公开 PyTorch 版本含自定义代码；本项目未执行。 [模型卡](https://huggingface.co/microsoft/Aion-1.0-Instruct-2.3B) · [ONNX WebGPU](https://huggingface.co/microsoft/Aion-1.0-Instruct-2.3B-ONNX-WebGPU) |
| Qwen3.5-2B | 2.27B 发布权重参数，包含文本与视觉组件，262,144 文本上下文。官方模板支持工具及思考开关。公开 Qwen3.6/3.8 发布目录的所见对话模型规模更大，保留 Qwen3.5-2B。 | Apache-2.0。文本测试采用明确注明的 Unsloth 转换件，独立固定 SHA256。 [模型卡](https://huggingface.co/Qwen/Qwen3.5-2B) · [官方目录](https://huggingface.co/Qwen/models) |
| Granite-4.2-3B | 2026-08-25 发布，128K 上下文，企业工作流、内建思考、工具调用。官方权重目录统计 3.66B，超出严格 3.5B 总参数组，保留为指定扩展对照。 | Apache-2.0，IBM 官方 Q8_0 GGUF。 [模型卡](https://huggingface.co/ibm-granite/granite-4.2-3b) · [官方 GGUF](https://huggingface.co/ibm-granite/granite-4.2-3b-GGUF) |
| Ministral-3-3B-Instruct-2512 | 3B 级、262,144 上下文、多语种及视觉能力。官方 Instruct 模型支持函数调用及 JSON 输出。 | Apache-2.0。Mistral 官方 Q8_0 GGUF，测试只启用文本路径。 [官方 GGUF](https://huggingface.co/mistralai/Ministral-3-3B-Instruct-2512-GGUF) |
| Gemma-4-E2B-it | 2.3B 有效参数、5.1B 含嵌入参数，131,072 上下文。有效计算规模组，存储量按全权重衡量。 | Apache-2.0。GGML 发布的 GGUF，b12359 有专用 Gemma 4 parser。 [模型卡](https://huggingface.co/google/gemma-4-E2B-it) · [GGML GGUF](https://huggingface.co/ggml-org/gemma-4-E2B-it-GGUF) |
| Qwen3-8B | 8.19B 权重参数，沿用 IJ-0.6 官方 ModelScope Q8_0 参考。 | Apache-2.0，单列大模型对照。 [模型卡](https://huggingface.co/Qwen/Qwen3-8B) · [参考身份](../configs/qwen3_8b_reference.json) |
| No-LLM SOP | 业务系统参考，保留自动执行与人工确认规则。 | 复用既有 SOP 和 SQLite Gateway。 [ADR-003](../docs/decisions/ADR-003-PURPOSE-BUILT-EXECUTION.md) |

厂商公布的任务结果保留在各模型卡。由于工具类型、提示、评分语义和执行环境不同，本轮未把这些分数用于项目排名。转换器提交和权重训练后版本能确认到发布件的字段见身份目录。GGUF 转换器实现身份缺少明确上游元数据的条目暂保留未核实状态。
