[CmdletBinding(DefaultParameterSetName = 'Wire')]
param(
  [Parameter(Mandatory = $true)][string]$Output,
  [Parameter(ParameterSetName = 'Wire')][string]$BaseUrl = 'http://127.0.0.1:8080',
  [Parameter(ParameterSetName = 'Wire')][switch]$Resume,
  [Parameter(ParameterSetName = 'Wire')][string]$CandidateServer,
  [Parameter(ParameterSetName = 'Wire')][int]$CandidatePid,
  [Parameter(ParameterSetName = 'Wire')][string]$CandidateLaunch,
  [Parameter(ParameterSetName = 'Direct', Mandatory = $true)][string]$Probe,
  [Parameter(ParameterSetName = 'Direct', Mandatory = $true)][string]$ChatTemplate,
  [Parameter(ParameterSetName = 'Direct')][string]$UpstreamCommit = 'b1b770d90d94cad9e9ea5b993bdbc383a522fb28',
  [string[]]$Patch = @(),
  [switch]$Lexical,
  [Parameter(ParameterSetName = 'Direct')][switch]$RequireNativePass
)

$ErrorActionPreference = 'Stop'
$root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')
$python = Join-Path $root '.venv/Scripts/python.exe'
if (!(Test-Path -LiteralPath $python)) { throw 'Run bootstrap before parser qualification.' }
$env:PYTHONPATH = Join-Path $root 'src'
$env:PYTHONIOENCODING = 'utf-8'
Push-Location -LiteralPath $root
try {
  if ($PSCmdlet.ParameterSetName -eq 'Direct') {
    $outputParent = Split-Path -Parent $Output
    if ($outputParent) { New-Item -ItemType Directory -Force -Path $outputParent | Out-Null }
    $arguments = @('-m', 'benchmarks.tool_calling_v2.parser.run_direct', '--probe', $Probe,
      '--chat-template', $ChatTemplate, '--output', $Output, '--upstream-commit', $UpstreamCommit)
    foreach ($item in $Patch) { $arguments += @('--patch', $item) }
    if ($RequireNativePass) { $arguments += '--require-native-pass' }
  } else {
    $arguments = @('-m', 'benchmarks.tool_calling_v2.parser.run_wire', '--base-url', $BaseUrl, '--output', $Output)
    if ($Resume) { $arguments += '--resume' }
    if ($CandidateServer -or $CandidatePid -or $CandidateLaunch -or $Patch) {
      if (!$CandidateServer -or $CandidatePid -le 0 -or !$Patch) {
        throw 'Candidate wire tests require CandidateServer, CandidatePid and Patch.'
      }
      $arguments += @('--candidate-server', $CandidateServer, '--candidate-pid', $CandidatePid)
      if ($CandidateLaunch) { $arguments += @('--candidate-launch', $CandidateLaunch) }
      foreach ($item in $Patch) { $arguments += @('--candidate-patch', $item) }
    }
  }
  if ($Lexical) { $arguments += '--lexical' }
  & $python @arguments
  $status = $LASTEXITCODE
} finally {
  Pop-Location
}
exit $status
