<#
.SYNOPSIS
  Starts the pinned llama-server on the local loopback interface.

.DESCRIPTION
  One server is managed at a time; its process id and launch configuration
  are stored in .runtime/llama-server/server.json. The script waits until
  /health answers, then checks the server log for the number of layers that
  were actually offloaded to the GPU. A GPU backend that offloads nothing is
  reported as FAIL and the server is stopped, so a CPU fallback is never
  silent.

  With -NoWait the script returns as soon as the process is started.

.EXAMPLE
  pwsh -File scripts/windows/start_llama_server.ps1 -Backend vulkan -Model q8 -ContextLength 8192
#>
[CmdletBinding()]
param(
  [ValidateSet("cpu", "vulkan", "rocm")][string]$Backend = "vulkan",
  [ValidateSet("f16", "q8", "q4")][string]$Model = "q8",
  [Nullable[int]]$Port,
  [Nullable[int]]$ContextLength,
  [Nullable[int]]$GpuLayers,
  [Nullable[int]]$Parallel,
  [string]$Device = "",
  [string]$ExtraArgs = "",
  [string]$ChatTemplateFile = "",
  [string]$ReasoningFormat = "",
  [switch]$NoWait
)

. (Join-Path $PSScriptRoot "common.ps1")
$root = Get-RepoRoot
$engine = Read-JsonFile (Join-Path $root "configs\llama_cpp\engine.json")
$launch = Read-JsonFile (Join-Path $root "configs\llama_cpp\launch.json")
$runtimeDir = Join-Path $root $engine.runtime_dir
$server = Get-LlamaServerPath $runtimeDir $Backend
if (-not (Test-Path $server)) { throw "Backend '$Backend' is not installed. Run install_llama_cpp.ps1 first." }

if ($null -eq $Port) { $Port = $launch.port }
if ($null -eq $ContextLength) { $ContextLength = $launch.context_length }
if ($null -eq $GpuLayers) { $GpuLayers = $launch.gpu_layers }
if ($null -eq $Parallel) { $Parallel = $launch.parallel_slots }
if ($Port -lt 1 -or $Port -gt 65535) { throw "Port must be between 1 and 65535." }
if ($ContextLength -lt 1) { throw "ContextLength must be positive." }
if ($Parallel -lt 1) { throw "Parallel must be at least 1." }

$modelFile = Join-Path $root $launch.models.$Model
if (-not (Test-Path $modelFile)) { throw "Model '$Model' is not present at $($launch.models.$Model). Run download_models_modelscope.ps1 first." }

$backendConfig = @($engine.backends | Where-Object { $_.name -eq $Backend })[0]
$usesGpu = [bool]$backendConfig.gpu_libraries_present -and ($GpuLayers -ne 0)

# Only loopback is accepted: the engine is a local resource behind the JobBot API.
$hostAddress = $launch.host
if ($hostAddress -notin @("127.0.0.1", "::1", "localhost")) { throw "Refusing to listen on '$hostAddress'. Only loopback is allowed." }

$stateDir = Join-Path $root $launch.state_dir
$logDir = Join-Path $root $launch.log_dir
New-Item -ItemType Directory -Force -Path $stateDir, $logDir | Out-Null
$statePath = Join-Path $stateDir "server.json"

# Refuse to start when the managed server is still alive.
if (Test-Path $statePath) {
  $previous = Read-JsonFile $statePath
  $alive = $null
  try { $alive = Get-Process -Id $previous.pid -ErrorAction Stop } catch { }
  if ($alive -and $alive.Path -and $alive.Path -eq $server) {
    throw "llama-server is already running (PID $($alive.Id), port $($previous.port)). Run stop_llama_server.ps1 first."
  }
}

$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMdd-HHmmss")
$baseName = "llama-server-$Backend-$Model-$stamp"
$mainLog = Join-Path $logDir "$baseName.log"
$stdoutLog = Join-Path $logDir "$baseName.stdout.log"
$stderrLog = Join-Path $logDir "$baseName.stderr.log"

$argumentList = @(
  "-m", $modelFile,
  "--jinja",
  "-ngl", "$GpuLayers",
  "-c", "$ContextLength",
  "-np", "$Parallel",
  "--host", $hostAddress,
  "--port", "$Port",
  "-a", $launch.alias,
  "--offline",
  "--metrics",
  "--slots",
  "--no-webui",
  # Verbosity 4 is the lowest level that reports layer offload and buffer
  # allocations; it is what the offload check below depends on.
  "-lv", "$([int]$launch.log_verbosity)",
  "--log-file", $mainLog
)
if ($Device) { $argumentList += @("--device", $Device) }
if ($ChatTemplateFile) { $argumentList += @("--chat-template-file", (Join-Path $root $ChatTemplateFile)) }
if ($ReasoningFormat) { $argumentList += @("--reasoning-format", $ReasoningFormat) }
if ($ExtraArgs) { $argumentList += @($ExtraArgs -split ";" | ForEach-Object { $_.Trim() } | Where-Object { $_ }) }

$rocmDirs = Get-RocmLibraryDirectories $runtimeDir
if ($Backend -eq "rocm") {
  if (-not $rocmDirs) { throw "The ROCm backend needs its runtime libraries. Run install_rocm_runtime.ps1 first." }
  # Process-scoped only: this PATH is inherited by llama-server and nothing else.
  $env:PATH = "$($rocmDirs.libraries);$($rocmDirs.core);$env:PATH"
}

