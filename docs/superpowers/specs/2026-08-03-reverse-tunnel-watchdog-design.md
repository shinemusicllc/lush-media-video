# Reverse Tunnel Watchdog Design

## Goal

Prevent a stale VPS SSH listener from blocking either GPU worker's reverse
tunnel, without restarting ComfyUI, the app container, or the other worker.

## Root Cause and Boundary

Each Windows supervisor already checks local ComfyUI health and whether its
own `ssh.exe` process has exited. It retries a missing tunnel with bounded
backoff. A stale server-side `sshd: deploy` child can still own a reverse port
after its Windows-side process is gone, so the new tunnel is rejected with
`remote port forwarding failed`. Only the VPS can safely release that listener.

The VPS watchdog is therefore the remote half of the existing worker watchdog;
it never starts, stops, or probes ComfyUI on Windows directly.

## Design

Add a root-owned, tracked shell script and systemd timer on the VPS.

1. Every minute, probe `http://172.19.0.1:18188/system_stats` and
   `http://172.19.0.1:18288/system_stats` with a short timeout.
2. A successful probe removes that port's transient failure counter.
3. The first failed probe records one failure and takes no action.
4. On the second consecutive failed probe, probe once more immediately. If it
   has recovered, clear the counter and do nothing.
5. If it is still unhealthy, inspect only the configured reverse listener.
   The script may send `TERM` only when all checks match: exact allowlisted
   port, `sshd` process name, process user `deploy`, `sshd: deploy` command,
   and the same PID still owns that port at action time.
6. The script never uses a broad `pkill`, never touches `18188` while handling
   `18288` (or the reverse), and never stops a ComfyUI or Docker process.
7. It logs every failure, recovery, skipped unsafe candidate, and termination
   to the system journal. The Windows supervisor sees its SSH process close and
   reconnects normally.

Transient counters live under `/run/lush-media-reverse-tunnel-watchdog/`, so a
VPS reboot starts with a clean observation window rather than killing a newly
created tunnel based on old state.

## Components

| File | Responsibility |
| --- | --- |
| `deploy/scripts/watch_reverse_tunnels.sh` | Probe ports, retain consecutive-failure state, verify exact `sshd` owner, and terminate a stale listener safely. |
| `deploy/systemd/lush-media-reverse-tunnel-watchdog.service` | Run one watchdog pass as root. |
| `deploy/systemd/lush-media-reverse-tunnel-watchdog.timer` | Trigger the service every minute after boot. |
| `deploy/scripts/install_helpers.sh` | Install, enable, and restart the new timer alongside the existing backup timer. |
| `tests/test_reverse_tunnel_watchdog.py` | Verify success reset, two-failure threshold, exact verified termination, and unsafe-candidate refusal using injected command stubs. |

## Safety and Operations

- Hard-code the current contract ports `18188` and `18288` in the tracked
  script; changing a worker port requires a source review and test update.
- Use `flock` so manual runs and the timer cannot race each other.
- Send `TERM` only. A later timed pass may retry if a verified stale process
  refuses to exit; the watchdog never escalates to broad or forced killing.
- The service has no dependency on the app container's status. It validates the
  same host-side reverse URLs that the backend uses.
- Operators can inspect status with
  `systemctl status lush-media-reverse-tunnel-watchdog.timer` and history with
  `journalctl -u lush-media-reverse-tunnel-watchdog.service`.

## Test Plan

The test suite runs the script with temporary command stubs and state paths.
It proves that a healthy endpoint clears a prior failure, one failure does not
kill, two consecutive failures terminate only the verified listener PID, and a
non-`deploy`/non-`sshd` candidate is refused.

## Non-Goals

- No changes to worker SSH keys, SSH restrictions, Windows runtime configs, or
  ComfyUI workflow behavior.
- No app redeploy and no change to scheduler logic.
- No global `sshd_config` keepalive policy; that would affect unrelated VPS SSH
  sessions without guaranteeing reverse-forward health.
