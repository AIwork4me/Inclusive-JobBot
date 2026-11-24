# Handoff

Read this first when resuming. Last updated: 2026-11-24 (end of the first
working session, before the owner decides on optional tools).

Everything below was checked against the disk and the running system at the
time of writing. If something here disagrees with what you find, trust the
machine, fix this file, and say so in the commit.

## 1. Resume procedure

Work from the repository root, the folder that contains this file.

```powershell
git status --short                                      # must print nothing
git log --oneline | Select-Object -First 12
python scripts/tools/scan_sensitive.py                 # must report 0 findings
Get-Process llama-server -ErrorAction SilentlyContinue # must print nothing
```

Then read section 6 (open items), section 7 (next steps) and section 8 (what
the owner has to do). Nothing is running in the background right now.

## 2. Where the work is

IJ-0 (change order ECO-01) is complete through IJ-0.5. The tool-calling step is
in progress. Antigravity integration, the Model Gateway, the performance step
and everything in IJ-1.0 (missions M3 to M10) have not started.

| Step | Status | What it established | Evidence |
|---|---|---|---|
| M0 environment | PASS | Hardware, OS, driver, tools and security state frozen | `evidence/M0/`, `reports/M0_ENVIRONMENT_REPORT.md` |
| IJ-0.1 upstream audit | PASS | llama.cpp PR #24889 merged; stable `v1.0.0` ships build `b12359` | `reports/IJ0_UPSTREAM_AUDIT.md` |
| IJ-0.2 models | PASS | MiniCPM5-2B from ModelScope, 17 of 17 files match SHA256 | `evidence/IJ0/model_identity.json` |
| IJ-0.3 engine install | PASS | CPU, Vulkan and ROCm builds run and enumerate the GPU | `evidence/IJ0/engine_install.json` |
| IJ-0.4 launch scripts | PASS | Start, stop, check; 9 of 9 API checks on Vulkan | `evidence/IJ0/server_api_check.json` |
| IJ-0.5 GPU proof | PASS | Same output on CPU, Vulkan and ROCm/HIP; GPU execution shown four ways | `reports/IJ0_GPU_BACKEND_QUALIFICATION.md` |
| TC tool calling | IN PROGRESS | First experiment 5 of 5; benchmark harness written but never run | `evidence/IJ0/protocol/tool_calling_smoke.json` |

Gates: G0, G1, G2, G3, G4 are **PASS**. G5 to G14 are **NOT_RUN**. No verdict
is granted yet; see `MISSION_STATE.json`.

## 3. Things written but not yet verified

Treat these as unproven until they have been run:

- `benchmarks/tool_calling/runner/run_benchmark.py` has never been executed.
  The generator, the datasets, `tool_simulators.py` and `evaluate.py` have
  only been checked by generating the datasets and parsing code.
- The parser fixture runner does not exist. The plan is to feed each fixture in
  `benchmarks/tool_calling/fixtures/minicpm5_parser_fixtures.json` to the
  native parser as an assistant prefix through `/v1/chat/completions`. Whether
  this llama.cpp build supports that is **untested**.
- `benchmarks/tool_calling/README.md` and the tool-calling report generator are
  not written.
- There is no unit-test suite. `CONTRIBUTING.md` says so.

## 4. Repository state

- Local branch `mission/ij-1.0-windows-fullstack-qualification`; all work is
  committed and the working tree is clean (`git log --oneline` lists it).
- **No remote.** `AIwork4me/Inclusive-JobBot` does not exist on GitHub. Nothing
  has been pushed or published.
- Repository-local git identity: `AIwork4me <AIwork4me@qq.com>`. The global
  git identity was not changed.
- Not in git on purpose: `.venv`, `.tools`, `.runtime`, `.scratch`, `models/*`
  except the manifest, `runtime/llama-cpp/*` except the README.

## 5. What is on disk

