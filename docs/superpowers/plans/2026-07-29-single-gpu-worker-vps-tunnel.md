# Single-GPU Worker VPS Tunnel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Kết nối RTX 5090 trên máy Windows hiện tại với Lush Media Video dưới vai trò `gpu1`, tự phục hồi ComfyUI/tunnel, đồng bộ local–GitHub–VPS và tạo runbook cho `gpu2`.

**Architecture:** Mỗi máy GPU chạy một ComfyUI local trên `127.0.0.1:8188` và một PowerShell supervisor. Supervisor duy trì reverse SSH tunnel tới một port riêng trên Docker gateway của VPS; FastAPI giữ một queue tuần tự cho mỗi worker và chọn worker online theo trạng thái rảnh, độ dài queue, rồi round-robin khi hòa.

**Tech Stack:** Python 3, FastAPI, `asyncio`, `unittest`, PowerShell 5.1, Windows Scheduled Tasks, OpenSSH, Docker Compose, SQLite.

## Global Constraints

- `origin/main` là source of truth cho production.
- Không public ComfyUI hoặc bind ComfyUI trên `0.0.0.0`.
- Không thay đổi API payload, SQLite schema, `DB_PATH`, `UPLOAD_DIR`, `WORKFLOW_ARCHIVE_DIR`, admin credentials hoặc `JWT_SECRET`.
- Giữ nguyên `deploy/.env` và toàn bộ `deploy/data/` khi cập nhật VPS.
- `gpu1` dùng local `127.0.0.1:8188` và remote VPS port `18188`.
- `gpu2` sau này dùng local `127.0.0.1:8188` và remote VPS port `18288`.
- Mỗi GPU chạy tối đa một job cùng lúc.
- Mọi PowerShell background process do script tạo phải dùng `-WindowStyle Hidden`.
- Không ghi private key, password, token hoặc nội dung secret env vào Git/log.

---

### Task 1: Bảo toàn thay đổi local và đồng bộ với `origin/main`

**Files:**

- Preserve: `comfyui_client.py`
- Preserve without restoring to production: `static/lush-logo-red.svg`
- Preserve without restoring to production: `FULLHD_6S_Loop_API.backup-20260307-174926.json`
- Preserve without restoring to production: `static/demo-login-covers/`
- Preserve without restoring to production: `static/lush-logo-red.ico`
- Preserve: `docs/superpowers/specs/2026-07-29-single-gpu-worker-vps-tunnel-design.md`
- Preserve: `docs/superpowers/plans/2026-07-29-single-gpu-worker-vps-tunnel.md`

**Interfaces:**

- Consumes: local `main`, fetched `origin/main`, dirty tracked/untracked files.
- Produces: rebased clean history plus named backup ref `backup/local-pre-gpu1-sync-20260729`.

- [ ] **Step 1: Ghi lại trạng thái trước đồng bộ**

Run:

```powershell
git status --short --branch
git rev-parse HEAD
git rev-parse origin/main
git diff --stat
```

Expected: local có hai file tracked đã sửa và các file untracked đã biết; không có secret env được track.

- [ ] **Step 2: Lưu toàn bộ thay đổi chưa commit vào stash và tạo ref backup**

Run:

```powershell
git stash push --include-untracked -m "backup local state before gpu1 sync 2026-07-29"
$backupCommit = git rev-parse "stash@{0}"
git branch backup/local-pre-gpu1-sync-20260729 $backupCommit
git show --stat --oneline backup/local-pre-gpu1-sync-20260729
```

Expected: working tree sạch; backup branch trỏ tới stash commit và giữ được cả parent chứa untracked files.

- [ ] **Step 3: Rebase các commit docs lên GitHub mới nhất**

Run:

```powershell
git fetch --prune origin
git rebase origin/main
git status --short --branch
```

Expected: `main` ahead `origin/main` bằng các commit docs, không còn behind và working tree sạch.

- [ ] **Step 4: Khôi phục riêng bản vá worker-release để review**

Run:

```powershell
git restore --source backup/local-pre-gpu1-sync-20260729 -- comfyui_client.py
git diff -- comfyui_client.py
```

Expected: chỉ phần polling ComfyUI history và fallback WebSocket xuất hiện; logo/demo/backup không quay lại working tree.

- [ ] **Step 5: Xác minh Python vẫn parse được trước khi tiếp tục**

Run:

```powershell
python -m py_compile auth.py config.py database.py models.py workflow_guard.py comfyui_client.py load_balancer.py main.py telegram_bot.py
```

Expected: exit code `0`.

---

