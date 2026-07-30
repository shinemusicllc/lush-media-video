# CHANGELOG

### 2026-07-30 - Tile bundled VAE decode and enforce singleton GPU workers
- Changed: fallback workflow and all five presets now use `VAEDecodeTiled` with `512/64/16/4`; all bundled Wan workflows use 61 source frames while existing filenames remain stable.
- Added: regression tests for workflow VAE/frame contracts and supervisor checks for batch/config agreement, cross-port process reconciliation, and launch guarding.
- Verified: GPU1 kill/restart retained one supervisor, one ComfyUI process, only listener 8188, no listener 8288, and one watchdog restart entry.
- Risk: a 61-frame render attempt native-crashed while system RAM was exhausted, so production scheduling remains disabled pending a clean render with adequate free RAM.

### 2026-07-29 17:30 - Split GPU1 into an independently supervised worker
- Changed: synchronized local/GitHub/VPS source, made offline-aware idle/queue/round-robin scheduling and terminal ComfyUI history recovery explicit, and deployed commit `79fb6f4`.
- Added: tested Windows ComfyUI/SSH watchdog scripts, a `SYSTEM` startup task for GPU1, a restricted reverse tunnel on `172.19.0.1:18188`, backend/supervisor regression tests, and the GPU2 handoff runbook.
- Affected: `comfyui_client.py`, `load_balancer.py`, `tests/`, `deploy/windows/`, `docs/PROJECT_BRIEF.md`, `docs/MEMORY_INDEX.md`, `docs/DECISIONS*`, `docs/modules/gpu-workers.md`.
- Risk: Medium; connectivity and self-recovery are verified, but GPU1 twice hit a native `torch.OutOfMemoryError` on the existing Full HD Wan workflow, so hardware/runtime VRAM stability remains a separate follow-up.

### 2026-05-28 - Switch diffusion models to Wan 2.2 fp8 KJ
- Changed: switched the default workflow, bundled workflow presets, and runtime diffusion model normalization to `Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors` and `Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors`.
- Affected files: `config.py`, `FULLHD_6S_Loop_API.json`, `workflows/Jazz & lofi 6s Khong Loop.json`, `workflows/presets/*.json`, `docs/DECISIONS_INDEX.md`, `docs/DECISIONS.md`, `docs/CHANGELOG.md`
- Impact/Risk: Medium; generated jobs now require the matching fp8 KJ high/low Wan 2.2 model files to exist on the target ComfyUI servers.

### 2026-05-28 - Lock workflow diffusion models at runtime
- Added: runtime guard that forces all web, Telegram, and prompt-build workflows to use the configured Wan 2.2 high/low diffusion model filenames.
- Affected files: `config.py`, `main.py`, `telegram_bot.py`, `comfyui_client.py`, `workflow_guard.py`, root workflow JSON backups, `docs/DECISIONS_INDEX.md`, `docs/DECISIONS.md`, `docs/CHANGELOG.md`
- Impact/Risk: Medium; uploaded workflows using old diffusion model names are silently normalized before archive and ComfyUI submission.

### 2026-05-27 - Update workflow diffusion models
- Changed: switched the default workflow and bundled preset `UNETLoader` high/low diffusion model names to `wan2.2_i2v_high_noise_14B_nvfp4_mixed.safetensors` and `wan2.2_i2v_low_noise_14B_nvfp4_mixed.safetensors`.
- Affected files: `workflows/Jazz & lofi 6s Khong Loop.json`, `workflows/presets/*.json`, `docs/CHANGELOG.md`
- Impact/Risk: Medium; generated jobs now require the matching high/low Wan 2.2 model files to exist on the target ComfyUI servers.

### 2026-05-27 - Speed up queue thumbnails
- Added: server-side cached JPEG thumbnails for job input images so the queue no longer sends full-size uploads into 124px preview slots.
- Changed: queue rendering now eagerly decodes visible thumbnails and prefetches neighboring pagination thumbnails after render.
- Affected files: `config.py`, `main.py`, `requirements.txt`, `static/app.js`, `docs/CHANGELOG.md`
- Impact/Risk: Medium; adds Pillow at build time and a new thumbnail cache directory under persistent app data.

