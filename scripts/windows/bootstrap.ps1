<#
.SYNOPSIS
  Creates the project Python environment from the locked dependency versions.

.DESCRIPTION
  Creates .venv with Python 3.12, installs requirements.lock with
  --require-hashes, and checks that the installed set is consistent. The lock
  file carries a SHA256 per package that scripts/tools/lock_hashes.py has
  cross-checked against pypi.org.

  Python packages are ordinary source code that the project needs; nothing is
  installed outside the repository directory.

.PARAMETER Python
  Interpreter used to create the virtual environment. Default: "py -3.12".

.PARAMETER IndexUrl
  Package index. The official index is the default; on networks where
  files.pythonhosted.org is unreliable pass the Tsinghua mirror.

.EXAMPLE
  pwsh -File scripts/windows/bootstrap.ps1
  pwsh -File scripts/windows/bootstrap.ps1 -IndexUrl https://pypi.tuna.tsinghua.edu.cn/simple
#>
[CmdletBinding()]
param(
  [string]$Python = "py",
  [string[]]$PythonArgs = @("-3.12"),
  [string]$IndexUrl = ""
)

. (Join-Path $PSScriptRoot "common.ps1")
$root = Get-RepoRoot
$lock = Join-Path $root "requirements.lock"
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $lock)) { throw "requirements.lock is missing." }

if (-not (Test-Path $venvPython)) {
  Write-Host "creating .venv"
  & $Python @PythonArgs -m venv (Join-Path $root ".venv")
  if ($LASTEXITCODE -ne 0) { throw "Could not create the virtual environment." }
}

$version = (& $venvPython -c "import sys; print('%d.%d.%d' % sys.version_info[:3])").Trim()
if (-not $version.StartsWith("3.12")) { throw "Python 3.12 is required; found $version." }

$pipArgs = @("-m", "pip", "install", "--disable-pip-version-check", "--require-hashes", "-r", $lock)
if ($IndexUrl) { $pipArgs += @("-i", $IndexUrl) }
$ErrorActionPreference = "Continue"
& $venvPython @pipArgs 2>&1 | ForEach-Object { Write-Host ([string]$_) }
$installExit = $LASTEXITCODE
$ErrorActionPreference = "Stop"
if ($installExit -ne 0) { throw "pip install failed with exit code $installExit." }

$check = Invoke-Native $venvPython @("-m", "pip", "check", "--disable-pip-version-check")
if ($check.exit_code -ne 0) { throw "pip check reported broken dependencies: $($check.stdout) $($check.stderr)" }

$frozen = @(((Invoke-Native $venvPython @("-m", "pip", "freeze", "--disable-pip-version-check")).stdout -split "`r?`n") | Where-Object { $_ })
$installed = @{}
foreach ($line in $frozen) { if ($line -match "^([^=]+)==(.+)$") { $installed[$Matches[1].ToLower()] = $Matches[2] } }
$drift = @()
foreach ($line in (Get-Content $lock)) {
  $pin = ($line -split "--hash")[0].Trim()
  if ($pin -notmatch "^([^=]+)==(.+)$") { continue }
  $actual = $installed[$Matches[1].ToLower()]
  if ($actual -ne $Matches[2]) { $drift += "$pin (installed: $actual)" }
}
if ($drift.Count -gt 0) { throw "Installed versions differ from requirements.lock: $($drift -join '; ')" }

$sdk = Invoke-Native $venvPython @("-c", "import google.antigravity as a, importlib.metadata as m; print(m.version('google-antigravity'))")
Write-Host "environment ready: Python $version, $($frozen.Count) packages, google-antigravity $($sdk.stdout)"
exit 0
