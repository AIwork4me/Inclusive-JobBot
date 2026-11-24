<#
.SYNOPSIS
  Installs the pinned official llama.cpp Windows builds: CPU, Vulkan and ROCm.

.DESCRIPTION
  Reads the pinned identity from configs/llama_cpp/engine.json, downloads the
  three release archives (reusing files that already match the digest),
  extracts one directory per backend under runtime/llama-cpp and verifies that
  each llama-server.exe starts and enumerates the expected devices.

  The ROCm archive is a complete build but ships without hipBLAS, rocBLAS
  and hipBLASLt. Run install_rocm_runtime.ps1 to add them from the ROCm wheels.

  The result is written to evidence/IJ0/engine_install.json. Exit code is 0
  when every backend passes, 2 otherwise.

.EXAMPLE
  pwsh -File scripts/windows/install_llama_cpp.ps1
#>
[CmdletBinding()]
param(
  [string]$PythonExe = ".venv\Scripts\python.exe",
  [switch]$SkipDownload,
  [string]$Evidence = "evidence/IJ0/engine_install.json"
)

. (Join-Path $PSScriptRoot "common.ps1")
$root = Get-RepoRoot
$engine = Read-JsonFile (Join-Path $root "configs\llama_cpp\engine.json")
$python = Join-Path $root $PythonExe
if (-not (Test-Path $python)) {
  throw "Python not found at $PythonExe. Create the project environment first (python -m venv .venv)."
}
$fetcher = Join-Path $root "scripts\tools\parallel_fetch.py"
$downloadDir = Join-Path $root $engine.download_dir
$runtimeDir = Join-Path $root $engine.runtime_dir
New-Item -ItemType Directory -Force -Path $downloadDir, $runtimeDir | Out-Null
Add-Type -AssemblyName System.IO.Compression.FileSystem

# 1. Download and verify every archive against its published digest.
if (-not $SkipDownload) {
  foreach ($asset in $engine.assets) {
    Write-Host "fetching $($asset.file)"
    $run = Invoke-Native $python @("-I", $fetcher, "$($engine.download_base_url)/$($asset.file)", (Join-Path $downloadDir $asset.file), "--sha256", $asset.sha256) -TimeoutMs 3600000
    if ($run.exit_code -ne 0) {
      throw "download or digest verification failed for $($asset.file): $($run.stderr)"
    }
  }
}
$verifiedArchives = @()
foreach ($asset in $engine.assets) {
  $path = Join-Path $downloadDir $asset.file
  if (-not (Test-Path $path)) { throw "missing archive $($asset.file). Run without -SkipDownload." }
  $hash = (Get-FileHash $path -Algorithm SHA256).Hash.ToLower()
  $size = (Get-Item $path).Length
  $ok = ($hash -eq $asset.sha256) -and ($size -eq $asset.size)
  if (-not $ok) { throw "archive $($asset.file) does not match the pinned digest or size" }
  $verifiedArchives += [ordered]@{ file = $asset.file; size = $size; sha256 = $hash; digest_source = $asset.sha256_source; verified = $ok }
}

# 2. Never replace a backend that a running server is executing from.
$running = @(Get-Process -Name "llama-server" -ErrorAction SilentlyContinue | Where-Object { $_.Path -and $_.Path.StartsWith($runtimeDir, [StringComparison]::OrdinalIgnoreCase) })
if ($running.Count -gt 0) {
  throw "llama-server is running from $($engine.runtime_dir) (PID $($running[0].Id)). Run stop_llama_server.ps1 first."
}

# 3. Extract one directory per backend.
foreach ($backend in $engine.backends) {
  if ($backend.name -notmatch "^[a-z0-9_-]+$") { throw "unsafe backend name '$($backend.name)'" }
  $target = Join-Path $runtimeDir $backend.name
  if (Test-Path $target) { Remove-Item -Recurse -Force $target }
  New-Item -ItemType Directory -Force -Path $target | Out-Null
  foreach ($archive in $backend.archives) {
    Expand-ArchiveTo (Join-Path $downloadDir $archive) $target
  }
  Write-Host "extracted $($backend.name) <- $(($backend.archives) -join ', ')"
}