### 2026-05-27 - Align login UI with cinematic app style
- Changed: refined the login card with dark app surfaces, dark inputs, and the green primary action while preserving the original cinematic background, starfield, and centered login composition.
- Affected files: `static/index.html`, `static/style.css`, `docs/CHANGELOG.md`
- Impact/Risk: Low; auth flow and API behavior are unchanged.

### 2026-05-20 - Add workflow preset picker UI
- Added: authenticated workflow preset listing/download endpoints backed by `WORKFLOW_PRESET_DIR`.
- Added: `workflows/Jazz & lofi 6s Khong Loop.json` as the repository default workflow when users do not select one.
- Added: bundled workflow presets under `workflows/presets/` so the VPS picker does not depend on a Windows-only folder.
- Changed: the workflow button now opens a compact hover popover under the button with preset choices plus a manual upload action in the header.
- Changed: workflow preset hover tooltips now show purpose notes instantly, including a black-border risk note for `Co Loop` presets.
- Fixed: sidebar logo alignment in collapsed mode by keeping the brand image centered like the nav icons.
- Affected files: `config.py`, `main.py`, `static/index.html`, `static/style.css`, `static/app.js`, `workflows/*`, `docs/UI_SYSTEM.md`, `docs/MEMORY_INDEX.md`, `docs/CHANGELOG.md`
- Impact/Risk: Low; job creation still uploads a normal `workflow_file`, whether selected from preset or user upload.

### 2026-05-20 - Normalize VPS deploy source of truth
- Added: lean project memory files for future Project Tasks and deploy routing.
- Changed: VPS deploy scripts now refuse dirty tracked builds, preserve runtime state, pass `APP_COMMIT` into Docker builds, and work under root/deploy ownership differences with Git `safe.directory`.
- Added: `BUNDLE_PATH` support for VPS updates when the server cannot fetch the private GitHub repo directly.
- Fixed: runtime data/secrets/backups are ignored by Git and Docker build context; deploy shell scripts are executable in Git; the backup systemd service no longer runs as `deploy`, which could not read root-owned upload files.
- Affected files: `.gitignore`, `.dockerignore`, `.gitattributes`, `Dockerfile`, `deploy/docker-compose.vps.yml`, `deploy/scripts/redeploy.sh`, `deploy/scripts/update_app.sh`, `deploy/systemd/lush-media-backup.service`, `docs/*`
- Impact/Risk: Medium; deployment behavior changes intentionally, but persistent data remains under `deploy/data/` and is not reset by source sync.

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

### 2026-03-23 18:25 - Complete GitHub sync after permission update
- Added: a final verification record for the successful publish of the VPS-aligned snapshot to `origin/main`.
- Changed: GitHub `main` now points to commit `3866b1a5b372079488d533f17f1e7dc6968d3919`, matching local `main` after a successful push and `pull --ff-only`.
- Fixed: the repository is no longer stuck in the earlier "ahead locally but blocked from pushing" state.
- Affected files: `docs/WORKLOG.md`, `docs/CHANGELOG.md`
- Impact/Risk: Low; source control is synchronized again, and no runtime files or secrets were added as part of this publish step.

### 2026-03-23 19:10 - Integrate Telegram bot with shared backend queue
- Added: `telegram_bot.py`, Telegram-specific job metadata columns, long-polling bot ingestion, and Telegram completion notifications with download links backed by existing JWT-secured job endpoints.
- Changed: web and Telegram now submit into the same backend queue, while the web API/UI only shows jobs with `visibility=web` and ignores hidden Telegram jobs by default.
- Fixed: project context now documents the Telegram ingress path, and admin user listing excludes pseudo-users created for Telegram chats.
- Affected files: `config.py`, `database.py`, `load_balancer.py`, `main.py`, `telegram_bot.py`, `static/app.js`, `.env.example`, `deploy/.env.example`, `docs/PROJECT_CONTEXT.md`, `docs/DECISIONS.md`, `docs/WORKLOG.md`, `docs/CHANGELOG.md`
- Impact/Risk: Medium; Telegram integration is live in code but depends on correct `TELEGRAM_BOT_TOKEN` and `PUBLIC_BASE_URL` configuration, and the first version pairs image/workflow per chat in memory rather than persisting unfinished drafts across restarts.

