# Project Brief

## Purpose

Lush Media Video is a FastAPI app for submitting image + workflow jobs to ComfyUI GPU endpoints, tracking job state in SQLite, serving the static dashboard, and supporting Telegram-based ComfyUIBot submissions through the same backend queue.

## Runtime Shape

- Local app entrypoint: `main.py`
- Static UI: `static/`
- SQLite persistence: `database.py`
- Config/env source: `config.py`
- ComfyUI orchestration: `comfyui_client.py`, `load_balancer.py`
- Telegram ingress and completion notifications: `telegram_bot.py`
- VPS compose stack: `deploy/docker-compose.vps.yml`
- VPS persistent runtime data: `deploy/data/` mounted to `/data`

## Build, Test, Run

- Local dev: `uvicorn main:app --host 127.0.0.1 --port 8000 --reload`
- Docker build: `docker build -t lush-media-video D:\lush-media-video`
- VPS redeploy: `deploy/scripts/redeploy.sh`
- VPS update from git: `deploy/scripts/update_app.sh`
- Smoke check: `curl http://127.0.0.1:8000/`
- No dedicated automated test suite is checked in yet; use targeted syntax checks and the regression checklist in `AGENTS.md`.

## Invariants

- Browser traffic must go through the backend; `static/` must not call ComfyUI directly.
- Keep API routes and JSON payloads stable unless a migration plan exists.
- Keep deployment secrets and runtime data out of Git and Docker build context.
- SQLite schema changes must be additive/backward compatible in `database.py`.
- Production Docker images must be built from a clean tracked Git tree, with `deploy/data/` preserved as runtime state.

