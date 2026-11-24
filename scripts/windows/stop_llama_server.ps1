<#
.SYNOPSIS
  Stops the llama-server that start_llama_server.ps1 launched.

.DESCRIPTION
  Reads the recorded process id and verifies that the process still is the
  expected llama-server.exe before touching it, so a recycled pid can never
  stop an unrelated program. A graceful request is attempted first; the
  process is terminated only if it ignores it.

.EXAMPLE
  pwsh -File scripts/windows/stop_llama_server.ps1
#>
[CmdletBinding()]
param()

. (Join-Path $PSScriptRoot "common.ps1")
$root = Get-RepoRoot
$launch = Read-JsonFile (Join-Path $root "configs\llama_cpp\launch.json")
$statePath = Join-Path (Join-Path $root $launch.state_dir) "server.json"

if (-not (Test-Path $statePath)) {
  Write-Host "no managed llama-server is recorded; nothing to stop"
  exit 0
}
$state = Read-JsonFile $statePath
$expectedExe = Join-Path $root $state.exe
$process = $null
try { $process = Get-Process -Id $state.pid -ErrorAction Stop } catch { }

if (-not $process) {
  Write-Host "recorded PID $($state.pid) is not running; removing the stale state file"
  Remove-Item $statePath -Force
  exit 0
}
if (-not $process.Path -or $process.Path -ne $expectedExe) {
  Write-Host "PID $($state.pid) now belongs to another program; leaving it alone and removing the stale state file"
  Remove-Item $statePath -Force
  exit 0
}

& taskkill.exe /PID $process.Id 2>&1 | Out-Null
if (-not $process.WaitForExit(15000)) {
  Stop-Process -Id $process.Id -Force
  $process.WaitForExit(15000) | Out-Null
}
Remove-Item $statePath -Force
Write-Host "stopped llama-server PID $($state.pid) ($($state.backend), port $($state.port))"
exit 0
