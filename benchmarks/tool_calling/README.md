# IJ-0 tool-calling qualification

The benchmark runs real MiniCPM5-2B inference on the managed llama-server.
Tool handlers work entirely in memory with synthetic records. The parser fixture
runner separately feeds fixed assistant outputs to the native parser.

## Reproduce a run

From the repository root, with the pinned engine, Q8_0 model and Python
dependencies installed, run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File scripts/windows/start_llama_server.ps1 -Backend vulkan -Model q8
.venv/Scripts/python.exe benchmarks/tool_calling/generators/generate_dataset.py --check
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe benchmarks/tool_calling/runner/run_benchmark.py --dataset dev --output .runtime/tool-calling/dev
.venv/Scripts/python.exe benchmarks/tool_calling/runner/run_parser_fixtures.py --output .runtime/tool-calling/fixtures-vulkan
.venv/Scripts/python.exe benchmarks/tool_calling/runner/run_benchmark.py --dataset test --resume --output .runtime/tool-calling/test-vulkan
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File scripts/windows/stop_llama_server.ps1
```

Use `-Backend rocm` and distinct ROCm output directories for the second arm.
Start `scripts/windows/sample_gpu_counters.ps1` on the managed server PID
before each test run and stop it after the last case. Write the samples to
`gpu.jsonl` in the arm's output directory. To render a report from both arms:

```powershell
.venv/Scripts/python.exe benchmarks/tool_calling/runner/report_benchmark.py .runtime/tool-calling/test-vulkan .runtime/tool-calling/test-rocm --output .runtime/tool-calling/reproduced-report.md
```

## Evidence and interpretation

- `run.json` binds the run to the dataset, code, Git revision, engine binaries,
  ModelScope revision and model digest, backend, device and settings.
  `results.jsonl` appends one completed case at a time. `metrics.json`
  summarizes all selected cases after completion.
- `--resume` retains the run ID and finished cases. It checks the case list,
  code hashes, engine and server configuration before appending. A transient
  request failure leaves the current case available to retry.
- The immutable generator 1.0.2 split has 120 development and 500 test cases.
  Subsets and prompt or decode experiments belong on the development split.
  For the two-order comparisons the frozen scorer requires a randomly selected
  first order and a single first-turn call, even though both independent lookups
  can be issued together. Keep this limitation with the results.
- Argument accuracy covers the expected first-turn arguments specified by the
  frozen cases. The denominator includes missing calls. The invalid-call rate
  includes malformed or undeclared calls and arguments rejected by the schema.
  An explicit native parser error is a failed case and a separate request error.
- Fixture evidence records the configured EOS token and its sampled bytes for
  successful parser replies. It records explicit native parser rejections
  separately. These results measure parser behavior on fixed inputs.
- The Antigravity smoke command is
  `run_antigravity_smoke.py`. It exercises one local, read-only loop and records
  the SDK's transcript. The full SDK qualification follows ECO-01 §6.

See the [baseline report](../../reports/IJ0_TOOL_CALLING_BENCHMARK.md)
and the [new acceptance thresholds](../../docs/decisions/ADR-002-IJ0-TOOL-CALLING-ACCEPTANCE.md).
