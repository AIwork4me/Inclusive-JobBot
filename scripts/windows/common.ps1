# Shared helpers for scripts/windows/*.ps1. Windows PowerShell 5.1 compatible.

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.IO.Compression.FileSystem

function Get-RepoRoot {
  return (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}

function Protect-Text([string]$Text) {
  if (-not $Text) { return $Text }
  $result = $Text
  # Redact by pattern, not by bare token: an account name can coincide with
  # a vendor name that must stay exact in hardware evidence (for example "AMD").
  $user = [regex]::Escape($env:USERNAME)
  $hostName = [regex]::Escape($env:COMPUTERNAME)
  $domain = [regex]::Escape($env:USERDOMAIN)
  $boundary = "(?i)(?<![A-Za-z0-9_.-])"
  if ($env:USERNAME) {
    $result = $result -replace ("(?i)Users[\\/]+" + $user + "(?=[\\/`"'\s]|$)"), "Users/<REDACTED>"
    $principals = @($domain, $hostName) | Where-Object { $_ } | Select-Object -Unique
    $result = $result -replace ($boundary + "(?:" + ($principals -join "|") + ")\\" + $user + "(?![A-Za-z0-9_.-])"), "<REDACTED>"
  }
  if ($env:COMPUTERNAME) {
    $result = $result -replace ($boundary + $hostName + "(?![A-Za-z0-9_.-])"), "<HOST>"
  }
  if ($env:USERDOMAIN -and $env:USERDOMAIN -ne $env:COMPUTERNAME) {
    $result = $result -replace ($boundary + $domain + "(?![A-Za-z0-9_.-])"), "<DOMAIN>"
  }
  return $result
}

# .NET's notion of the current directory can differ from the PowerShell
# location, so relative paths are anchored to (Get-Location) explicitly.
function Resolve-FullPath([string]$Path) {
  if ([System.IO.Path]::IsPathRooted($Path)) { return [System.IO.Path]::GetFullPath($Path) }
  return [System.IO.Path]::GetFullPath((Join-Path (Get-Location).Path $Path))
}

function Write-JsonFile($Object, [string]$Path) {
  $full = Resolve-FullPath $Path
  $directory = Split-Path $full
  if (-not (Test-Path $directory)) { New-Item -ItemType Directory -Force -Path $directory | Out-Null }
  [IO.File]::WriteAllText($full, (Protect-Text ($Object | ConvertTo-Json -Depth 12)) + "`n", (New-Object Text.UTF8Encoding $false))
}

function Read-JsonFile([string]$Path) {
  return (Get-Content -Raw -Encoding UTF8 $Path) | ConvertFrom-Json
}

# Calls a JSON HTTP endpoint and decodes the body as UTF-8 explicitly, because
# Windows PowerShell 5.1 otherwise decodes JSON without a charset as Latin-1
# and corrupts non-ASCII text such as Chinese model output.
function Invoke-JsonRequest {
  param(
    [ValidateSet("GET", "POST")][string]$Method = "GET",
    [Parameter(Mandatory = $true)][string]$Uri,
    [string]$Body,
    [int]$TimeoutSec = 30
  )
  $request = @{ UseBasicParsing = $true; Uri = $Uri; Method = $Method; TimeoutSec = $TimeoutSec }
  # An unbound [string] parameter is an empty string, not $null, so test whether
  # the caller supplied a body; a GET with a body is rejected by Invoke-WebRequest.
  if ($PSBoundParameters.ContainsKey("Body")) {
    $request.ContentType = "application/json; charset=utf-8"
    $request.Body = [Text.Encoding]::UTF8.GetBytes($Body)
  }
  $response = Invoke-WebRequest @request
  return ([Text.Encoding]::UTF8.GetString($response.RawContentStream.ToArray()) | ConvertFrom-Json)
}

# Runs a native executable and captures stdout and stderr without letting
# PowerShell turn stderr lines into terminating errors.
function Invoke-Native {
  param(
    [Parameter(Mandatory = $true)][string]$Exe,
    [string[]]$NativeArgs = @(),
    [int]$TimeoutMs = 180000,
    [string]$WorkingDirectory = ""
  )
  if (-not (Test-Path $Exe)) { return [pscustomobject]@{ exit_code = $null; stdout = ""; stderr = "" } }
  $start = New-Object System.Diagnostics.ProcessStartInfo
  $start.FileName = $Exe
  $start.Arguments = ($NativeArgs | ForEach-Object { if ($_ -match "\s") { '"' + $_ + '"' } else { $_ } }) -join " "
  if ($WorkingDirectory) { $start.WorkingDirectory = $WorkingDirectory } else { $start.WorkingDirectory = Split-Path $Exe }
  $start.UseShellExecute = $false
  $start.RedirectStandardOutput = $true
  $start.RedirectStandardError = $true
  $start.CreateNoWindow = $true
  $process = [System.Diagnostics.Process]::Start($start)
  $stdout = $process.StandardOutput.ReadToEndAsync()
  $stderr = $process.StandardError.ReadToEndAsync()
  if (-not $process.WaitForExit($TimeoutMs)) { try { $process.Kill() } catch { } }
  return [pscustomobject]@{
    exit_code = $process.ExitCode
    stdout = $stdout.Result.Trim()
    stderr = $stderr.Result.Trim()
  }
}

function Get-SmartAppControlState {
  try { return [string](Get-MpComputerStatus -ErrorAction Stop).SmartAppControlState } catch { return "unknown" }
}

function Get-LlamaServerPath([string]$RuntimeRoot, [string]$Backend) {
  return Join-Path (Join-Path $RuntimeRoot $Backend) "llama-server.exe"
}

# The official ROCm zip is a complete build, but it has no hipBLAS, rocBLAS
# or hipBLASLt. Those come from the ROCm wheels installed by
# install_rocm_runtime.ps1 and are added to PATH for the server process only.
function Get-RocmLibraryDirectories([string]$RuntimeRoot) {
  $root = Join-Path $RuntimeRoot "rocm-libs\Lib\site-packages"
  if (-not (Test-Path $root)) { return $null }
  $hipblas = Get-ChildItem -Path $root -Recurse -Filter "hipblas.dll" -ErrorAction SilentlyContinue | Select-Object -First 1
  $hip = Get-ChildItem -Path $root -Recurse -Filter "amdhip64_7.dll" -ErrorAction SilentlyContinue | Select-Object -First 1
  if (-not $hipblas -or -not $hip) { return $null }
  return [pscustomobject]@{ libraries = $hipblas.DirectoryName; core = $hip.DirectoryName }
}

function Get-RepoRelative([string]$Root, [string]$Path) {
  return (Resolve-FullPath $Path).Substring($Root.Length + 1).Replace("\", "/")
}

# Extracts a zip archive into an existing directory, one entry at a time,
# because .NET Framework's ExtractToDirectory refuses to overwrite an existing
# file. An entry that would escape the destination directory aborts.
function Expand-ArchiveTo([string]$ZipPath, [string]$Destination) {
  $destinationRoot = [System.IO.Path]::GetFullPath($Destination).TrimEnd("\") + "\"
  $archive = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
  try {
    foreach ($entry in $archive.Entries) {
      if ($entry.FullName.EndsWith("/") -or $entry.FullName.EndsWith("\")) { continue }
      $target = [System.IO.Path]::GetFullPath((Join-Path $Destination $entry.FullName))
      if (-not $target.StartsWith($destinationRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "archive entry escapes the destination directory: $($entry.FullName)"
      }
      $parent = Split-Path $target
      if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
      [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $target, $true)
    }
  }
  finally { $archive.Dispose() }
}

# Parses `vulkaninfo --summary` into device records. vulkaninfo.exe ships with
# the GPU driver on Windows; when it is missing the function returns $null so
# callers can record the absence instead of failing the collection.
# Added 2026-11-27: collect_environment.ps1 called this helper but no
# definition existed on the branch (IJ-SDK-1.0 P1 repair).
function Get-VulkanDevices {
  $exe = Get-Command vulkaninfo.exe -ErrorAction SilentlyContinue
  if (-not $exe) { return $null }
  # vulkaninfo prints loader warnings on stderr; PowerShell 5.1 turns a
  # redirected stderr line into an error record, so silence it locally.
  $prevPreference = $ErrorActionPreference
  $ErrorActionPreference = "SilentlyContinue"
  try {
    $output = & $exe.Path --summary 2>$null | Out-String
    $code = $LASTEXITCODE
  }
  finally { $ErrorActionPreference = $prevPreference }
  if ($code -ne 0) { return $null }
  $devices = @()
  $instanceVersion = [regex]::Match($output, "Vulkan Instance Version:\s*(.+)").Groups[1].Value.Trim()
  $blocks = $output -split "(?m)^GPU\d+:" | Select-Object -Skip 1
  foreach ($block in $blocks) {
    # Select-String treats a multi-line string as one line; use [regex]::Match
    # with (?m) so ^ and $ match at embedded line boundaries.
    $field = { param($name)
      [regex]::Match($block, "(?m)^\s*" + [regex]::Escape($name) + "\s*=\s*(.+?)\s*$").Groups[1].Value
    }
    $devices += [ordered]@{
      api_version     = & $field "apiVersion"
      driver_version  = & $field "driverVersion"
      vendor_id       = & $field "vendorID"
      device_id       = & $field "deviceID"
      device_type     = & $field "deviceType"
      device_name     = & $field "deviceName"
      driver_id       = & $field "driverID"
      driver_name     = & $field "driverName"
      driver_info     = & $field "driverInfo"
      instance_version = $instanceVersion
    }
  }
  if ($devices.Count -eq 0) { return $null }
  return $devices
}
