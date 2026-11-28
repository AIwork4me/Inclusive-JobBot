# AGENTIC-PLAN-V1

The IJ-0.7 M4 holdout contains 800 synthetic task worlds, with 100 cases per level and 400 prompts each in English and Chinese. The 14 domains cover the business scenarios in the mission and two general domains, community event preparation and library research. The original Radeon first-pass roster has 1,600 measured trajectories. The verification commands below exercise the dataset and scoring software with synthetic witnesses. [Measured results](../../reports/IJ07_AUTONOMOUS_PLANNING_BENCHMARK.md)

## Frozen artifacts

| File | Contents |
| --- | --- |
| `datasets/holdout.jsonl` | Public case ID, prompt, any required policy, tool surface and budgets. |
| `datasets/protocol.json` | Shared tool and answer contracts, instructions for each track, and per-level research thresholds. |
| `datasets/repeat_panel.json` | 160 fixed case IDs, 20 per level, and three fixed seeds in execution order. |
| `task_graphs/holdout.jsonl` | Private initial and target states, graph, minimum subgoal groups, expected facts and disposition, disruption, risk and synthetic service fixtures. |
| `datasets/manifest.json` | Exact SHA-256 of the frozen bytes and LF-normalized implementation digests. |

```powershell
python -m benchmarks.agentic_planning_v1.freeze verify
python -m pytest -q tests/regression/ij07/test_agentic_planning_v1.py
```

To reproduce the files elsewhere, run `python -m benchmarks.agentic_planning_v1.freeze freeze --directory PATH`. The command refuses to replace a differing file. Once live scoring starts, changes to a case, policy, scoring rule or runtime condition require a new dataset or run identity. Keep the original artifacts and results.

## Task families

| Level | What the cases require | Observed threshold |
| --- | --- | ---: |
| L0 | Interpret a goal, identify required evidence, or clarify missing or conflicting constraints. | 95% |
| L1 | Choose a tool and report one verified fact. | 95% |
| L2 | Get current and historical facts with independent calls. Either status service can satisfy the status subgoal. | 95% |
| L3 | Follow 2–5 calls with IDs obtained from earlier results. | 85% |
| L4 | Resolve, cross-check and verify an assessment in 4–10 calls, including independent evidence lanes. | 85% |
| L5 | Recover from one of eight injected events or escalate on a permission denial. Preserve a valid history lookup when recovering. | 80% |
| L6 | Complete 11–20 calls, recover from an interruption, reconcile evidence lanes and verify a persisted draft. | 75% |
| L7 | Apply a domain policy to a cross-system result, obtain external approval for publication and verify the persisted audit record. Other cases require a read-only result, clarification or escalation after declined approval. | 90% |

The graph allows independent lanes to interleave in either order. It permits declared tool alternatives and requires observed, grounded IDs for dependent arguments. Private witness order is used for software verification. The 800 instances have unique worlds and correlate within scenario families. They do not establish transfer to unseen production workflows, policies or input formats.

## Live runner contract

The Windows runner launches the existing IJ-0.7 source observer on loopback after it verifies the MiniCPM5-2B Q8_0 ModelScope pin and the selected Radeon backend libraries. Start from the repository root after the historical queue releases the GPU.

```powershell
$env:PYTHONPATH = (Resolve-Path src).Path
.venv/Scripts/python.exe -m benchmarks.agentic_planning_v1.run --backend vulkan --engine-dir .tools/ij07-observer-p4b-vulkan --output .runtime/ij07-planning-diagnostic --case AP1-L2-001 --case AP1-L7-001 --preflight-only
.venv/Scripts/python.exe -m benchmarks.agentic_planning_v1.run --backend vulkan --engine-dir .tools/ij07-observer-p4b-vulkan --output .runtime/ij07-planning-diagnostic --case AP1-L2-001 --case AP1-L7-001 --batch-size 2
.venv/Scripts/python.exe -m benchmarks.agentic_planning_v1.run --backend vulkan --engine-dir .tools/ij07-observer-p4b-vulkan --output .runtime/ij07-planning-diagnostic --case AP1-L2-001 --case AP1-L7-001 --resume
```

Both tracks are enabled by default. Omit `--case` on a fresh output directory for the 800-case primary roster per track. Use `--panel repeat` with a separate output directory for the frozen three-seed panel. `--stream`, `--temperature` and `--thinking` are explicit run settings. Preserve the exact original settings on resume. `--batch-size` limits scheduling per invocation, and a completed trial's terminal status stays in the denominator on resume. The run manifest binds the case roster, source and model digests, binaries, backend, Git HEAD and sampling settings. A process restart starts a new server session under the same configuration.

The runner writes each request, raw observed response and tool observation to an fsync'd attempt journal. An interrupted attempt remains in `attempts/`. A successful terminal write in `cases/` binds to its journal hash and is required to skip that trial on resume. `summary.json` counts complete and pending trials. Local source capture, server logs and GPU counters stay in the output directory. The current implementation sends Chat Completions directly through the repository's native wire decoder. Antigravity SDK execution remains a separate qualification track.

### Strict-admission Vulkan comparison

Use `--candidate B|D|F|G --model PATH --backend vulkan` with the strict-admission Vulkan directory. The runner verifies the candidate's official and packaged model identity, GGUF digest, embedded native template, executable and DLL set against its strict-admission evidence. After launch it checks the native template digest, Vulkan device, source observer and full GPU offload before the first planning request. The process and requests use the same `ij07-candidate-<id>` alias as strict admission.

