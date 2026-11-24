[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateSet('vulkan','rocm')][string]$Backend,
    [Parameter(Mandatory = $true)][string]$Output,
    [Parameter(Mandatory = $true)][string]$CandidateDirectory,
    [ValidateRange(1024,65535)][int]$Port = 8091,
    [string]$SdkOutput,
    [switch]$Resume
)
. (Join-Path $PSScriptRoot common.ps1)
$root = Get-RepoRoot
$bin = (Resolve-Path -LiteralPath $CandidateDirectory).Path
$out = Resolve-FullPath $Output
if ((Test-Path -LiteralPath $out) -and !$Resume) { throw 'Use a new output directory.' }
if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) { throw 'Candidate port is occupied.' }
$exe = Join-Path $bin 'llama-server.exe'
$model = Join-Path $root 'models/MiniCPM5-2B-GGUF/MiniCPM5-2B-Q8_0.gguf'
if (!(Test-Path -LiteralPath $exe) -or !(Test-Path -LiteralPath $model)) { throw 'Candidate or Q8_0 model missing.' }
$plugin = if ($Backend -eq 'vulkan') { 'ggml-vulkan.dll' } else { 'ggml-hip.dll' }
$base = Join-Path $root 'runtime/llama-cpp'
$installed = Join-Path $base ($Backend + '/' + $plugin)
if ((Get-FileHash -LiteralPath $installed).Hash -ne (Get-FileHash -LiteralPath (Join-Path $bin $plugin)).Hash) {
    throw 'The candidate plugin differs from the official installed build.'
}
if ($Backend -eq 'rocm') {
    $dirs = Get-RocmLibraryDirectories $base
    if (!$dirs) { throw 'The pinned ROCm libraries are missing.' }
    $env:PATH = "$($dirs.libraries);$($dirs.core);$env:PATH"
}
$device = if ($Backend -eq 'vulkan') { 'Vulkan0' } else { 'ROCm0' }
New-Item -ItemType Directory -Path $out -Force | Out-Null
$launchId = [Guid]::NewGuid().ToString('N')
$rawLog = Join-Path $out "llama-$launchId.log"
$opts = @('-m', ('"' + $model + '"'), '--host', '127.0.0.1', '--port', $Port,
    '--ctx-size', '8192', '--jinja', '--alias', 'minicpm5-2b', '--parallel', '1',
    '--device', $device, '--n-gpu-layers', '99', '--no-webui', '--offline', '--verbosity', '4',
    '--log-file', ('"' + $rawLog + '"'))
$proc = Start-Process -FilePath $exe -WindowStyle Hidden -WorkingDirectory $bin -ArgumentList $opts -PassThru
$stop = Join-Path $out "stop-$launchId"
$launchPath = Join-Path $out "launch-$launchId.json"
$samplePath = Join-Path $out "gpu-$launchId.jsonl"
$sampler = $null
$baseUrl = "http://127.0.0.1:$Port"
try {
    $offloaded = $null
    for ($attempt = 0; $attempt -lt 180; $attempt++) {
        if ($proc.HasExited) { throw 'GPU candidate quit before readiness.' }
        $listeners = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
        if ($listeners.Count -eq 1 -and $listeners[0].OwningProcess -eq $proc.Id) {
            try {
                $ready = Invoke-RestMethod -Uri "$baseUrl/health" -TimeoutSec 3
                if ($ready.status -eq 'ok') {
                    $offloaded = Select-String -LiteralPath $rawLog -Pattern 'offloaded ([1-9][0-9]*)/([1-9][0-9]*) layers to GPU' |
                        Select-Object -Last 1
                    if ($offloaded) { break }
                }
            } catch { }
        }
        Start-Sleep -Milliseconds 500
    }
    if (!$offloaded) { throw 'GPU candidate readiness was not verified.' }
    $deviceLine = (Select-String -LiteralPath $rawLog -Pattern ("using device " + $device) | Select-Object -First 1).Line
    $launch = @{
        backend = $Backend; status = 'PASS'; pid = $proc.Id; owns_port = $true
        base_url = $baseUrl; gpu_line = Protect-Text $deviceLine
        layers_offloaded = [int]$offloaded.Matches[0].Groups[1].Value
        layers_total = [int]$offloaded.Matches[0].Groups[2].Value
        started_utc = $proc.StartTime.ToUniversalTime().ToString('o')
    }
    Write-JsonFile $launch $launchPath
    $samplerScript = Join-Path $PSScriptRoot 'sample_gpu_counters.ps1'
    $samplerArgs = @('-NoProfile', '-ExecutionPolicy', 'RemoteSigned', '-File', ('"' + $samplerScript + '"'),
        '-TargetProcessId', $proc.Id, '-OutputPath', ('"' + $samplePath + '"'), '-StopFile', ('"' + $stop + '"'),
        '-MaxSeconds', '600')
    $sampler = Start-Process powershell.exe -WindowStyle Hidden -ArgumentList $samplerArgs -PassThru
    for ($attempt = 0; !(Test-Path -LiteralPath "$stop.ready") -and $attempt -lt 60; $attempt++) {
        Start-Sleep -Milliseconds 250
    }
    if (!(Test-Path -LiteralPath "$stop.ready")) { throw 'The counter sampler did not become ready.' }
    $source = Join-Path $root 'benchmarks/tool_calling_v2/parser'
    $patches = @((Join-Path $source 'minicpm5-terminal-integrity.patch'), (Join-Path $source 'minicpm5-native-json-lexical.patch'))
    $parameters = @{ Output=$out; BaseUrl=$baseUrl; CandidateServer=$exe; CandidatePid=$proc.Id;
        CandidateLaunch=$launchPath; Patch=$patches; Lexical=$true; Resume=$Resume }
    & (Join-Path $PSScriptRoot 'run_ij06_parser_tests.ps1') @parameters
    $code = $LASTEXITCODE
    if ($SdkOutput -and (Test-Path -LiteralPath (Join-Path $out 'summary.json'))) {
        $sdkParameters = @{ Output=$SdkOutput; BaseUrl=$baseUrl; Backend=$Backend; CandidateServer=$exe;
            CandidatePid=$proc.Id; CandidateLaunch=$launchPath }
        & (Join-Path $PSScriptRoot 'run_ij06_sdk_tests.ps1') @sdkParameters
        Write-Output "SDK exit $LASTEXITCODE"
    }
} finally {
    if ($sampler) {
        [IO.File]::WriteAllText($stop, 'stop')
        $null = $sampler.WaitForExit(15000)
    }
    if (!$proc.HasExited) { Stop-Process -InputObject $proc }
}
exit $code