### 2026-03-23 20:45 - Enable Telegram bot on VPS runtime
- Added: live VPS env configuration for `PUBLIC_BASE_URL`, `TELEGRAM_BOT_TOKEN`, Telegram polling intervals, and `/data/telegram_pending`.
- Changed: the VPS app at `82.197.71.6` was redeployed with commit `2049e64`, and the public bot `@Lush_Video_Bot` now runs via long polling inside the app container.
- Fixed: Telegram webhook state was cleared and bot commands were registered so long polling can receive user messages immediately.
- Affected files: `docs/PROJECT_CONTEXT.md`, `docs/WORKLOG.md`, `docs/CHANGELOG.md`
- Impact/Risk: Medium; production bot is active, but end-to-end user testing still depends on sending a real chat message and the current implementation keeps unfinished image/workflow pairing only in memory until enqueue.

### 2026-03-23 21:15 - Refine Telegram bot replies and document-only image intake
- Added: clearer Vietnamese bot responses and a hard rule that image uploads for Telegram must come through `Document` mode to preserve original quality.
- Changed: completion notifications now render short clickable labels for video/image downloads instead of dumping full raw URLs, and the workflow download link was removed from the bot reply.
- Fixed: delayed guidance messages now mention `ảnh dạng tài liệu`, reducing confusion when users send workflow and image close together, and bot no longer accepts compressed Telegram `Photo` uploads as valid image input.
- Affected files: `telegram_bot.py`, `docs/PROJECT_CONTEXT.md`, `docs/DECISIONS.md`, `docs/WORKLOG.md`, `docs/CHANGELOG.md`
- Impact/Risk: Low; this is a Telegram UX/input-quality refinement, but users must now follow the stricter `Document` upload path for images.

### 2026-03-23 21:30 - Delay Telegram missing-file hint until same batch settles
- Added: per-chat batch tracking for Telegram updates so the bot can detect when another file from the same send action is still being processed.
- Changed: the missing-file reminder now waits longer before firing, making it tolerant of slower document uploads over unstable networks.
- Fixed: when users choose both workflow and image in one send action, the bot is much less likely to incorrectly say "Đã nhận workflow. Gửi thêm ảnh dạng tài liệu để xếp job."
- Affected files: `telegram_bot.py`, `docs/WORKLOG.md`, `docs/CHANGELOG.md`
- Impact/Risk: Low; this only changes Telegram timing/UX behavior and does not affect queue ordering or job execution logic.

### 2026-03-23 21:45 - Settle Telegram document batches before enqueueing
- Added: per-chat batch activity tracking so Telegram uploads are only finalized after the chat has been idle for `6` seconds since the last document arrived.
- Changed: the bot now acknowledges a completed upload batch before enqueueing and phrases incomplete-batch reminders around the current batch state instead of individual file arrivals.
- Fixed: duplicate Telegram jobs caused by slow multi-document uploads or stale debounce tasks are now blocked by activity-based enqueue gating and safer task cleanup.
- Affected files: `telegram_bot.py`, `docs/DECISIONS.md`, `docs/WORKLOG.md`, `docs/CHANGELOG.md`
- Impact/Risk: Low; Telegram jobs now wait a few seconds longer before entering the shared queue, trading a small delay for more reliable batch detection.

### 2026-03-23 22:05 - Enqueue Telegram jobs ngay khi batch da du 2 file
- Added: an `enqueue_started` guard so the same Telegram batch cannot enqueue twice while job submission is already in progress.
- Changed: the `6`-second batch settle wait was removed; the bot now enqueues immediately once both workflow and image are present, while the missing-file hint remains a short delayed reminder for true single-file states.
- Fixed: when a poll batch effectively contains both files, the bot now skips the confusing "Gửi thêm ảnh..." guidance and goes straight to "Đã nhận job..." without the earlier duplicate-enqueue behavior.
- Affected files: `telegram_bot.py`, `docs/DECISIONS.md`, `docs/WORKLOG.md`, `docs/CHANGELOG.md`
- Impact/Risk: Low; Telegram feels faster again, but cross-poll uploads that arrive very far apart can still hit the short missing-file reminder before the second file appears.