### Task 2: Đặc tả bằng test việc chọn worker và giải phóng worker

**Files:**

- Create: `tests/test_load_balancer.py`
- Create: `tests/test_comfyui_client.py`
- Modify: `load_balancer.py`
- Modify: `comfyui_client.py`

**Interfaces:**

- Consumes: `LoadBalancer._select_server()`, ComfyUI history item.
- Produces: `_classify_history_item(item: dict) -> tuple[str, str | None] | None`; `_select_server()` trả `None` khi không có server online.

- [ ] **Step 1: Viết test fail cho least-load, round-robin và offline**

Create `tests/test_load_balancer.py`:

```python
import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from load_balancer import LoadBalancer, ServerQueue


def make_server(server_id: str, online: bool = True) -> ServerQueue:
    server = ServerQueue(
        {"id": server_id, "name": server_id.upper(), "url": f"http://{server_id}"}
    )
    server.is_online = online
    return server


class SelectServerTests(unittest.IsolatedAsyncioTestCase):
    async def test_round_robin_breaks_equal_load_ties(self):
        balancer = LoadBalancer()
        gpu1 = make_server("gpu1")
        gpu2 = make_server("gpu2")
        balancer.servers = [gpu1, gpu2]

        with patch.object(
            balancer, "_refresh_server_status", new=AsyncMock()
        ):
            first = await balancer._select_server()
            second = await balancer._select_server()

        self.assertIs(first, gpu1)
        self.assertIs(second, gpu2)

    async def test_idle_worker_wins_over_busy_worker(self):
        balancer = LoadBalancer()
        gpu1 = make_server("gpu1")
        gpu2 = make_server("gpu2")
        gpu1.current_job = "running-job"
        balancer.servers = [gpu1, gpu2]

        with patch.object(
            balancer, "_refresh_server_status", new=AsyncMock()
        ):
            selected = await balancer._select_server()

        self.assertIs(selected, gpu2)

    async def test_shorter_queue_wins_when_both_workers_busy(self):
        balancer = LoadBalancer()
        gpu1 = make_server("gpu1")
        gpu2 = make_server("gpu2")
        gpu1.current_job = "job-1"
        gpu2.current_job = "job-2"
        await gpu1.queue.put({"job_id": "queued-1"})
        balancer.servers = [gpu1, gpu2]

        with patch.object(
            balancer, "_refresh_server_status", new=AsyncMock()
        ):
            selected = await balancer._select_server()

        self.assertIs(selected, gpu2)

    async def test_returns_none_when_all_workers_are_offline(self):
        balancer = LoadBalancer()
        balancer.servers = [
            make_server("gpu1", online=False),
            make_server("gpu2", online=False),
        ]

        with patch.object(
            balancer, "_refresh_server_status", new=AsyncMock()
        ):
            selected = await balancer._select_server()

        self.assertIsNone(selected)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Viết test fail cho phân loại ComfyUI history terminal**

Create `tests/test_comfyui_client.py`:

```python
import unittest

from comfyui_client import _classify_history_item


