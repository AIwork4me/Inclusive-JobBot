# Handoff

Read this first when resuming. Last updated: 2026-11-24.

## Where the work is

IJ-0 (ECO-01) is in progress through IJ-0.4. IJ-0.5 and everything after it
have not started. IJ-1.0 missions M3-M10 have not started.

Done and evidenced:

- M0 environment baseline collected (`evidence/M0/`,
  `reports/M0_ENVIRONMENT_REPORT.md`). All 54 locked packages carry a SHA256
  cross-checked with pypi.org, and a clean-environment `--require-hashes`
  install rehearsal passed.
- IJ-0.1 upstream audit. llama.cpp PR #24889 (native MiniCPM5 parser) is
  merged; stable release `v1.0.0` ships binaries through build `b12359`.
- IJ-0.2 MiniCPM5-2B from ModelScope at pinned revisions; 17 of 17 files match
  the published SHA256.
- IJ-0.3 official `b12359` builds installed under `runtime/llama-cpp/`:
  CPU, Vulkan and ROCm each enumerate as expected.
- IJ-0.4 launch, stop and check scripts verified on Vulkan with Q8_0 and an
  8K context: 43/43 layers on the GPU, 9 of 9 API checks, first real
  inference correct.

No llama-server is running right now.

## Next steps, in order

1. IJ-0.5: Arms A-G in `reports/IJ0_GPU_BACKEND_QUALIFICATION.md`. Arms:
   A CPU/F16, B Vulkan/F16, C Vulkan/Q8_0, D ROCm/Q8_0, E CPU/Q8_0,
   F qualified-GPU/Q4_K_M, G Ollama/Q8_0 (optional). Collect llama.cpp logs,
   Windows GPU counters and a same-weight CPU-versus-GPU Q8 comparison.
2. Native tool calling: streaming and non-streaming through
   `/v1/chat/completions` with tools, parser fixtures, the 500-case frozen
   benchmark in `benchmarks/tool_calling/`.
3. Antigravity SDK against llama-server (12 items in ECO-01 section 6).
   Disable the default file, command, subagent and MCP capabilities first.
4. Model Gateway refactor and contract tests.
5. Performance qualification and engine selection; `configs/production.yaml`.
6. Gates G0-G14 and the IJ-0 reports, then resume IJ-1.0.
7. Create the GitHub repository and push (not done yet; see below).

## Repository state

No git repository exists yet in this working directory and
`AIwork4me/Inclusive-JobBot` does not exist on GitHub. Before the first commit:
set the repository-local identity, run `python scripts/tools/scan_sensitive.py`,
and commit on branch `mission/ij-1.0-windows-fullstack-qualification`.

## Things that will trip you up

- The machine is reached over a remote display session. Never disable its
  network or interfere with the remote session.
- Smart App Control is off because the owner turned it off on 2026-11-24. The
  project never changes that setting.
- `files.pythonhosted.org` and `raw.githubusercontent.com` are unreliable on
  this network. Use `gh api`, the Tsinghua PyPI mirror and
  `scripts/tools/parallel_fetch.py`.
- `grep` is `ugrep` here. Use `scripts/tools/scan_sensitive.py` for leak checks.
- From Git Bash, redirect a script's output to a file instead of piping it when
  the script starts the server; otherwise the pipeline never ends.
- Scripts run under Windows PowerShell 5.1: keep `.ps1` files ASCII.
- The ROCm arm needs `install_rocm_runtime.ps1`; its wheels are 2.8 GB and its
  `ggml-hip.dll` is 1.1 GB. Keep both out of git.

## Key identities

| Item | Value |
|---|---|
| MiniCPM5-2B-GGUF revision | `8cc1178b0a5cee98872ca3f2f88d49b3d3fa6f59` |
| MiniCPM5-2B (BF16) revision | `4e7a94716d4526da493d68962f475390e852954b` |
| llama.cpp stable release | `v1.0.0` -> build `b12359`, commit `b1b770d90d94cad9e9ea5b993bdbc383a522fb28` |
| MiniCPM5 parser merge | PR #24889, commit `c818263f2a5ddab028dea5f169ea2b2266421125` |
| GGUF-embedded chat template | 9060 chars, SHA256 `cc945752db555d60949b16989df4ccfeb52a313d6b4b5c5229dd786e2e9fcf1c` |
| Antigravity SDK | `google-antigravity` 0.1.24 (Apache-2.0) |
| Ollama (baseline only) | v0.40.17 in `.tools/ollama-core` |

## Everyday commands

```powershell
pwsh -File scripts/windows/start_llama_server.ps1 -Backend vulkan -Model q8
pwsh -File scripts/windows/check_llama_server.ps1 -Probe
python scripts/tools/llama_server_api_check.py
pwsh -File scripts/windows/stop_llama_server.ps1
```

Backends: `cpu`, `vulkan`, `rocm`. Models: `f16`, `q8`, `q4`. Defaults are in
`configs/llama_cpp/launch.json`; the pinned engine is in
`configs/llama_cpp/engine.json`.
