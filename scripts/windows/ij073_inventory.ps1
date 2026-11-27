param([Parameter(Mandatory)][string]$AssetRoot)
$ErrorActionPreference = "Stop"
$repo = (Resolve-Path "$PSScriptRoot/../..").Path
$assets = (Resolve-Path $AssetRoot).Path
. "$PSScriptRoot/common.ps1"
$engine = Get-Content -Raw "$repo/evidence/IJ0/engine_install.json" | ConvertFrom-Json
$models = Get-Content -Raw "$repo/models/model_manifest.json" | ConvertFrom-Json
$runtime = Join-Path $assets "runtime/llama-cpp"
$backends = foreach ($entry in $engine.backends) {
    $binary = Join-Path $runtime "$($entry.backend)/llama-server.exe"
    $hash = (Get-FileHash -LiteralPath $binary -Algorithm SHA256).Hash.ToLowerInvariant()
    $savedPath = $env:PATH
    try {
        if ($entry.backend -eq "rocm") {
            $dirs = Get-RocmLibraryDirectories $runtime
            $env:PATH = (@($dirs.libraries, $dirs.core, $savedPath) -join ";")
        }
        $listing = @(& $binary --list-devices 2>&1 | ForEach-Object { "$_" })
        $code = $LASTEXITCODE
        $device = @($listing | Where-Object { $_ -match '^\s*(ROCm|Vulkan)\d+:' } | ForEach-Object { $_.Trim() })
        $ok = $hash -eq $entry.exe_sha256 -and $code -eq 0
        if ($entry.backend -ne "cpu") { $ok = $ok -and ($device -match '8060S').Count -gt 0 }
        [ordered]@{backend=$entry.backend; sha256=$hash; expected_sha256=$entry.exe_sha256; devices=$device
                   command="--list-devices"; exit_code=$code; status=$(if ($ok) {"PASS"} else {"FAIL"})}
    } finally { $env:PATH = $savedPath }
}
$files = foreach ($model in $models.models) {
    foreach ($pin in $model.files) {
        if ($pin.path -notmatch '(\.gguf$|^tokenizer.*\.json$|^chat_template\.jinja$)') {continue}
        $file = Join-Path (Join-Path $assets $model.local_dir) $pin.path
        $sha = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant()
        [ordered]@{repo=$model.model_id; revision=$model.revision; file=$pin.path; sha256=$sha
                   status=$(if ($sha -eq $pin.sha256) {"PASS"} else {"FAIL"})}
    }
}
$system = Get-CimInstance Win32_ComputerSystem
$graphics = @(Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion)
$os = Get-CimInstance Win32_OperatingSystem
$counterCount = @(Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine).Count
[ordered]@{scope="Installed MiniCPM assets, baseline binaries and GPU counter availability. No inference."
           utc=[DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ"); cpu=(Get-CimInstance Win32_Processor).Name
           os=$os.Caption; build=$os.BuildNumber; os_reported_physical_memory_bytes=$system.TotalPhysicalMemory
           installed_memory_bytes=[uint64]((Get-CimInstance Win32_PhysicalMemory | Measure-Object Capacity -Sum).Sum)
           gpu=$graphics; gpu_engine_counter_instances=$counterCount; backends=@($backends); files=@($files)
           sdk=(& "$assets/.venv/Scripts/python.exe" -c "from importlib.metadata import version; print(version('google-antigravity'))")
           inference_status="NOT_RUN"} | ConvertTo-Json -Depth 8
