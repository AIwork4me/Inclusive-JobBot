<#
.SYNOPSIS
  IJ-SDK-1.0 P1: frozen backend qualification protocol on gfx1100.

.DESCRIPTION
  Runs, per backend arm, the same representative workload on the pinned
  b12359 engine and one MiniCPM5-2B quantization:

    1. managed server start (offload evidence per decision D-010),
    2. GPU counter sampler bound to the server process (GPU arms),
    3. server probe (first real inference),
    4. the 9-check API surface check (streaming/non-streaming parity),
    5. the native tool-calling smoke suite (single call, streamed call,
       tool-result continuation, tool_choice none/required),
    6. managed stop.

  One backend at a time; backends never share a qualification cell. A GPU
  arm passes only with the full D-010 proof: the server's own offload line
  (N > 0 layers) AND sampled counter rows showing engine activity for the
  server process. CPU is the reference arm.

  Exit code 0 = all arms PASS, 2 = at least one arm failed or was blocked.

.EXAMPLE
  pwsh -File scripts/windows/ij_sdk_p1_backend_qualify.ps1 -Backends cpu,vulkan,rocm
#>
[CmdletBinding()]
param(
  [string[]]$Backends = @("cpu", "vulkan", "rocm"),
  [ValidateSet("q8", "q4", "f16")][string]$Model = "q8",
  [string]$Evidence = "evidence/IJSDK/P1/backend_qualification.json",
  [string]$WorkDir = ".runtime/ijsdk_p1"
)

$ErrorActionPreference = "Continue"
# Native callers pass one comma-joined string for a string[] parameter
# (PowerShell -File binding); normalize both shapes here.
$Backends = @($Backends | ForEach-Object { $_ -split "," } | Where-Object { $_ -and $_.Trim() } | ForEach-Object { $_.Trim() })
. (Join-Path $PSScriptRoot "common.ps1")
$root = Get-RepoRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "Project .venv is missing. Run bootstrap.ps1 first." }

$workDir = Join-Path $root $WorkDir
New-Item -ItemType Directory -Force -Path $workDir | Out-Null
$manifest = Read-JsonFile (Join-Path $root "models\model_manifest.json")
$ggufModel = $manifest.models | Where-Object { $_.role -eq "gguf-inference" } | Select-Object -First 1
$ggufFile = $ggufModel.files | Where-Object { $_.path -like "*$($Model.ToUpper())*" } | Select-Object -First 1
if (-not $ggufFile) { throw "Model $Model not found in the manifest." }

