# CHANGELOG

### 2026-03-19 15:21 - Add Lush admin credential helper
- Added: `deploy/scripts/set_admin_credentials.sh` for rotating persisted admin username/password inside SQLite.
- Changed: `lushvideo` wrapper and deploy docs now expose the `set-admin` operation, sync `deploy/.env`, and rewrite `jobs.username` when the admin username changes.
- Fixed: clarified that changing startup env alone does not update an existing migrated admin account.
- Affected files: `deploy/scripts/set_admin_credentials.sh`, `deploy/scripts/lushvideo.sh`, `deploy/README.md`, `AGENTS.md`, `docs/PROJECT_CONTEXT.md`, `docs/DECISIONS.md`, `docs/WORKLOG.md`, `docs/CHANGELOG.md`
- Impact/Risk: Low; updates operational tooling only, and existing JWT sessions remain valid until they expire or the user logs out.

### 2026-03-19 14:10 - Prepare VPS deployment and migrate live data
- Added: `AGENTS.md`, `deploy/AGENTS.md`, `deploy/.env.example`, `deploy/docker-compose.vps.yml`, `deploy/README.md`, `deploy/scripts/backup_data.sh`, `deploy/scripts/redeploy.sh`, `deploy/scripts/update_app.sh`, `deploy/scripts/lushvideo.sh`, `deploy/scripts/install_helpers.sh`, `deploy/scripts/migrate_from_live_api.py`, `deploy/systemd/lush-media-backup.service`, `deploy/systemd/lush-media-backup.timer`, `docs/CHANGELOG.md`.
- Changed: project context now reflects the prepared VPS runtime on `82.197.71.6`, internal bind `127.0.0.1:8011`, shared-Caddy publish model, and current migration limits.
- Fixed: historical app state can now be restored onto the VPS from the live Railway app without manually rebuilding users/jobs, and the app now runs under a unique Docker Compose project name `lushvideo` instead of colliding with the Spotify stack.
- Affected files: `AGENTS.md`, `deploy/AGENTS.md`, `deploy/.env.example`, `deploy/docker-compose.vps.yml`, `deploy/README.md`, `deploy/scripts/backup_data.sh`, `deploy/scripts/redeploy.sh`, `deploy/scripts/update_app.sh`, `deploy/scripts/lushvideo.sh`, `deploy/scripts/install_helpers.sh`, `deploy/scripts/migrate_from_live_api.py`, `deploy/systemd/lush-media-backup.service`, `deploy/systemd/lush-media-backup.timer`, `docs/PROJECT_CONTEXT.md`, `docs/DECISIONS.md`, `docs/WORKLOG.md`, `docs/CHANGELOG.md`
- Impact/Risk: Medium; the VPS app is healthy and data is present locally, but `video.jazzrelaxation.com` still points to Railway until Cloudflare DNS is cut over to `82.197.71.6`, and only the latest `100` jobs were migratable through the current admin API.
### 2026-03-19 14:40 - Delete local job files and scope Clear List to current page
- Added: `JobClearRequest` body model and backend support for clearing specific `job_ids`.
- Changed: the queue footer action now targets only the jobs visible on the current page and the button label clarifies that scope.
- Fixed: deleting a job now also removes its local VPS files (`uploads` + `workflows`), and `Clear List` no longer wipes every page of the queue.
- Affected files: `main.py`, `database.py`, `models.py`, `static/app.js`, `static/index.html`, `docs/PROJECT_CONTEXT.md`, `docs/DECISIONS.md`, `docs/WORKLOG.md`, `docs/CHANGELOG.md`
- Impact/Risk: Medium; local VPS cleanup is now more aggressive by design, but historical output files that still live only on the GPU machines are not deleted by this change.
### 2026-03-19 14:55 - Normalize queue time display to Viet Nam time
- Added: frontend timestamp parsing that treats timezone-less job timestamps as UTC before formatting them for `Asia/Ho_Chi_Minh`.
- Changed: the pagination previous label now renders `Trước`.
- Fixed: queue item times no longer drift away from Viet Nam time because of browser-dependent timestamp parsing.
- Affected files: `static/app.js`, `static/index.html`, `docs/PROJECT_CONTEXT.md`, `docs/DECISIONS.md`, `docs/WORKLOG.md`, `docs/CHANGELOG.md`
- Impact/Risk: Low; this is a frontend-only display correction and does not change stored timestamps in SQLite.

### 2026-03-23 18:00 - Sync local repo from VPS working tree
- Added: a documented recovery step for using the current VPS working tree as the source when local/GitHub are behind the live server state.
- Changed: local source, deploy scripts, and project docs were overwritten from `/opt/lush-media-video/app` so the local checkout follows the VPS working tree instead of `origin/main`.
- Fixed: the root `AGENTS.md` workspace paths now point to `D:\Comfyuibot\lush-media-video` and reflect that there is no checked-in automated test/lint suite yet.
- Affected files: multiple synced source files under repo root, `deploy/`, `docs/PROJECT_CONTEXT.md`, `docs/DECISIONS.md`, `docs/WORKLOG.md`, `AGENTS.md`, `docs/CHANGELOG.md`
- Impact/Risk: Medium; local source now matches the VPS working tree for synced files, but `deploy/.env`, `deploy/data/`, and cache folders were intentionally excluded so secrets/runtime data stay on the server.

### 2026-03-23 18:15 - Publish verified VPS snapshot to GitHub
- Added: a source-control decision to use the verified VPS snapshot as the publish baseline when GitHub is behind the live server.
- Changed: `docs/PROJECT_CONTEXT.md` was restored to the current VPS deployment reality before publishing, and a local commit `debe3c3` now contains the verified VPS snapshot.
- Fixed: repository memory no longer points back to the older Railway-only runtime after syncing from the VPS working tree.
- Affected files: `docs/PROJECT_CONTEXT.md`, `docs/DECISIONS.md`, `docs/WORKLOG.md`, `docs/CHANGELOG.md`
- Impact/Risk: Medium; the publish step is blocked because GitHub denied push access to account `pearhoang`, so `origin/main` has not moved yet even though the local commit is ready.
