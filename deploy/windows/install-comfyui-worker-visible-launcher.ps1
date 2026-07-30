param(
    [Parameter(Mandatory)]
    [string]$ConfigPath,

    [string]$TaskName = "",

    [string]$LauncherName = "",

    [string]$GuardTaskName = ""
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\comfyui-worker-common.ps1"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principalCheck = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principalCheck.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run this installer from an elevated PowerShell session"
}

$resolvedConfig = (Resolve-Path -LiteralPath $ConfigPath).Path
$config = Read-WorkerConfig -Path $resolvedConfig
$visibleLauncherPath = Join-Path $PSScriptRoot "start-comfyui-worker-visible.bat"
$visibleGuardPath = Join-Path $PSScriptRoot "comfyui-worker-visible-guard.ps1"

foreach ($requiredPath in @(
    $visibleLauncherPath,
    $visibleGuardPath,
    (Join-Path $PSScriptRoot "comfyui-worker-supervisor.ps1"),
    $config.ComfyDirectory,
    $config.BatchFile,
    $config.PrivateKey
)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "Required worker path not found: $requiredPath"
    }
}

if (-not $TaskName) {
    $TaskName = "LushMedia-ComfyUI-$($config.WorkerId)"
}
if (-not $LauncherName) {
    $LauncherName = "START LushMedia $($config.WorkerId.ToUpperInvariant()).bat"
}
if (-not $GuardTaskName) {
    $GuardTaskName = "$TaskName-VisibleGuard"
}

$interactiveSupervisor = Get-CimInstance Win32_Process `
    -Filter "Name = 'powershell.exe'" `
    -ErrorAction SilentlyContinue |
    Where-Object {
        $commandLine = [string]$_.CommandLine
        $commandLine -match "comfyui-worker-supervisor\.ps1" -and
        $commandLine -match [regex]::Escape($resolvedConfig) -and
        $commandLine -match "(?:^|\s)-Interactive(?:\s|$)"
    } |
    Select-Object -First 1

$managedComfy = Get-ManagedComfyProcess `
    -ComfyDirectory $config.ComfyDirectory `
    -LocalPort $config.LocalPort
if ($managedComfy) {
    try {
        $queue = Invoke-RestMethod `
            -Uri "http://127.0.0.1:$($config.LocalPort)/queue" `
            -TimeoutSec 10
    }
    catch {
        throw "Cannot verify ComfyUI queue before runtime migration: $($_.Exception.Message)"
    }

    $runningCount = @($queue.queue_running).Count
    $pendingCount = @($queue.queue_pending).Count
    if ($runningCount -gt 0 -or $pendingCount -gt 0) {
        throw "Refusing runtime migration while queue_running=$runningCount queue_pending=$pendingCount"
    }
}

$legacyTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($legacyTask) {
    if ($legacyTask.State -ne "Disabled") {
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    }
    Disable-ScheduledTask -TaskName $TaskName | Out-Null
}

if (-not $interactiveSupervisor) {
    foreach ($process in @(
        Get-ComfyProcessesForDirectory -ComfyDirectory $config.ComfyDirectory
    )) {
        $verifiedProcess = Get-ComfyProcessesForDirectory `
            -ComfyDirectory $config.ComfyDirectory |
            Where-Object { $_.ProcessId -eq $process.ProcessId } |
            Select-Object -First 1
        if ($verifiedProcess) {
            Stop-Process -Id $verifiedProcess.ProcessId -Force
        }
    }
}

$takeownPath = "$env:SystemRoot\System32\takeown.exe"
$icaclsPath = "$env:SystemRoot\System32\icacls.exe"
& $takeownPath /F $config.PrivateKey | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Failed to take ownership of private key: $($config.PrivateKey)"
}
& $icaclsPath `
    $config.PrivateKey `
    "/inheritance:r" `
    "/grant:r" `
    "SYSTEM:(F)" `
    "$($identity.Name):(R)" |
    Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Failed to grant private-key read access to $($identity.Name)"
}

$desktopDirectory = [Environment]::GetFolderPath("Desktop")
$startupDirectory = [Environment]::GetFolderPath("Startup")
if (-not $desktopDirectory -or -not $startupDirectory) {
    throw "Cannot resolve Desktop or Startup directory for $($identity.Name)"
}

$desktopLauncherPath = Join-Path $desktopDirectory $LauncherName
$launcherContent = New-VisibleLauncherContent `
    -GuardTaskName $GuardTaskName
[System.IO.File]::WriteAllText(
    $desktopLauncherPath,
    $launcherContent,
    [System.Text.Encoding]::ASCII
)

$shortcutPath = Join-Path `
    $startupDirectory `
    ("LushMedia-ComfyUI-$($config.WorkerId).lnk")
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $desktopLauncherPath
$shortcut.WorkingDirectory = $desktopDirectory
$shortcut.WindowStyle = 1
$shortcut.Description = "Visible LushMedia $($config.WorkerId) ComfyUI supervisor"
$shortcut.Save()

$guardArguments = (
    "-NoLogo -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden " +
    "-File `"$visibleGuardPath`" " +
    "-ConfigPath `"$resolvedConfig`" " +
    "-VisibleLauncherPath `"$visibleLauncherPath`""
)
$guardAction = New-ScheduledTaskAction `
    -Execute "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
    -Argument $guardArguments `
    -WorkingDirectory $PSScriptRoot
$guardTrigger = New-ScheduledTaskTrigger -AtLogOn -User $identity.Name
$guardPrincipal = New-ScheduledTaskPrincipal `
    -UserId $identity.Name `
    -LogonType Interactive `
    -RunLevel Highest
$guardSettings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero)

$existingGuardTask = Get-ScheduledTask `
    -TaskName $GuardTaskName `
    -ErrorAction SilentlyContinue
if ($existingGuardTask -and $existingGuardTask.State -eq "Running") {
    Stop-ScheduledTask -TaskName $GuardTaskName
    Start-Sleep -Seconds 1
}
Register-ScheduledTask `
    -TaskName $GuardTaskName `
    -Action $guardAction `
    -Trigger $guardTrigger `
    -Principal $guardPrincipal `
    -Settings $guardSettings `
    -Description "Keeps the visible LushMedia $($config.WorkerId) worker window alive" `
    -Force |
    Out-Null
Start-ScheduledTask -TaskName $GuardTaskName

Write-Host "Installed Desktop launcher: $desktopLauncherPath"
Write-Host "Installed Startup shortcut: $shortcutPath"
Write-Host "Disabled legacy Scheduled Task: $TaskName"
Write-Host "Started interactive visible guard task: $GuardTaskName"
Write-Host "The guard reopens the worker window if it or its supervisor exits."
