# Project Brief

## Purpose

Lush Media Video is a FastAPI app for submitting image + workflow jobs to ComfyUI GPU endpoints, tracking job state in SQLite, serving the static dashboard, and supporting Telegram-based ComfyUIBot submissions through the same backend queue.

## Runtime Shape

- Local app entrypoint: `main.py`
- Static UI: `static/`
- SQLite persistence: `database.py`
- Config/env source: `config.py`
- ComfyUI orchestration: `comfyui_client.py`, `load_balancer.py`
- Windows GPU workers: one ComfyUI instance per physical machine, supervised by
  `deploy/windows/comfyui-worker-supervisor.ps1` and exposed to the VPS through
  a dedicated reverse SSH port.
- Telegram ingress and completion notifications: `telegram_bot.py`
- VPS compose stack: `deploy/docker-compose.vps.yml`
- VPS persistent runtime data: `deploy/data/` mounted to `/data`

## Build, Test, Run

- Local dev: `uvicorn main:app --host 127.0.0.1 --port 8000 --reload`
- Docker build: `docker build -t lush-media-video .`
- VPS redeploy: `deploy/scripts/redeploy.sh`
- VPS update from git: `deploy/scripts/update_app.sh`
- Smoke check: `curl http://127.0.0.1:8000/`
- Python regression tests: `python -m unittest discover -s tests -v`
- Windows worker tests:
  `powershell -NoProfile -ExecutionPolicy Bypass -File deploy/windows/tests/comfyui-worker-common.tests.ps1`
  and
  `powershell -NoProfile -ExecutionPolicy Bypass -File deploy/windows/tests/comfyui-worker-scripts.tests.ps1`

## Invariants

- Browser traffic must go through the backend; `static/` must not call ComfyUI directly.
- Keep API routes and JSON payloads stable unless a migration plan exists.
- Keep deployment secrets and runtime data out of Git and Docker build context.
- SQLite schema changes must be additive/backward compatible in `database.py`.
- Production Docker images must be built from a clean tracked Git tree, with `deploy/data/` preserved as runtime state.
- Each GPU worker has a stable `gpuN` ID, its own SSH key and remote port; ComfyUI
  remains bound to `127.0.0.1` on the Windows host.
- The scheduler must never assign a new job to an offline worker.