class ClassifyHistoryItemTests(unittest.TestCase):
    def test_completed_history_is_done(self):
        self.assertEqual(
            _classify_history_item({"status": {"completed": True}}),
            ("done", None),
        )

    def test_outputs_are_done_when_completed_flag_is_missing(self):
        self.assertEqual(
            _classify_history_item({"status": {}, "outputs": {"9": {}}}),
            ("done", None),
        )

    def test_success_status_is_done(self):
        self.assertEqual(
            _classify_history_item({"status": {"status_str": "success"}}),
            ("done", None),
        )

    def test_error_status_is_not_reported_as_success(self):
        self.assertEqual(
            _classify_history_item(
                {
                    "status": {
                        "status_str": "error",
                        "messages": [["execution_error", {"exception_message": "OOM"}]],
                    }
                }
            ),
            ("error", "OOM"),
        )

    def test_active_history_is_not_terminal(self):
        self.assertIsNone(
            _classify_history_item({"status": {"status_str": "running"}})
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Chạy test để xác nhận fail đúng lý do**

Run:

```powershell
python -m unittest tests.test_load_balancer tests.test_comfyui_client -v
```

Expected: offline selection fail vì trả server offline; import `_classify_history_item` fail vì helper chưa tồn tại.

- [ ] **Step 4: Implement helper phân loại history**

Add to `comfyui_client.py` before `listen_progress()`:

```python
def _classify_history_item(item: dict) -> tuple[str, str | None] | None:
    status = item.get("status") or {}
    status_str = str(status.get("status_str", "")).strip().lower()
    if status_str in {"error", "failed"}:
        error = "ComfyUI execution failed"
        for message in status.get("messages") or []:
            if (
                isinstance(message, list)
                and len(message) > 1
                and isinstance(message[1], dict)
                and message[1].get("exception_message")
            ):
                error = str(message[1]["exception_message"])
                break
        return ("error", error)
    if status.get("completed") or status_str == "success" or bool(item.get("outputs")):
        return ("done", None)
    return None
```

Use this helper in both idle-timeout history polling and periodic `status` heartbeat polling. Return `{"status": "error", "error": error}` for an error classification and call `on_progress(100)` only for `done`.

- [ ] **Step 5: Không chọn server offline**

Change `LoadBalancer._select_server()`:

```python
ordered = [
    self.servers[(self._next_index + i) % len(self.servers)]
    for i in range(len(self.servers))
]
online = [server for server in ordered if server.is_online]
if not online:
    return None
server = min(
    online,
    key=lambda candidate: (
        1 if candidate.current_job else 0,
        candidate.queue.qsize(),
    ),
)
self._next_index = (self.servers.index(server) + 1) % len(self.servers)
return server
```

Change the submit error to:

```python
raise RuntimeError("No online ComfyUI servers available")
```

- [ ] **Step 6: Chạy test và syntax check**

Run:

```powershell
python -m unittest tests.test_load_balancer tests.test_comfyui_client -v
python -m py_compile comfyui_client.py load_balancer.py
```

Expected: tất cả test pass; syntax check exit `0`.

- [ ] **Step 7: Commit backend behavior**

Run:

```powershell
git add tests/test_load_balancer.py tests/test_comfyui_client.py load_balancer.py comfyui_client.py
git commit -m "fix: recover and schedule ComfyUI workers safely"
```

Expected: commit chỉ chứa bốn file trên.

---

### Task 3: Tạo PowerShell supervisor dùng chung cho mỗi máy GPU

**Files:**

- Create: `deploy/windows/comfyui-worker-common.ps1`
- Create: `deploy/windows/comfyui-worker-supervisor.ps1`
- Create: `deploy/windows/install-comfyui-worker-task.ps1`
- Create: `deploy/windows/worker.example.json`
- Create: `deploy/windows/tests/comfyui-worker-common.tests.ps1`

**Interfaces:**

- Consumes: worker JSON config, ComfyUI batch file, OpenSSH key.
- Produces: health-managed ComfyUI process, persistent reverse tunnel, Scheduled Task installer.

- [ ] **Step 1: Viết test fail cho config và backoff**

Create `deploy/windows/tests/comfyui-worker-common.tests.ps1`:

```powershell
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\..\comfyui-worker-common.ps1"

function Assert-Equal($Expected, $Actual, $Message) {
    if ($Expected -ne $Actual) {
        throw "$Message expected=[$Expected] actual=[$Actual]"
    }
}

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
} catch {
    $failed = $true
}
Assert-Equal $true $failed "invalid local port"

Write-Host "PASS comfyui-worker-common.tests.ps1"
```

- [ ] **Step 2: Chạy test để xác nhận fail vì common script chưa tồn tại**

Run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File deploy\windows\tests\comfyui-worker-common.tests.ps1
```

Expected: fail tại dot-source `comfyui-worker-common.ps1`.

- [ ] **Step 3: Implement common functions**

`deploy/windows/comfyui-worker-common.ps1` phải export các function:

```powershell
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
        "WorkerId", "ComfyDirectory", "BatchFile", "LocalPort", "CudaDevice",
        "RemoteHost", "RemoteBindAddress", "RemotePort", "PrivateKey",
        "RuntimeDirectory"
    )
    foreach ($name in $required) {
        if ($null -eq $Config.$name -or [string]::IsNullOrWhiteSpace([string]$Config.$name)) {
            throw "Missing worker config field: $name"
        }
    }
    foreach ($name in @("LocalPort", "RemotePort")) {
        $port = [int]$Config.$name
        if ($port -lt 1 -or $port -gt 65535) {
            throw "Invalid $name: $port"
        }
    }
    if ([int]$Config.CudaDevice -lt 0) {
        throw "Invalid CudaDevice: $($Config.CudaDevice)"
    }
}
```

Also implement `Read-WorkerConfig`, `Write-RotatingLog`, `Test-TcpPort`, and `Test-ComfyHealth`. `Write-RotatingLog` rotates one `.1` backup when the active log exceeds configured bytes.

- [ ] **Step 4: Chạy common tests**

Run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File deploy\windows\tests\comfyui-worker-common.tests.ps1
```

