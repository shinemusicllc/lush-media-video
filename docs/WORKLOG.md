# WORKLOG

## 2026-03-03 — Initial Build

- Phân tích workflow `FULLHD_6S_Loop_API.json`, xác định 7 node cần mapping
- Tạo implementation plan, review + approve bởi user
- Triển khai backend: 8 files Python (config, models, database, auth, comfyui_client, load_balancer, main, requirements.txt)
- Triển khai frontend: 3 files (index.html, style.css, app.js)
- Cài dependencies, khởi động server thành công
- Test: login API OK, giao diện login + dashboard hiển thị đúng
- ComfyUI server hiện OFFLINE (chưa bật trên máy dev) — dự kiến

## 2026-03-03 — Cloud Deploy Setup

- Sửa `config.py`: env vars (`COMFYUI_BASE_URL`, `ADMIN_PASSWORD`, `JWT_SECRET`), port 8188
- Sửa `comfyui_client.py`: thêm Cloudflare Access headers cho tất cả HTTP + WebSocket calls
- Sửa `main.py`: đọc PORT từ env var cho Railway
- Tạo `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `railway.json`
- Tạo `.env.example` với template env vars
- Tạo docs: `CLOUDFLARE_TUNNEL_SETUP.md`, `RAILWAY_DEPLOY.md`
- Cập nhật `PROJECT_CONTEXT.md`, `DECISIONS.md`

## 2026-03-23 — Sync local source from VPS working tree

- SSH vào VPS `82.197.71.6` bằng user `deploy` và xác nhận repo runtime nằm tại `/opt/lush-media-video/app`
- Đối chiếu thấy local ở commit `10ac0dc` còn VPS ở `267b1f5` kèm nhiều thay đổi chưa commit trong working tree
- Kéo source/deploy/docs từ VPS về local để local bám theo trạng thái thực tế đang chạy trên server
- Chủ động loại trừ `deploy/.env`, `deploy/data/`, và `deploy/scripts/__pycache__/` để không kéo secrets hay dữ liệu runtime về máy dev
- Giữ lại `AGENTS.md` root và `docs/CHANGELOG.md` tại local làm file workflow-local, sau đó cập nhật lại rule và log dự án

## 2026-03-23 — Publish VPS snapshot to GitHub

- Doc lai bo nho du an va phat hien `docs/PROJECT_CONTEXT.md` trong working tree tren VPS da cu hon trang thai deploy da xac minh truoc do
- Sua lai `docs/PROJECT_CONTEXT.md` theo runtime VPS hien tai (`/opt/lush-media-video/app`, bind `127.0.0.1:8011`, shared Caddy, backup timer, data path)
- Chuan bi commit tong hop de dua snapshot da doi chieu tu VPS len GitHub lam moc dong bo chinh
- Tao commit local `debe3c3` voi snapshot da doi chieu tu VPS
- Thu push qua ca HTTPS va SSH nhung deu bi GitHub tu choi vi account `pearhoang` khong co quyen ghi vao `shinemusicllc/lush-media-video`

## 2026-03-23 — Complete GitHub sync after access grant

- Thu push lai sau khi user cap quyen va dua thanh cong `main` len GitHub
- Xac nhan `refs/heads/main` tren `origin` da tro toi commit `3866b1a5b372079488d533f17f1e7dc6968d3919`
- Chay `git pull --ff-only origin main` va nhan ket qua `Already up-to-date`
- Xac nhan local `main`, `origin/main`, va GitHub da dong bo cung mot commit

## 2026-03-23 — Integrate Telegram bot into shared queue

- Mo rong schema `jobs` voi `source`, `source_user_id`, `telegram_chat_id`, `visibility`, va `telegram_notified_at`
- Them service `telegram_bot.py` dung long polling, nhan anh + workflow JSON theo chat, tao pseudo-user Telegram, va enqueue vao cung `load_balancer`
- Sua `load_balancer.py` de job Telegram van xu ly FIFO chung nhung khong broadcast len web UI neu `visibility=hidden`
- Sua `main.py` va `static/app.js` de web chi lay/render cac job `visibility=web`
- Bo sung config/env mau cho `PUBLIC_BASE_URL`, `TELEGRAM_BOT_TOKEN`, va thu muc pending cua Telegram
- Verify bang `compileall`, import runtime, va bai test SQLite tam cho migration + filter `visibility`