$arms = @()
foreach ($backend in $Backends) {
  $arm = [ordered]@{
    backend = $backend
    model_alias = $Model
    model_path = ($ggufModel.local_dir + "/" + $ggufFile.path)
    model_sha256 = $ggufFile.sha256
    started_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
  }

  # 1. Managed start with offload proof (start_llama_server refuses a silent
  #    CPU fallback and stops the server itself on failure).
  Write-Host "[start-$backend] $(Get-Date -Format 'HH:mm:ss')"
  $startLog = Join-Path $workDir "start_$backend.log"
  $startOut = & powershell -NoProfile -ExecutionPolicy RemoteSigned -File (Join-Path $PSScriptRoot "start_llama_server.ps1") `
    -Backend $backend -Model $Model -ContextLength 8192 2>&1 | Out-String
  [IO.File]::WriteAllText($startLog, $startOut, (New-Object Text.UTF8Encoding $false))
  Write-Host $startOut.TrimEnd()

  $statePath = Join-Path $root ".runtime\llama-server\server.json"
  if ($LASTEXITCODE -ne 0 -or -not (Test-Path $statePath)) {
    $arm.status = "BLOCKED"
    $arm.reason = "managed server start failed; see $WorkDir/start_$backend.log"
    $arm.finished_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    $arms += $arm
    continue
  }
  $serverState = Read-JsonFile $statePath
  $arm.server = [ordered]@{
    port = $serverState.port
    backend_reported = $serverState.backend
    layers_offloaded = $serverState.layers_offloaded
    layers_total = $serverState.layers_total
    offload_log_line = $serverState.offload_log_line
    startup_seconds = $serverState.startup_seconds
    allocation_log_lines = $serverState.allocation_log_lines
    server_log = $serverState.logs.main
  }

  # 2. GPU counter sampler bound to the real server PID (GPU arms).
  $counterPath = $null
  $stopFile = $null
  if ($backend -ne "cpu") {
    $counterPath = Join-Path $workDir "counters_$backend.jsonl"
    $stopFile = Join-Path $workDir "stop-sampler-$backend"
    if (Test-Path $stopFile) { Remove-Item $stopFile -Force }
    $samplerLog = Join-Path $workDir "sampler_$backend.log"
    Start-Process powershell -ArgumentList @(
      "-NoProfile", "-ExecutionPolicy", "RemoteSigned", "-File",
      (Join-Path $PSScriptRoot "sample_gpu_counters.ps1"),
      "-TargetProcessId", "$($serverState.pid)",
      "-OutputPath", $counterPath, "-StopFile", $stopFile, "-MaxSeconds", "900"
    ) -RedirectStandardOutput $samplerLog -RedirectStandardError "$samplerLog.err" -WindowStyle Hidden | Out-Null
    $ready = "$stopFile.ready"
    $deadline = (Get-Date).AddSeconds(120)
    while (-not (Test-Path $ready) -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 500 }
    $arm.counter_sampler_ready = (Test-Path $ready)
  }

  # 3. Probe (first real inference).
  Write-Host "[probe-$backend] $(Get-Date -Format 'HH:mm:ss')"
  & powershell -NoProfile -ExecutionPolicy RemoteSigned -File (Join-Path $PSScriptRoot "check_llama_server.ps1") -Probe 2>&1 |
    Out-File (Join-Path $workDir "probe_$backend.log") -Encoding utf8
  $arm.probe_exit = $LASTEXITCODE

  # 4. API surface check.
  Write-Host "[api-$backend] $(Get-Date -Format 'HH:mm:ss')"
  & $python -I (Join-Path $root "scripts\tools\llama_server_api_check.py") `
    --base-url "http://127.0.0.1:$($serverState.port)" `
    --output (Join-Path $workDir "api_check_$backend.json") | Out-Host
  $arm.api_check_exit = $LASTEXITCODE
  $arm.api_check_evidence = "$WorkDir/api_check_$backend.json"

  # 5. Native tool-calling smoke suite.
  Write-Host "[smoke-$backend] $(Get-Date -Format 'HH:mm:ss')"
  & $python -I (Join-Path $root "scripts\tools\tool_calling_smoke.py") `
    --base-url "http://127.0.0.1:$($serverState.port)" `
    --output (Join-Path $workDir "tool_smoke_$backend.json") | Out-Host
  $arm.tool_smoke_exit = $LASTEXITCODE
  $arm.tool_smoke_evidence = "$WorkDir/tool_smoke_$backend.json"

  # 6. Close the sampler, then the managed stop.
  if ($stopFile) { New-Item -ItemType File -Force -Path $stopFile | Out-Null }
  Write-Host "[stop-$backend] $(Get-Date -Format 'HH:mm:ss')"
  & powershell -NoProfile -ExecutionPolicy RemoteSigned -File (Join-Path $PSScriptRoot "stop_llama_server.ps1") 2>&1 | Out-Host

  # GPU proof aggregation (D-010 second condition).
  if ($counterPath -and (Test-Path $counterPath)) {
    $rows = Get-Content $counterPath | ForEach-Object { $_ | ConvertFrom-Json }
    $engineRows = @($rows | Where-Object { $_.kind -eq "gpu_engine" -and $_.utilization -gt 0 })
    $memRows = @($rows | Where-Object { $_.kind -eq "gpu_process_memory" })
    $arm.gpu_counters = [ordered]@{
      rows = $rows.Count
      nonzero_engine_rows = $engineRows.Count
      max_utilization = if ($engineRows.Count) { ($engineRows | Measure-Object utilization -Maximum).Maximum } else { 0 }
      engine_types = @($engineRows | ForEach-Object { $_.engine_type } | Sort-Object -Unique)
      max_dedicated_memory_bytes = if ($memRows.Count) { ($memRows | Measure-Object dedicated_bytes -Maximum).Maximum } else { $null }
      evidence = "$WorkDir/counters_$backend.jsonl"
    }
  }

  $arm.finished_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
  $arm.status = "PASS"
  $arm.reason = ""
  if ($arm.probe_exit -ne 0) { $arm.status = "FAIL"; $arm.reason = "probe failed" }
  elseif ($arm.api_check_exit -ne 0) { $arm.status = "FAIL"; $arm.reason = "API surface check failed" }
  elseif ($arm.tool_smoke_exit -ne 0) { $arm.status = "FAIL"; $arm.reason = "tool-calling smoke failed" }
  if ($backend -ne "cpu") {
    if (-not $serverState.layers_offloaded -or $serverState.layers_offloaded -le 0) {
      $arm.status = "FAIL"; $arm.reason = "no GPU offload evidence (D-010)"
    }
    elseif (-not $arm.gpu_counters -or $arm.gpu_counters.nonzero_engine_rows -eq 0) {
      $arm.status = "FAIL"; $arm.reason = "no GPU engine activity observed (D-010)"
    }
  }
  $arms += $arm
}

$overall = "PASS"
foreach ($a in $arms) { if ($a.status -ne "PASS") { $overall = "FAIL" } }

$evidence = [ordered]@{
  schema_version = 1
  protocol = "IJ-SDK-1.0 P1 backend qualification (frozen 2026-11-27)"
  mission = "IJ-SDK-1.0"
  generated_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
  engine = [ordered]@{
    build = "b12359"
    release = "v1.0.0"
    commit = "b1b770d90d94cad9e9ea5b993bdbc383a522fb28"
    exe_sha256 = "38c5affb81c9a8f88f5538c7d11bc445e13bc46a2c6eda05694b8b31a8d45995"
  }
  gpu = [ordered]@{
    architecture = "gfx1100"
    device = "AMD Radeon RX 7900 XTX"
    device_id = "0x744c"
    driver = "32.0.21030.2001"
  }
  rule = "Backend results never mix within one experimental cell; CPU is the reference arm; GPU arms require D-010 proof (offload line + counter engine activity)."
  arms = $arms
  overall_status = $overall
}
$json = $evidence | ConvertTo-Json -Depth 10
$outPath = Join-Path $root $Evidence
[IO.File]::WriteAllText($outPath, $json + "`n", (New-Object Text.UTF8Encoding $false))
Write-Host "wrote $Evidence (overall: $overall)"
if ($overall -ne "PASS") { exit 2 }
