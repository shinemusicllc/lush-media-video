$ErrorActionPreference = "Stop"
. "$PSScriptRoot\..\comfyui-worker-common.ps1"

function Assert-Equal($Expected, $Actual, $Message) {
    if ($Expected -ne $Actual) {
        throw "$Message expected=[$Expected] actual=[$Actual]"
    }
}

function Assert-True($Actual, $Message) {
    if (-not $Actual) {
        throw "$Message expected true"
    }
}

$testRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("lush-worker-tests-" + [guid]::NewGuid())
New-Item -ItemType Directory -Path $testRoot | Out-Null

try {
    Assert-Equal 5 (Get-BackoffSeconds -FailureCount 0 -BaseSeconds 5 -MaxSeconds 60) "initial backoff"
    Assert-Equal 20 (Get-BackoffSeconds -FailureCount 2 -BaseSeconds 5 -MaxSeconds 60) "exponential backoff"
    Assert-Equal 60 (Get-BackoffSeconds -FailureCount 10 -BaseSeconds 5 -MaxSeconds 60) "capped backoff"

    $valid = [pscustomobject]@{
        WorkerId = "gpu1"
        ComfyDirectory = "D:\ComfyUI1"
        BatchFile = "D:\ComfyUI1\run_nvidia_gpu.bat"
        LocalPort = 8188
        CudaDevice = 0
        RemoteHost = "deploy@82.197.71.6"
        RemoteBindAddress = "172.19.0.1"
        RemotePort = 18188
        PrivateKey = "D:\ComfyUI-Autostart\gpu1_worker_ed25519"
        RuntimeDirectory = "D:\ComfyUI-Autostart"
    }
    Assert-WorkerConfig -Config $valid

    $invalid = $valid.PSObject.Copy()
    $invalid.LocalPort = 0
    $failed = $false
    try {
        Assert-WorkerConfig -Config $invalid
    }
    catch {
        $failed = $true
    }
    Assert-Equal $true $failed "invalid local port"

    $configPath = Join-Path $testRoot "worker.json"
    [System.IO.File]::WriteAllText(
        $configPath,
        ($valid | ConvertTo-Json),
        [System.Text.UTF8Encoding]::new($false)
    )
    $loaded = Read-WorkerConfig -Path $configPath
    Assert-Equal "gpu1" $loaded.WorkerId "config worker id"
    Assert-Equal 10 $loaded.HealthIntervalSeconds "default health interval"
    Assert-Equal 10485760 $loaded.LogMaxBytes "default log size"

    $correctProcess = [pscustomobject]@{
        ProcessId = 100
        CommandLine = "python ComfyUI\main.py --cuda-device 0 --port 8188"
    }
    $wrongPortProcess = [pscustomobject]@{
        ProcessId = 200
        CommandLine = "python ComfyUI\main.py --cuda-device 0 --port 8288"
    }
    $duplicateProcess = [pscustomobject]@{
        ProcessId = 300
        CommandLine = "python ComfyUI\main.py --cuda-device 0 --port 8188"
    }
    Assert-Equal 8188 (Get-ComfyProcessPort -Process $correctProcess) "parse correct port"
    Assert-Equal 8288 (Get-ComfyProcessPort -Process $wrongPortProcess) "parse wrong port"

    $processPlan = Get-ComfyProcessPlan `
        -Processes @($correctProcess, $wrongPortProcess, $duplicateProcess) `
        -LocalPort 8188
    Assert-Equal 100 $processPlan.KeepProcess.ProcessId "keep one expected process"
    Assert-Equal `
        "200,300" `
        (($processPlan.StopProcesses.ProcessId | Sort-Object) -join ",") `
        "stop wrong-port and duplicate processes"

    $wrongOnlyPlan = Get-ComfyProcessPlan `
        -Processes @($wrongPortProcess) `
        -LocalPort 8188
    Assert-Equal $null $wrongOnlyPlan.KeepProcess "wrong-port process is not managed"
    Assert-Equal 200 $wrongOnlyPlan.StopProcesses[0].ProcessId "wrong-port process is stopped"

    $wrongBatchPath = Join-Path $testRoot "wrong-port.bat"
    [System.IO.File]::WriteAllText(
        $wrongBatchPath,
        ".\python_embeded\python.exe -s ComfyUI\main.py --cuda-device 0 --port 8288"
    )
    $batchRejected = $false
    try {
        Assert-ComfyBatchContract `
            -BatchFile $wrongBatchPath `
            -LocalPort 8188 `
            -CudaDevice 0
    }
    catch {
        $batchRejected = $true
    }
    Assert-True $batchRejected "batch with mismatched port is rejected"

    $validBatchPath = Join-Path $testRoot "valid.bat"
    [System.IO.File]::WriteAllText(
        $validBatchPath,
        ".\python_embeded\python.exe -s ComfyUI\main.py --cuda-device 0 --port 8188"
    )
    Assert-ComfyBatchContract `
        -BatchFile $validBatchPath `
        -LocalPort 8188 `
        -CudaDevice 0

    $logPath = Join-Path $testRoot "worker.log"
    [System.IO.File]::WriteAllText($logPath, ("x" * 64))
    Write-RotatingLog -Path $logPath -Message "rotated" -MaxBytes 32
    Assert-True (Test-Path -LiteralPath "$logPath.1") "rotated log exists"
    Assert-True ((Get-Content -LiteralPath $logPath -Raw).Contains("rotated")) "new log contains message"

    $listener = [System.Net.Sockets.TcpListener]::new(
        [System.Net.IPAddress]::Loopback,
        0
    )
    $listener.Start()
    $openPort = ([System.Net.IPEndPoint]$listener.LocalEndpoint).Port
    Assert-Equal $true (Test-TcpPort -HostName "127.0.0.1" -Port $openPort -TimeoutMs 1000) "open tcp port"
    $listener.Stop()
    Assert-Equal $false (Test-TcpPort -HostName "127.0.0.1" -Port $openPort -TimeoutMs 200) "closed tcp port"

    Assert-Equal $false (Test-ComfyHealth -Port $openPort -TimeoutSeconds 1) "closed health endpoint"

    $tunnelArgs = Get-TunnelArguments -Config $valid
    Assert-True ($tunnelArgs -contains "172.19.0.1:18188:127.0.0.1:8188") "tunnel forwarding argument"
    Assert-True ($tunnelArgs -contains "deploy@82.197.71.6") "tunnel remote argument"
    Assert-True ($tunnelArgs -contains "UserKnownHostsFile=D:\ComfyUI-Autostart\known_hosts") "isolated known hosts file"

    $missingProcess = Get-ManagedComfyProcess `
        -ComfyDirectory "D:\path-that-does-not-exist" `
        -LocalPort 65534
    Assert-Equal $null $missingProcess "unknown process is not managed"

    Write-Host "PASS comfyui-worker-common.tests.ps1"
}
finally {
    if (Test-Path -LiteralPath $testRoot) {
        Remove-Item -LiteralPath $testRoot -Recurse -Force
    }
}
