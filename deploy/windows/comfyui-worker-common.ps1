function Get-BackoffSeconds {
    param(
        [int]$FailureCount,
        [int]$BaseSeconds,
        [int]$MaxSeconds
    )

    $value = [int]($BaseSeconds * [math]::Pow(2, [math]::Max(0, $FailureCount)))
    return [math]::Min($value, $MaxSeconds)
}


function Assert-WorkerConfig {
    param([Parameter(Mandatory)]$Config)

    $required = @(
        "WorkerId",
        "ComfyDirectory",
        "BatchFile",
        "LocalPort",
        "CudaDevice",
        "RemoteHost",
        "RemoteBindAddress",
        "RemotePort",
        "PrivateKey",
        "RuntimeDirectory"
    )
    foreach ($name in $required) {
        if (
            $null -eq $Config.$name -or
            [string]::IsNullOrWhiteSpace([string]$Config.$name)
        ) {
            throw "Missing worker config field: $name"
        }
    }

    foreach ($name in @("LocalPort", "RemotePort")) {
        $port = [int]$Config.$name
        if ($port -lt 1 -or $port -gt 65535) {
            throw "Invalid ${name}: $port"
        }
    }
    if ([int]$Config.CudaDevice -lt 0) {
        throw "Invalid CudaDevice: $($Config.CudaDevice)"
    }
}


function Read-WorkerConfig {
    param([Parameter(Mandatory)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Worker config not found: $Path"
    }
    $config = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json

    $defaults = [ordered]@{
        HealthIntervalSeconds = 10
        HealthFailureThreshold = 3
        StartupGraceSeconds = 300
        SshBackoffBaseSeconds = 5
        SshBackoffMaxSeconds = 60
        LogMaxBytes = 10485760
    }
    foreach ($entry in $defaults.GetEnumerator()) {
        if ($null -eq $config.PSObject.Properties[$entry.Key]) {
            $config | Add-Member `
                -NotePropertyName $entry.Key `
                -NotePropertyValue $entry.Value
        }
    }

    Assert-WorkerConfig -Config $config
    return $config
}


function Write-RotatingLog {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$Message,
        [int64]$MaxBytes = 10485760
    )

    $directory = Split-Path -Parent $Path
    if ($directory -and -not (Test-Path -LiteralPath $directory)) {
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }

    if (
        (Test-Path -LiteralPath $Path -PathType Leaf) -and
        (Get-Item -LiteralPath $Path).Length -ge $MaxBytes
    ) {
        $rotatedPath = "$Path.1"
        if (Test-Path -LiteralPath $rotatedPath) {
            Remove-Item -LiteralPath $rotatedPath -Force
        }
        Move-Item -LiteralPath $Path -Destination $rotatedPath
    }

    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -LiteralPath $Path -Value "[$stamp] $Message" -Encoding UTF8
}


function Test-TcpPort {
    param(
        [Parameter(Mandatory)][string]$HostName,
        [Parameter(Mandatory)][int]$Port,
        [int]$TimeoutMs = 1000
    )

    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $asyncResult = $client.BeginConnect($HostName, $Port, $null, $null)
        if (-not $asyncResult.AsyncWaitHandle.WaitOne($TimeoutMs)) {
            return $false
        }
        $client.EndConnect($asyncResult)
        return $true
    }
    catch {
        return $false
    }
    finally {
        $client.Dispose()
    }
}


function Test-ComfyHealth {
    param(
        [Parameter(Mandatory)][int]$Port,
        [int]$TimeoutSeconds = 8
    )

    try {
        $response = Invoke-WebRequest `
            -UseBasicParsing `
            -Uri "http://127.0.0.1:$Port/system_stats" `
            -TimeoutSec $TimeoutSeconds
        return $response.StatusCode -eq 200
    }
    catch {
        return $false
    }
}


function Get-TunnelArguments {
    param([Parameter(Mandatory)]$Config)

    Assert-WorkerConfig -Config $Config
    return @(
        "-N",
        "-T",
        "-i",
        [string]$Config.PrivateKey,
        "-o",
        "IdentitiesOnly=yes",
        "-o",
        "BatchMode=yes",
        "-o",
        "ExitOnForwardFailure=yes",
        "-o",
        "TCPKeepAlive=yes",
        "-o",
        "ServerAliveInterval=15",
        "-o",
        "ServerAliveCountMax=4",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        "UserKnownHostsFile=$($Config.RuntimeDirectory)\known_hosts",
        "-R",
        "$($Config.RemoteBindAddress):$($Config.RemotePort):127.0.0.1:$($Config.LocalPort)",
        [string]$Config.RemoteHost
    )
}


function Get-ManagedComfyProcess {
    param(
        [Parameter(Mandatory)][string]$ComfyDirectory,
        [Parameter(Mandatory)][int]$LocalPort
    )

    $expectedRoot = [System.IO.Path]::GetFullPath($ComfyDirectory).
        TrimEnd("\").
        ToLowerInvariant()
    $portPattern = "--port\s+$LocalPort(?:\s|$)"

    return Get-CimInstance Win32_Process `
        -Filter "Name = 'python.exe'" `
        -ErrorAction SilentlyContinue |
        Where-Object {
            $commandLine = [string]$_.CommandLine
            $executablePath = [string]$_.ExecutablePath
            $commandLine -match "ComfyUI\\main\.py" -and
            $commandLine -match $portPattern -and
            $executablePath.ToLowerInvariant().StartsWith($expectedRoot)
        } |
        Select-Object -First 1
}
