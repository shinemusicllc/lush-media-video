# Lush Media Video Root Rules

## Build / Test / Run

- Install deps: `pip install -r D:\Comfyuibot\lush-media-video\requirements.txt`
- Local dev server: `uvicorn main:app --host 127.0.0.1 --port 8000 --reload`
- Docker build: `docker build -t lush-media-video D:\Comfyuibot\lush-media-video`
- Docker compose reference: `docker compose -f D:\Comfyuibot\lush-media-video\docker-compose.yml up -d --build`
- Smoke check: `curl http://127.0.0.1:8000/`
- VPS helper usage: `lushvideo status|logs|backup|redeploy|update|set-admin`
- Automated test/lint: no dedicated suite is checked in yet; use the regression checklist below after changes.

## Coding Conventions

- Keep API routes and JSON payloads stable unless there is a migration plan for the live dashboard.
- Preserve the current static UI structure in `static/` unless the task explicitly changes UX.
- Keep config/env behavior centralized in `config.py`; avoid hardcoding deployment values in route handlers.
- Maintain backward compatibility for SQLite schema changes by using additive migrations in `database.py`.

## Module Boundaries

- `main.py` owns FastAPI routes, auth wiring, static serving, and WebSocket endpoints.
- `database.py` owns SQLite schema and persistence helpers.
- `comfyui_client.py` and `load_balancer.py` own ComfyUI/network orchestration and must stay separate from HTTP route logic.
- `static/` must not call ComfyUI directly; browser traffic goes through the backend only.

## Debug Workflow

- Reproduce locally first with a valid `.env` and at least one reachable ComfyUI endpoint.
- For production issues, verify `/`, `/api/auth/login`, `/api/jobs`, and `/api/admin/servers` in that order.
- When migrating data, verify both the SQLite DB and persisted upload/workflow directories, not just application health.
- Before signoff, test login, job list loading, and at least one authenticated API request.

## Regression Checklist

- Admin login still works with the configured credentials.
- Existing jobs remain visible after migration.
- Thumbnail/video/workflow download endpoints still resolve for historical jobs.
- GPU server indicators still reflect the configured ComfyUI endpoints.

## Refactor Safety

- Do not expose ComfyUI directly to the public internet as part of this app deploy.
- Do not change `DB_PATH`, `UPLOAD_DIR`, or `WORKFLOW_ARCHIVE_DIR` semantics without a data migration path.
- Do not rotate `JWT_SECRET` or admin credentials implicitly during deploy/migration.
- Use the tracked helper when rotating admin credentials on VPS so SQLite and runtime docs stay in sync.