Expected: output `PASS comfyui-worker-common.tests.ps1`.

- [ ] **Step 5: Tạo config example không chứa secret**

Create `deploy/windows/worker.example.json`:

```json
{
  "WorkerId": "gpu1",
  "ComfyDirectory": "D:\\ComfyUI1",
  "BatchFile": "D:\\ComfyUI1\\run_nvidia_gpu.bat",
  "LocalPort": 8188,
  "CudaDevice": 0,
  "RemoteHost": "deploy@82.197.71.6",
  "RemoteBindAddress": "172.19.0.1",
  "RemotePort": 18188,
  "PrivateKey": "D:\\ComfyUI-Autostart\\gpu1_worker_ed25519",
  "RuntimeDirectory": "D:\\ComfyUI-Autostart",
  "HealthIntervalSeconds": 10,
  "HealthFailureThreshold": 3,
  "StartupGraceSeconds": 300,
  "SshBackoffBaseSeconds": 5,
  "SshBackoffMaxSeconds": 60,
  "LogMaxBytes": 10485760
}
```

- [ ] **Step 6: Implement supervisor**

`deploy/windows/comfyui-worker-supervisor.ps1` must:

- Accept mandatory `-ConfigPath`.
- Dot-source `comfyui-worker-common.ps1`.
- Lock the path built by `Join-Path $config.RuntimeDirectory "$($config.WorkerId).supervisor.lock"` using `FileShare.None`.
- Verify `nvidia-smi -L` contains `CudaDevice`.
- Detect only `python.exe` whose command line contains the configured `ComfyUI\main.py` and the exact string built from `"--port $($config.LocalPort)"`.
- Start ComfyUI using:

```powershell
Start-Process `
    -FilePath "$env:WINDIR\System32\cmd.exe" `
    -ArgumentList @(
        "/d", "/c",
        "call `"$($config.BatchFile)`" 1>>`"$comfyOutLog`" 2>>`"$comfyErrLog`""
    ) `
    -WorkingDirectory $config.ComfyDirectory `
    -WindowStyle Hidden `
    -PassThru
```

- Start SSH using:

```powershell
$tunnelArgs = @(
    "-N", "-T",
    "-i", $config.PrivateKey,
    "-o", "IdentitiesOnly=yes",
    "-o", "BatchMode=yes",
    "-o", "ExitOnForwardFailure=yes",
    "-o", "TCPKeepAlive=yes",
    "-o", "ServerAliveInterval=15",
    "-o", "ServerAliveCountMax=4",
    "-o", "StrictHostKeyChecking=accept-new",
    "-R", "$($config.RemoteBindAddress):$($config.RemotePort):127.0.0.1:$($config.LocalPort)",
    $config.RemoteHost
)
Start-Process `
    -FilePath "$env:WINDIR\System32\OpenSSH\ssh.exe" `
    -ArgumentList $tunnelArgs `
    -RedirectStandardError $sshErrLog `
    -WindowStyle Hidden `
    -PassThru
```

- Restart ComfyUI only after the configured startup grace and health-failure threshold.
- Restart tunnel independently using capped exponential backoff.
- Refuse to kill a process when executable path/command line/port do not match the managed ComfyUI.

- [ ] **Step 7: Implement Scheduled Task installer**

`deploy/windows/install-comfyui-worker-task.ps1` must accept:

```powershell
param(
    [Parameter(Mandatory)][string]$ConfigPath,
    [string]$TaskName = "LushMedia-ComfyUI-gpu1"
)
```

It must validate the config, create a startup action pointing to the tracked supervisor, register under `SYSTEM` with highest privileges, set restart count/interval, and never touch unrelated Scheduled Tasks.

- [ ] **Step 8: Parse-check all PowerShell files**

Run:

```powershell
$files = @(
    "deploy\windows\comfyui-worker-common.ps1",
    "deploy\windows\comfyui-worker-supervisor.ps1",
    "deploy\windows\install-comfyui-worker-task.ps1",
    "deploy\windows\tests\comfyui-worker-common.tests.ps1"
)
foreach ($file in $files) {
    $tokens = $null
    $errors = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile(
        (Resolve-Path $file),
        [ref]$tokens,
        [ref]$errors
    )
    if ($errors.Count) {
        throw ($errors | Out-String)
    }
}
```

Expected: no parser error.

- [ ] **Step 9: Commit Windows worker assets**

Run:

```powershell
git add deploy/windows
git commit -m "feat: add resilient Windows ComfyUI worker"
```

---

### Task 4: Thiết lập SSH key riêng và quyền reverse forwarding cho `gpu1`

