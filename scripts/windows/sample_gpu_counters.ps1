<#
.SYNOPSIS
  Samples Windows GPU and process performance counters for one process.

.DESCRIPTION
  Writes one JSON object per line to -OutputPath roughly twice per second
  until -StopFile exists or -MaxSeconds elapse. Counter classes are read
  through CIM, so the script works on any Windows display language.

  The first CIM query pays a one-time WMI start-up cost. The script performs
  that warm-up first and creates "<StopFile>.ready" only afterwards, so a
  runner can start its workload knowing sampling is already live.

  Rows:
    gpu_engine          utilization of each GPU engine the process uses; the
                        engine type is the first word of engtype (3D, Compute,
                        Copy, ...). Vulkan work usually appears under 3D and
                        ROCm/HIP work under Compute.
    gpu_process_memory  dedicated and shared GPU memory of the process
    gpu_adapter_memory  dedicated and shared GPU memory of an adapter, for
                        every adapter; match by the luid in the instance name
    process             CPU time (100 = one logical processor), private
                        working set, private bytes and thread count

.EXAMPLE
  pwsh -File scripts/windows/sample_gpu_counters.ps1 -TargetProcessId 1234 `
    -OutputPath evidence/IJ0/gpu/arm_C/counters.jsonl -StopFile .runtime/stop-sampler
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)][int]$TargetProcessId,
  [Parameter(Mandatory = $true)][string]$OutputPath,
  [Parameter(Mandatory = $true)][string]$StopFile,
  [int]$MaxSeconds = 7200,
  [int]$SampleIntervalMs = 250
)

. (Join-Path $PSScriptRoot "common.ps1")
$output = Resolve-FullPath $OutputPath
$stop = Resolve-FullPath $StopFile
$ready = "$stop.ready"
foreach ($stale in @($stop, $ready)) { if (Test-Path $stale) { Remove-Item $stale -Force } }
$parent = Split-Path $output
if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
$pidPattern = "pid_${TargetProcessId}_*"
$logicalProcessors = [Environment]::ProcessorCount

$engineClass = "Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine"
$processMemoryClass = "Win32_PerfFormattedData_GPUPerformanceCounters_GPUProcessMemory"
$adapterMemoryClass = "Win32_PerfFormattedData_GPUPerformanceCounters_GPUAdapterMemory"
$processClass = "Win32_PerfFormattedData_PerfProc_Process"

# Warm up every perf provider before the measured period starts.
foreach ($class in @($engineClass, $processMemoryClass, $adapterMemoryClass)) { $null = Get-CimInstance $class -ErrorAction SilentlyContinue }
$null = Get-CimInstance $processClass -Filter "IDProcess=$TargetProcessId" -ErrorAction SilentlyContinue

$writer = New-Object System.IO.StreamWriter -ArgumentList $output, $false, (New-Object Text.UTF8Encoding $false)
$timer = [System.Diagnostics.Stopwatch]::StartNew()
[IO.File]::WriteAllText($ready, "ready`n")
try {
  while (-not (Test-Path $stop) -and $timer.Elapsed.TotalSeconds -lt $MaxSeconds) {
    $sampleStarted = $timer.Elapsed.TotalSeconds
    $stamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
    $rows = New-Object System.Collections.ArrayList
    try {
      foreach ($engine in @(Get-CimInstance $engineClass -ErrorAction Stop | Where-Object { $_.Name -like $pidPattern })) {
        $type = if ($engine.Name -match "engtype_([A-Za-z0-9]+)") { $Matches[1] } else { "unknown" }
        # PowerShell 5.1 returns $null for a property that does not exist, which
        # would silently record a fake 0 percent. Require the real property.
        if ($engine.CimInstanceProperties.Name -notcontains "UtilizationPercentage") {
          throw "Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine has no UtilizationPercentage property"
        }
        [void]$rows.Add([ordered]@{ t = $stamp; elapsed_s = $sampleStarted; kind = "gpu_engine"; instance = $engine.Name; engtype = $type; utilization = [double]$engine.UtilizationPercentage })
      }
      foreach ($memory in @(Get-CimInstance $processMemoryClass -ErrorAction Stop | Where-Object { $_.Name -like $pidPattern })) {
        [void]$rows.Add([ordered]@{ t = $stamp; elapsed_s = $sampleStarted; kind = "gpu_process_memory"; instance = $memory.Name; dedicated_bytes = [long]$memory.DedicatedUsage; shared_bytes = [long]$memory.SharedUsage; committed_bytes = [long]$memory.TotalCommitted })
      }
      foreach ($adapter in @(Get-CimInstance $adapterMemoryClass -ErrorAction Stop)) {
        [void]$rows.Add([ordered]@{ t = $stamp; elapsed_s = $sampleStarted; kind = "gpu_adapter_memory"; instance = $adapter.Name; dedicated_bytes = [long]$adapter.DedicatedUsage; shared_bytes = [long]$adapter.SharedUsage; committed_bytes = [long]$adapter.TotalCommitted })
      }
      foreach ($process in @(Get-CimInstance $processClass -Filter "IDProcess=$TargetProcessId" -ErrorAction Stop)) {
        [void]$rows.Add([ordered]@{ t = $stamp; elapsed_s = $sampleStarted; kind = "process"; cpu_percent_of_one_core = [double]$process.PercentProcessorTime; logical_processors = $logicalProcessors; working_set_private_bytes = [long]$process.WorkingSetPrivate; private_bytes = [long]$process.PrivateBytes; threads = [int]$process.ThreadCount })
      }
      if ($rows.Count -eq 0) { [void]$rows.Add([ordered]@{ t = $stamp; elapsed_s = $sampleStarted; kind = "no_data" }) }
    }
    catch {
      [void]$rows.Add([ordered]@{ t = $stamp; elapsed_s = $sampleStarted; kind = "sample_error"; message = Protect-Text $_.Exception.Message })
    }
    foreach ($row in $rows) { $writer.WriteLine(($row | ConvertTo-Json -Compress)) }
    $writer.Flush()
    $remaining = $SampleIntervalMs - [int](($timer.Elapsed.TotalSeconds - $sampleStarted) * 1000)
    if ($remaining -gt 0) { Start-Sleep -Milliseconds $remaining }
  }
}
finally {
  $writer.Dispose()
}
