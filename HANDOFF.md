# Handoff

## IJ-0.7.2 A1 checkpoint

Status **INCOMPLETE**. Start with the [checkpoint report](reports/ATLAS_IJ072_CHECKPOINT_CN.md) and
[physical queue](atlas/physical_queue.json). The frozen 540-trial Qwen3-8B PC-S protocol is archived. Matched L0 P0/P1
replays and the larger reference admission remain separate diagnostics. Work
from the existing PR #6 branch. Reserve the Radeon for a single process at a
time. The original JOB-V1 A and B run directories remain under the IJ-0.7
worktree and keep their own identities and checkpoints.

The Qwen3 PC-S Planning source is `6a7ea4f9d527fffeeb32d8ef88496916d9dbc8ed`.
A pinned local worktree at `.scratch/ij072-plan-runtime` preserves that runtime
identity. The TC-V2 development and MULTITOOL sources are bound individually in
their run manifests. Keep separate outputs for any changed runtime or prompt.

From a fresh checkout, verify the portable evidence with
`python scripts/tools/verify_atlas_artifacts.py`,
`python -m scripts.tools.atlas_archive_pc_s_tc --verify-archive evidence/IJ072/benchmark_validity/pc-s-tc`
and `python -m scripts.tools.atlas_failure_ledger --check`.
Qwen3-14B passed [admission](evidence/IJ072/model_identity/admission/J/report.json) and
completed the [100-trial TC-V2 component](evidence/IJ072/benchmark_validity/pc-s-j-tc/summary.json).
The [complete MULTITOOL archive](evidence/IJ072/benchmark_validity/pc-s-j-multi-full/coverage.json)
sealed 120/120 trials and the [streaming comparison](evidence/IJ072/benchmark_validity/pc-s-j-multitool-streaming-pairs.json)
verified 10 physical pairs. Its [complete Planning archive](evidence/IJ072/benchmark_validity/pc-s-j-planning-full/diagnostic.json)
sealed 320/320 trials. The larger reference's original source and outputs are
linked to the clean workstation worktree `.scratch/ij072-reference-runtime`
at `cbe2107f434890f14ff3431cc16a4c0bf41fd752`.

The [stratified PC-P panel](atlas/benchmarks/pc_p_factorial.json) has 423 sealed
trials, combining the [complete Qwen3-8B block](evidence/IJ072/benchmark_validity/pc-p-h-factorial-full.json)
with the [first five cases for the other three models](evidence/IJ072/benchmark_validity/pc-p-factorial-first-five-four-models.json).
Use the workstation `.scratch/ij072-prompt-runtime` worktree at
`876ee84baa86f86399a5ae46bd7721671e16a090` with the same shared Radeon slot.
Verify the device is available and save results at completed batch boundaries.
Reuse the matching output directory for each model and arm.
Candidate A resolves the pinned MiniCPM5 GGUF in the worktree's ignored
model directory. Candidates B and G use the existing Q8_0 files under
`../ij07-worktree/.runtime/ij07-candidates/`. The model hashes are checked
for each launch.

```powershell
$env:PYTHONPATH = (Resolve-Path src).Path
$arm = 'p0'
python -m scripts.tools.atlas_pc_p --candidate A --arm $arm --engine-dir ../../.tools/ij07-toolchoice-p4b-vulkan --output "../ij071-atlas/.runtime/ij072-pc-p-a-clean-$arm" --batch-size 27
```

The raw competitive and JOB-V1 A/B reconciliation commands require the
original workstation data. A1 must pass before revised large-scale qualification.
The [score-blind review packet](reports/ATLAS_A1_BLIND_REVIEW.md) is prepared.
Human assessments and reconciliation still need independent reviewers.

## IJ-0.7.1 Atlas checkpoint