# 4. Start each binary and enumerate devices.
$rocmDirs = Get-RocmLibraryDirectories $runtimeDir
$originalPath = $env:PATH
$records = @()
foreach ($backend in $engine.backends) {
  $server = Get-LlamaServerPath $runtimeDir $backend.name
  $rocmOnPath = $false
  $env:PATH = $originalPath
  if ($backend.requires_rocm_runtime -and $rocmDirs) {
    $env:PATH = "$($rocmDirs.libraries);$($rocmDirs.core);$originalPath"
    $rocmOnPath = $true
  }
  $version = Invoke-Native $server @("--version")
  $devices = Invoke-Native $server @("--list-devices")
  $env:PATH = $originalPath
  $banner = (($version.stdout, $version.stderr) -join "`n").Trim()
  $output = (($devices.stdout, $devices.stderr) -join "`n").Trim()

  $status = "FAIL"
  $reason = ""
  if ($version.exit_code -ne 0) {
    $status = "BLOCKED"
    $reason = "llama-server.exe did not start. Authenticode status: $((Get-AuthenticodeSignature $server).Status). Smart App Control: $(Get-SmartAppControlState). See BLOCKERS.md B-001."
  }
  elseif (-not $backend.gpu_libraries_present) {
    $status = if ($version.exit_code -eq 0) { "PASS" } else { "FAIL" }
  }
  else {
    $expected = if ($backend.name -eq "vulkan") { "Vulkan\d+:" } else { "ROCm\d+:" }
    if ($output -match $expected) {
      $status = "PASS"
    }
    elseif ($backend.requires_rocm_runtime -and -not $rocmDirs) {
      $status = "BLOCKED"
      $reason = "ROCm runtime libraries are not installed. Run install_rocm_runtime.ps1."
    }
    else {
      $reason = "no $($backend.name) device was enumerated"
    }
  }

  $records += [ordered]@{
    backend = $backend.name
    directory = "$($engine.runtime_dir)/$($backend.name)"
    archives = @($backend.archives)
    exe_sha256 = (Get-FileHash $server -Algorithm SHA256).Hash.ToLower()
    authenticode = [string](Get-AuthenticodeSignature $server).Status
    version_banner = $banner
    version_exit_code = $version.exit_code
    list_devices_exit_code = $devices.exit_code
    list_devices_output = $output
    rocm_runtime_on_path = $rocmOnPath
    status = $status
    reason = $reason
  }
  Write-Host "$($backend.name): $status $reason"
}

$rocmPackages = @()
$rocmPython = Join-Path $runtimeDir "rocm-libs\Scripts\python.exe"
if (Test-Path $rocmPython) {
  $rocmPackages = @(((Invoke-Native $rocmPython @("-m", "pip", "freeze", "--disable-pip-version-check")).stdout -split "`r?`n") | Where-Object { $_ })
}

$failed = @($records | Where-Object { $_.status -ne "PASS" })
$report = [ordered]@{
  schema_version = 1
  installed_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
  installer = "scripts/windows/install_llama_cpp.ps1"
  repository = $engine.repository
  license = $engine.license
  stable_release_tag = $engine.stable_release_tag
  stable_release_commit = $engine.stable_release_commit
  build_tag = $engine.build_tag
  build_commit = $engine.build_commit
  download_base_url = $engine.download_base_url
  archives = $verifiedArchives
  build_flags = $engine.build_flags
  smart_app_control = Get-SmartAppControlState
  rocm_runtime = [ordered]@{
    present = [bool]$rocmDirs
    package_spec = $engine.rocm_runtime.package_spec
    packages = $rocmPackages
    library_directories = if ($rocmDirs) { @((Get-RepoRelative $root $rocmDirs.libraries), (Get-RepoRelative $root $rocmDirs.core)) } else { @() }
  }
  backends = $records
  overall_status = if ($failed.Count -eq 0) { "PASS" } else { "FAIL" }
}
Write-JsonFile $report (Join-Path $root $Evidence)
Write-Host "overall: $($report.overall_status) ($Evidence)"
if ($failed.Count -gt 0) { exit 2 }
exit 0
