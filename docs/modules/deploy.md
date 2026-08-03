# Deploy Module

## Scope

The deploy module owns VPS Docker Compose runtime, helper scripts, systemd backup timer, and operational boundaries between tracked source code and persistent data.

## Entry Points

- `deploy/docker-compose.vps.yml`: production compose stack.
- `deploy/scripts/update_app.sh`: sync tracked source to `origin/main`, then redeploy.
- `deploy/scripts/redeploy.sh`: rebuild/recreate the container from the current clean checkout.
- `deploy/scripts/backup_data.sh`: backup `deploy/data/` and run retention cleanup.
- `deploy/systemd/lush-media-backup.service`: scheduled backup service.
- `deploy/scripts/watch_reverse_tunnels.sh`: safe reverse-listener health and stale-session cleanup.
- `deploy/systemd/lush-media-reverse-tunnel-watchdog.timer`: runs the reverse-tunnel watchdog every minute.

## Invariants

- `deploy/data/`, `deploy/.env`, and deploy backups are runtime state, not source.
- Docker build context must exclude runtime data and secrets.
- `redeploy.sh` must refuse dirty tracked source so the container can be traced to a commit.
- `update_app.sh` may force-sync only when `FORCE_SYNC=1`; it writes a patch/status backup first.
- If the VPS cannot fetch the private GitHub repo directly, copy a Git bundle to the VPS and run `BUNDLE_PATH=/tmp/<bundle> deploy/scripts/update_app.sh`.
- The built image receives `APP_COMMIT` from Git so container provenance is inspectable.
- `install_helpers.sh` installs both systemd timers. The reverse-tunnel timer is
  root-owned, keeps state only in `/run`, probes ports `18188`/`18288`, and may
  send `TERM` only to a verified `deploy`-owned `sshd` child after two failed
  checks and one immediate recheck. It must never use a broad process kill.

## VPS Notes

- Live app path: `/opt/lush-media-video/app`
- Compose path: `/opt/lush-media-video/app/deploy/docker-compose.vps.yml`
- Live container: `lushvideo-app-1`
- Persistent data bind: `/opt/lush-media-video/app/deploy/data -> /data`
