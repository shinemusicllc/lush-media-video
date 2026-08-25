# GPU Workers

## Responsibility

- Run one ComfyUI process on each Windows GPU machine.
- Keep ComfyUI and its reverse SSH tunnel alive independently.
- Give the VPS backend a private, stable URL for each worker.
- Detect offline workers before scheduling; prefer idle workers and use
  round-robin as the final tie-breaker.
- This module does not expose ComfyUI directly to the public Internet and does
  not own job persistence.

## Runtime Contract

| Worker | Windows GPU | Local bind | VPS reverse bind | Backend env |
| --- | --- | --- | --- | --- |
| `gpu1` | CUDA `0` on machine 1 | `127.0.0.1:8188` | `172.19.0.1:18188` | `COMFYUI_GPU1=http://172.19.0.1:18188` |
| `gpu2` | CUDA `0` on machine 2 | `127.0.0.1:8188` | `172.19.0.1:18288` | `COMFYUI_GPU2=http://172.19.0.1:18288` |

`172.19.0.1` is the current `lushvideo_default` Docker gateway. Before adding a
worker, verify it on the VPS:

```bash
docker network inspect lushvideo_default \
  --format '{{(index .IPAM.Config 0).Gateway}}'
```

If the gateway changes, update the worker `RemoteBindAddress` and all matching
`COMFYUI_GPU*` values together.

## Entry Points

- Supervisor:
  `deploy/windows/comfyui-worker-supervisor.ps1 -ConfigPath <worker.json> [-Interactive]`
- Scheduled Task installer:
  `deploy/windows/install-comfyui-worker-task.ps1`
- Visible Desktop/Startup installer:
  `deploy/windows/install-comfyui-worker-visible-launcher.ps1`
- Visible batch entrypoint:
  `deploy/windows/start-comfyui-worker-visible.bat`
- Visible window guard:
  `deploy/windows/comfyui-worker-visible-guard.ps1`
- Backend scheduler: `load_balancer.py`
- ComfyUI WebSocket/history handling: `comfyui_client.py`

## Key Files

- `deploy/windows/comfyui-worker-common.ps1`
- `deploy/windows/comfyui-worker-supervisor.ps1`
- `deploy/windows/install-comfyui-worker-task.ps1`
- `deploy/windows/worker.example.json`
- `deploy/windows/tests/`
- Runtime-only config, keys, and logs: `D:\ComfyUI-Autostart\`

## GPU1 Current State

- Config: `D:\ComfyUI-Autostart\gpu1.worker.json`
- Scheduled Task: `LushMedia-ComfyUI-gpu1`, retained but disabled.
- Desktop launcher:
  `C:\Users\Admin\Desktop\START LushMedia GPU1.bat`
- Startup shortcut:
  `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\LushMedia-ComfyUI-gpu1.lnk`
- Runtime owner: interactive `Admin` session after Windows login.
- ComfyUI directory/batch:
  `D:\ComfyUI1` / `D:\ComfyUI1\run_nvidia_gpu.bat`
- Private key: `D:\ComfyUI-Autostart\gpu1_worker_ed25519`
- Public-key fingerprint:
  `SHA256:fI5xR8u8k4NsoFNpjy5xLEFqLTgEIhTOm+oOSmwDuw0`
- VPS key restriction:
  `restrict,port-forwarding,permitlisten="172.19.0.1:18188"`

The key file remains restricted and grants read access only to the identities
that run the worker (`SYSTEM` for rollback and the explicit interactive
account). Do not grant broad `Users`/`Everyone` access.

## Visible Launcher Mode

GPU1 uses visible launcher mode so a non-technical operator can inspect the
ComfyUI output and recover the worker by double-clicking one Desktop file.

Install from elevated PowerShell only while the queue is empty:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\deploy\windows\install-comfyui-worker-visible-launcher.ps1 `
  -ConfigPath 'D:\ComfyUI-Autostart\gpu1.worker.json' `
  -TaskName 'LushMedia-ComfyUI-gpu1'
```

The installer:

- refuses migration while `queue_running` or `queue_pending` is non-empty;
- stops and disables the legacy `SYSTEM` Scheduled Task;
- stops only ComfyUI processes rooted in the configured `ComfyDirectory`;
- grants private-key read access to the exact interactive Windows identity;
- creates `START LushMedia GPU1.bat` on Desktop and one Startup shortcut.
- registers a hidden per-user `*-VisibleGuard` task with an interactive logon
  token and restart-on-failure settings.

The guard starts the same singleton supervisor with `-Interactive`. ComfyUI
shares that console through `-NoNewWindow`, so native output remains visible.
If ComfyUI crashes, the supervisor restarts it in the same window. If the
whole worker window or supervisor exits, the independent per-user guard opens
a new visible window automatically. The Desktop batch asks the guard task to
run and remains the manual recovery entrypoint.

