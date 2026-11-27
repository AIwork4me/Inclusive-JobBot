[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$AssetsRoot
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$assets = (Resolve-Path -LiteralPath $AssetsRoot).Path
$runtime = Join-Path $assets '.runtime/ij-slm-1.0'
$python = Join-Path $assets '.venv/Scripts/python.exe'
$env:PYTHONPATH = '.;src;benchmarks/tool_calling/runner'
Set-Location -LiteralPath $repo

$profile = Get-Content -Raw -LiteralPath 'atlas/slm/v1.0/sdk-causal-experiment.json' | ConvertFrom-Json
$diagnosticCases = @($profile.development_case_ids | Where-Object { $_ -notin $profile.pilot_case_ids })
$completedWaves = [math]::Ceiling($diagnosticCases.Count / 3)
$diagnostics = Join-Path $runtime 'sdk-causal-waves'
New-Item -ItemType Directory -Path $diagnostics -Force | Out-Null

for ($round = 0; $round -lt 46; $round++) {
    foreach ($candidate in $profile.models) {
        & $python -m benchmarks.slm10.tc_queue --assets $assets --candidate $candidate --batch-size 36 --limit 36
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }

        if ($round -lt $completedWaves) {
            $folder = Join-Path $diagnostics ('{0}-{1:d2}' -f $candidate, $round)
            if (!(Test-Path -LiteralPath $folder)) {
                $arguments = @()
                foreach ($case in ($diagnosticCases | Select-Object -Skip (3 * $round) -First 3)) {
                    $arguments += @('--case', $case)
                }
                & $python -m benchmarks.slm10.sdk_causal_ablation $candidate --assets $assets --output $folder @arguments
                if ($LASTEXITCODE -ne 0) {
                    Write-Output "Diagnostic phase failed for $candidate wave $round with exit $LASTEXITCODE"
                }
            }
        }

        if ($round -eq 0 -and $candidate -eq 'D') {
            $transport = Join-Path $runtime 'sdk-transport-controls-v1'
            if (!(Test-Path -LiteralPath $transport)) {
                & $python -m benchmarks.slm10.sdk_transport_controls --assets $assets --output $transport
                if ($LASTEXITCODE -ne 0) {
                    Write-Output "Transport control stopped with exit $LASTEXITCODE"
                }
            }
        }
    }
}

& $python -m benchmarks.slm10.tc_five_model_queue --assets $assets
exit $LASTEXITCODE
