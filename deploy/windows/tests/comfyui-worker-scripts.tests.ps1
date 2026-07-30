$ErrorActionPreference = "Stop"
. "$PSScriptRoot\..\comfyui-worker-common.ps1"

function Assert-True($Actual, $Message) {
    if (-not $Actual) {
        throw "$Message expected true"
    }
}

$supervisorPath = Join-Path $PSScriptRoot "..\comfyui-worker-supervisor.ps1"
$installerPath = Join-Path $PSScriptRoot "..\install-comfyui-worker-task.ps1"
$examplePath = Join-Path $PSScriptRoot "..\worker.example.json"

foreach ($path in @($supervisorPath, $installerPath, $examplePath)) {
    Assert-True (Test-Path -LiteralPath $path -PathType Leaf) "required worker asset $path"
}

foreach ($path in @($supervisorPath, $installerPath)) {
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
Assert-True ($supervisor.Contains("Get-TunnelArguments")) "shared tunnel contract"
Assert-True ($supervisor.Contains("Get-ManagedComfyProcess")) "guarded process discovery"

$installer = Get-Content -LiteralPath $installerPath -Raw
Assert-True ($installer.Contains('UserId "SYSTEM"')) "SYSTEM scheduled task"
Assert-True ($installer.Contains("-LogonType ServiceAccount")) "service-account logon"
Assert-True ($installer.Contains("-RunLevel Highest")) "elevated scheduled task"
Assert-True ($installer.Contains("New-ScheduledTaskTrigger -AtStartup")) "startup trigger"

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