**Files:**

- Create runtime: `D:\ComfyUI-Autostart\gpu1_worker_ed25519`
- Create runtime: `D:\ComfyUI-Autostart\gpu1_worker_ed25519.pub`
- Modify remote runtime: `/home/deploy/.ssh/authorized_keys`

**Interfaces:**

- Consumes: existing deploy SSH access and VPS OpenSSH configuration.
- Produces: dedicated `gpu1` key restricted to listener `172.19.0.1:18188`.

- [ ] **Step 1: Tạo bản key setup có ACL an toàn để audit VPS**

Run:

```powershell
$setupKey = Join-Path $env:TEMP "lush-vps-setup-ed25519"
Copy-Item -LiteralPath "D:\Tools\comfyui_vps_tunnel_ed25519" -Destination $setupKey
icacls $setupKey /inheritance:r
icacls $setupKey /grant:r "$($env:USERNAME):(F)"
ssh -i $setupKey -o IdentitiesOnly=yes -o BatchMode=yes deploy@82.197.71.6 "whoami; hostname"
```

Expected: output user `deploy`; không in private key.

- [ ] **Step 2: Audit Docker gateway, SSH reverse forwarding và port conflict**

Run through deploy SSH:

```bash
cd /opt/lush-media-video/app
git status --short --branch
git rev-parse HEAD
docker inspect lushvideo-app-1 --format '{{range $name,$network := .NetworkSettings.Networks}}{{$name}} gateway={{$network.Gateway}} ip={{$network.IPAddress}}{{println}}{{end}}'
ss -lnt | grep -E ':(18188|18288)[[:space:]]' || true
sshd -T 2>/dev/null | grep -E '^(allowtcpforwarding|gatewayports) ' || true
```

Expected: xác định gateway thật; port `18188` không bị listener ngoài kế hoạch chiếm; `AllowTcpForwarding` cho phép remote forwarding và `GatewayPorts` cho phép client-specified bind.

- [ ] **Step 3: Tạo key mới nếu chưa tồn tại**

Run:

```powershell
$workerKey = "D:\ComfyUI-Autostart\gpu1_worker_ed25519"
if (Test-Path -LiteralPath $workerKey) {
    throw "Refusing to overwrite existing worker key: $workerKey"
}
ssh-keygen -t ed25519 -N '""' -C "lush-gpu1@$env:COMPUTERNAME" -f $workerKey
ssh-keygen -lf "$workerKey.pub"
```

Expected: key ED25519 mới, fingerprint được ghi vào task note nhưng private key không bị đọc/in.

- [ ] **Step 4: Cài public key hạn chế trên VPS**

Build entry:

```powershell
$publicKey = (Get-Content -LiteralPath "$workerKey.pub" -Raw).Trim()
$authorizedEntry = 'restrict,port-forwarding,permitlisten="172.19.0.1:18188" ' + $publicKey
$entryBytes = [Text.Encoding]::UTF8.GetBytes($authorizedEntry)
$entryBase64 = [Convert]::ToBase64String($entryBytes)
```

Build and run the remote command without a plaintext temporary file:

```powershell
$remoteCommand = @"
set -eu
install -d -m 700 /home/deploy/.ssh
touch /home/deploy/.ssh/authorized_keys
chmod 600 /home/deploy/.ssh/authorized_keys
entry=`$(printf '%s' '$entryBase64' | base64 -d)
grep -qxF "`$entry" /home/deploy/.ssh/authorized_keys || printf '%s\n' "`$entry" >> /home/deploy/.ssh/authorized_keys
"@
ssh -i $setupKey -o IdentitiesOnly=yes -o BatchMode=yes deploy@82.197.71.6 $remoteCommand
```

- [ ] **Step 5: Khóa ACL private key cho Scheduled Task**

Run:

```powershell
icacls $workerKey /inheritance:r
icacls $workerKey /setowner "SYSTEM"
icacls $workerKey /grant:r "SYSTEM:(F)"
icacls $workerKey
```

Expected: private key chỉ SYSTEM truy cập; `.pub` có thể giữ quyền read thông thường.

---

### Task 5: Cài và xác minh worker `gpu1` trên máy hiện tại

**Files:**

- Create runtime: `D:\ComfyUI-Autostart\gpu1.worker.json`
- Modify runtime: Scheduled Task `LushMedia-ComfyUI-gpu1`
- Preserve: `D:\ComfyUI1\run_nvidia_gpu.bat`

**Interfaces:**

- Consumes: tracked supervisor, dedicated key, RTX 5090 index `0`.
- Produces: healthy ComfyUI listener `127.0.0.1:8188` và VPS listener `18188`.

- [ ] **Step 1: Tạo runtime config cho máy hiện tại**

Create `D:\ComfyUI-Autostart\gpu1.worker.json` with:

```json
{
  "WorkerId": "gpu1",
  "ComfyDirectory": "D:\\ComfyUI1",
  "BatchFile": "D:\\ComfyUI1\\run_nvidia_gpu.bat",
  "LocalPort": 8188,
  "CudaDevice": 0,
  "RemoteHost": "deploy@82.197.71.6",
  "RemoteBindAddress": "172.19.0.1",
  "RemotePort": 18188,
  "PrivateKey": "D:\\ComfyUI-Autostart\\gpu1_worker_ed25519",
  "RuntimeDirectory": "D:\\ComfyUI-Autostart",
  "HealthIntervalSeconds": 10,
  "HealthFailureThreshold": 3,
  "StartupGraceSeconds": 300,
  "SshBackoffBaseSeconds": 5,
  "SshBackoffMaxSeconds": 60,
  "LogMaxBytes": 10485760
}
```

If Task 4 discovers a different Docker gateway, use that verified value consistently in both runtime config and backend env.

- [ ] **Step 2: Xác nhận script cũ không còn chạy**

Run:

```powershell
Get-CimInstance Win32_Process |
    Where-Object {
        $_.CommandLine -match "start-comfyui-servers\.ps1|comfyui-vps-tunnel\.ps1|Start-ComfyUI-GPU[12]\.ps1"
    } |
    Select-Object ProcessId, Name, CommandLine
```

If results exist, stop only those exact process IDs after re-reading the command line. Do not kill all `powershell.exe`, `cmd.exe`, `python.exe`, or `ssh.exe`.

- [ ] **Step 3: Cài và start Scheduled Task**

Run from elevated PowerShell:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
    -File "D:\web app comfyui\comfyui_bot\deploy\windows\install-comfyui-worker-task.ps1" `
    -ConfigPath "D:\ComfyUI-Autostart\gpu1.worker.json" `
    -TaskName "LushMedia-ComfyUI-gpu1"
Start-ScheduledTask -TaskName "LushMedia-ComfyUI-gpu1"
```

- [ ] **Step 4: Poll local health có giới hạn**

Run:

```powershell
$deadline = (Get-Date).AddMinutes(8)
do {
    try {
        $response = Invoke-WebRequest `
            -UseBasicParsing `
            -Uri "http://127.0.0.1:8188/system_stats" `
            -TimeoutSec 8
        if ($response.StatusCode -eq 200) { break }
    } catch {}
    Start-Sleep -Seconds 10
} while ((Get-Date) -lt $deadline)
if (-not $response -or $response.StatusCode -ne 200) {
    throw "ComfyUI gpu1 did not become healthy within 8 minutes"
}
```

Expected: HTTP `200`.

- [ ] **Step 5: Xác minh task/process/log**

Run:

```powershell
Get-ScheduledTask -TaskName "LushMedia-ComfyUI-gpu1" | Select-Object TaskName,State
Get-ScheduledTaskInfo -TaskName "LushMedia-ComfyUI-gpu1" |
    Select-Object LastRunTime,LastTaskResult,NextRunTime
Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 8188 -State Listen
Get-Content -LiteralPath "D:\ComfyUI-Autostart\gpu1-watchdog.log" -Tail 50
Get-Content -LiteralPath "D:\ComfyUI-Autostart\gpu1-ssh-error.log" -Tail 50
```

Expected: task running, port `8188` listen, không có SSH permission/forward failure.

- [ ] **Step 6: Xác minh tunnel từ VPS**

Run through deploy SSH:

```bash
ss -lnt | grep ':18188 '
curl --fail --silent --show-error --max-time 10 http://172.19.0.1:18188/system_stats >/dev/null
docker exec lushvideo-app-1 python -c "import urllib.request; print(urllib.request.urlopen('http://172.19.0.1:18188/system_stats', timeout=10).status)"
```

Expected: listener `18188`, host curl success và container nhận HTTP `200`.

- [ ] **Step 7: Test recovery có kiểm soát**

Identify the managed SSH child PID from its exact command line, stop it, and verify a new PID appears while ComfyUI PID remains unchanged. Then stop only the managed ComfyUI Python PID and verify `/system_stats` returns `200` again within the configured recovery window.

Expected: tunnel và ComfyUI phục hồi độc lập; không có duplicate supervisor.

---

### Task 6: Push code và đồng bộ VPS về cùng commit

**Files:**

- Modify runtime: `/opt/lush-media-video/app/deploy/.env`
- Preserve runtime: `/opt/lush-media-video/app/deploy/data/`
- Deploy: `/opt/lush-media-video/app`

**Interfaces:**

- Consumes: tested local commits, working reverse tunnel.
- Produces: GitHub/VPS/container cùng commit và backend cấu hình `gpu1`.

- [ ] **Step 1: Chạy full local verification trước push**

Run:

```powershell
python -m unittest discover -s tests -v
python -m py_compile auth.py config.py database.py models.py workflow_guard.py comfyui_client.py load_balancer.py main.py telegram_bot.py
powershell.exe -NoProfile -ExecutionPolicy Bypass -File deploy\windows\tests\comfyui-worker-common.tests.ps1
git diff --check
git status --short --branch
```

Expected: test pass, syntax pass, chỉ file docs/memory dự kiến còn chưa commit.

- [ ] **Step 2: Push tested commits**

Run:

```powershell
git push origin main
git rev-parse HEAD
git rev-parse origin/main
```

Expected: hai commit hash giống nhau.

- [ ] **Step 3: Backup trạng thái VPS trước update**

Run through deploy SSH:

```bash
cd /opt/lush-media-video/app
mkdir -p deploy/backups/code-state
ts="$(date -u +%Y-%m-%dT%H-%M-%SZ)"
git status --short > "deploy/backups/code-state/status_${ts}.txt"
git diff > "deploy/backups/code-state/tracked_${ts}.patch"
cp -a deploy/.env "deploy/backups/code-state/env_${ts}.bak"
test -d deploy/data
du -sh deploy/data
```

Expected: backup files tồn tại và `deploy/data` được giữ nguyên.

- [ ] **Step 4: Cập nhật backend endpoint không làm lộ secret**

Remove prior ComfyUI endpoint keys and append one JSON endpoint:

```bash
cd /opt/lush-media-video/app
sed -i.bak-gpu1 \
  -e '/^COMFYUI_SERVERS_JSON=/d' \
  -e '/^COMFYUI_GPU1=/d' \
  -e '/^COMFYUI_GPU2=/d' \
  -e '/^COMFYUI_BASE_URL=/d' \
  deploy/.env