# Another server on the same port would answer /health and fake readiness.
$occupant = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($occupant) {
  $occupantName = (Get-Process -Id $occupant.OwningProcess -ErrorAction SilentlyContinue).ProcessName
  throw "Port $Port is already in use by PID $($occupant.OwningProcess) ($occupantName). Stop it first or choose another port."
}

$quoted = $argumentList | ForEach-Object { if ($_ -match "\s") { '"' + $_ + '"' } else { $_ } }
$startedUtc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$process = Start-Process -FilePath $server -ArgumentList $quoted -WorkingDirectory (Split-Path $server) `
  -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog -WindowStyle Hidden -PassThru

$state = [ordered]@{
  pid = $process.Id
  exe = (Get-RepoRelative $root $server)
  started_utc = $startedUtc
  host = $hostAddress
  port = $Port
  backend = $Backend
  model = $Model
  model_file = $launch.models.$Model
  context_length = $ContextLength
  gpu_layers = $GpuLayers
  parallel_slots = $Parallel
  device = $Device
  chat_template_file = $ChatTemplateFile
  reasoning_format = $ReasoningFormat
  arguments = $argumentList
  logs = [ordered]@{ main = (Get-RepoRelative $root $mainLog); stdout = (Get-RepoRelative $root $stdoutLog); stderr = (Get-RepoRelative $root $stderrLog) }
}
Write-JsonFile $state $statePath

function Test-OwnsPort {
  $listeners = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
  return ($listeners.Count -gt 0) -and (@($listeners | Where-Object { $_.OwningProcess -ne $process.Id }).Count -eq 0)
}

function Get-LogTail([int]$Count = 30) {
  $text = ""
  foreach ($file in @($stderrLog, $stdoutLog, $mainLog)) {
    if (Test-Path $file) { $text += ((Get-Content $file -Tail $Count -ErrorAction SilentlyContinue) -join "`n") + "`n" }
  }
  return (Protect-Text $text).Trim()
}

if ($NoWait) {
  $state | ConvertTo-Json -Depth 6 -Compress | Write-Host
  exit 0
}

$base = "http://${hostAddress}:$Port"
$timeout = [int]$launch.startup_timeout_seconds
$ready = $false
$timer = [System.Diagnostics.Stopwatch]::StartNew()
while ($timer.Elapsed.TotalSeconds -lt $timeout) {
  if ($process.HasExited) { break }
  # Accept readiness only from the process started here.
  if (Test-OwnsPort) {
    try {
      $response = Invoke-WebRequest -UseBasicParsing -Uri "$base/health" -TimeoutSec 5
      if ($response.StatusCode -eq 200) { $ready = $true; break }
    }
    catch { }
  }
  Start-Sleep -Seconds 2
}

$failure = ""
if (-not $ready) {
  $failure = if ($process.HasExited) { "llama-server exited with code $($process.ExitCode) before /health answered" } else { "llama-server did not answer /health within $timeout seconds" }
}

# Verify GPU offload from the server's own log instead of trusting the request.
$offloaded = $null
$total = $null
$offloadLine = ""
$allocationLines = @()
if ($ready -and (Test-Path $stderrLog)) {
  $match = Select-String -Path $stderrLog -Pattern "offloaded (\d+)/(\d+) layers to GPU" | Select-Object -First 1
  if ($match) {
    $offloaded = [int]$match.Matches[0].Groups[1].Value
    $total = [int]$match.Matches[0].Groups[2].Value
    $offloadLine = $match.Line.Trim()
  }
  $allocationLines = @(Select-String -Path $stderrLog -Pattern "model buffer size|KV buffer size|compute buffer size|output buffer size|using device|flash_attn" |
    ForEach-Object { ($_.Line -replace "\s+", " ").Trim() })
}
if ($ready -and $usesGpu) {
  if ($null -eq $offloaded) { $failure = "GPU backend requested but the log has no offload report; refusing to assume GPU execution." }
  elseif ($offloaded -eq 0) { $failure = "GPU backend requested but 0 of $total layers were offloaded: this would be a silent CPU fallback." }
}

$state.ready = $ready
$state.startup_seconds = if ($ready) { [math]::Round($timer.Elapsed.TotalSeconds, 2) } else { $null }
$state.owns_port = if ($ready) { Test-OwnsPort } else { $false }
$state.layers_offloaded = $offloaded
$state.layers_total = $total
$state.offload_log_line = $offloadLine
$state.allocation_log_lines = $allocationLines
$state.status = if ($failure) { "FAIL" } else { "PASS" }
$state.failure = $failure
Write-JsonFile $state $statePath

if ($failure) {
  Write-Host "FAIL: $failure"
  Write-Host (Get-LogTail)
  if (-not $process.HasExited) {
    Stop-Process -Id $process.Id -Force
    $process.WaitForExit(15000) | Out-Null
  }
  Remove-Item $statePath -Force
  exit 2
}

Write-Host "PASS: llama-server PID $($process.Id) on $base ($Backend, $Model, ctx $ContextLength, $offloadLine)"
Write-Host "logs: $($state.logs.main)"
exit 0
