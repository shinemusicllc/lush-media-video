# Deploy Delta Rules

- Keep this deploy stack app-local only; the public `80/443` reverse proxy is shared elsewhere on the VPS.
- Persist SQLite DB, uploads, and workflow snapshots together under `deploy/data/` on the server.
- Treat API-based migration as best-effort for live data unless the original Railway volume files are available.
- Do not rotate `ADMIN_PASSWORD` or `JWT_SECRET` during migration unless the user explicitly asks.
