# Owner-assisted AG-11 capture

**AG-11 is `BLOCKED` pending a real owner-run capture and independent review.** The procedure records one dedicated, read-only local SDK diagnostic on the approved Radeon. The owner elevates the collector console only. The SDK, model server, loopback controls, decoder, and replay run from the ordinary workstation token.

## Before capture

- Use the existing IJ-SLM-1.0 worktree and its pinned Python environment on the approved workstation. Use a newly generated run ID for each candidate. A, B, and D each need their own capture.
- Wait for the physical queue and other Radeon work to finish naturally. The normal runner checks the active controllers and uses the repository's existing shared Radeon lease. Use an available local provider port such as `18754`.
- Confirm sufficient free space for the private ETL file and SDK artifacts. The collector caps its ETL file at 256 MiB and has a finite window. The elevated shell and ordinary shell should be opened by the same workstation owner with the expected two tokens.
- Leave all evidence in the ignored `.runtime/ag11` directory. The ETL contains machine-wide process and connection metadata from that time window. The decoded events and SDK raw evidence also require private handling.

## Start the dedicated collector

In the **ordinary** PowerShell console, from the linked IJ-SLM-1.0 worktree root, prepare the following values. The two-level assets path applies to the existing linked worktree layout.

```powershell
$assets = (Resolve-Path -LiteralPath '../..').Path
$python = Join-Path $assets '.venv/Scripts/python.exe'
$runId = [guid]::NewGuid().ToString('N')
$python
$runId
```

In a **separately elevated** 64-bit PowerShell console in the same worktree, substitute the two values printed above. The script checks elevation, the ETW providers, and the fresh private capture directory before creating a uniquely named temporary session. It announces `READY` only after session creation succeeds. The session uses Microsoft Kernel-Process and Kernel-Network providers and a sequential ETL file. [Microsoft provider list and identifiers](https://learn.microsoft.com/windows-hardware/drivers/devtest/dtrace-etw) · [Logman trace session options](https://learn.microsoft.com/windows-server/administration/windows-commands/logman-create-trace)

```powershell
.\scripts\windows\RUN_AG11_ELEVATED.ps1 -RunId '<copied-run-id>' -Python '<copied-pinned-python-path>' -TimeoutSeconds 600
```

Back in the **ordinary** console, start the normal-token run only after the separate collector prints `READY` with the matching run ID. Run one candidate per capture. The runner uses the existing `native-on` diagnostic, with fully local SDK and inference, and records the subject subprocess PID and Windows creation time. The two separate canary processes exercise short-lived loopback TCP and UDP over IPv4 and IPv6 before and after the subject. They give positive coverage for all four transport classes and a negative control for tree attribution. No Internet or LAN address is used by a canary.

```powershell
$env:PYTHONPATH = '.;src;benchmarks/tool_calling/runner'
& $python -m scripts.tools.ag11_owner run --run-id $runId --assets $assets --candidate A --port 18754
```

The driver writes its terminal marker after the dedicated diagnostic and second canary exit. The elevated collector sees that marker and stops only the session created by this invocation. It records the ETL SHA-256 and native before-stop and final ETW loss counters. A timeout or a start, stop, or counter failure leaves the credential `BLOCKED`. If PowerShell was forcibly terminated, use the exact `JobbotAG11-<run-id>` name for this invocation when checking cleanup. The displayed query and stop commands refer only to that capture. [ControlTraceW query and stop](https://learn.microsoft.com/windows/win32/api/evntrace/nf-evntrace-controltracew) · [Session statistics and event loss](https://learn.microsoft.com/windows/win32/etw/about-event-tracing)

## Decode and review

Wait for the collector to exit. Run both commands in the **ordinary** console. The decode supports the host's inspected ETW schemas and verifies the raw file hash before producing private normalized events. Unsupported, undecodable, or unattributable records can block qualification. [Reading ETL with Get-WinEvent](https://learn.microsoft.com/powershell/module/microsoft.powershell.diagnostics/get-winevent?view=powershell-5.1)

```powershell
.\scripts\windows\RUN_AG11_ELEVATED.ps1 -RunId $runId -Decode
& $python -m scripts.tools.ag11_owner replay --run-id $runId
```

The replay matches process sequence numbers and start/end lifetimes against the subject PID and creation time, then attributes outgoing flow records using the payload PID at the event time. It checks zero ETW loss, distinct canary lifetimes bracketing the subject, ordinary tokens throughout its tree, observed SDK loopback traffic, and expected SDK and model child processes. The redacted JSON contains counts, disposition, a reason code, and hashes for the trace, normalized events, collector and runner receipts, and SDK report. It omits addresses, ports, PIDs, usernames, process paths, and raw transcripts.

Use `redacted-observation.json` for the review. Keep `scope.etl`, `events.ndjson`, the private collector and run receipts, and `sdk/` on the workstation. A replay classification of `PASS` makes the TCP/UDP observation available to review for that narrow run. It does not release AG-11. An attributed non-loopback transmission is a replay `FAIL`. Incomplete capture, loss, parser ambiguity, missing canary traffic, or missing SDK evidence is `BLOCKED`. Qualification still depends on a real capture, independent semantic review of the provider and process coverage, and evidence linked to the exact candidate, engine, backend, SDK, and run.