On 2026-07-30, GPU1 recovery kept guard PID `3040` and replaced visible shell,
supervisor, ComfyUI and tunnel PIDs `4812/6500/10824/13448` with
`16460/17388/6148/13856`. The guard logged one launch, restored one loopback
listener on `8188`, left `8288` closed and returned queue `0/0` with HTTP 200.
The recovered ComfyUI command line contained `--disable-auto-launch`.

Visible mode starts only after the Windows user logs in. It does not make the
worker available at the pre-login screen. Never enable the legacy Scheduled
Task at the same time as the visible launcher.

## GPU2 Current State

- Config: `D:\ComfyUI-Autostart\gpu2.worker.json`
- Scheduled Task: `LushMedia-ComfyUI-gpu2`, chạy dưới `SYSTEM`
- ComfyUI directory: `D:\ComfyUI2`
- Local bind: `127.0.0.1:8188`; không có listener `8288`
- Reverse bind: `172.19.0.1:18288`
- Máy đã nâng lên 128 GB RAM.
- Ngày 2026-07-30, cold và warm job 61 frame đều `success`, dùng cùng một
  ComfyUI PID. RAM available thấp nhất lần lượt là 69.708 GiB và 77.548 GiB;
  Codex private memory cao nhất chỉ 1.262 GiB.
- Cold job có `cached_nodes=0`; warm job đổi seed, tạo MP4 với SHA-256 khác.
  Cả hai dùng tiled VAE `512/64/16/4`, không crash hoặc restart watchdog.
- Stale VPS SSH child giữ port `18288` đã được kết thúc có chọn lọc. Supervisor
  tự bind tunnel mới; local, VPS host và app container đều trả HTTP 200.

## GPU2 Handoff

Perform these steps from machine 2 after cloning/pulling `origin/main`.

1. Confirm `nvidia-smi -L` sees the RTX 5090 and ComfyUI starts manually on
   CUDA `0`.
2. Copy `deploy/windows/worker.example.json` to a runtime-only file such as
   `D:\ComfyUI-Autostart\gpu2.worker.json`.
3. Set:
   - `WorkerId`: `gpu2`
   - `ComfyDirectory` and `BatchFile`: the real machine-2 paths
   - `CudaDevice`: `0`
   - `LocalPort`: `8188`
   - `RemoteBindAddress`: the verified Docker gateway
   - `RemotePort`: `18288`
   - `PrivateKey`: `D:\ComfyUI-Autostart\gpu2_worker_ed25519`
4. Generate a new, unique key; never copy GPU1's private key:

   ```powershell
   New-Item -ItemType Directory -Path 'D:\ComfyUI-Autostart' -Force
   ssh-keygen -t ed25519 `
     -f 'D:\ComfyUI-Autostart\gpu2_worker_ed25519' `
     -C 'lush-gpu2' `
     -N '""'
   ```

5. Add only the `.pub` line to `/home/deploy/.ssh/authorized_keys` on the VPS
   with:

   ```text
   restrict,port-forwarding,permitlisten="172.19.0.1:18288" <gpu2-public-key>
   ```

6. Tighten the private-key ACL so the Scheduled Task `SYSTEM` account can read
   it and ordinary local users cannot.
7. Choose exactly one runtime mode. For the same visible/manual recovery
   behavior as GPU1, run:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass `
     -File .\deploy\windows\install-comfyui-worker-visible-launcher.ps1 `
     -ConfigPath 'D:\ComfyUI-Autostart\gpu2.worker.json' `
     -TaskName 'LushMedia-ComfyUI-gpu2'
   ```

   Then double-click `START LushMedia GPU2.bat` on Desktop. If pre-login
   startup is required instead, keep the legacy Scheduled Task mode:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass `
     -File .\deploy\windows\install-comfyui-worker-task.ps1 `
     -ConfigPath 'D:\ComfyUI-Autostart\gpu2.worker.json' `
     -TaskName 'LushMedia-ComfyUI-gpu2'

   Start-ScheduledTask -TaskName 'LushMedia-ComfyUI-gpu2'
   ```

8. Verify locally:

   ```powershell
   Invoke-WebRequest http://127.0.0.1:8188/system_stats -UseBasicParsing
   Get-ScheduledTaskInfo -TaskName 'LushMedia-ComfyUI-gpu2'
   Get-Content 'D:\ComfyUI-Autostart\gpu2-watchdog.log' -Tail 30
   ```

9. Verify from both the VPS host and app container:

   ```bash
   curl -fsS http://172.19.0.1:18288/system_stats >/dev/null
   docker exec lushvideo-app-1 \
     python -c "import urllib.request; print(urllib.request.urlopen('http://172.19.0.1:18288/system_stats', timeout=10).status)"
   ```

10. Add
    `COMFYUI_GPU2=http://172.19.0.1:18288` to `deploy/.env`, redeploy only
    while both ComfyUI queues are empty, then verify `/api/servers`.

## Operations

- Queue:
  `Invoke-RestMethod http://127.0.0.1:8188/queue`
- GPU:
  `nvidia-smi --query-gpu=index,memory.used,memory.free,utilization.gpu --format=csv`