### 2026-03-24 08:55 - Retry va backfill Telegram completion notifications
- Added: a database query for Telegram jobs that finished without `telegram_notified_at`, plus a background retry loop that periodically backfills missed completion notifications.
- Changed: Telegram completion sends now retry multiple times before giving up, instead of failing once and requiring manual intervention.
- Fixed: a completed Telegram job for chat `6857168706` that previously missed its completion message because of `All connection attempts failed` was resent successfully, and future transient network failures should self-recover.
- Affected files: `database.py`, `telegram_bot.py`, `docs/DECISIONS.md`, `docs/WORKLOG.md`, `docs/CHANGELOG.md`
- Impact/Risk: Low; notification delivery is more robust, though a rare failure can still resend once if Telegram accepts the message but the DB update fails before `telegram_notified_at` is written.

### 2026-07-07 10:05 - Refresh local login screen visual
- Added: cinematic login chrome, editorial copy block, updated sign-in card structure, and JetBrains Mono support for small technical UI labels.
- Changed: login keeps the existing `static/login-bg.jpg` background but uses stronger cinematic overlays, a sharper dark card, green focus states, and compact dashboard-aligned form styling.
- Fixed: local login redesign preserves the existing auth element IDs so `static/app.js` login behavior remains unchanged.
- Affected files: `static/index.html`, `static/style.css`, `docs/CHANGELOG.md`
- Impact/Risk: Low; visual-only change, no auth/API contract changes.

### 2026-07-10 - Add list and grid job views
- Added: a persistent list/grid segmented toggle in the queue filter toolbar, with `10` jobs per list page and `20` jobs per grid page.
- Changed: grid cards prioritize the thumbnail, title, GPU, status, timestamp, and progress while download/image/delete actions appear as hover icons; touch devices keep actions visible.
- Fixed: stacked mobile/tablet layout now follows normal document flow so the upload panel cannot overlap the queue panel.
- Affected files: `static/index.html`, `static/style.css`, `static/app.js`, `docs/CHANGELOG.md`
- Impact/Risk: Low; frontend-only display change with no API, auth, queue, or database contract changes.

### 2026-07-10 - Compact grid metadata into thumbnails
- Changed: grid cards now place the job title, GPU, status, timestamp, and running progress directly over the thumbnail with a restrained readability gradient instead of a separate information panel.
- Changed: grid actions are individual icon buttons with no enclosing action container; they remain hover/focus-only on pointer devices and visible on touch devices.
- Fixed: grid tracks now use the same explicit height as each card, preventing dense multi-row pages from shrinking tracks and visually overlapping cards.
- Affected files: `static/style.css`, `docs/CHANGELOG.md`
- Impact/Risk: Low; grid-view styling only, with list view and job actions unchanged.
## 2026-07-11 - Align Grid/List status and safe deletion

- Mapped legacy `cancelled` jobs to the existing error presentation and error filter instead of exposing a cancel state that the dashboard cannot create.
- Kept download/delete action availability consistent between List and Grid.
- Restored the fixed completed-job contract (video + last-frame image) and added a workflow download action to Grid cards.
- Added compact status badges in Grid while preserving the last selected List/Grid mode in browser storage.
- Allowed queued jobs to be deleted while keeping running jobs protected; workers now skip queue entries whose DB rows were deleted before execution.

## 2026-07-30 - Validate consecutive warm-cache GPU1 renders

- Verified two fresh-seed 61-frame jobs completed consecutively on GPU1/8188 without `/free`; the warm job reduced runtime from 351.3 to 290.7 seconds and kept at least 15.71 GB RAM available.
- Confirmed both MP4 outputs, an empty final queue, and the same sole ComfyUI PID throughout.
- Documented that normal worker operation preserves ComfyUI's model cache between jobs.

## 2026-07-30 - Khóa workflow về 5 giây

- Đổi tên fallback và hai preset Jazz từ `6s` thành `5s`; API chỉ liệt kê tên mới nhưng vẫn resolve hai alias cũ.
- Khóa mọi node `WanFirstLastFrameToVideo` ở `61` frame cho web, Telegram, archive và prompt cuối gửi sang ComfyUI.
- Thêm regression test cho guard, preset alias, workflow đóng gói và các đường nhận workflow.
