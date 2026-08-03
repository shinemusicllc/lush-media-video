# Decisions Index

## Active Decisions

| ID | Decision | Canonical detail |
| --- | --- | --- |
| DEPLOY-001 | `origin/main` is the source of truth for production code. | Production must not be built from uncommitted tracked changes. |
| DEPLOY-002 | Runtime data stays in `deploy/data/` and is ignored by Git and Docker build context. | Data is mounted to `/data` in `deploy/docker-compose.vps.yml`. |
| DEPLOY-003 | VPS deploy uses the `lushvideo` compose project and an internal bind on `127.0.0.1:${APP_PORT:-8011}`. | Public traffic is routed by the shared reverse proxy. |
| BOT-001 | Telegram long polling runs inside the FastAPI app process. | `telegram_bot.py` starts during FastAPI startup when `TELEGRAM_BOT_TOKEN` is configured. |
| WORKFLOW-001 | Workflow submissions normalize Wan 2.2 high/low diffusion model filenames at runtime. | Web uploads, Telegram workflows, default workflows, and prompt build fallback must normalize stale UNETLoader names to the configured fp8 KJ files before archive/submission. |
| WORKFLOW-002 | Bundled fallback/presets use regular `VAEDecode`; Jazz is 73 frames/6s while Kling and Livewallpaper remain 61 frames/5s. | Tiled VAE caused reproducible temporal brightness flicker; regular VAE is safe on the validated 128 GB worker. Historical `/data/workflows` are not rewritten. |
| WORKFLOW-003 | Workflow ingress enforces a maximum of 73 frames without lengthening valid shorter workflows. | Web, Telegram and `build_prompt` preserve positive integer lengths up to 73, cap larger values and default invalid/missing values to 73. |
| GPU-001 | Each physical Windows machine runs one independently supervised ComfyUI worker and one dedicated reverse SSH tunnel. | Worker IDs and VPS ports are stable (`gpu1`/`18188`, `gpu2`/`18288`); the backend schedules only online workers, preferring idle capacity and using round-robin as the tie-breaker. |
| GPU-002 | A worker reconciles all ComfyUI processes in its configured directory to one process on its configured local port. | Batch port/CUDA must match config; wrong-port and duplicate processes are stopped; launch retries use a 30-second guard. |
| GPU-003 | Preserve ComfyUI's warm model cache between consecutive jobs. | Do not call `/free` after every job; reserve it for manual recovery or a future measured idle/memory-pressure policy. |
| GPU-004 | Visible workers run from an interactive Desktop window protected by a separate per-user guard task instead of an active `SYSTEM` worker task. | Startup/recovery occurs only after Windows login; the guard automatically reopens a killed worker window, while the same singleton supervisor/watchdog manages ComfyUI and the legacy SYSTEM task remains disabled for rollback. |
| GPU-005 | Reverse-tunnel health uses two watchdog layers. | Windows workers supervise local ComfyUI and `ssh.exe`; a root-owned VPS timer clears only a verified stale `sshd: deploy` listener after two failed reverse health probes so the worker can reconnect. |