| Path | Content |
|---|---|
| `models/MiniCPM5-2B-GGUF/` | F16, Q8_0, Q4_K_M GGUF, SHA256 verified |
| `models/MiniCPM5-2B/` | BF16 safetensors, config, tokenizer, `chat_template.jinja` |
| `runtime/llama-cpp/cpu`, `vulkan`, `rocm` | official llama.cpp build `b12359` |
| `runtime/llama-cpp/rocm-libs/` | ROCm 10.0.0 wheels (hipBLAS, rocBLAS, hipBLASLt), 2.8 GB |
| `.tools/ollama-core/` | Ollama 0.40.17 portable copy; optional baseline, not running |
| `.tools/downloads/` | verified release archives |
| `.runtime/logs/` | server logs and script outputs |
| `.runtime/gpu_run1/` | results of the first GPU run, used for the repeatability check |

## 6. Open items

See `BLOCKERS.md` for detail.

| ID | Item | Owner |
|---|---|---|
| B-005 | No C++ toolchain: upstream `test-chat` and debug builds are not possible locally | owner (optional install) |
| B-006 | No power meter: energy per task stays `NOT_RUN` | owner (hardware) |
| B-007 | 24 h and 168 h soak tests need the machine awake for days | owner (power settings) |
| B-004 | Long runs exceed one session; everything must stay resumable | project |

Open technical questions, none of them a blocker today:

- Does the native parser hold up across the 500 frozen cases? Only five
  hand-written checks have run.
- Does the prefix-continuation technique reach the native parser? Untested.
- Which backend becomes the default? Vulkan decodes faster, ROCm/HIP
  prefills faster in IJ-0.5; the performance step decides.
- Upstream PR #32746 (recovery of malformed MiniCPM5 XML) was not merged. If
  the fixtures show a parser defect, follow ECO-01 section 5.5.

## 7. Next steps, in order

### 7.1 Tool-calling benchmark on the development split

```powershell
pwsh -File scripts/windows/start_llama_server.ps1 -Backend vulkan -Model q8
python benchmarks/tool_calling/runner/run_benchmark.py --dataset dev --limit 20
```

Expect to find defects in the runner, the simulators or the expectations on
the first run. Fix them, then run the whole development split without
`--limit`. Only tune prompts, tool descriptions and decode settings on the
development split.

### 7.2 The frozen 500-case test set

```powershell
python benchmarks/tool_calling/runner/run_benchmark.py --dataset test --resume
pwsh -File scripts/windows/stop_llama_server.ps1
pwsh -File scripts/windows/start_llama_server.ps1 -Backend rocm -Model q8
python benchmarks/tool_calling/runner/run_benchmark.py --dataset test --output evidence/IJ0/protocol/tool_calling_test_rocm
```

The test file must still match `benchmarks/tool_calling/datasets/dataset.manifest.json`
(generator 1.0.2). If a generator change becomes unavoidable, that is a new
freeze: bump the version, regenerate, and say so in the report. Report the
real numbers against the targets of ECO-01 section 5.4; do not adjust the
targets.

### 7.3 Parser fixtures

Write `benchmarks/tool_calling/runner/run_parser_fixtures.py`. Probe first
whether an assistant message with tools is continued (prefix) or treated as a
finished turn. Expectations are already fixed in the fixture file.

### 7.4 Antigravity SDK against llama-server

`LocalOpenAIAgentConfig(model="minicpm5-2b", base_url="http://127.0.0.1:8080/v1")`.
Disable file reads and writes, command execution, sub-agents and MCP in
`CapabilitiesConfig`, and add `deny("*")` plus `allow(...)` for the job tools.
`.lightweight()` alone is not a boundary. Then work through the 12 items of
ECO-01 section 6 and capture the harness traffic under
`evidence/IJ0/antigravity/`.

### 7.5 After that

Model Gateway refactor and contract tests, performance qualification and engine
selection, gates G0 to G14 with the IJ-0 reports, GitHub publication, then
IJ-1.0.

## 8. What the owner has to do

The project does not install system-level software and does not change
Windows, security or power settings.

**Optional, useful (blocker B-005)**: Visual Studio 2022 Build Tools with the
"Desktop development with C++" workload, including the CMake and Ninja
components. This lets the project build and run llama.cpp's own `test-chat` at
commit `b1b770d9` on this machine and build a debug binary if raw model output
has to be captured before the parser. Without it, upstream tests run only in
GitHub-hosted Linux CI. It is checked with `cmake --version`, `ninja --version`
and a build of `test-chat`.

