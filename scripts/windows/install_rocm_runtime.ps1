<#
.SYNOPSIS
  Adds the ROCm math libraries that the official ROCm build of llama.cpp needs.

.DESCRIPTION
  The llama.cpp Windows ROCm archive is a complete build, but ggml-hip.dll
  imports hipblas.dll, which is not in the archive. This script supplies the
  math libraries from the same ROCm wheels that the upstream release workflow
  uses.

  The wheels are installed into an isolated virtual environment under
  runtime/llama-cpp/rocm-libs. Nothing is installed system-wide; the start
  script adds the library directories to PATH for the llama-server process only.

  Exit code is 0 when the ROCm build enumerates a ROCm device.

.EXAMPLE
  pwsh -File scripts/windows/install_rocm_runtime.ps1
#>
[CmdletBinding()]
param(
  [switch]$Reinstall,
  [string]$Evidence = "evidence/IJ0/rocm_runtime_install.json"
)

. (Join-Path $PSScriptRoot "common.ps1")
$root = Get-RepoRoot
$engine = Read-JsonFile (Join-Path $root "configs\llama_cpp\engine.json")
$spec = $engine.rocm_runtime
$runtimeDir = Join-Path $root $engine.runtime_dir
$venvDir = Join-Path $root $spec.venv_dir
$server = Get-LlamaServerPath $runtimeDir "rocm"
if (-not (Test-Path $server)) {
  throw "The ROCm build is not installed. Run install_llama_cpp.ps1 first."
}

if ($Reinstall -and (Test-Path $venvDir)) { Remove-Item -Recurse -Force $venvDir }
if (-not (Test-Path (Join-Path $venvDir "Scripts\python.exe"))) {
  $projectPython = Join-Path $root ".venv\Scripts\python.exe"
  $basePython = if (Test-Path $projectPython) { (& $projectPython -c "import sys; print(sys._base_executable)") } else { "py" }
  if ($basePython -eq "py") { & py -3 -m venv $venvDir } else { & $basePython -m venv $venvDir }
}
$venvPython = Join-Path $venvDir "Scripts\python.exe"

Write-Host "installing $($spec.package_spec) from $($spec.index_url)"
$ErrorActionPreference = "Continue"
& $venvPython -m pip install --disable-pip-version-check --progress-bar off --index-url $spec.index_url $spec.package_spec 2>&1 |
  ForEach-Object { Write-Host ([string]$_) }
$installExit = $LASTEXITCODE
$ErrorActionPreference = "Stop"
if ($installExit -ne 0) { throw "pip failed with exit code $installExit" }

$packages = @(((Invoke-Native $venvPython @("-m", "pip", "freeze", "--disable-pip-version-check")).stdout -split "`r?`n") | Where-Object { $_ })
$dirs = Get-RocmLibraryDirectories $runtimeDir
$missing = @()
if (-not $dirs) {
  $missing = @($spec.required_dlls)
}
else {
  foreach ($dll in $spec.required_dlls) {
    $found = (Test-Path (Join-Path $dirs.libraries $dll)) -or (Test-Path (Join-Path $dirs.core $dll))
    if (-not $found) { $missing += $dll }
  }
}

$devicesOutput = ""
$deviceEnumerated = $false
if ($dirs) {
  $originalPath = $env:PATH
  $env:PATH = "$($dirs.libraries);$($dirs.core);$originalPath"
  $devices = Invoke-Native $server @("--list-devices") -TimeoutMs 600000
  $env:PATH = $originalPath
  $devicesOutput = (($devices.stdout, $devices.stderr) -join "`n").Trim()
  $deviceEnumerated = ($devices.exit_code -eq 0) -and ($devicesOutput -match "ROCm\d+:")
}

$status = if ($deviceEnumerated) { "PASS" } elseif ($dirs -and $missing.Count -eq 0) { "FAIL" } else { "BLOCKED" }
$report = [ordered]@{
  schema_version = 1
  installed_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
  installer = "scripts/windows/install_rocm_runtime.ps1"
  package_spec = $spec.package_spec
  index_url = $spec.index_url
  venv_dir = $spec.venv_dir
  packages = $packages
  library_directories = if ($dirs) { @((Get-RepoRelative $root $dirs.libraries), (Get-RepoRelative $root $dirs.core)) } else { @() }
  required_dlls_missing = $missing
  list_devices_output = $devicesOutput
  status = $status
}
Write-JsonFile $report (Join-Path $root $Evidence)
Write-Host "rocm runtime: $status ($Evidence)"
if ($status -ne "PASS") { exit 2 }
exit 0
