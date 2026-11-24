# IJ-0.6 Antigravity SDK verification

The real Windows Antigravity 0.1.24 harness ran MiniCPM5-2B Q8_0 through the pinned b12359 llama-server and a local wire boundary. The boundary assembled and validated whole responses before forwarding them to the SDK. Synthetic business tools received preserved arguments via one-use proposal matching and the scoped Gateway. Results and SDK transcripts are archived per backend. [Vulkan run](../evidence/IJ06/antigravity/vulkan.json) · [ROCm run](../evidence/IJ06/antigravity/rocm.json)

| Gate | Vulkan | ROCm/HIP | Observation |
|---|---|---|---|
| AG-01 | PASS | FAIL | ROCm appended a period to the requested exact string. |
| AG-02 | PASS | PASS | llama-server SSE and multiple SDK deltas observed. |
| AG-03 | PASS | PASS | Scoped order lookup executed once and was visible in the transcript. |
| AG-04 | PASS | PASS | Supplier lookup followed the order lookup and used its returned supplier identity. |
| AG-05 | PASS | PASS | Tool status was returned to the model and reproduced exactly. |
| AG-06 | PASS | FAIL | SDK returned an object on both arms. ROCm nested a serialized object inside the expected status string. |
| AG-07 | PASS | PASS | SDK cancellation observed after request start. The adapter closed the upstream connection and invalidated pending proposals. |
| AG-08 | PASS | PASS | Host deadline elapsed while a model request was active and the SDK turn was cancelled. |
| AG-09 | PASS | PASS | Synthetic HTTP 429 then real model response. Sustained 429 stopped after two calls. |
| AG-10 | PASS | PASS | Fresh SDK sessions saw distinct order statuses with separate workspaces and stores. |
| AG-11 | BLOCKED | BLOCKED | Process egress isolation or trusted complete traffic observation is unavailable. |
| AG-12 | PASS | PASS | Gateway denied both an out-of-scope resource and a declared but ungranted tool. |

Vulkan passed 11 of 12 gates with one blocked. ROCm passed 9 of 12 with two failures and one blocked. AG-07 and AG-08 establish SDK and adapter cancellation behavior. GPU preemption was unmeasured. The adapter buffers SSE before releasing a complete checked batch to the SDK, so these runs provide no provider-to-user TTFT measurement.

An earlier diagnostic run found `tool_choice: none` when the SDK had zero model-output retries, even with a registered callback. Increasing the output-token budget alone retained the symptom. An otherwise identical scoped run with one configured output retry sent `tool_choice: auto` and generated a native callback. The final run bounds API retries separately from output retries. This is observed interaction in SDK 0.1.24, with harness internals unverified. [SDK retry configuration](https://github.com/google-antigravity/antigravity-sdk-python/blob/main/skills/google-antigravity-sdk/examples/getting_started/customizing_retries.md)

The clean P4b reruns began at `fa50525ebf99fff98149746c05fadc472c8462ec`. Vulkan passed 10 gates, failed AG-06, and remained blocked on AG-11. Its structured status contained a serialized `result` object. ROCm passed 11 gates and remained blocked on AG-11. A single run per configuration cannot isolate which differences came from inference variability. [P4b Vulkan](../evidence/IJ06/antigravity/p4b-vulkan.json) · [P4b ROCm](../evidence/IJ06/antigravity/p4b-rocm.json)

The original read-only SDK smoke remains PASS. The updated integration supplies real model calls and persists synthetic document-review drafts in the development rehearsal. Human submission was exercised by the separate simulator regression. Full SDK qualification remains open.

Run from the repository with the requested Q8_0 backend ready.

    powershell -NoProfile -ExecutionPolicy RemoteSigned -File scripts/windows/run_ij06_sdk_tests.ps1 -Backend vulkan -Output .runtime/ij06-sdk/vulkan-repeat

Exit 1 indicates a measured failure. Exit 2 indicates the selected full suite has a blocked offline gate and no measured failures. Use a distinct output directory for a distinct run. The evidence files redact workstation paths. Raw tool-call argument content remains available for audit.
