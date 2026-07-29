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
  `deploy/windows/comfyui-worker-supervisor.ps1 -ConfigPath <worker.json>`
- Scheduled Task installer:
  `deploy/windows/install-comfyui-worker-task.ps1`
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
- Scheduled Task: `LushMedia-ComfyUI-gpu1`, running as `SYSTEM`
- ComfyUI directory/batch:
  `D:\ComfyUI1` / `D:\ComfyUI1\run_nvidia_gpu.bat`
- Private key: `D:\ComfyUI-Autostart\gpu1_worker_ed25519`
- Public-key fingerprint:
  `SHA256:fI5xR8u8k4NsoFNpjy5xLEFqLTgEIhTOm+oOSmwDuw0`
- VPS key restriction:
  `restrict,port-forwarding,permitlisten="172.19.0.1:18188"`

The key file is intentionally readable by `SYSTEM`, not by the interactive
Windows user.

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
7. From elevated PowerShell, install and start the task:

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
- Never restart a worker or redeploy the VPS app while its ComfyUI queue has a
  running or pending job.

## Failure Semantics

- An offline worker is excluded from new assignments.
- Existing jobs retain their stable `server_id` and can be recovered through
  ComfyUI history when the prompt finished before a transient WebSocket loss.
- A true ComfyUI execution error remains an error.
- A native ComfyUI crash may surface as WebSocket loss; inspect the Windows
  error log before classifying it as a tunnel problem.
- On 2026-07-29, GPU1 recovered automatically from a native crash caused by
  `torch.OutOfMemoryError`. The next submitted workflow was byte-identical to a
  previously successful workflow, so this was runtime/VRAM state rather than a
  bad workflow file.

## Invariants

- One physical Windows machine equals one worker/failure domain.
- Worker IDs and remote ports are unique and stable.
- Each worker has a unique restricted SSH key.
- ComfyUI listens on loopback only.
- Reverse listeners bind to the Docker gateway, not `0.0.0.0`.
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

## Related Decisions

- `DEPLOY-001`
- `DEPLOY-002`
- `GPU-001`
