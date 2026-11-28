# IJ-0.7 historical observation replay

The replay uses the original frozen 500-case set, native template, synthetic
V1 host, and both archived grading semantics. The loopback HTTP capture records
rendered prompts, responses and SSE frames. The source observer records exact
prompt and sampled token IDs plus generation bytes before stop filtering and
before protocol formatting. The wrapper checks the completion ID and token
counts against HTTP usage.

The control changes only the trace environment variable for the same build.
Compare visible outputs, exact non-streaming generated token IDs and stream
protocol results. A source trace missing after an early failure is recorded as
`BLOCKED`. The strict Gateway protocol decoder observes the wire, and the
frozen V1 simulator supplies task feedback. This diagnostic uses synthetic
receipts in memory. Persistent state and SDK execution are separate gates.

## Build and run on the qualification workstation

Use a clean llama.cpp source worktree at
`b1b770d90d94cad9e9ea5b993bdbc383a522fb28`. Apply the
[observer](../../patches/ij07/llama-b12359-generation-observer.patch) for R0.
For R1 apply both [P4b patches](../tool_calling_v2/parser/README.md) as well.
Build each in a distinct directory with the existing IJ-0.6 MSVC dynamic backend
configuration. Retain the exact source diff and binary hashes. Copy the pinned
Vulkan or ROCm plugin and its release dependencies beside each binary.

```powershell
$env:PYTHONPATH = (Resolve-Path src).Path
.venv/Scripts/python.exe -m benchmarks.root_cause.historical_replay --arm R0-V --engine-dir .tools/ij07-observer-original-vulkan --output .runtime/ij07-historical/R0-V --batch-size 25
.venv/Scripts/python.exe -m benchmarks.root_cause.historical_replay --arm R0-V --engine-dir .tools/ij07-observer-original-vulkan --output .runtime/ij07-historical/R0-V --resume
```

Use distinct output directories for R0-R, R1-V and R1-R. Use `--case` on
a fresh directory for a focused diagnostic and `--observer-disabled` for a
capture-off control. Leave all four arms on the same pinned run configuration.
Use a separate Git worktree for changes while a frozen run is underway.
