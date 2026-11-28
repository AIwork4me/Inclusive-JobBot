[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateSet('vulkan', 'rocm')][string]$Backend,
    [Parameter(Mandatory = $true)][string]$Output,
    [switch]$Resume
)
$ErrorActionPreference = 'Stop'
$root = Resolve-Path (Join-Path $PSScriptRoot '../..')
$python = Join-Path $root '.venv/Scripts/python.exe'
if (!(Test-Path -LiteralPath $python)) { throw 'Run bootstrap before the development rehearsal.' }
$arguments = @((Join-Path $root 'benchmarks/job_productivity_v1/development.py'), '--backend', $Backend, '--output', $Output)
if ($Resume) { $arguments += '--resume' }
& $python @arguments
exit $LASTEXITCODE
