[CmdletBinding()]
param([Parameter(Mandatory = $true)][string]$Output)

. (Join-Path $PSScriptRoot common.ps1)
$root = Get-RepoRoot
$outputPath = Resolve-FullPath $Output
if (Test-Path -LiteralPath $outputPath) { throw 'Candidate output already exists.' }
$cfg = Get-Content -Raw -Encoding UTF8 (Join-Path $root 'configs/qwen3_8b_reference.json') | ConvertFrom-Json
$model = Join-Path $root ('.tools/models/Qwen3-8B-GGUF/' + $cfg.filename)
if (!(Test-Path -LiteralPath $model) -or (Get-Item -LiteralPath $model).Length -ne $cfg.size -or
    (Get-FileHash -LiteralPath $model).Hash.ToLowerInvariant() -ne $cfg.sha256) {
    throw 'Qwen3 candidate missing or digest mismatch.'
}
if (Get-NetTCPConnection -LocalPort $cfg.port -State Listen -ErrorAction SilentlyContinue) {
    throw 'Candidate port is in use.'
}
$python = Join-Path $root '.venv/Scripts/python.exe'
$exe = Join-Path $root 'runtime/llama-cpp/vulkan/llama-server.exe'
New-Item -ItemType Directory -Path $outputPath | Out-Null
$rawLog = Join-Path $outputPath 'llama.log'
$opts = @('-m', ('"' + $model + '"'), '--host', '127.0.0.1', '--port', $cfg.port,
    '--ctx-size', $cfg.context_length, '--jinja', '--alias', $cfg.alias, '--parallel', '1',
    '--n-gpu-layers', '99', '--verbosity', '4', '--log-file', ('"' + $rawLog + '"'))
$proc = Start-Process -FilePath $exe -WindowStyle Hidden -ArgumentList $opts -PassThru
$stop = Join-Path $outputPath 'stop'
$sampler = $null
try {
    $offload = $null
    for ($attempt = 0; $attempt -lt 180; $attempt++) {
        if ($proc.HasExited) { throw 'Candidate quit before readiness.' }
        $listeners = @(Get-NetTCPConnection -LocalPort $cfg.port -State Listen -ErrorAction SilentlyContinue)
        if ($listeners.Count -eq 1 -and $listeners[0].OwningProcess -eq $proc.Id) {
            try {
                $online = Invoke-RestMethod -Uri ('http://127.0.0.1:' + $cfg.port + '/health') -TimeoutSec 3
                if ($online.status -eq 'ok') {
                    $offload = Select-String -LiteralPath $rawLog -Pattern 'offloaded ([1-9][0-9]*)/([1-9][0-9]*) layers to GPU' |
                        Select-Object -Last 1
                    if ($offload) { break }
                }
            } catch { }
        }
        Start-Sleep -Milliseconds 500
    }
    if (!$offload) { throw 'Candidate GPU readiness was not verified.' }
    $digs = @{}
    foreach ($file in 'llama-server-impl.dll', 'llama-common.dll', 'llama.dll', 'ggml-vulkan.dll') {
        $digs[$file] = (Get-FileHash -LiteralPath (Join-Path (Split-Path $exe) $file)).Hash.ToLowerInvariant()
    }
    $launch = @{
        backend = 'vulkan'; status = 'PASS'; pid = $proc.Id; owns_port = $true
        layers_offloaded = [int]$offload.Matches[0].Groups[1].Value
        layers_total = [int]$offload.Matches[0].Groups[2].Value
        executable_sha256 = (Get-FileHash -LiteralPath $exe).Hash.ToLowerInvariant()
        dll_sha256 = $digs
        gpu_line = Protect-Text ((Select-String -LiteralPath $rawLog -Pattern 'using device Vulkan' |
                                    Select-Object -First 1).Line)
        start_time_utc = $proc.StartTime.ToUniversalTime().ToString('o')
    }
    $launchFile = Join-Path $outputPath 'launch.json'
    Write-JsonFile $launch $launchFile
    $samplePath = Join-Path $outputPath 'gpu.jsonl'
    $sampleScript = Join-Path $PSScriptRoot 'sample_gpu_counters.ps1'
    $samplerArgs = @('-NoProfile', '-ExecutionPolicy', 'RemoteSigned', '-File', ('"' + $sampleScript + '"'),
        '-TargetProcessId', $proc.Id, '-OutputPath', ('"' + $samplePath + '"'), '-StopFile', ('"' + $stop + '"'),
        '-MaxSeconds', '600')
    $sampler = Start-Process powershell.exe -WindowStyle Hidden -ArgumentList $samplerArgs -PassThru
    for ($attempt = 0; !(Test-Path -LiteralPath "$stop.ready") -and $attempt -lt 60; $attempt++) {
        Start-Sleep -Milliseconds 250
    }
    if (!(Test-Path -LiteralPath "$stop.ready")) { throw 'Candidate GPU sampler did not become ready.' }
    Push-Location $root
    try {
        & $python -m benchmarks.job_productivity_v1.reference --output (Join-Path $outputPath 'reference.json') --launch $launchFile
        $code = $LASTEXITCODE
    } finally { Pop-Location }
} finally {
    if ($sampler) {
        [IO.File]::WriteAllText($stop, 'stop')
        $null = $sampler.WaitForExit(15000)
    }
    if (!$proc.HasExited) { Stop-Process -InputObject $proc }
}
exit $code
