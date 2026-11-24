[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateSet('vulkan', 'rocm')][string]$Backend,
    [Parameter(Mandatory = $true)][string]$Output,
    [string[]]$Gate = @(),
    [string]$BaseUrl = 'http://127.0.0.1:8080',
    [string]$CandidateServer,
    [int]$CandidatePid,
    [string]$CandidateLaunch,
    [switch]$Resume
)
$ErrorActionPreference = 'Stop'
$root = Resolve-Path (Join-Path $PSScriptRoot '../..')
$python = Join-Path $root '.venv/Scripts/python.exe'
if (!(Test-Path -LiteralPath $python)) { throw 'Run bootstrap before SDK qualification.' }
$arguments = @((Join-Path $root 'benchmarks/ij06_sdk/qualify.py'), '--backend', $Backend, '--output', $Output, '--base-url', $BaseUrl)
foreach ($item in $Gate) { $arguments += @('--gate', $item) }
if ($CandidateServer -or $CandidatePid -or $CandidateLaunch) {
    if (!$CandidateServer -or $CandidatePid -le 0 -or !$CandidateLaunch) {
        throw 'Candidate testing requires CandidateServer, CandidatePid and CandidateLaunch.'
    }
    $arguments += @('--candidate-server', $CandidateServer, '--candidate-pid', $CandidatePid,
        '--candidate-launch', $CandidateLaunch)
}
if ($Resume) { $arguments += '--resume' }
& $python @arguments
exit $LASTEXITCODE
