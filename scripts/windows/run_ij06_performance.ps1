[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateSet('vulkan', 'rocm')][string]$Backend,
    [Parameter(Mandatory = $true)][string]$Output,
    [switch]$Resume
)
. (Join-Path $PSScriptRoot 'common.ps1')
$root = Get-RepoRoot
$stateFile = Join-Path $root '.runtime/llama-server/server.json'
if (!(Test-Path -LiteralPath $stateFile)) { throw 'Start the requested managed GPU server first.' }
$state = Get-Content -Raw -Encoding UTF8 -LiteralPath $stateFile | ConvertFrom-Json
if ($state.status -ne 'PASS' -or $state.backend -ne $Backend -or !$state.layers_offloaded) {
    throw 'Managed server identity or offload does not match the requested GPU.'
}
$out = Resolve-FullPath $Output
New-Item -ItemType Directory -Force -Path $out | Out-Null
$sessionId = [Guid]::NewGuid().ToString('N')
$counter = Join-Path $out "gpu-$sessionId.jsonl"
$stop = Join-Path $out "stop-$sessionId"
$ready = "$stop.ready"
$script = Join-Path $PSScriptRoot 'sample_gpu_counters.ps1'
$quoted = @('-NoProfile', '-ExecutionPolicy', 'RemoteSigned', '-File', ('"' + $script + '"'),
    '-TargetProcessId', $state.pid, '-OutputPath', ('"' + $counter + '"'), '-StopFile', ('"' + $stop + '"'),
    '-MaxSeconds', '600')
$proc = Start-Process powershell.exe -WindowStyle Hidden -ArgumentList $quoted -PassThru
try {
    for ($attempt = 0; !(Test-Path -LiteralPath $ready) -and $attempt -lt 40; $attempt++) {
        if ($proc.HasExited) { throw 'GPU counter sampler exited before readiness.' }
        Start-Sleep -Milliseconds 250
    }
    if (!(Test-Path -LiteralPath $ready)) { throw 'GPU counter sampler did not become ready.' }
    $jobScript = Join-Path $PSScriptRoot 'run_ij06_job_ablation.ps1'
    & $jobScript -Backend $Backend -Output $out -Resume:$Resume
    $code = $LASTEXITCODE
} finally {
    [IO.File]::WriteAllText($stop, "stop")
    $null = $proc.WaitForExit(15000)
}
exit $code
