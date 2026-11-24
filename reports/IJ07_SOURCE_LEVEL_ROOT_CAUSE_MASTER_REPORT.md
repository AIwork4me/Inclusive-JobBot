# IJ-0.7 源码根因阶段记录

## RC-11 误接受显式对象型 tool_choice

共同 b12359 构建对未知工具的对象型选择返回 HTTP 200，并继续自动选择工具。根因是 `oaicompat_chat_params_parse` 用 `json_value(..., std::string("auto"))` 读取该字段。该模板遇到类型错误会记录警告并返回默认值。原生选择解析函数只实现 `auto`、`none`、`required` 三个字符串模式。 [精确服务器源码](https://github.com/ggml-org/llama.cpp/blob/b1b770d90d94cad9e9ea5b993bdbc383a522fb28/tools/server/server-common.cpp#L1425) · [读取函数](https://github.com/ggml-org/llama.cpp/blob/b1b770d90d94cad9e9ea5b993bdbc383a522fb28/tools/server/server-common.h#L45) · [准入原始记录](../evidence/IJ07/model_identity/admission/)

本地最小变更在选择解析前拒绝显式的非空非字符串类型，HTTP 包装器将 `std::invalid_argument` 映射为 HTTP 400。保留省略、null 和三种受支持字符串的现有行为。当前补丁对对象型强制命名选择显式报错。该功能可独立评审。 [补丁](../patches/ij07/llama-b12359-explicit-tool-choice.patch) · [对照工具](../benchmarks/root_cause/probe_tool_choice.py)

## RC-04 / RC-13 空 tags 生成与目标不一致

模型在四臂的 `tc-seq-0001` 直接生成空数组。原始工具 Schema 允许空数组，目标明确要求两条标签。空数组在所见原生解析、JSON 和历史模拟处理过程保持为空。当前证据确定错误出现于解析前，原始历史调用及空数组成因分别保留 `ROOT_CAUSE_UNVERIFIED`。 [逐案分析](IJ07_MULTITOOL_FAILURE_ROOT_CAUSE.md)

## AG-06 结构化结果

工具结果由 SDK 包为 `{"result": "ORDER-READY-X621"}` 后进入模型消息。两个失败臂的 SSE 中，模型的 `finish.status` 已是序列化后的整个对象，SDK 返回相同错误字符串。两个成功臂只选择真实状态值。此比较定位了错误首次可见的协议边界。未采集解析前生成，SDK 包装和提示的贡献仍需对照。AG-11 仍需可信进程级出站证据。 [SSE 独立复核](../evidence/IJ07/root_causes/ag06_archived_wire.json) · [验收规范](../docs/ANTIGRAVITY_SDK_ACCEPTANCE_SPEC.md)

## 上游比较

截至核查时，llama.cpp 默认分支为 `2a487782f2f218bc6c01e1f366a7e73f002faf08`。MiniCPM5 parser 从固定版本后已随 #29307 切换到 token-aware 解析、调整 CDATA 和字符串闭合规则。#32746 已关闭且未合并。上游源码的变化并不能给出相同负例上的实际结果，单独上游臂仍待固定和执行。 [核查源码](https://github.com/ggml-org/llama.cpp/blob/2a487782f2f218bc6c01e1f366a7e73f002faf08/common/parsers/minicpm5.cpp) · [#29307](https://github.com/ggml-org/llama.cpp/pull/29307) · [#32746](https://github.com/ggml-org/llama.cpp/pull/32746)
