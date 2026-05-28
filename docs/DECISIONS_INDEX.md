# Decisions Index

## Active Decisions

| ID | Decision | Canonical detail |
| --- | --- | --- |
| DEPLOY-001 | `origin/main` is the source of truth for production code. | Production must not be built from uncommitted tracked changes. |
| DEPLOY-002 | Runtime data stays in `deploy/data/` and is ignored by Git and Docker build context. | Data is mounted to `/data` in `deploy/docker-compose.vps.yml`. |
| DEPLOY-003 | VPS deploy uses the `lushvideo` compose project and an internal bind on `127.0.0.1:${APP_PORT:-8011}`. | Public traffic is routed by the shared reverse proxy. |
| BOT-001 | Telegram long polling runs inside the FastAPI app process. | `telegram_bot.py` starts during FastAPI startup when `TELEGRAM_BOT_TOKEN` is configured. |
| WORKFLOW-001 | Workflow submissions normalize Wan 2.2 high/low diffusion model filenames at runtime. | Web uploads, Telegram workflows, default workflows, and prompt build fallback must normalize stale UNETLoader names to the configured fp8 KJ files before archive/submission. |
