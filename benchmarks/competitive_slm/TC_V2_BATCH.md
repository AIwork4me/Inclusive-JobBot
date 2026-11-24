# Competitive TC-V2 roster runner

Use `tc_v2_batch` for the B, D, F and G candidates on the same strict-admission
Vulkan build. The full frozen roster contains 500 primary trials, 500 streaming
trials and 150 repeat trials on the preselected 50-case panel. The server stays
loaded across a batch. Each trial has its own SQLite database and resets the
per-trial budget. The generation observer advances continuously through the
session trace.

The existing `tc_v2_candidate` command runs single-case diagnostics with a
separate run identity. The batch runner verifies the same GGUF, embedded
template, binary, DLL, device and source observer identities.

```powershell
$env:PYTHONPATH = (Resolve-Path src).Path
$common = @(
    '--candidate', 'B',
    '--model', $candidateGguf,
    '--engine-dir', $strictVulkanEngineDir,
    '--panel', 'full'
)
python -m benchmarks.competitive_slm.tc_v2_batch @common --verify-runtime
python -m benchmarks.competitive_slm.tc_v2_batch @common --output $candidateOutput --batch-size 25
python -m benchmarks.competitive_slm.tc_v2_batch @common --output $candidateOutput --resume
```

Keep one output directory per candidate and roster. The panel choices
`primary`, `stream` and `repeat` can run those frozen rosters independently.
Use `full` to obtain both sides of the streaming parity check in one run.
Resume preserves the exact dataset, selected roster, port, source and runtime
identity. A batch limit can change across invocations. The runner also closes
the server before the process sampler's maximum capture interval expires.

The runner writes an atomic first-attempt journal before the model request.
It preserves the trajectory, complete source capture, SQLite state and the
checkpoint digests. After closing the session, it seals the GPU, source and
checkpoint evidence. An interrupted attempt with missing evidence is
`BLOCKED`. Resume continues at the next untouched trial. The summary reports
unmeasured cases against the original denominators and omits aggregate rates
that require complete evidence. A coverage `PASS` means the selected roster was
assessed. Individual task results and paired outcomes remain separate.
