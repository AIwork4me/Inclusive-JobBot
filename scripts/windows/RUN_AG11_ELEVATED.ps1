[CmdletBinding(DefaultParameterSetName = 'Collect')]
param(
    [Parameter(Mandatory)][ValidatePattern('^[a-f0-9]{32}$')][string]$RunId,
    [Parameter(Mandatory, ParameterSetName = 'Collect')][string]$Python,
    [Parameter(ParameterSetName = 'Collect')][ValidateRange(60, 1200)][int]$TimeoutSeconds = 600,
    [Parameter(Mandatory, ParameterSetName = 'Decode')][switch]$Decode
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($env:OS -ne 'Windows_NT' -or -not [Environment]::Is64BitProcess) {
    throw 'AG-11 requires a native 64-bit Windows PowerShell session.'
}
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
$elevated = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
$repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$captureParent = Join-Path $repo '.runtime/ag11'
$capture = Join-Path $captureParent $RunId
$trace = Join-Path $capture 'scope.etl'
$collector = Join-Path $capture 'collector.json'
$processProvider = '22fb2cd6-0e7b-422b-a0c7-2fad1fd0e716'
$networkProvider = '7dd42a49-5329-4832-8dfd-43d979153a88'

function Publish-Json($Value, [string]$Destination) {
    $partial = "$Destination.partial"
    [IO.File]::WriteAllText($partial, ($Value | ConvertTo-Json -Depth 6), [Text.UTF8Encoding]::new($false))
    [IO.File]::Move($partial, $Destination)
}

function Trace-Clock($Value) {
    if ($Value -is [DateTime]) { return $Value.ToUniversalTime().ToFileTimeUtc() }
    if ($Value -is [DateTimeOffset]) { return $Value.UtcDateTime.ToFileTimeUtc() }
    return [long]$Value
}

if ($Decode) {
    if ($elevated) { throw 'Decode must run in a separate ordinary-token console.' }
    $receipt = Get-Content -LiteralPath $collector -Raw | ConvertFrom-Json
    $rawHash = (Get-FileHash -LiteralPath $trace -Algorithm SHA256).Hash.ToLowerInvariant()
    if (-not $receipt.trace_complete -or $receipt.raw_etl_sha256 -ne $rawHash) {
        throw 'AG-11 BLOCKED. The collector did not seal this ETL file.'
    }
    $destination = Join-Path $capture 'events.ndjson'
    $partial = "$destination.partial"
    if ((Test-Path -LiteralPath $destination) -or (Test-Path -LiteralPath $partial)) {
        throw 'A private decode already exists for this capture.'
    }
    $v4tcp = @(10, 12, 14, 16)
    $v6tcp = @(26, 28, 30, 32)
    $inboundOrClose = @(11, 13, 15, 27, 29, 31, 43, 59)
    $output = [IO.StreamWriter]::new($partial, $false, [Text.UTF8Encoding]::new($false))
    try {
        Get-WinEvent -Path $trace -Oldest -ErrorAction Stop | ForEach-Object {
            $event = $_
            try {
                $provider = $event.ProviderId.ToString()
                $data = $event.Properties
                $kind = $event.Id
                $version = $event.Version
                $stamp = Trace-Clock $event.TimeCreated
                $row = $null
                if ($provider -eq $processProvider -and $kind -in @(1, 2)) {
                    if ($kind -eq 1 -and $version -in @(3, 4) -and $data.Count -ge 11) {
                        $row = @{type = 'start'; pid = [uint32]$data[0].Value; sequence = [uint64]$data[1].Value
                            created = Trace-Clock $data[2].Value; parent = [uint64]$data[4].Value
                            parent_pid = [uint32]$data[3].Value; elevated = [bool]$data[8].Value
                            image = [IO.Path]::GetFileName([string]$data[10].Value)}
                    } elseif ($kind -eq 2 -and $version -eq 2 -and $data.Count -ge 4) {
                        $row = @{type = 'stop'; pid = [uint32]$data[0].Value; sequence = [uint64]$data[1].Value
                            created = Trace-Clock $data[2].Value; ended = Trace-Clock $data[3].Value}
                    } else {
                        $row = @{type = 'unattributed'; time = $stamp}
                    }
                } elseif ($provider -eq $networkProvider -and $kind -notin $inboundOrClose) {
                    $family = switch ($kind) {
                        { $_ -in $v4tcp } { 'tcp4' }
                        { $_ -in $v6tcp } { 'tcp6' }
                        42 { 'udp4' }
                        58 { 'udp6' }
                    }
                    if ($null -eq $family -or $version -ne 0 -or $data.Count -lt 6) {
                        $row = @{type = 'unattributed'; time = $stamp}
                    } else {
                        $ipValue = $data[2].Value
                        if ($ipValue -is [string]) {
                            $address = [Net.IPAddress]::Parse($ipValue)
                        } elseif ($family.EndsWith('4')) {
                            $address = [Net.IPAddress]::new([BitConverter]::GetBytes([uint32]$ipValue))
                        } else {
                            $address = [Net.IPAddress]::new([byte[]]$ipValue)
                        }
                        $portValue = $data[4].Value
                        $port = if ($portValue -is [string]) { [int]$portValue } else {
                            (([uint16]$portValue -band 0xFF) * 256) + ([uint16]$portValue -shr 8)
                        }
                        $row = @{type = 'send'; pid = [uint32]$data[0].Value; time = $stamp
                            family = $family; remote = $address.ToString(); port = $port}
                    }
                }
                if ($null -ne $row) { $output.WriteLine(($row | ConvertTo-Json -Compress)) }
            } finally {
                $event.Dispose()
            }
        }
    } finally {
        $output.Dispose()
    }
    [IO.File]::Move($partial, $destination)
    $normalizedHash = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant()
    Publish-Json @{raw_etl_sha256 = $rawHash; normalized_sha256 = $normalizedHash} (Join-Path $capture 'decode.json')
    Write-Host 'Private ETW decode is available. The AG-11 credential is BLOCKED pending independent review.'
    return
}

if (-not $elevated) { throw 'AG-11 BLOCKED. The collector requires a separately elevated owner console.' }
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { throw 'Supply the pinned repository Python executable.' }
$Python = (Resolve-Path -LiteralPath $Python).Path
$logman = Join-Path $env:SystemRoot 'System32/logman.exe'
if (-not (Test-Path -LiteralPath $logman -PathType Leaf)) { throw 'The Windows ETW controller is unavailable.' }
foreach ($name in @('Microsoft-Windows-Kernel-Process', 'Microsoft-Windows-Kernel-Network')) {
    $registered = Get-WinEvent -ListProvider $name -ErrorAction Stop
    if ($null -eq $registered) { throw 'Required Windows ETW provider is unavailable.' }
}
if (-not (Test-Path -LiteralPath $captureParent)) {
    New-Item -Path $captureParent -ItemType Directory -Force | Out-Null
}
New-Item -Path $capture -ItemType Directory -ErrorAction Stop | Out-Null
$session = "JobbotAG11-$RunId"
$providers = Join-Path $capture 'providers.txt'
@("{$processProvider} 0x10 0xFF", "{$networkProvider} 0xFFFFFFFFFFFFFFFF 0xFF") |
    Set-Content -LiteralPath $providers -Encoding Ascii
$stopHelper = Join-Path $repo 'scripts/tools/ag11_owner.py'
$nativeOutput = Join-Path $capture 'collector-private.log'
$runMarker = Join-Path $capture 'run.json'
$receipt = [ordered]@{ag11_status = 'BLOCKED'; trace_complete = $false; start = $null; stop = $null
    events_lost = $null; log_buffers_lost = $null; realtime_buffers_lost = $null; raw_etl_sha256 = $null
    query_status = $null; stop_status = $null; buffers_written = $null; owner_cleanup_required = $false}
$started = $false
$runFinished = $false
$fileLimitMiB = 256
try {
    & $logman query $session -ets *> $nativeOutput
    if ($LASTEXITCODE -eq 0) { throw 'The trace name is already active. Choose a fresh run ID.' }
    & $logman create trace $session -ets -o $trace -f bin -max $fileLimitMiB -bs 64 -nb 64 256 -ft 1 -ct perf -pf $providers *> $nativeOutput
    if ($LASTEXITCODE -ne 0) { throw 'AG-11 BLOCKED. The dedicated ETW session failed to start.' }
    $started = $true
    $begin = [DateTime]::UtcNow
    $deadline = $begin.AddSeconds($TimeoutSeconds)
    $receipt.start = $begin.ToFileTimeUtc()
    Publish-Json @{run_id = $RunId; start = $receipt.start; deadline = $deadline.ToFileTimeUtc()} (Join-Path $capture 'ready.json')
    Write-Host "READY for the separate normal-token SDK run $RunId."
    while ([DateTime]::UtcNow -lt $deadline) {
        if (Test-Path -LiteralPath $runMarker -PathType Leaf) {
            $runFinished = $true
            break
        }
        Start-Sleep -Milliseconds 300
    }
} finally {
    if ($started) {
        try {
            $result = & $Python -I -S $stopHelper stop-owned $session 2>> $nativeOutput
            if ($LASTEXITCODE -ne 0) { throw 'Could not query final ETW loss counters.' }
            $stats = $result | ConvertFrom-Json
            $receipt.query_status = $stats.query_status
            $receipt.stop_status = $stats.stop_status
            $receipt.buffers_written = $stats.buffers_written
            $receipt.events_lost = $stats.events_lost
            $receipt.log_buffers_lost = $stats.log_buffers_lost
            $receipt.realtime_buffers_lost = $stats.realtime_buffers_lost
            if ($stats.stop_status -ne 0) { throw 'Named ETW stop did not succeed.' }
        } catch {
            # The session name is unique to this invocation, and only reached after its successful creation.
            & $logman stop $session -ets *>> $nativeOutput
            $receipt.owner_cleanup_required = ($LASTEXITCODE -ne 0)
            if ($receipt.owner_cleanup_required) {
                Write-Warning "Check cleanup of this capture only with logman query $session -ets."
            }
        }
        $receipt.stop = [DateTime]::UtcNow.ToFileTimeUtc()
        if (Test-Path -LiteralPath $trace -PathType Leaf) {
            $length = (Get-Item -LiteralPath $trace).Length
            $receipt.raw_etl_sha256 = (Get-FileHash -LiteralPath $trace -Algorithm SHA256).Hash.ToLowerInvariant()
            $receipt.trace_complete = $runFinished -and $receipt.query_status -eq 0 -and $receipt.stop_status -eq 0 -and
                $receipt.buffers_written -gt 0 -and $length -gt 0 -and
                $length -lt (($fileLimitMiB * 1MB) - 64KB)
        }
    }
    Publish-Json $receipt $collector
}
Write-Host 'Collector finished. AG-11 remains BLOCKED until the private capture is independently reviewed.'