- Logs:
  `D:\ComfyUI-Autostart\<worker>-watchdog.log`,
  `<worker>-comfy-output.log`, `<worker>-comfy-error.log`,
  `<worker>-ssh-error.log`
- The supervisor uses one file lock, refuses unmanaged processes on the worker
  port, rotates logs, restarts unhealthy ComfyUI, and reconnects SSH with
  bounded backoff.
- Workers perform the local half of tunnel recovery: they check their local
  ComfyUI endpoint and `ssh.exe`; a missing/exited tunnel is retried with
  `ServerAliveInterval=15` and `ServerAliveCountMax=4`. The VPS performs the
  remote half with `lush-media-reverse-tunnel-watchdog.timer`: after two failed
  reverse health probes it terminates only the verified stale `sshd: deploy`
  listener, causing the worker supervisor to reconnect without restarting
  ComfyUI.
- In interactive mode, ComfyUI output goes to the visible console instead of
  `gpuN-comfy-output.log`/`gpuN-comfy-error.log`; watchdog and SSH error logs
  remain available in the runtime directory.
- The batch `--port` and `--cuda-device` values must match worker config or the
  supervisor refuses to start.
- The supervisor reconciles every ComfyUI process under `ComfyDirectory`,
  including wrong-port or duplicate processes, and keeps only one process on
  `LocalPort`.
- `LaunchGuardSeconds=30` prevents repeated batch launches while Python is
  still forming after a restart.
- Never restart a worker or redeploy the VPS app while its ComfyUI queue has a
  running or pending job.

## Failure Semantics

- An offline worker is excluded from new assignments.
- Uploads tolerate slow VPS-to-worker routes for up to 600 seconds and retry one
  transport failure from byte zero. While a worker owns an active job, a
  transient `/system_stats` timeout keeps the UI state `busy` instead of
  incorrectly flipping the GPU to `offline`.
- Reverse SSH uses `IPQoS=none`, bounded connection setup, client keepalives,
  and matching VPS `ClientAlive*` checks. This targets half-open sessions where
  the reverse port remains bound but HTTP no longer flows.
- The VPS stale-listener watchdog must defer `TERM` while `ss` reports an
  established forwarded connection on that reverse port. Slow uploads can
  block `/system_stats`; an active data channel is not a stale listener.
- Existing jobs retain their stable `server_id` and can be recovered through
  ComfyUI history when the prompt finished before a transient WebSocket loss.
- A true ComfyUI execution error remains an error.
- A native ComfyUI crash may surface as WebSocket loss; inspect the Windows
  error log before classifying it as a tunnel problem.
- On 2026-07-29, GPU1 recovered automatically from a native crash caused by
  `torch.OutOfMemoryError`. The next submitted workflow was byte-identical to a
  previously successful workflow, so this was runtime/VRAM state rather than a
  bad workflow file.
- On 2026-07-30, GPU1 kill/restart validation changed PID `21900 -> 3228`.
  Health returned 200, exactly one supervisor and one ComfyUI process remained,
  only port 8188 listened, and the watchdog recorded exactly one restart.
- On 2026-07-30, GPU2 stale reverse listener recovery terminated only the VPS
  SSH child that owned `18288`; GPU1 `18188` stayed healthy and GPU2's
  supervisor recreated a working tunnel without restarting ComfyUI.

## Invariants

- One physical Windows machine equals one worker/failure domain.
- Worker IDs and remote ports are unique and stable.
- Each worker has a unique restricted SSH key.
- ComfyUI listens on loopback only.
- Each `ComfyDirectory` may own only one ComfyUI process; wrong-port and
  duplicate processes are stopped by its supervisor.
- Runtime batch port/CUDA must match the worker JSON.
- Reverse listeners bind to the Docker gateway, not `0.0.0.0`.
- A worker uses either visible launcher mode or `SYSTEM` Scheduled Task mode,
  never both.
- Visible mode uses a separate interactive-user guard task; it must never run
  as `SYSTEM` because a SYSTEM process cannot reliably create a window on the
  signed-in desktop.
- `origin/main` remains the canonical source; runtime configs, private keys,
  secrets, data, and logs stay out of Git.

## Known Pitfalls

- `CUDA 0` is correct on both machines because each machine owns one GPU.
- The Docker gateway must be reachable from the app container.
- A browser-visible WebSocket error can be secondary to an OOM/native process
  crash.
- Do not loosen the SSH key to an unrestricted interactive shell.
- Do not add GPU2 to `deploy/.env` until its tunnel passes host and container
  health checks.
- Set `LaunchGuardSeconds` to `30` on GPU2 and verify its batch contains
  `--cuda-device 0 --listen 127.0.0.1 --port 8188`.
- Visible launcher and its guard require a Windows login; they cannot recover
  a worker that remains at the login screen after reboot.
- Run a real 61-frame bundled workflow with sufficient free system RAM before
  adding GPU2 to the scheduler.

## Related Decisions

- `DEPLOY-001`
- `DEPLOY-002`
- `GPU-001`
- `GPU-002`
- `GPU-004`
