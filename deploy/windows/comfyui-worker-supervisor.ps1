param(
    [Parameter(Mandatory)]
    [string]$ConfigPath
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\comfyui-worker-common.ps1"

$config = Read-WorkerConfig -Path $ConfigPath
New-Item -ItemType Directory -Path $config.RuntimeDirectory -Force | Out-Null

$watchdogLog = Join-Path $config.RuntimeDirectory "$($config.WorkerId)-watchdog.log"
$comfyOutLog = Join-Path $config.RuntimeDirectory "$($config.WorkerId)-comfy-output.log"
$comfyErrLog = Join-Path $config.RuntimeDirectory "$($config.WorkerId)-comfy-error.log"
$sshErrLog = Join-Path $config.RuntimeDirectory "$($config.WorkerId)-ssh-error.log"
$lockPath = Join-Path $config.RuntimeDirectory "$($config.WorkerId).supervisor.lock"

try {
    $script:LockStream = [System.IO.File]::Open(
        $lockPath,
        [System.IO.FileMode]::OpenOrCreate,
        [System.IO.FileAccess]::ReadWrite,
        [System.IO.FileShare]::None
    )
}
catch {
    Write-RotatingLog `
        -Path $watchdogLog `
        -Message "Another $($config.WorkerId) supervisor is already running; exiting" `
        -MaxBytes $config.LogMaxBytes
    exit 0
}

foreach ($requiredPath in @(
    $config.ComfyDirectory,
    $config.BatchFile,
    $config.PrivateKey
)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "Required worker path not found: $requiredPath"
    }
}

$sshExecutable = "$env:SystemRoot\System32\OpenSSH\ssh.exe"
$nvidiaSmi = "$env:SystemRoot\System32\nvidia-smi.exe"
if (-not (Test-Path -LiteralPath $sshExecutable -PathType Leaf)) {
    throw "OpenSSH client not found: $sshExecutable"
}
if (-not (Test-Path -LiteralPath $nvidiaSmi -PathType Leaf)) {
    throw "nvidia-smi not found: $nvidiaSmi"
}

$gpuLines = & $nvidiaSmi -L 2>$null
$gpuCount = @($gpuLines | Where-Object { $_ -match "^GPU\s+\d+:" }).Count
if ($gpuCount -le [int]$config.CudaDevice) {
    throw "CUDA device $($config.CudaDevice) is unavailable; visible device count=$gpuCount"
}

$tunnelArguments = Get-TunnelArguments -Config $config
$forwardSpec = "$($config.RemoteBindAddress):$($config.RemotePort):127.0.0.1:$($config.LocalPort)"
$existingTunnel = Get-CimInstance Win32_Process `
    -Filter "Name = 'ssh.exe'" `
    -ErrorAction SilentlyContinue |
    Where-Object {
        $commandLine = [string]$_.CommandLine
        $commandLine.Contains([string]$config.PrivateKey) -and
        $commandLine.Contains($forwardSpec) -and
        $commandLine.Contains([string]$config.RemoteHost)
    } |
    Select-Object -First 1

$tunnelProcess = $null
if ($existingTunnel) {
    $tunnelProcess = Get-Process -Id $existingTunnel.ProcessId -ErrorAction SilentlyContinue
}

$comfyFailures = 0
$tunnelFailures = 0
$lastComfyStart = [datetime]::MinValue
$lastTunnelStart = [datetime]::MinValue
$nextTunnelStart = [datetime]::MinValue

Write-RotatingLog `
    -Path $watchdogLog `
    -Message "$($config.WorkerId) supervisor started for CUDA $($config.CudaDevice)" `
    -MaxBytes $config.LogMaxBytes

while ($true) {
    try {
        $managedComfy = Get-ManagedComfyProcess `
            -ComfyDirectory $config.ComfyDirectory `
            -LocalPort $config.LocalPort
        $healthOk = Test-ComfyHealth `
            -Port $config.LocalPort `
            -TimeoutSeconds 8

        if ($healthOk -and $managedComfy) {
            if ($comfyFailures -gt 0) {
                Write-RotatingLog `
                    -Path $watchdogLog `
                    -Message "ComfyUI recovered on port $($config.LocalPort)" `
                    -MaxBytes $config.LogMaxBytes
            }
            $comfyFailures = 0
        }
        elseif ($healthOk -and -not $managedComfy) {
            Write-RotatingLog `
                -Path $watchdogLog `
                -Message "Refusing unmanaged healthy process on port $($config.LocalPort)" `
                -MaxBytes $config.LogMaxBytes
        }
        elseif ($managedComfy) {
            $startupAge = ((Get-Date) - $lastComfyStart).TotalSeconds
            if ($startupAge -ge [int]$config.StartupGraceSeconds) {
                $comfyFailures += 1
                Write-RotatingLog `
                    -Path $watchdogLog `
                    -Message "ComfyUI health failed ($comfyFailures/$($config.HealthFailureThreshold))" `
                    -MaxBytes $config.LogMaxBytes

                if ($comfyFailures -ge [int]$config.HealthFailureThreshold) {
                    $verifiedComfy = Get-ManagedComfyProcess `
                        -ComfyDirectory $config.ComfyDirectory `
                        -LocalPort $config.LocalPort
                    if ($verifiedComfy -and $verifiedComfy.ProcessId -eq $managedComfy.ProcessId) {
                        Write-RotatingLog `
                            -Path $watchdogLog `
                            -Message "Stopping unresponsive ComfyUI pid=$($verifiedComfy.ProcessId)" `
                            -MaxBytes $config.LogMaxBytes
                        Stop-Process -Id $verifiedComfy.ProcessId -Force
                        Start-Sleep -Seconds 3
                    }
                    $comfyFailures = 0
                    $lastComfyStart = [datetime]::MinValue
                }
            }
        }
        else {
            if (Test-TcpPort -HostName "127.0.0.1" -Port $config.LocalPort -TimeoutMs 500) {
                Write-RotatingLog `
                    -Path $watchdogLog `
                    -Message "Refusing to start ComfyUI because port $($config.LocalPort) is owned by an unmanaged process" `
                    -MaxBytes $config.LogMaxBytes
            }
            else {
                foreach ($path in @($comfyOutLog, $comfyErrLog)) {
                    if (
                        (Test-Path -LiteralPath $path -PathType Leaf) -and
                        (Get-Item -LiteralPath $path).Length -ge [int64]$config.LogMaxBytes
                    ) {
                        $rotatedPath = "$path.1"
                        if (Test-Path -LiteralPath $rotatedPath) {
                            Remove-Item -LiteralPath $rotatedPath -Force
                        }
                        Move-Item -LiteralPath $path -Destination $rotatedPath
                    }
                }

                Write-RotatingLog `
                    -Path $watchdogLog `
                    -Message "Starting ComfyUI on CUDA $($config.CudaDevice), port $($config.LocalPort)" `
                    -MaxBytes $config.LogMaxBytes
                Start-Process `
                    -FilePath "$env:WINDIR\System32\cmd.exe" `
                    -ArgumentList @(
                        "/d",
                        "/c",
                        "call `"$($config.BatchFile)`" 1>>`"$comfyOutLog`" 2>>`"$comfyErrLog`""
                    ) `
                    -WorkingDirectory $config.ComfyDirectory `
                    -WindowStyle Hidden `
                    -PassThru |
                    Out-Null
                $lastComfyStart = Get-Date
                $comfyFailures = 0
            }
        }
    }
    catch {
        Write-RotatingLog `
            -Path $watchdogLog `
            -Message "ComfyUI supervisor error: $($_.Exception.Message)" `
            -MaxBytes $config.LogMaxBytes
    }

    try {
        $managedComfy = Get-ManagedComfyProcess `
            -ComfyDirectory $config.ComfyDirectory `
            -LocalPort $config.LocalPort
        $comfyReady = $managedComfy -and (
            Test-ComfyHealth -Port $config.LocalPort -TimeoutSeconds 8
        )

        if ($tunnelProcess -and $tunnelProcess.HasExited) {
            $tunnelFailures += 1
            $delay = Get-BackoffSeconds `
                -FailureCount ($tunnelFailures - 1) `
                -BaseSeconds $config.SshBackoffBaseSeconds `
                -MaxSeconds $config.SshBackoffMaxSeconds
            $nextTunnelStart = (Get-Date).AddSeconds($delay)
            Write-RotatingLog `
                -Path $watchdogLog `
                -Message "Tunnel exited code=$($tunnelProcess.ExitCode); retry in ${delay}s" `
                -MaxBytes $config.LogMaxBytes
            $tunnelProcess = $null
        }

        if (
            $comfyReady -and
            -not $tunnelProcess -and
            (Get-Date) -ge $nextTunnelStart
        ) {
            Write-RotatingLog `
                -Path $watchdogLog `
                -Message "Starting reverse tunnel $forwardSpec" `
                -MaxBytes $config.LogMaxBytes
            $tunnelProcess = Start-Process `
                -FilePath $sshExecutable `
                -ArgumentList $tunnelArguments `
                -RedirectStandardError $sshErrLog `
                -WindowStyle Hidden `
                -PassThru
            $lastTunnelStart = Get-Date
        }
        elseif (
            $tunnelProcess -and
            -not $tunnelProcess.HasExited -and
            ((Get-Date) - $lastTunnelStart).TotalSeconds -ge 60
        ) {
            $tunnelFailures = 0
        }
    }
    catch {
        Write-RotatingLog `
            -Path $watchdogLog `
            -Message "Tunnel supervisor error: $($_.Exception.Message)" `
            -MaxBytes $config.LogMaxBytes
        $tunnelProcess = $null
    }

    Start-Sleep -Seconds ([int]$config.HealthIntervalSeconds)
}
