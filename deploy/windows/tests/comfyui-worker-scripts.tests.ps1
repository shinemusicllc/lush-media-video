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
$visibleGuardPath = Join-Path $PSScriptRoot "..\comfyui-worker-visible-guard.ps1"
$examplePath = Join-Path $PSScriptRoot "..\worker.example.json"

foreach ($path in @(
    $supervisorPath,
    $installerPath,
    $visibleInstallerPath,
    $visibleLauncherPath,
    $visibleGuardPath,
    $examplePath
)) {
    Assert-True (Test-Path -LiteralPath $path -PathType Leaf) "required worker asset $path"
}

foreach ($path in @(
    $supervisorPath,
    $installerPath,
    $visibleInstallerPath,
    $visibleGuardPath
)) {
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
Assert-True ($visibleInstaller.Contains("-LogonType Interactive")) "guard uses interactive user token"
Assert-True ($visibleInstaller.Contains("-RestartCount 999")) "guard task restarts after failure"
Assert-True ($visibleInstaller.Contains("Start-ScheduledTask")) "guard task starts after install"

$visibleGuard = Get-Content -LiteralPath $visibleGuardPath -Raw
Assert-True ($visibleGuard.Contains("[System.IO.FileShare]::None")) "guard is single-instance"
Assert-True ($visibleGuard.Contains("Get-InteractiveWorkerSupervisor")) "guard detects visible supervisor"
Assert-True `
    ($visibleGuard.Contains('-notmatch "(?i)(?:^|\s)-(?:Command|EncodedCommand)')) `
    "guard ignores diagnostic PowerShell commands"
Assert-True ($visibleGuard.Contains("Stop-ScopedOrphanTunnel")) "guard scopes orphan tunnel cleanup"
Assert-True ($visibleGuard.Contains("Stop-IdleOrphanComfy")) "guard scopes idle ComfyUI cleanup"
Assert-True ($visibleGuard.Contains("Starting a new visible worker window")) "guard relaunches visible window"
Assert-True ($visibleGuard.Contains("-WindowStyle Normal")) "guard opens a normal visible window"
Assert-True ($visibleGuard.Contains('"call"')) "guard supports quoted batch paths with spaces"

$visibleLauncher = Get-Content -LiteralPath $visibleLauncherPath -Raw
Assert-True ($visibleLauncher.Contains("-Interactive")) "visible launcher selects interactive mode"

$generatedLauncher = New-VisibleLauncherContent `
    -GuardTaskName "LushMedia-ComfyUI-gpu1-VisibleGuard"
Assert-True `
    ($generatedLauncher.Contains(
        'schtasks.exe /Run /TN "LushMedia-ComfyUI-gpu1-VisibleGuard"'
    )) `
    "generated launcher starts guard task"

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
