# TC-V2 independent tool-calling qualification

The holdout contains 500 synthetic English and Chinese requests across the
eight ADR-002 benchmark categories. Ten authored workflow families keep
the archived suite's category counts. The 120 development cases use eight
separate families. Parameterized instances within a family share a workflow,
so case counts describe task instances and the family counts describe the
tested workflow variety.

The manifest pins both splits, their generator and oracle inputs, the
historical datasets used for overlap checks, and the 50 repeat case IDs.
The repeat panel contains five cases per holdout family, with 25 English
and 25 Chinese cases, selected by a seeded hash before inference. The
historical overlap audit checks IDs, normalized complete user requests and
declared tool names.

Every holdout case runs a complete non-streaming trajectory and a separate
complete streaming trajectory with an isolated database and the same seed.
The repeat panel runs on seeds 101, 211 and 307, with temperature zero on
all trials. This measures repeatability under the pinned greedy sampling
configuration. The 500 first non-streaming trajectories form the primary
success-rate denominator.

The model receives the task, system constraints and tool schemas. The
evaluator checks the requested steps, typed arguments, allowed dependency
order, returned values, final facts and complete business database. The
SQLite gateway checks authorization and signed review. The simulator's
positive write cases contain an independently seeded test review authorizing
specific values. The gateway binds each accepted review to the actual
wire proposal. Wrong or unsigned proposals are denied and audited. The
underlying benchmark uses synthetic records and tests the gateway directly.
The separate Antigravity SDK integration gates still require independent
execution evidence.

## Verify the freeze and runtime files

Run from the checkout. Set the runtime root to the project directory
containing the installed model and binary assets when running inside a
separate Git worktree.

```powershell
$env:PYTHONPATH = (Resolve-Path src).Path
$runtimeRoot = (Get-Location).Path
$python = Join-Path $runtimeRoot '.venv/Scripts/python.exe'
& $python -m benchmarks.tool_calling_v2.holdout.dataset
& $python -m pytest -q tests/regression/ij07/test_tc_v2_holdout.py

$backend = 'vulkan'
$engineDir = Join-Path $runtimeRoot ".tools/ij07-observer-p4b-$backend"
$parameters = @('--backend', $backend, '--runtime-root', $runtimeRoot, '--engine-dir', $engineDir)
& $python -m benchmarks.tool_calling_v2.holdout.qualify @parameters --verify-runtime
```

The verification command hashes the executable, libraries and pinned
ModelScope weights without launching a server. Local tests replay authored
oracles through SQLite and exercise fixture-backed protocol rejection.
They provide software verification only.

## Run the qualification

Use a distinct output directory for each backend. Run the two GPU arms in
sequence on the qualification workstation.

```powershell
$output = Join-Path $runtimeRoot ".runtime/ij07-tc-v2/$backend"
& $python -m benchmarks.tool_calling_v2.holdout.qualify @parameters --output $output --batch-size 25
& $python -m benchmarks.tool_calling_v2.holdout.qualify @parameters --output $output --resume
& $python -m benchmarks.tool_calling_v2.holdout.qualify @parameters --output $output --resume --fixtures
```

Repeat with `$backend = 'rocm'` and the corresponding engine directory,
parameters and output directory. For development, use `--split dev` and
a dedicated output. The holdout uses the P4b generation-observer binary
identity from the historical run metadata. The fresh model traces and
fresh native fixture trials provide the qualification observations.

The runner never retries a recorded model failure. Interrupted transport
or incomplete source capture is kept in `interruptions/`. Resume retries
that missing trajectory on the same configuration with a clean case
database. Each terminal record binds a run ID, phase, case, server session,
evidence digest and database digest. The runner verifies these before
resuming. It yields after the configured batch or 90 minutes, whichever
comes first, then releases the server and sampler. Reissue the resume
command until the first-pass, paired and repeat rosters are complete.

The final summary uses the ADR-002 thresholds and requires the native
fixture, GPU process counter and identity evidence for a passing verdict.
The fixture phase scores native behavior, strict arguments and streaming
parity independently. Some deliberately invalid arguments will be rejected
in the wire decoder. Keep the original task results, fixture results and
interruption records together. The raw inference logs remain local and
require the repository's identity redaction before publication.
