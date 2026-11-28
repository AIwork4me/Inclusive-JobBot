# IJSDK_03_SDK_SURVEY_AND_ADMISSION — P3 Agentic SDK Survey, Installation and Admission

Mission: **IJ-SDK-1.0** · Generated: 2026-11-27 · Branch: `mission/ij-sdk-1.0-cross-sdk-agentic-benchmark`
Evidence: `evidence/IJSDK/P3/sdk_research_findings.json` (landscape + security findings), `evidence/IJSDK/P3/installed_artifacts.json` (exact per-venv freeze output), `evidence/IJSDK/P3/conformance/` (per-arm probe records incl. wire captures and traces)

---

## 1. Verdict

| Gate item | Status |
|---|---|
| Mandatory arms surveyed from official sources (versions verified 2026-11-27) | PASS |
| Commercial/offline license audit recorded per arm | PASS (`sdk_research_findings.json`) |
| Isolated per-SDK venvs installed and freeze-recorded | PASS (10 venvs, pip freeze per venv) |
| Local-only connection to the pinned llama-server verified per arm | PASS — 10/10 arms connect over loopback |
| Native tool roundtrip (C1/C2/C3) per arm | PASS — 10/10 arms complete the C3 roundtrip through their own SDK interfaces |
| Gate `P3_SDK_ADMISSION_AUDITED` | **PASS** (security condition on B8 recorded below) |

## 2. Security audit highlights

- **SEC-01 (critical)**: Microsoft Agent Framework PyPI 1.26.1/1.26.2 were hijacked in Nov 2026 (a `.pth` startup hook exfiltrated credentials; ~192k weekly downloads affected; upstream repo offline since 2026-11-18). Arm B8 installs **only 1.26.0** (last clean release) in an isolated venv with the freeze recorded; 1.26.1/1.26.2 must never be installed. If the owner requires a trustworthy upstream, B8 drops to comparator status — recorded, not hidden.
- **SEC-02**: LiteLLM 1.82.7/.8 advisory — the ADK arm uses the native `OpenAILlm` connector, not LiteLLM.
- Every install is version-pinned and freeze-recorded (motivated by SEC-01); the ROCm wheel drift found in P1 reinforces digest-pinning as mission policy.
- Responses-API trap (OpenAI Agents, Pydantic AI, MS Agent Framework): adapters must force Chat Completions mode; encoded in the conformance probes and required in adapter conformance tests.

## 3. Conformance matrix (S1 MiniCPM5-2B Q8_0, Vulkan, loopback; probe: 1 tool, tool→result→final answer)

| Arm | SDK (version) | Tier | C1 connect | C2 chat | C3 tool roundtrip | Notes |
|---|---|---|---|---|---|---|
| B1 | google-antigravity 0.1.24 | sdk-native | PASS | PASS | PASS (via repo smoke path: `LocalOpenAIAgentConfig` + `Agent.chat`) | public docs omit the local path; repository evidence + this run confirm it |
| B2 | openai-agents 0.26.0 | sdk-native | PASS | PASS | PASS | `set_default_openai_api("chat_completions")` + tracing disabled |
| B3 | smolagents 1.26.0 ToolCallingAgent | sdk-native | PASS | PASS | PASS | `OpenAIServerModel(flatten_messages_as_text=True)` per upstream issue #908; `openai` extra required |
| B4 | smolagents 1.26.0 CodeAgent | sdk-native | PASS | PASS | PASS | in-process Python executor: P11 security gate must contain it before formal runs; one earlier run produced a mangled final ("-2026") from model-generated code — small-model code-action variance is recorded |
| B5 | pydantic-ai-slim 2.76.0 | sdk-native | PASS | PASS | PASS | typed `ToolOutput` (Pydantic model) roundtrip verified |
| B6 | langgraph 1.2.24 + langchain-openai 1.8.5 | sdk-native | PASS | PASS | PASS | `create_react_agent`; first-run empty final answer resolved by scanning all messages (checker bug, not SDK) |
| B7 | google-adk 2.15.1 | sdk-native | PASS | PASS | PASS | native `OpenAILlm` connector; earlier FAIL was our checker missing "17,420.50" (comma) — checker fixed |
| B8 | agent-framework 1.26.0 | sdk-native (conditional) | PASS | PASS | PASS | `Agent(client=OpenAIChatCompletionClient(model=…))`; kwargs differ from docs — API verified against the installed artifact |
| B9 | pocketflow 0.0.3 | custom-adapter | PASS | PASS | PASS | framework has NO model layer; the LLM utility/tool plumbing/loop are OUR disclosed reference implementation; self-loop (`-"ask">>node`) required |
| O1 | dspy 3.5.0 | sdk-native | PASS | PASS | n/a (optimization arm; chat only) | not an agent runtime; A13 uses dev data exclusively |

Failure accounting across sweeps: 3 sweeps were needed; every earlier failure was root-caused to (a) missing SDK extra (smolagents `openai`), (b) probe API mismatches against installed artifacts (b1 `Agent.chat`, b8 `Agent(client=…)`, `model=` vs `model_id=`), (c) our own checker bugs (comma in amount, single-message scan), or (d) one instance of genuine small-model CodeAgent output variance (recorded, not tuned away). No SDK was marked PASS without its own interface completing the roundtrip.

## 4. Commercial and community snapshot

Full per-arm license/offline/community data in `sdk_research_findings.json`. Summary: every admitted arm is MIT or Apache-2.0 with no mandatory cloud service (B1 Antigravity is Apache-2.0 but its hosted path is cloud; the local path used here is offline-capable). Community traction (stars ≈): LangGraph 45k, DSPy 39k, OpenAI Agents 31k, smolagents 31k, ADK 22k, Pydantic AI 21k, PocketFlow 11k, Antigravity 4k (alpha), Agent Framework unmeasurable (repo offline). Release activity is highest for Pydantic AI (near-daily) and ADK (bi-weekly); PocketFlow is frozen by design; smolagents' PyPI cadence slowed in H2 2026 while the repo remains active.

## 5. Carry-forward into P4/P8

1. Adapter conformance tests must pin the Responses-API mode to Chat Completions for B2/B5/B8.
2. B4 CodeAgent requires the P11 sandbox (no host shell, no network, no secrets, bounded CPU/memory/time) before formal trials; otherwise its physical runs stay BLOCKED.
3. B8 remains conditional on SEC-01; its trials run with no secrets in the environment and egress observation.
4. B9's disclosed-implementation rule carries into every published comparison (its scores reflect model + our reference loop, not PocketFlow's model support).
5. Streaming-mode and wire-capture conformance extends the P4 harness (A11); the probe's `wire` fields already record what each SDK exposes.