printf '%s\n' \
  'COMFYUI_SERVERS_JSON=[{"id":"gpu1","url":"http://172.19.0.1:18188","name":"GPU #1"}]' \
  >> deploy/.env
```

Use the gateway verified in Task 4 if it differs from `172.19.0.1`.

- [ ] **Step 5: Update checkout và rebuild**

Try:

```bash
cd /opt/lush-media-video/app
deploy/scripts/update_app.sh
```

If private GitHub fetch is unavailable, create a bundle locally:

```powershell
git bundle create "$env:TEMP\lush-media-video-main.bundle" main
scp -i $setupKey "$env:TEMP\lush-media-video-main.bundle" deploy@82.197.71.6:/tmp/lush-media-video-main.bundle
```

Then run remotely:

```bash
cd /opt/lush-media-video/app
BUNDLE_PATH=/tmp/lush-media-video-main.bundle deploy/scripts/update_app.sh
```

- [ ] **Step 6: Xác minh commit provenance và data**

Run:

```bash
cd /opt/lush-media-video/app
expected="$(git rev-parse HEAD)"
actual="$(docker inspect lushvideo-app-1 --format '{{range .Config.Env}}{{println .}}{{end}}' | sed -n 's/^APP_COMMIT=//p')"
test "$expected" = "$actual"
docker compose -f deploy/docker-compose.vps.yml --env-file deploy/.env ps
test -f deploy/data/comfybot.db
curl --fail --silent --show-error http://127.0.0.1:8011/ >/dev/null
```

Expected: commit khớp, container healthy, database và root route tồn tại.

---

### Task 7: Kiểm thử end-to-end trên production

**Files:**

- Read runtime: `/opt/lush-media-video/app/deploy/.env`
- Use test input: `/opt/lush-media-video/app/static/login-bg.jpg`

**Interfaces:**

- Consumes: live API, configured admin login, `gpu1`.
- Produces: một production smoke job có tên `codex-gpu1-smoke-20260729`.

- [ ] **Step 1: Xác minh auth và server status**

On VPS, source `deploy/.env` without echoing values, login through `127.0.0.1:8011`, extract the bearer token in memory, then call:

```bash
curl --fail --silent --show-error \
  -H "Authorization: Bearer ${token}" \
  http://127.0.0.1:8011/api/admin/servers
