# Decisions Index

## Active Decisions

| ID | Decision | Canonical detail |
| --- | --- | --- |
| DEPLOY-001 | `origin/main` is the source of truth for production code. | Production must not be built from uncommitted tracked changes. |
| DEPLOY-002 | Runtime data stays in `deploy/data/` and is ignored by Git and Docker build context. | Data is mounted to `/data` in `deploy/docker-compose.vps.yml`. |
| DEPLOY-003 | VPS deploy uses the `lushvideo` compose project and an internal bind on `127.0.0.1:${APP_PORT:-8011}`. | Public traffic is routed by the shared reverse proxy. |
| BOT-001 | Telegram long polling runs inside the FastAPI app process. | `telegram_bot.py` starts during FastAPI startup when `TELEGRAM_BOT_TOKEN` is configured. |
| WORKFLOW-001 | Workflow submissions normalize Wan 2.2 high/low diffusion model filenames at runtime. | Web uploads, Telegram workflows, default workflows, and prompt build fallback must normalize stale UNETLoader names to the configured fp8 KJ files before archive/submission. |
| WORKFLOW-002 | Bundled fallback/presets use temporally tiled VAE decode and at most 61 source frames. | Canonical settings are documented in `docs/modules/workflows.md`; historical `/data/workflows` are not rewritten. |
| WORKFLOW-003 | Mọi workflow được app chấp nhận bị khóa chính xác ở 61 frame. | Web, Telegram và `build_prompt` chuẩn hóa `WanFirstLastFrameToVideo.length`; preset chỉ hiển thị tên `5s`, còn hai tên Jazz `6s` là alias ẩn. |
| GPU-001 | Each physical Windows machine runs one independently supervised ComfyUI worker and one dedicated reverse SSH tunnel. | Worker IDs and VPS ports are stable (`gpu1`/`18188`, `gpu2`/`18288`); the backend schedules only online workers, preferring idle capacity and using round-robin as the tie-breaker. |
| GPU-002 | A worker reconciles all ComfyUI processes in its configured directory to one process on its configured local port. | Batch port/CUDA must match config; wrong-port and duplicate processes are stopped; launch retries use a 30-second guard. |
| GPU-003 | Preserve ComfyUI's warm model cache between consecutive jobs. | Do not call `/free` after every job; reserve it for manual recovery or a future measured idle/memory-pressure policy. |
