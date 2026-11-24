<#
.SYNOPSIS
  Downloads MiniCPM5-2B from ModelScope at the pinned revisions and verifies it.

.DESCRIPTION
  Reads the pinned repository revisions from models/model_manifest.json and
  downloads each repository with the ModelScope CLI through
  "python -m modelscope" (the pip launcher .exe is not used). Files that are
  already complete are skipped by the CLI.

  Afterwards every file is compared with the SHA256 and size that ModelScope
  published, using the listing archived in evidence/IJ0/modelscope_listing.json
  so the comparison needs no network. Exit code is 0 when all files match.

.EXAMPLE
  pwsh -File scripts/windows/download_models_modelscope.ps1
#>
[CmdletBinding()]
param(
  [string]$PythonExe = ".venv\Scripts\python.exe",
  [switch]$VerifyOnly
)

. (Join-Path $PSScriptRoot "common.ps1")
$root = Get-RepoRoot
$python = Join-Path $root $PythonExe
if (-not (Test-Path $python)) {
  throw "Python not found at $PythonExe. Create the project environment and install the 'model-download' extra first."
}
$manifestPath = Join-Path $root "models\model_manifest.json"
if (-not (Test-Path $manifestPath)) {
  throw "models/model_manifest.json is missing. It is committed with the repository."
}
$manifest = Read-JsonFile $manifestPath
$listing = Join-Path $root "evidence\IJ0\modelscope_listing.json"

if (-not $VerifyOnly) {
  foreach ($model in $manifest.models) {
    if ($model.source_url -notmatch "^https://modelscope\.cn/models/") {
      throw "Refusing a weight source outside modelscope.cn: $($model.source_url)"
    }
    Write-Host "downloading $($model.model_id) at $($model.revision)"
    $target = Join-Path $root $model.local_dir
    $ErrorActionPreference = "Continue"
    & $python -m modelscope.cli.cli download $model.model_id --revision $model.revision --local-dir $target 2>&1 |
      ForEach-Object { Write-Host ([string]$_) }
    $downloadExit = $LASTEXITCODE
    $ErrorActionPreference = "Stop"
    if ($downloadExit -ne 0) { throw "ModelScope download failed for $($model.model_id) with exit code $downloadExit" }
  }
}

$verifyArgs = @((Join-Path $root "scripts\tools\model_identity.py"))
if (Test-Path $listing) { $verifyArgs += @("--listing", $listing) }
Write-Host "verifying every file against the ModelScope SHA256 listing"
& $python @verifyArgs
exit $LASTEXITCODE