**Nothing else is required.** Node.js for the frontend can be a portable copy
inside the repository. The AMD HIP SDK is not needed: the official ROCm build
runs with the ROCm wheels. Ollama, PowerShell 7 and the ROCm SDK are not
needed either.

**Decisions that belong to the owner, when the time comes**: power settings
for the soak tests (B-007), a power meter if energy per task is wanted (B-006),
and the moment the repository becomes public.

## 9. Things that will trip you up

- The machine is reached over a remote display session. Never disable its
  network or interfere with the remote session.
- Smart App Control is off because the owner turned it off on 2026-11-24.
  The project never changes that setting.
- `files.pythonhosted.org` and `raw.githubusercontent.com` are unreliable on
  this network. Use `gh api`, the Tsinghua PyPI mirror and
  `scripts/tools/parallel_fetch.py`.
- `grep` and `sed` here are not the GNU tools (`grep` is `ugrep`); backslash
  patterns behave differently and a leak check with them was a false negative.
  Use the Python tools: `scan_sensitive.py`, `redact_text.py`.
- Python `-I` ignores `PYTHONIOENCODING`; call
  `sys.stdout.reconfigure(encoding="utf-8")` before printing model output.
- From Git Bash, write a script's output to a file instead of piping it when
  the script starts the server, or the pipeline never ends.
- Stop processes by their Windows process id. `$!` in Git Bash is an MSYS pid.
- Windows PowerShell 5.1 reads BOM-less scripts in the local code page: keep
  `.ps1` files ASCII. It also returns `$null` for a property that does not
  exist; check that a property exists before trusting a 0.
- PowerShell variable names are case-insensitive (`-Probe` and `$probe` are one
  variable), and an unbound `[string]` parameter is `""`, not `$null`.
- A CPU-only llama.cpp build logs `offloaded 43/43 layers to GPU` for
  `-ngl 99`. The launch script forces 0 GPU layers for such builds.
- The ROCm `ggml-hip.dll` is 1.1 GB and its wheels 2.8 GB. Keep them out of git.

## 10. Key identities

| Item | Value |
|---|---|
| MiniCPM5-2B-GGUF revision | `8cc1178b0a5cee98872ca3f2f88d49b3d3fa6f59` |
| MiniCPM5-2B (BF16) revision | `4e7a94716d4526da493d68962f475390e852954b` |
| llama.cpp stable release | `v1.0.0` -> build `b12359`, commit `b1b770d90d94cad9e9ea5b993bdbc383a522fb28` |
| MiniCPM5 parser merge | PR #24889, commit `c818263f2a5ddab028dea5f169ea2b2266421125` |
| GGUF-embedded chat template | 9060 chars, SHA256 `cc945752db555d60949b16989df4ccfeb52a313d6b4b5c5229dd786e2e9fcf1c` |
| Antigravity SDK | `google-antigravity` 0.1.24 (Apache-2.0) |
| Tool-calling test set | generator 1.0.2, 500 cases, SHA256 `ce6bf6bf433baab69e511328faae42c34d6a245e44dfd432e2a30f94c84e6add` |
| Tool-calling development set | generator 1.0.2, 120 cases, SHA256 `e5e2308ff8b4fe5a13dfdd9d279018845e20fcf8d9e151ea8ccd8fef3a03a5fa` |
| Engine workload | v1.0.2, 52 items, manifest in `benchmarks/engine_qualification/` |

## 11. Everyday commands

```powershell
pwsh -File scripts/windows/start_llama_server.ps1 -Backend vulkan -Model q8
pwsh -File scripts/windows/check_llama_server.ps1 -Probe
python scripts/tools/llama_server_api_check.py
python scripts/tools/tool_calling_smoke.py
pwsh -File scripts/windows/stop_llama_server.ps1
```

Backends `cpu`, `vulkan`, `rocm`; models `f16`, `q8`, `q4`. Defaults are in
`configs/llama_cpp/launch.json`, the pinned engine in
`configs/llama_cpp/engine.json`.
