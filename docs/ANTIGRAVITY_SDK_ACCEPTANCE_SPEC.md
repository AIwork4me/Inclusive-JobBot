# Antigravity SDK acceptance specification

IJ-0.6D restores the ECO-01 checklist supplied by the project owner on 2026-11-24. Evaluate each gate independently on native Windows with the pinned real SDK, local MiniCPM5-2B and llama-server. Report Vulkan and ROCm/HIP separately.

| Gate | Required behavior |
|---|---|
| AG-01 | Ordinary local conversation |
| AG-02 | Streaming |
| AG-03 | One real tool invocation |
| AG-04 | Sequential and dependent multi-tool invocation |
| AG-05 | Tool result returned to the model |
| AG-06 | Final structured result |
| AG-07 | Agent cancellation |
| AG-08 | Timeout |
| AG-09 | Bounded retry |
| AG-10 | Session isolation |
| AG-11 | Offline execution |
| AG-12 | Unauthorized tool rejection |

Retain native installation, local Skills, no Gemini API key, independent permission checks and explicit error handling. AG-11 requires process-level isolation or trusted network observation. Loopback service binding alone is insufficient. Capture the SDK version, transcript, actual model requests and responses, Gateway decisions, tool calls and results, final answer and final business state. Raw protocol validation must precede SDK argument coercion. Keep read-only smoke, stateful workflow and full qualification verdicts independent. Use PASS, FAIL, BLOCKED or NOT_RUN for each test.
