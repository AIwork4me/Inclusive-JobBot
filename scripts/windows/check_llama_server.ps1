<#
.SYNOPSIS
  Checks the managed llama-server.

.DESCRIPTION
  Reads .runtime/llama-server/server.json, verifies that the recorded process
  is alive and is the expected binary, then queries /health, /props and
  /v1/models. With -Probe it also sends one real chat completion and reports
  the server's own timings. Output is JSON. Exit code is 0 when healthy.

.EXAMPLE
  pwsh -File scripts/windows/check_llama_server.ps1 -Probe
#>
[CmdletBinding()]
param(
  [switch]$Probe,
  [string]$Prompt = "",
  [int]$MaxTokens = 48
)

. (Join-Path $PSScriptRoot "common.ps1")
$root = Get-RepoRoot
$launch = Read-JsonFile (Join-Path $root "configs\llama_cpp\launch.json")
# Non-ASCII text lives in the UTF-8 JSON config: Windows PowerShell 5.1 reads
# BOM-less script files in the local code page and would corrupt it.
if (-not $Prompt) { $Prompt = $launch.probe_prompt }
$statePath = Join-Path (Join-Path $root $launch.state_dir) "server.json"

if (-not (Test-Path $statePath)) {
  @{ status = "FAIL"; reason = "no managed llama-server is recorded" } | ConvertTo-Json -Compress | Write-Host
  exit 2
}
$state = Read-JsonFile $statePath
$expectedExe = Join-Path $root $state.exe
$process = $null
try { $process = Get-Process -Id $state.pid -ErrorAction Stop } catch { }
$identityOk = [bool]($process -and $process.Path -and $process.Path -eq $expectedExe)

$base = "http://$($state.host):$($state.port)"
$health = $null
$props = $null
$models = $null
$problem = ""
if (-not $identityOk) {
  $problem = "recorded PID $($state.pid) is not the expected llama-server.exe"
}
else {
  try { $health = Invoke-JsonRequest -Uri "$base/health" -TimeoutSec 10 } catch { $problem = "GET /health failed: $($_.Exception.Message)" }
  if ($health.status -eq "ok") {
    try { $props = Invoke-JsonRequest -Uri "$base/props" -TimeoutSec 10 } catch { $problem = "GET /props failed: $($_.Exception.Message)" }
    try { $models = Invoke-JsonRequest -Uri "$base/v1/models" -TimeoutSec 10 } catch { $problem = "GET /v1/models failed: $($_.Exception.Message)" }
  }
}

$probeResult = $null
if ($Probe -and -not $problem) {
  $body = @{
    model = $launch.alias
    messages = @(@{ role = "user"; content = $Prompt })
    max_tokens = $MaxTokens
    stream = $false
  } | ConvertTo-Json -Depth 6
  try {
    $watch = [System.Diagnostics.Stopwatch]::StartNew()
    $reply = Invoke-JsonRequest -Method POST -Uri "$base/v1/chat/completions" -Body $body -TimeoutSec 300
    $watch.Stop()
    $probeResult = [ordered]@{
      status = "PASS"
      wall_clock_ms = [int]$watch.Elapsed.TotalMilliseconds
      content = $reply.choices[0].message.content
      reasoning_content = $reply.choices[0].message.reasoning_content
      finish_reason = $reply.choices[0].finish_reason
      usage = $reply.usage
      timings = $reply.timings
    }
  }
  catch {
    $probeResult = [ordered]@{ status = "FAIL"; error = $_.Exception.Message }
  }
}

$status = if ($problem) { "FAIL" } elseif ($probeResult -and $probeResult.status -ne "PASS") { "FAIL" } else { "PASS" }
$result = [ordered]@{
  status = $status
  reason = $problem
  pid = $state.pid
  process_identity_verified = $identityOk
  base_url = "$base/v1"
  launch = [ordered]@{
    backend = $state.backend
    model = $state.model
    context_length = $state.context_length
    gpu_layers = $state.gpu_layers
    parallel_slots = $state.parallel_slots
    layers_offloaded = $state.layers_offloaded
    layers_total = $state.layers_total
    chat_template_file = $state.chat_template_file
  }
  endpoints = [ordered]@{
    health = $health
    props = $props
    models = $models
  }
  probe = $probeResult
}
Write-JsonFile $result (Join-Path (Join-Path $root $launch.state_dir) "last_check.json")
Write-Host (Protect-Text ($result | ConvertTo-Json -Depth 10))
if ($status -ne "PASS") { exit 2 }
exit 0
