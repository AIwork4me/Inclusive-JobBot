# AG-11 owner action required

**AG-11 is BLOCKED.** Only the machine owner can authorize and run the collector in a separately elevated console. The ordinary-token process and offline replay controls are in `tests/regression/slm10/test_ag11_owner.py`. The current Radeon queue keeps its lease and takes precedence.

On the ordinary workstation token, the collector syntax, Get-WinEvent and logman availability, all four TCP/UDP IPv4/IPv6 loopback controls, and 10 offline regression cases passed. The owner capture and process-tree attribution are pending.

Use the existing IJ-SLM worktree. Once the GPU queue and scheduled diagnostics have finished, open an ordinary PowerShell console there and set up a fresh run identifier for one candidate.

```powershell
$assets = (Resolve-Path -LiteralPath '../..').Path
$python = Join-Path $assets '.venv/Scripts/python.exe'
$runId = [guid]::NewGuid().ToString('N')
$candidate = 'A'
$python
$runId
```

In a separately elevated 64-bit PowerShell console opened at the same worktree, paste the two printed values.

```powershell
.\scripts\windows\RUN_AG11_ELEVATED.ps1 -RunId '<run-id>' -Python '<pinned-python-path>' -TimeoutSeconds 600
```

Once the collector prints `READY` with that run ID, use the original ordinary console.

```powershell
$env:PYTHONPATH = '.;src;benchmarks/tool_calling/runner'
& $python -m scripts.tools.ag11_owner run --run-id $runId --assets $assets --candidate $candidate --port 18754
```

Wait for the collector to exit, then decode and replay from the ordinary console.

```powershell
.\scripts\windows\RUN_AG11_ELEVATED.ps1 -RunId $runId -Decode
& $python -m scripts.tools.ag11_owner replay --run-id $runId
```

Repeat with fresh run IDs for B and D. Give the project reviewer only `redacted-observation.json` and the already-approved public runtime identity references. Leave ETL, normalized events, process IDs, connection addresses, and private SDK evidence on the workstation.

The reviewer checks the matching trace digest and ordinary-token process tree, PID reuse protection, the before-and-after short-lived TCP and UDP controls for IPv4 and IPv6, zero event loss, and the attributed SDK traffic. A missing control or uncertain attribution leaves the observation BLOCKED. An attributed non-loopback transmission is FAIL. A successful observation covers its own time window and candidate. [Complete collection and review protocol](docs/AG11_OWNER_INSTRUCTIONS.md)
