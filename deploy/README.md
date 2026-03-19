# VPS Deployment

This deploy stack runs the Lush Media app on an internal VPS port and expects a shared reverse proxy to publish the public domain.

- Internal app bind: `127.0.0.1:${APP_PORT}`
- Persistent data: `deploy/data/`
- Public domain: `video.jazzrelaxation.com`

Recommended rollout:

1. Copy `.env.example` to `.env` and fill the real values.
2. Run `docker compose -f docker-compose.vps.yml --env-file .env up -d --build`.
3. Verify locally on the VPS:
   - `curl http://127.0.0.1:${APP_PORT}/`
   - `curl http://127.0.0.1:${APP_PORT}/api/admin/servers -H "Authorization: Bearer ..."`
4. Add the reverse-proxy rule for `video.jazzrelaxation.com` to point at `127.0.0.1:${APP_PORT}`.
5. After cutover, verify login, job list, and GPU server status.

Operational notes:

- This app persists SQLite plus uploaded inputs/workflow snapshots, so backups must include the whole `data/` directory, not just a database file.
- `scripts/migrate_from_live_api.py` imports the latest visible Railway jobs through the live API. It does not bypass the current `100`-job admin API cap.
- After installing the helper wrapper, day-to-day commands can use `lushvideo status|logs|backup|redeploy|update|set-admin`.
- `lushvideo set-admin [--current <old_admin>] [--username <new_admin>] [--password <new_password>]` updates the live admin row in SQLite, rewrites historical job ownership strings to the new username, syncs `deploy/.env` for future restarts, auto-selects the only admin when `--current` is omitted, and prompts securely when `--password` is omitted.