See [baseline audit](reports/ATLAS_A0_BASELINE_AUDIT.md), [live progress entry](atlas/progress.json), and [tracking issue #5](https://github.com/AIwork4me/Inclusive-JobBot/issues/5). Work from branch `mission/ij-0.7.1-jobbot-agentic-capability-atlas-v1`, stacked on the reviewed IJ-0.7 HEAD `888f910b99b90dd7a3ac0f8d8760c6a6bbdc4102`.

A0 rechecks historical records. A1 remains BLOCKED pending full independent Witness, critical mutations across all suites, prompt ablations, and real strong-model controls. The 3,300 passed reference fixtures are software controls. Preserve the original workload identities and consult [the GPU queue](atlas/physical_queue.json) before reserving the Radeon slot.

To regenerate the dashboard run `python scripts/tools/atlas_progress.py`. To regenerate the software-control records run `python scripts/tools/atlas_controls.py --output .runtime/atlas-controls.json`.

## IJ-0.7

IJ-0.7 starts from the exact reviewed IJ-0.6 HEAD
`d2e5b31aa1f0894638f7b648a4cf3591fbb71e6e` on the separate mission branch.
Follow [issue #3](https://github.com/AIwork4me/Inclusive-JobBot/issues/3)
and the [execution plan](docs/IJ07_EXECUTION_PLAN.md). G0 has archival
audit evidence. Follow the [audit report](reports/IJ07_INITIAL_INDEPENDENT_AUDIT.md)
for the regenerated figures, original failures and local hardware capture.

The historical replay, candidate admissions and fresh holdout runners use
separate identities. Start with the [historical runbook](benchmarks/root_cause/README.md)
and the [TC-V2 runbook](benchmarks/tool_calling_v2/holdout/README.md).
The latter uses separate SQLite stores and a trusted synthetic confirmation
source. The [planning runbook](benchmarks/agentic_planning_v1/README.md)
uses the native model and retains both Plan-first and Acting-first traces.
The capture worktree stays pinned to the exact experiment commit. Continue
reporting and software changes in the mission branch worktree.

The four historical arms and both independent TC-V2 backend profiles
finished. See the [dual-backend report](reports/IJ07_TC_V2_QUALIFICATION.md)
and [JOB-V1 Arm F results](reports/IJ07_PURPOSE_BUILT_VALIDATION.md).
Use the [multi-tool runbook](benchmarks/multitool_v1/README.md) for the full
primary roster and the planning runbook for the paired tracks. Retain exact
runtime and source identity when resuming an interrupted output directory.
The MULTITOOL-V1 primary run completed 600/600 trials with the original
16-call wire limit. Keep the first 213-case archive as the wire control's
exact input. The explicit 32-call profile has a separate wire-only
regression. Assign a new output directory to a live test of that profile.
 [Full primary evidence](evidence/IJ07/multitool/primary-vulkan-full/)

The [competitive TC-V2 batch runner](benchmarks/competitive_slm/TC_V2_BATCH.md)
keeps the strict-admission Vulkan server loaded through a roster. Use the
[frozen B/D/F/G plan](configs/ij07/tc_v2_competitive_plan.json) and the
[journal archive runbook](benchmarks/competitive_slm/TC_V2_ARCHIVE.md). The
[JOB-V1 model treatment runner](benchmarks/job_productivity_v1/holdout/MODEL_ARMS.md)
uses the same frozen inputs for A–E. Physical full-roster results are pending
for both runners. Use the planning archive CLI to verify journals and produce
separate Plan-first and Acting-first coverage by level.

The original planning profile completed the full 1,600-trial roster in
eight sessions using the unchanged P4b observer. Both tracks failed the
entry level. Use a new output directory for live runs of the corrected
Chinese reference profile. [Planning archive](evidence/IJ07/planning/primary-vulkan-full/)

The original MULTITOOL repeat panel completed 300/300 physical trials.
The original planning repeat panel completed all 960 frozen trials. Each
track failed all 480. The strict B/D/F/G TC-V2 queue uses the same single-GPU
slot. Its first B session verified 200 trials. The A–E JOB-V1 queue waits for
all four competitive TC-V2 rosters before using the GPU. Each active run
keeps its resumable local folder and exact runtime source identity.
 [Multi-tool repeat archive](evidence/IJ07/multitool/repeat-vulkan-full/) · [Planning repeat archive](evidence/IJ07/planning/repeat-vulkan-full/)

The [Arm F receipt-correction control](evidence/IJ07/job_ablation/F/receipt-correction/)
reruns the observed holdout on two clean commits with source digests that
differ only at `arm_f.py`. Keep these exploratory results separate from the
original registered F archive and future independent qualification.

Read this first when resuming. Last updated: 2026-11-24.

Everything below was checked against the disk and the running system at the
time of writing. If something here disagrees with what you find, trust the
machine, fix this file, and say so in the commit.

## 1. Resume procedure

Work from the repository root, the folder that contains this file.

```powershell
git status --short --branch
git log --oneline | Select-Object -First 12
python scripts/tools/scan_sensitive.py                 # must report 0 findings
Get-Process llama-server -ErrorAction SilentlyContinue
```

For IJ-0.6 read the [closure matrix](reports/IJ06_P0_CLOSURE_MATRIX.md)
and [open risks](reports/IJ06_OPEN_RISKS.md). The managed and candidate
servers were stopped after the dual-backend trials.

## 2. Where the work is

IJ-0 is complete through IJ-0.5. IJ-0.6 reproduced the original b12359
parser failures and qualified P4b against the expanded fixed suite on both
GPU backends. The original baseline failed its frozen strict fixtures.
Evaluator V2 replayed 1,000 archived traces. The Gateway and SQLite simulator
passed software regression, and the SDK and SOP trials produced real
local development evidence. Full SDK, independent holdouts, production
backend selection and IJ-1.0 qualification are pending.

| Step | Status | What it established | Evidence |
|---|---|---|---|
| M0 environment | PASS | Hardware, OS, driver, tools and security state frozen | `evidence/M0/`, `reports/M0_ENVIRONMENT_REPORT.md` |
| IJ-0.1 upstream audit | PASS | llama.cpp PR #24889 merged; stable `v1.0.0` ships build `b12359` | `reports/IJ0_UPSTREAM_AUDIT.md` |
| IJ-0.2 models | PASS | MiniCPM5-2B from ModelScope, 17 of 17 files match SHA256 | `evidence/IJ0/model_identity.json` |
| IJ-0.3 engine install | PASS | CPU, Vulkan and ROCm builds run and enumerate the GPU | `evidence/IJ0/engine_install.json` |
| IJ-0.4 launch scripts | PASS | Start, stop, check; 9 of 9 API checks on Vulkan | `evidence/IJ0/server_api_check.json` |
| IJ-0.5 GPU proof | PASS | Same output on CPU, Vulkan and ROCm/HIP; GPU execution shown four ways | `reports/IJ0_GPU_BACKEND_QUALIFICATION.md` |
| TC tool calling | FAIL | Vulkan development 100/120. Frozen baseline 433/500 Vulkan, 432/500 ROCm. Strict native parser fixtures 20/26 on each. | `reports/IJ0_TOOL_CALLING_BENCHMARK.md` |
| TC acceptance criteria | PASS | New project thresholds established from published research. | `docs/decisions/ADR-002-IJ0-TOOL-CALLING-ACCEPTANCE.md` |
| AG read-only loop | PASS | Real MiniCPM5 tool call, simulator result and exact final status on each backend. | `evidence/IJ0/antigravity/` |

Gates G0–G4 and G6–G8 are **PASS**. G5 is **FAIL** on the fixed native parser
fixtures. The 500-case coverage gate concerns execution of the original split.
The independent holdout under ADR-002 is **NOT_RUN**.

## 3. Tool-calling reproduction

See `benchmarks/tool_calling/README.md` for the fixture, benchmark, reporting
and regression commands. Parser fixtures reach the native parser through
assistant prefix continuation. Successful responses prove that the model
sampled only the configured end-of-sequence token.

## 4. Repository state

- Local qualification work is on `codex/ij0-tool-calling`, based on
  `mission/ij-1.0-windows-fullstack-qualification`.
- GitHub default branch `codex/ij0-tool-calling` and local HEAD matched
  `0592c319ab341f70bda979874697386e33ccc680` at the IJ-0.6 audit.
  New work uses `mission/ij-0.6-root-cause-and-purpose-built-execution`
  and tracking issue [#1](https://github.com/AIwork4me/Inclusive-JobBot/issues/1).
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
| B-006 | No power meter: energy per task stays `NOT_RUN` | owner (hardware) |
| B-007 | 24 h and 168 h soak tests need the machine awake for days | owner (power settings) |
| B-004 | Long runs exceed one session; everything must stay resumable | project |
| B-009 | The pinned native parser fails fixed fixtures. P4b has passed the fixed conformance suite. | project |
| B-010 | SDK offline gate requires complete process egress evidence | project |

Open technical questions, none of them a blocker today:

- Which parser fix or alternate engine identity should qualify under the
  new thresholds in ADR-002?
- Which backend becomes the default? Vulkan decodes faster, ROCm/HIP
  prefills faster in IJ-0.5; the performance step decides.
- Upstream PR #32746 (recovery of malformed MiniCPM5 XML) was not merged. If
  the fixtures show a parser defect, follow ECO-01 section 5.5.

## 7. Next steps, in order

### 7.1 Resolve the native parser gate

Use the P4b source and candidate hashes in
`reports/IJ06_PARSER_ROOT_CAUSE_REPORT.md`. The frozen generator 1.0.2
results and V2 replay are diagnostics. Freeze the new independent data,
oracle and candidate configurations before model admission.

### 7.2 Antigravity SDK against llama-server

The read-only smoke command and evidence are in
`benchmarks/tool_calling/runner/run_antigravity_smoke.py` and
`evidence/IJ0/antigravity/`. The command explicitly allowlists one synthetic
lookup and disables built-in tools, subagents and MCP. Finish the full SDK
checklist in `docs/ANTIGRAVITY_SDK_ACCEPTANCE_SPEC.md`. Resolve the remaining
structured-output and process egress cases listed in the SDK report.

### 7.3 After that

Model Gateway refactor and contract tests, performance qualification and engine
selection, gates G0 to G14 with the IJ-0 reports, GitHub publication, then
IJ-1.0.

## 8. What the owner has to do

The project does not install system-level software and does not change
Windows, security or power settings.

Visual Studio Community 2026 includes MSVC, CMake and Ninja. Initialize the
developer environment in a child process when building `test-chat`.
PowerShell 7 is optional. The project scripts also run with Windows PowerShell
`-ExecutionPolicy RemoteSigned` for each invocation on this machine.

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
