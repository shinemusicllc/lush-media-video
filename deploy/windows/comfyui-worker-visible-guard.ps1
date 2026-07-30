param(
    [Parameter(Mandatory)]
    [string]$ConfigPath,

    [Parameter(Mandatory)]
    [string]$VisibleLauncherPath,

    [int]$PollSeconds = 5
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\comfyui-worker-common.ps1"

$resolvedConfig = (Resolve-Path -LiteralPath $ConfigPath).Path
$resolvedVisibleLauncher = (Resolve-Path -LiteralPath $VisibleLauncherPath).Path
$config = Read-WorkerConfig -Path $resolvedConfig
New-Item -ItemType Directory -Path $config.RuntimeDirectory -Force | Out-Null

$guardLog = Join-Path `
    $config.RuntimeDirectory `
    "$($config.WorkerId)-visible-guard.log"
$guardLockPath = Join-Path `
    $config.RuntimeDirectory `
    "$($config.WorkerId).visible-guard.lock"
$supervisorScriptName = "comfyui-worker-supervisor.ps1"
$desktopLauncherName = "START LushMedia $($config.WorkerId.ToUpperInvariant()).bat"
$forwardSpec = (
    "$($config.RemoteBindAddress):$($config.RemotePort):" +
    "127.0.0.1:$($config.LocalPort)"
)

try {
    $script:GuardLockStream = [System.IO.File]::Open(
        $guardLockPath,
        [System.IO.FileMode]::OpenOrCreate,
        [System.IO.FileAccess]::ReadWrite,
        [System.IO.FileShare]::None
    )
}
catch {
    exit 0
}

function Get-InteractiveWorkerSupervisor {
    return @(
        Get-CimInstance Win32_Process `
            -Filter "Name = 'powershell.exe'" `
            -ErrorAction SilentlyContinue |
            Where-Object {
                $commandLine = [string]$_.CommandLine
                $commandLine -match "(?i)^\s*`"?[^`"]*powershell\.exe`"?\s+" -and
                $commandLine -notmatch "(?i)(?:^|\s)-(?:Command|EncodedCommand)(?:\s|$)" -and
                $commandLine -match "(?i)(?:^|\s)-File\s+" -and
                $commandLine -match [regex]::Escape($supervisorScriptName) -and
                $commandLine -match [regex]::Escape($resolvedConfig) -and
                $commandLine -match "(?:^|\s)-Interactive(?:\s|$)"
            }
    )
}

function Stop-ScopedOrphanTunnel {
    foreach ($process in @(
        Get-CimInstance Win32_Process `
            -Filter "Name = 'ssh.exe'" `
            -ErrorAction SilentlyContinue |
            Where-Object {
                $commandLine = [string]$_.CommandLine
                $commandLine.Contains([string]$config.PrivateKey) -and
                $commandLine.Contains($forwardSpec) -and
                $commandLine.Contains([string]$config.RemoteHost)
            }
    )) {
        $verified = Get-CimInstance Win32_Process `
            -Filter "ProcessId = $($process.ProcessId)" `
            -ErrorAction SilentlyContinue
        if (
            $verified -and
            $verified.Name -eq "ssh.exe" -and
            ([string]$verified.CommandLine).Contains($forwardSpec)
        ) {
            Write-RotatingLog `
                -Path $guardLog `
                -Message "Stopping orphan tunnel pid=$($verified.ProcessId)" `
                -MaxBytes $config.LogMaxBytes
            Stop-Process -Id $verified.ProcessId -Force
        }
    }
}

function Stop-IdleOrphanComfy {
    $managedComfy = Get-ManagedComfyProcess `
        -ComfyDirectory $config.ComfyDirectory `
        -LocalPort $config.LocalPort
    if (-not $managedComfy) {
        return
    }

    try {
        $queue = Invoke-RestMethod `
            -Uri "http://127.0.0.1:$($config.LocalPort)/queue" `
            -TimeoutSec 10
    }
    catch {
        Write-RotatingLog `
            -Path $guardLog `
            -Message "Preserving orphan ComfyUI because queue state is unavailable" `
            -MaxBytes $config.LogMaxBytes
        return
    }

    if (
        @($queue.queue_running).Count -gt 0 -or
        @($queue.queue_pending).Count -gt 0
    ) {
        Write-RotatingLog `
            -Path $guardLog `
            -Message "Preserving orphan ComfyUI while its queue is active" `
            -MaxBytes $config.LogMaxBytes
        return
    }

    foreach ($process in @(
        Get-ComfyProcessesForDirectory -ComfyDirectory $config.ComfyDirectory
    )) {
        $verified = Get-ComfyProcessesForDirectory `
            -ComfyDirectory $config.ComfyDirectory |
            Where-Object { $_.ProcessId -eq $process.ProcessId } |
            Select-Object -First 1
        if ($verified) {
            Write-RotatingLog `
                -Path $guardLog `
                -Message "Stopping idle orphan ComfyUI pid=$($verified.ProcessId)" `
                -MaxBytes $config.LogMaxBytes
            Stop-Process -Id $verified.ProcessId -Force
        }
    }
}

function Stop-StaleVisibleShell {
    foreach ($process in @(
        Get-CimInstance Win32_Process `
            -Filter "Name = 'cmd.exe'" `
            -ErrorAction SilentlyContinue |
            Where-Object {
                $commandLine = [string]$_.CommandLine
                $commandLine -match [regex]::Escape($desktopLauncherName) -or
                $commandLine -match [regex]::Escape($resolvedVisibleLauncher)
            }
    )) {
        $verified = Get-CimInstance Win32_Process `
            -Filter "ProcessId = $($process.ProcessId)" `
            -ErrorAction SilentlyContinue
        if ($verified -and $verified.Name -eq "cmd.exe") {
            Stop-Process -Id $verified.ProcessId -Force
        }
    }
}

function Start-VisibleWorkerWindow {
    Write-RotatingLog `
        -Path $guardLog `
        -Message "Starting a new visible worker window" `
        -MaxBytes $config.LogMaxBytes
    Start-Process `
        -FilePath "$env:WINDIR\System32\cmd.exe" `
        -ArgumentList @(
            "/d",
            "/c",
            "call",
            "`"$resolvedVisibleLauncher`"",
            "`"$resolvedConfig`""
        ) `
        -WorkingDirectory $PSScriptRoot `
        -WindowStyle Normal `
        -PassThru |
        Out-Null
}

$lastLaunchAttempt = [datetime]::MinValue
Write-RotatingLog `
    -Path $guardLog `
    -Message "$($config.WorkerId) visible guard started" `
    -MaxBytes $config.LogMaxBytes

try {
    while ($true) {
        $supervisors = @(Get-InteractiveWorkerSupervisor)
        if (
            $supervisors.Count -eq 0 -and
            (Test-ComfyLaunchAllowed `
                -LastLaunchAttempt $lastLaunchAttempt `
                -Now (Get-Date) `
                -LaunchGuardSeconds $config.LaunchGuardSeconds)
        ) {
            Stop-ScopedOrphanTunnel
            Stop-IdleOrphanComfy
            Stop-StaleVisibleShell
            Start-VisibleWorkerWindow
            $lastLaunchAttempt = Get-Date
        }
        Start-Sleep -Seconds $PollSeconds
    }
}
finally {
    if ($script:GuardLockStream) {
        $script:GuardLockStream.Dispose()
    }
}
