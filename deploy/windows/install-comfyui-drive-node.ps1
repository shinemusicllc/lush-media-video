param(
    [Parameter(Mandatory = $true)]
    [string]$ComfyDirectory
)

$ErrorActionPreference = 'Stop'
$ComfyDirectory = [System.IO.Path]::GetFullPath($ComfyDirectory)
$Python = Join-Path $ComfyDirectory 'python_embeded\python.exe'
$ComfyQueueUrl = 'http://127.0.0.1:8188/queue'
$SourceDirectory = Join-Path $PSScriptRoot '..\comfyui_nodes\lush_drive_image'
$TargetDirectory = Join-Path $ComfyDirectory 'custom_nodes\lush_drive_image'

if (-not (Test-Path -LiteralPath $ComfyDirectory -PathType Container)) {
    throw "ComfyUI directory does not exist: $ComfyDirectory"
}
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Portable ComfyUI Python was not found: $Python"
}
if (-not (Test-Path -LiteralPath (Join-Path $SourceDirectory 'drive_image_loader.py') -PathType Leaf)) {
    throw "Drive node source is missing: $SourceDirectory"
}

try {
    $queue = Invoke-RestMethod -Uri $ComfyQueueUrl -TimeoutSec 5
    $running = @($queue.queue_running).Count
    $pending = @($queue.queue_pending).Count
    if ($running -gt 0 -or $pending -gt 0) {
        throw "ComfyUI queue is not empty (running=$running, pending=$pending). Wait for all jobs to finish before installing."
    }
} catch {
    if ($_.Exception.Message -like 'ComfyUI queue is not empty*') { throw }
    Write-Warning 'ComfyUI queue could not be queried; verify no jobs are running before continuing.'
}

& $Python -m pip install --disable-pip-version-check 'gdown>=5.2,<6'
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install gdown into the ComfyUI Python runtime (exit $LASTEXITCODE)."
}

New-Item -ItemType Directory -Path $TargetDirectory -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $SourceDirectory '__init__.py') -Destination $TargetDirectory -Force
Copy-Item -LiteralPath (Join-Path $SourceDirectory 'drive_image_loader.py') -Destination $TargetDirectory -Force

Write-Host "Installed LushLoadImageFromDrive into $TargetDirectory"
Write-Host 'Restart ComfyUI after all running and queued jobs have finished.'
