[CmdletBinding()]
param(
    [string]$Output = '.runtime/ij06/security',
    [switch]$Resume
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'common.ps1')
$root = Get-RepoRoot
$python = Join-Path $root '.venv/Scripts/python.exe'
if (!(Test-Path -LiteralPath $python)) { throw 'Run bootstrap before testing the gateway.' }
Push-Location $root
try {
    $runDirectory = Resolve-FullPath $Output
    if ($Resume -and (Test-Path -LiteralPath (Join-Path $runDirectory 'summary.json'))) {
        $prior = Read-JsonFile (Join-Path $runDirectory 'summary.json')
        foreach ($entry in $prior.source_manifest.PSObject.Properties) {
            if (!(Test-Path -LiteralPath $entry.Name) -or
                    (Get-FileHash -Algorithm SHA256 -LiteralPath $entry.Name).Hash.ToLowerInvariant() -ne $entry.Value) {
                throw 'The security test source differs from the saved run.'
            }
        }
        if ($prior.status -eq 'PASS') { exit 0 }
        exit 1
    }
    & $python (Join-Path $root 'scripts/tools/run_ij06_security_tests.py') $runDirectory
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
