<#
.SYNOPSIS
  Collects the non-sensitive Windows hardware and software baseline (mission M0).

.DESCRIPTION
  Writes environment.json, gpu_inventory.json and dependency_inventory.json.
  User directory names, account names, host names, IP addresses and serial
  numbers are never written; detected values are replaced before output.

.PARAMETER OutputDir
  Repository-relative directory for the three evidence files.

.EXAMPLE
  pwsh -File scripts/windows/collect_environment.ps1
#>
[CmdletBinding()]
param(
  [string]$OutputDir = "evidence/M0"
)

. (Join-Path $PSScriptRoot "common.ps1")
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$outDir = Join-Path $repoRoot $OutputDir
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

function Write-Evidence($object, [string]$name) {
  $json = $object | ConvertTo-Json -Depth 10
  $path = Join-Path $outDir $name
  [IO.File]::WriteAllText($path, (Protect-Text $json) + "`n", (New-Object Text.UTF8Encoding $false))
  Write-Host "wrote $OutputDir/$name"
}

# --- OS and hardware -------------------------------------------------------
$os = Get-CimInstance Win32_OperatingSystem
$system = Get-CimInstance Win32_ComputerSystem
$processor = Get-CimInstance Win32_Processor | Select-Object -First 1
$memory = Get-CimInstance Win32_PhysicalMemory
$cv = Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion"

$environment = [ordered]@{
  schema_version = 1
  collected_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
  collector = "scripts/windows/collect_environment.ps1"
  redactions = @("user profile path", "user name", "host name", "domain")
  os = [ordered]@{
    caption = $os.Caption
    display_version = $cv.DisplayVersion
    version = $os.Version
    build_number = $os.BuildNumber
    ubr = $cv.UBR
    architecture = $os.OSArchitecture
    installation_type = $os.InstallationType
    locale = (Get-Culture).Name
    ui_language = (Get-UICulture).Name
    time_zone = (Get-TimeZone).Id
  }
  hardware = [ordered]@{
    manufacturer = $system.Manufacturer
    model = $system.Model
    system_type = $system.SystemType
    cpu = [ordered]@{
      name = $processor.Name.Trim()
      physical_cores = $processor.NumberOfCores
      logical_processors = $processor.NumberOfLogicalProcessors
      max_clock_mhz = $processor.MaxClockSpeed
    }
    memory = [ordered]@{
      installed_gb = [math]::Round((($memory | Measure-Object Capacity -Sum).Sum) / 1GB, 2)
      os_visible_gb = [math]::Round($system.TotalPhysicalMemory / 1GB, 2)
      modules = @($memory).Count
      speed_mtps = ($memory | Select-Object -First 1).ConfiguredClockSpeed
    }
    remote_display_adapter_present = [bool](Get-CimInstance Win32_VideoController | Where-Object { $_.Name -like "*Remote Display*" })
  }
}

# --- Security state relevant to running the engine -------------------------
$defender = $null
try { $defender = Get-MpComputerStatus -ErrorAction Stop } catch { }
$deviceGuard = $null
try { $deviceGuard = Get-CimInstance -Namespace root\Microsoft\Windows\DeviceGuard -ClassName Win32_DeviceGuard -ErrorAction Stop } catch { }
$environment.security = [ordered]@{
  smart_app_control = if ($defender) { [string]$defender.SmartAppControlState } else { "unknown" }
  defender_realtime_protection = if ($defender) { [bool]$defender.RealTimeProtectionEnabled } else { "unknown" }
  code_integrity_policy_enforcement = if ($deviceGuard) { [int]$deviceGuard.CodeIntegrityPolicyEnforcementStatus } else { "unknown" }
  usermode_code_integrity_policy_enforcement = if ($deviceGuard) { [int]$deviceGuard.UsermodeCodeIntegrityPolicyEnforcementStatus } else { "unknown" }
  virtualization_based_security_status = if ($deviceGuard) { [int]$deviceGuard.VirtualizationBasedSecurityStatus } else { "unknown" }
  powershell_execution_policy = [ordered]@{
    local_machine = (Get-ExecutionPolicy -Scope LocalMachine).ToString()
    current_user = (Get-ExecutionPolicy -Scope CurrentUser).ToString()
    effective = (Get-ExecutionPolicy).ToString()
  }
  note = "Smart App Control was turned off by the machine owner on 2026-11-24; see BLOCKERS.md B-001."
}

# --- Tools -----------------------------------------------------------------
$pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"
$llamaRoot = Join-Path $repoRoot "runtime\llama-cpp"
$ollamaExe = Join-Path $repoRoot ".tools\ollama-core\ollama.exe"
$gitVersion = (Invoke-Native (Get-Command git).Source @("--version")).stdout
$ghVersion = (Invoke-Native (Get-Command gh).Source @("--version")).stdout

$llamaBackends = [ordered]@{}
if (Test-Path $llamaRoot) {
  foreach ($backend in (Get-ChildItem $llamaRoot -Directory | Sort-Object Name)) {
    $server = Join-Path $backend.FullName "llama-server.exe"
    if (-not (Test-Path $server)) { continue }
    $version = Invoke-Native $server @("--version")
    $devices = Invoke-Native $server @("--list-devices")
    # llama.cpp writes its log, including the version banner, to stderr.
    $llamaBackends[$backend.Name] = [ordered]@{
      version = (($version.stdout, $version.stderr) -join "`n").Trim()
      list_devices_exit_code = $devices.exit_code
      list_devices_stdout = $devices.stdout
      list_devices_stderr = $devices.stderr
    }
  }
}