```

Expected: `gpu1` reports online and idle.

- [ ] **Step 2: Submit one real smoke job**

Run:

```bash
response="$(curl --fail --silent --show-error \
  -H "Authorization: Bearer ${token}" \
  -F "file=@static/login-bg.jpg;type=image/jpeg" \
  -F "job_name=codex-gpu1-smoke-20260729" \
  http://127.0.0.1:8011/api/jobs)"
job_id="$(printf '%s' "$response" | jq -r '.job_id')"
test -n "$job_id"
test "$job_id" != "null"
```

- [ ] **Step 3: Poll job tới terminal state**

Poll `GET /api/jobs/$job_id` every 15 seconds with a 45-minute deadline. Log only job ID prefix, status and progress; do not log bearer token.

Expected: `queued -> running -> done`, progress reaches `100`, output metadata exists and video download endpoint succeeds.

- [ ] **Step 4: Xác minh worker được giải phóng**

Submit a second named smoke job only after the first is `done`; confirm it changes from `queued` to `running` on `gpu1` without restarting the backend.

- [ ] **Step 5: Xác minh recovery app không tạo prompt trùng**

During a controlled queued/running test, record job ID and ComfyUI prompt ID, restart only `lushvideo-app-1`, then confirm:

- Database vẫn có cùng job ID.
- ComfyUI không có hai prompt cho cùng job.
- Backend either resumes monitoring the original prompt or safely requeues only after proving the original prompt inactive.

If a live production workload is present, defer this disruptive check and record the reason in the task note instead of restarting under user traffic.

---

### Task 8: Hoàn thiện project memory và runbook máy `gpu2`

**Files:**

- Create: `docs/modules/gpu-workers.md`
- Create/update during execution: `docs/tasks/active/single-gpu-worker-vps-tunnel.md`
- Modify: `docs/PROJECT_BRIEF.md`
- Modify: `docs/MEMORY_INDEX.md`
- Modify: `docs/DECISIONS_INDEX.md`
- Modify: `docs/DECISIONS.md`
- Modify: `docs/CHANGELOG.md`

**Interfaces:**

- Consumes: verified runtime values, commit IDs, Scheduled Task name, recovery results.
- Produces: canonical worker contract and handoff checklist for machine #2.

- [ ] **Step 1: Viết module memory**

`docs/modules/gpu-workers.md` must contain:

- Worker contract table for `gpu1:18188` and `gpu2:18288`.
- Local ComfyUI invariant `127.0.0.1:8188`, CUDA index `0` per machine.
- Supervisor/task names, log locations and health commands.
- VPS listener/container health commands.
- Key isolation rule: one private key per machine.
- Failure/recovery matrix.
- Rollback steps that disable only the named worker task and restore the backed-up VPS env.

- [ ] **Step 2: Cập nhật project routing**

Add `docs/modules/gpu-workers.md` to `docs/MEMORY_INDEX.md`; update `docs/PROJECT_BRIEF.md` runtime shape to describe per-machine workers and reverse SSH ports.

- [ ] **Step 3: Ghi quyết định active**

Add an active decision to `docs/DECISIONS_INDEX.md` and matching canonical detail to `docs/DECISIONS.md`:

```text
GPU-001: Mỗi máy GPU chạy một ComfyUI local và một reverse SSH tunnel riêng tới VPS; backend không public ComfyUI và chỉ thêm worker sau khi health check từ container thành công.
```

- [ ] **Step 4: Ghi changelog ngắn**

Append one dated entry to `docs/CHANGELOG.md` summarizing:

- single-GPU Windows supervisor,
- restricted reverse tunnel,
- backend offline/terminal-history behavior,
- production `gpu1` verification,
- `gpu2` handoff contract.

- [ ] **Step 5: Final verification**

Run:

```powershell
python -m unittest discover -s tests -v
python -m py_compile auth.py config.py database.py models.py workflow_guard.py comfyui_client.py load_balancer.py main.py telegram_bot.py
powershell.exe -NoProfile -ExecutionPolicy Bypass -File deploy\windows\tests\comfyui-worker-common.tests.ps1
git diff --check
git status --short --branch
```

Also re-run local `/system_stats`, VPS listener, container-to-worker health, public root page, auth, jobs and admin servers checks.

- [ ] **Step 6: Commit docs and close active task note**

Commit the canonical docs and short changelog. Remove or archive `docs/tasks/active/single-gpu-worker-vps-tunnel.md` once no follow-up work remains.

Run:

```powershell
git add docs
git commit -m "docs: document GPU worker operations"
git push origin main
```

Expected: local/GitHub/VPS/container end on the same final commit after one final VPS update/redeploy.