| Candidate | Model | Local path under `.runtime/ij07-candidates/` |
| --- | --- | --- |
| B | LFM3-1.7B | `LiquidAI__LFM3-1.7B-GGUF/LFM3-1.7B-Q8_0.gguf` |
| D | Qwen3.5-2B | `unsloth__Qwen3.5-2B-GGUF/Qwen3.5-2B-Q8_0.gguf` |
| F | Ministral-3-3B-Instruct-2512 | `mistralai__Ministral-3-3B-Instruct-2512-GGUF/Ministral-3-3B-Instruct-2512-Q8_0.gguf` |
| G | Gemma-4-E2B-it | `ggml-org__gemma-4-E2B-it-GGUF/gemma-4-E2B-it-Q8_0.gguf` |

```powershell
$env:PYTHONPATH = (Resolve-Path src).Path
$model = '.runtime/ij07-candidates/LiquidAI__LFM3-1.7B-GGUF/LFM3-1.7B-Q8_0.gguf'
.venv/Scripts/python.exe -m benchmarks.agentic_planning_v1.run --candidate B --model $model --backend vulkan --engine-dir .tools/ij07-toolchoice-p4b-vulkan --output .runtime/ij07-planning-candidate-b --case AP1-L2-001 --preflight-only
```

Preflight verifies files and the selected roster without launching a server. When the GPU is available, remove `--preflight-only` to run the selection. Use separate output directories for candidates, diagnostics, primary panels and repeat panels. Keep the same case roster, tracks and sampling settings for a controlled comparison. With the default settings all candidates use the frozen planning action and context budgets, up to 2,048 completion tokens per turn, temperature zero, non-streaming and requested thinking disabled. A MiniCPM5 comparison should use the same strict-admission engine directory and matching settings, with `--candidate` and `--model` omitted. Existing runs remain readable through the archive tool. Resume an earlier checkpoint using its exact runner revision.

Use `contract.request(public_case, track)` to construct the messages and schemas. Give each case and track a new `SyntheticSandbox(private_graph["world"])`. Only service observations cross into model context. Keep world fixtures, graph nodes, witnesses and scoring results outside the model-facing context. Capture true model turns and tool calls with the full IJ-0.7 runtime identity and evidence contract.

- **Track P** starts with a machine-readable plan. Capture the exact public plan and verify that it preceded the first tool action. Then continue with actual model decisions. The scorer validates actionable dependency and reference structure, confirms initially applicable graph subgoals and compares the observed outcome. Text in `subgoals`, `preconditions`, `success_conditions` and `stop_conditions` receives a shape check. The scorer uses actual graph behavior for business semantics. For an injected disruption, unknown downstream branches can remain conditional in the initial plan. They are scored from their actual execution.
- **Track A** starts from the same public task and policies and proceeds from each observable result. It allows an agent to act without an explicit initial plan and measures the graph from the resulting trace.
- The host may enforce schema, authorization, transaction and budget checks. Record model, host and SOP tool decisions separately. Emit tools exactly as proposed, with observed arguments, responses and source attribution. Deliver a synthetic external scope change or confirmation to the model as a trusted user/environment observation. The synthetic user grants approval only after an exact staged draft is requested for confirmation. Treat approval values as authorized only when received through that external event.
- For parallel calls, capture that their proposals preceded the batch responses and evaluate each with only earlier available inputs. Graph-independent calls may be serialized in any order. A runtime integration must enforce proposal-time availability for every dependent argument and carry the original batching evidence.
- Each action record supplies `tool`, parsed `args`, `observation`, `origin` (`model`, `host` or `sop`), and, for model actions, `trigger` (`user_request` or `tool_feedback`). Pass state from a fresh sandbox snapshot and the raw model final object to `oracle.score(...)`. For Track P also pass the raw `plan` and independently observed `plan_before_tools=True`. Pass maximum prompt context tokens observed across model calls via `peak_context_tokens`.
- Preserve timeout, missing trace and failed setup states explicitly as `FAIL`, `BLOCKED` or `NOT_RUN` where appropriate. The offline scorer's `PASS` and `FAIL` apply to the supplied trace. A live qualification requires complete capture, verified context budget, a run ID and exact model, runtime and hardware identities, along with the dataset digest. The scorer allows unknown context usage for software-only fixture checks.

## Reporting

Keep all 800 case IDs per track in the first-pass denominator, including unexecuted rows. Report initial plan and graph coverage, dependency validity, efficiency, successful Plan-first execution, replanning, unnecessary and hallucinated actions, clarification, recovery, budget adherence, verified completion, safe termination and false success. The scorer returns per-case operands and `null` where a measure does not apply. Track A goal-understanding accuracy is directly observable at L0. At higher levels use graph subgoals and verified results and preserve the absence of a separate goal statement.

Compute the observed per-level rates and 95% intervals, then apply the continuous-level rule. Report the project's observed threshold and statistical support separately. Correct clarification and escalation can satisfy the case disposition. Business-completion rates count cases with verified target completion as their distinct outcome. An actual unauthorized operation, unconfirmed high-risk publication or unexplained evidence gap prevents capability qualification.

The repeat panel uses a fixed hash ranking within level, scenario variant and language strata. Run all three listed seeds in array order for each case, track and frozen configuration. Record the first result, any of three successes, all three successes and the failure transition matrix. The first trial can contribute to the primary first-pass analysis only if it uses the exact same configuration as that analysis. Keep failure-driven diagnostic repeats outside this panel.

Verify the gzip text parts and their raw file digests with
`python -m scripts.tools.bundle_ij07_planning evidence/IJ07/planning/primary-vulkan-full`.
Use `--restore PATH` to recover an exact copy into a fresh directory,
then reanalyze with `python -m scripts.tools.archive_ij07_planning --source PATH`.
