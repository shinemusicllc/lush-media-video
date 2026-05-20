# Deploy Module

## Scope

The deploy module owns VPS Docker Compose runtime, helper scripts, systemd backup timer, and operational boundaries between tracked source code and persistent data.

## Entry Points

- `deploy/docker-compose.vps.yml`: production compose stack.
- `deploy/scripts/update_app.sh`: sync tracked source to `origin/main`, then redeploy.
- `deploy/scripts/redeploy.sh`: rebuild/recreate the container from the current clean checkout.
- `deploy/scripts/backup_data.sh`: backup `deploy/data/` and run retention cleanup.
- `deploy/systemd/lush-media-backup.service`: scheduled backup service.

## Invariants

- `deploy/data/`, `deploy/.env`, and deploy backups are runtime state, not source.
- Docker build context must exclude runtime data and secrets.
- `redeploy.sh` must refuse dirty tracked source so the container can be traced to a commit.
- `update_app.sh` may force-sync only when `FORCE_SYNC=1`; it writes a patch/status backup first.
- The built image receives `APP_COMMIT` from Git so container provenance is inspectable.

## VPS Notes

- Live app path: `/opt/lush-media-video/app`
- Compose path: `/opt/lush-media-video/app/deploy/docker-compose.vps.yml`
- Live container: `lushvideo-app-1`
- Persistent data bind: `/opt/lush-media-video/app/deploy/data -> /data`

