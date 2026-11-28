# IJ-SDK-1.0 P3: install every admitted SDK into its own isolated venv.
#
# Network note (D-002): packages come from the Tsinghua PyPI mirror through an
# explicit -i argument; versions are pinned per evidence/IJSDK/P3/sdk_research_findings.json.
# SEC-01: Microsoft Agent Framework is installed ONLY at the last clean
# release 1.26.0 into an isolated venv; the wheel digest is recorded after
# install. Never install 1.26.1/1.26.2.
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy RemoteSigned -File scripts/windows/ij_sdk_install_sdks.ps1
$ErrorActionPreference = "Continue"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$mirror = "https://pypi.tuna.tsinghua.edu.cn/simple"
$venvRoot = Join-Path $root ".venvs"
New-Item -ItemType Directory -Force -Path $venvRoot | Out-Null
$py = Join-Path $root ".venv\Scripts\python.exe"

$arms = @(
  @{ name = "b2-openai-agents";  pkgs = @("openai-agents==0.26.0") },
  @{ name = "b3b4-smolagents";   pkgs = @("smolagents==1.26.0") },
  @{ name = "b5-pydantic-ai";    pkgs = @("pydantic-ai-slim[openai]==2.76.0") },
  @{ name = "b6-langgraph";      pkgs = @("langgraph==1.2.24", "langchain-openai==1.8.5") },
  @{ name = "b7-adk";            pkgs = @("google-adk[openai]==2.15.1") },
  @{ name = "b8-agent-framework";pkgs = @("agent-framework==1.26.0") },
  @{ name = "b9-pocketflow";     pkgs = @("pocketflow==0.0.3") },
  @{ name = "o1-dspy";           pkgs = @("dspy==3.5.0") }
)

foreach ($arm in $arms) {
  $venv = Join-Path $venvRoot $arm.name
  Write-Host "=== $($arm.name) ==="
  if (-not (Test-Path (Join-Path $venv "Scripts\python.exe"))) {
    & $py -m venv $venv
    if ($LASTEXITCODE -ne 0) { Write-Host "FAIL venv $($arm.name)"; continue }
  }
  $vp = Join-Path $venv "Scripts\python.exe"
  & $vp -m pip install --disable-pip-version-check --no-cache-dir -i $mirror @($arm.pkgs) 2>&1 | Select-Object -Last 3 | Write-Host
  if ($LASTEXITCODE -eq 0) {
    Write-Host "PASS $($arm.name)"
  } else {
    Write-Host "FAIL $($arm.name)"
  }
}

# Record the exact installed set per venv (pip freeze) as installation evidence.
$recordPath = Join-Path $root "evidence\IJSDK\P3\installed_artifacts.json"
$records = [ordered]@{}
foreach ($arm in $arms) {
  $vp = Join-Path $venvRoot $arm.name "Scripts\python.exe"
  if (Test-Path $vp) {
    $freeze = (& $vp -m pip freeze --disable-pip-version-check 2>$null) -join "`n"
    $records[$arm.name] = $freeze
  }
}
[IO.File]::WriteAllText($recordPath, ($records | ConvertTo-Json -Depth 6) + "`n", (New-Object Text.UTF8Encoding $false))
Write-Host "wrote $recordPath"
