$ErrorActionPreference = "Stop"
. "$PSScriptRoot\..\comfyui-worker-common.ps1"

function Assert-True($Actual, $Message) {
    if (-not $Actual) {
        throw "$Message expected true"
    }
}

$supervisorPath = Join-Path $PSScriptRoot "..\comfyui-worker-supervisor.ps1"
$installerPath = Join-Path $PSScriptRoot "..\install-comfyui-worker-task.ps1"
$visibleInstallerPath = Join-Path $PSScriptRoot "..\install-comfyui-worker-visible-launcher.ps1"
$visibleLauncherPath = Join-Path $PSScriptRoot "..\start-comfyui-worker-visible.bat"
$examplePath = Join-Path $PSScriptRoot "..\worker.example.json"

foreach ($path in @(
    $supervisorPath,
    $installerPath,
    $visibleInstallerPath,
    $visibleLauncherPath,
    $examplePath
)) {
    Assert-True (Test-Path -LiteralPath $path -PathType Leaf) "required worker asset $path"
}

foreach ($path in @($supervisorPath, $installerPath, $visibleInstallerPath)) {
    $tokens = $null
    $errors = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile(
        (Resolve-Path -LiteralPath $path),
        [ref]$tokens,
        [ref]$errors
    )
    Assert-True ($errors.Count -eq 0) "PowerShell parser errors in $path"
}

$supervisor = Get-Content -LiteralPath $supervisorPath -Raw
Assert-True ($supervisor.Contains("[System.IO.FileShare]::None")) "single-instance file lock"
Assert-True ($supervisor.Contains("-WindowStyle Hidden")) "hidden background processes"
Assert-True ($supervisor.Contains("[switch]`$Interactive")) "interactive supervisor switch"
Assert-True ($supervisor.Contains("-NoNewWindow")) "interactive ComfyUI shares visible console"
Assert-True ($supervisor.Contains("Get-TunnelArguments")) "shared tunnel contract"
Assert-True ($supervisor.Contains("Get-ManagedComfyProcess")) "guarded process discovery"

$installer = Get-Content -LiteralPath $installerPath -Raw
Assert-True ($installer.Contains('UserId "SYSTEM"')) "SYSTEM scheduled task"
Assert-True ($installer.Contains("-LogonType ServiceAccount")) "service-account logon"
Assert-True ($installer.Contains("-RunLevel Highest")) "elevated scheduled task"
Assert-True ($installer.Contains("New-ScheduledTaskTrigger -AtStartup")) "startup trigger"

$visibleInstaller = Get-Content -LiteralPath $visibleInstallerPath -Raw
Assert-True ($visibleInstaller.Contains("Disable-ScheduledTask")) "legacy task is disabled"
Assert-True ($visibleInstaller.Contains("CreateShortcut")) "Startup shortcut is created"
Assert-True ($visibleInstaller.Contains("Get-ComfyProcessesForDirectory")) "only configured ComfyUI processes are stopped"
Assert-True ($visibleInstaller.Contains("queue_running")) "running queue is checked"
Assert-True ($visibleInstaller.Contains("queue_pending")) "pending queue is checked"
Assert-True ($visibleInstaller.Contains("takeown.exe")) "SYSTEM-only private key ownership is recovered"
Assert-True ($visibleInstaller.Contains("/inheritance:r")) "private-key inherited ACL is removed"
Assert-True ($visibleInstaller.Contains("SYSTEM:(F)")) "SYSTEM retains private-key access"

$visibleLauncher = Get-Content -LiteralPath $visibleLauncherPath -Raw
Assert-True ($visibleLauncher.Contains("-Interactive")) "visible launcher selects interactive mode"

$generatedLauncher = New-VisibleLauncherContent `
    -VisibleLauncherPath "D:\repo path\start-comfyui-worker-visible.bat" `
    -ConfigPath "D:\runtime path\gpu1.worker.json"
Assert-True `
    ($generatedLauncher.Contains('"D:\repo path\start-comfyui-worker-visible.bat"')) `
    "generated launcher quotes repo path"
Assert-True `
    ($generatedLauncher.Contains('"D:\runtime path\gpu1.worker.json"')) `
    "generated launcher quotes config path"

$config = Read-WorkerConfig -Path $examplePath
Assert-True ($config.WorkerId -eq "gpu1") "example worker id"
Assert-True ($config.LocalPort -eq 8188) "example local port"
Assert-True ($config.RemotePort -eq 18188) "example remote port"

$explicitExampleConfig = Get-Content -LiteralPath $examplePath -Raw |
    ConvertFrom-Json
Assert-True `
    ($null -ne $explicitExampleConfig.PSObject.Properties["LaunchGuardSeconds"]) `
    "example explicitly documents launch guard"
Assert-True `
    ($explicitExampleConfig.LaunchGuardSeconds -eq 30) `
    "example launch guard value"

Write-Host "PASS comfyui-worker-scripts.tests.ps1"
