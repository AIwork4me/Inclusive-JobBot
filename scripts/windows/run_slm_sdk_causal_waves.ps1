[CmdletBinding(DefaultParameterSetName = 'Audit')]
param(
    [Parameter(Mandatory = $true)][string]$AssetsRoot,
    [Parameter(ParameterSetName = 'Audit')][switch]$Audit,
    [Parameter(Mandatory = $true, ParameterSetName = 'Resume')][switch]$Resume
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$assets = (Resolve-Path -LiteralPath $AssetsRoot).Path
$python = Join-Path $assets '.venv/Scripts/python.exe'
$env:PYTHONPATH = '.;src;benchmarks/tool_calling/runner'
Set-Location -LiteralPath $repo

$mode = '--audit'
if ($Resume) {
    $legacyController = Get-CimInstance Win32_Process | Where-Object {
        $_.ProcessId -ne $PID -and $_.CommandLine -match '(?i)-File\s+[^\r\n]*run_slm_sdk_causal_waves\.ps1\b' -and
        $_.CommandLine -notmatch '(?i)(?:^|\s)-Resume\b'
    }
    if ($legacyController) {
        throw 'The original interleaved controller is active. Resume after it exits.'
    }
    $mode = '--resume'
}
& $python -m benchmarks.slm10.sdk_wave_queue --assets $assets $mode
exit $LASTEXITCODE
