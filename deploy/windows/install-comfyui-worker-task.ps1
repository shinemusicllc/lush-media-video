param(
    [Parameter(Mandatory)]
    [string]$ConfigPath,

    [string]$TaskName = "LushMedia-ComfyUI-gpu1"
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
$supervisorPath = Join-Path $PSScriptRoot "comfyui-worker-supervisor.ps1"

foreach ($requiredPath in @(
    $supervisorPath,
    $config.ComfyDirectory,
    $config.BatchFile,
    $config.PrivateKey
)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "Required worker path not found: $requiredPath"
    }
}

$powershellPath = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$arguments = (
    '-NoProfile -ExecutionPolicy Bypass -File "{0}" -ConfigPath "{1}"' -f
    $supervisorPath,
    $resolvedConfig
)

$action = New-ScheduledTaskAction `
    -Execute $powershellPath `
    -Argument $arguments `
    -WorkingDirectory $PSScriptRoot
$trigger = New-ScheduledTaskTrigger -AtStartup
$taskPrincipal = New-ScheduledTaskPrincipal `
    -UserId "SYSTEM" `
    -LogonType ServiceAccount `
    -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([timespan]::Zero) `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Principal $taskPrincipal `
    -Settings $settings `
    -Description "Lush Media $($config.WorkerId) ComfyUI and reverse SSH supervisor" `
    -Force |
    Out-Null

Write-Host "Installed Scheduled Task: $TaskName"
