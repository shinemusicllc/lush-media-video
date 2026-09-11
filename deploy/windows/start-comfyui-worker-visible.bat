@echo off
setlocal

if "%~1"=="" (
    echo Missing worker config path.
    echo Usage: %~nx0 D:\ComfyUI-Autostart\gpu1.worker.json
    pause
    exit /b 2
)

title LushMedia ComfyUI Worker
echo ============================================================
echo LushMedia ComfyUI visible worker
echo Keep this window open. Close it only when stopping the worker.
echo ============================================================
echo.

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0comfyui-worker-supervisor.ps1" -ConfigPath "%~1" -Interactive
set "WORKER_EXIT_CODE=%ERRORLEVEL%"

echo.
echo Worker supervisor stopped with exit code %WORKER_EXIT_CODE%.
echo Double-click the Desktop launcher again to restart it.
pause
exit /b %WORKER_EXIT_CODE%
