[CmdletBinding()]
param(
    [string]$RunManifest,
    [string[]]$RequiredGate = @()
)
$ErrorActionPreference = 'Stop'
$root = Resolve-Path (Join-Path $PSScriptRoot '../..')
$python = Join-Path $root '.venv/Scripts/python.exe'
if (!(Test-Path -LiteralPath $python)) { $python = 'python' }
$arguments = @((Join-Path $root 'scripts/tools/verify_ij06_evidence.py'))
if ($RunManifest) { $arguments += @('--run', $RunManifest) }
foreach ($gate in $RequiredGate) { $arguments += @('--required-gate', $gate) }
& $python @arguments
exit $LASTEXITCODE