$environment.tools = [ordered]@{
  powershell = [ordered]@{ edition = $PSVersionTable.PSEdition; version = [string]$PSVersionTable.PSVersion }
  python = if (Test-Path $pythonExe) { (Invoke-Native $pythonExe @("--version")).stdout } else { "not installed in .venv" }
  git = $gitVersion
  github_cli = $ghVersion
  node = $null
  ollama_portable = [ordered]@{
    present = (Test-Path $ollamaExe)
    client_version = if (Test-Path $ollamaExe) { ((Invoke-Native $ollamaExe @("--version")).stdout -split "`r?`n" | Select-Object -Last 1) } else { $null }
    role = "optional compatibility baseline only (ECO-01)"
  }
  llama_cpp = $llamaBackends
  network = [ordered]@{
    proxy_variables_set = [ordered]@{
      http_proxy = [bool]$env:HTTP_PROXY
      https_proxy = [bool]$env:HTTPS_PROXY
      no_proxy = [bool]$env:NO_PROXY
    }
  }
}
if (Get-Command node -ErrorAction SilentlyContinue) {
  $environment.tools.node = (Invoke-Native (Get-Command node).Source @("--version")).stdout
}

Write-Evidence $environment "environment.json"

# --- GPU inventory ---------------------------------------------------------
$gpuClass = "HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
$controllers = @(Get-CimInstance Win32_VideoController)
$registryVideo = @()
if (Test-Path $gpuClass) {
  foreach ($key in (Get-ChildItem $gpuClass -ErrorAction SilentlyContinue)) {
    $props = Get-ItemProperty $key.PSPath -ErrorAction SilentlyContinue
    if (-not $props.DriverDesc) { continue }
    $registryVideo += [ordered]@{
      description = $props.DriverDesc
      driver_version = $props.DriverVersion
      dedicated_memory_bytes = $props."HardwareInformation.qwMemorySize"
      matching_device_id = $props.MatchingDeviceId
    }
  }
}
$vulkan = Get-VulkanDevices
$hipRuntime = @()
foreach ($dll in (Get-ChildItem (Join-Path $env:SystemRoot "System32") -Filter "amdhip64*.dll" -ErrorAction SilentlyContinue)) {
  $hipRuntime += [ordered]@{ name = $dll.Name; file_version = $dll.VersionInfo.FileVersion; description = $dll.VersionInfo.FileDescription }
}

$gpuInventory = [ordered]@{
  schema_version = 1
  collected_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
  collector = "scripts/windows/collect_environment.ps1"
  controllers = @($controllers | ForEach-Object {
    [ordered]@{
      name = $_.Name
      driver_version = $_.DriverVersion
      driver_date = if ($_.DriverDate) { ([datetime]$_.DriverDate).ToString("yyyy-MM-dd") } else { $null }
      pnp_device_id = $_.PNPDeviceID
      adapter_ram_reported_bytes = $_.AdapterRAM
      video_processor = $_.VideoProcessor
      status = $_.Status
    }
  })
  display_class_registry = $registryVideo
  vulkan = $vulkan
  system_hip_runtime = $hipRuntime
  notes = @(
    "The 8060S is an integrated GPU in unified memory; AdapterRAM and qwMemorySize report the dedicated UMA segment, not the GPU's usable memory.",
    "The gfx1151 architecture identifier is reported by the ROCm and Vulkan runtimes, see tools.llama_cpp in environment.json and evidence/IJ0/gpu/."
  )
}
Write-Evidence $gpuInventory "gpu_inventory.json"

# --- Dependency inventory --------------------------------------------------
$freeze = @()
$pipVersion = $null
$pythonVersion = $null
if (Test-Path $pythonExe) {
  $freeze = ((Invoke-Native $pythonExe @("-m", "pip", "freeze", "--disable-pip-version-check")).stdout -split "`r?`n") | Where-Object { $_ }
  $pipVersion = (Invoke-Native $pythonExe @("-m", "pip", "--version", "--disable-pip-version-check")).stdout
  $pythonVersion = (Invoke-Native $pythonExe @("-c", "import sys, platform; print(platform.platform()); print(sys.version)")).stdout
}
$rocmPython = Join-Path $llamaRoot "rocm-libs\Scripts\python.exe"
$rocmPackages = @()
if (Test-Path $rocmPython) {
  $rocmPackages = ((Invoke-Native $rocmPython @("-m", "pip", "freeze", "--disable-pip-version-check")).stdout -split "`r?`n") | Where-Object { $_ }
}
$lockPath = Join-Path $repoRoot "requirements.lock"
$dependencyInventory = [ordered]@{
  schema_version = 1
  collected_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
  collector = "scripts/windows/collect_environment.ps1"
  project_venv = [ordered]@{
    platform_and_version = $pythonVersion
    pip = $pipVersion
    packages = @($freeze)
  }
  rocm_runtime_venv = [ordered]@{
    present = (Test-Path $rocmPython)
    packages = @($rocmPackages)
  }
  requirements_lock = [ordered]@{
    present = (Test-Path $lockPath)
    sha256 = if (Test-Path $lockPath) { (Get-FileHash $lockPath -Algorithm SHA256).Hash.ToLower() } else { $null }
  }
}
Write-Evidence $dependencyInventory "dependency_inventory.json"
