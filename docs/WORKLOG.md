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

## 2026-03-23 — Deploy Telegram bot integration to VPS

- Commit local thay doi Telegram thanh `2049e64` va push len `origin/main`
- Dong bo source tu local len `/opt/lush-media-video/app` tren VPS theo cach giu nguyen `deploy/.env` va `deploy/data/`
- Bo sung `PUBLIC_BASE_URL`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_POLL_TIMEOUT_S`, `TELEGRAM_POLL_INTERVAL_S`, `TELEGRAM_PENDING_DIR` vao `deploy/.env`
- Redeploy Docker stack va xac nhan container `lushvideo-app-1` healthy tren `127.0.0.1:8011`
- Kiem tra log startup xac nhan `telegram_bot polling started` va ca hai GPU deu online
- Goi Telegram Bot API de `getMe`, `deleteWebhook`, `setMyCommands`, va xac nhan webhook dang rong cho che do long polling

## 2026-03-23 — Refine Telegram bot messaging and input rules

- Sua bot tra loi sang tieng Viet co dau va doi link dai thanh link HTML gon gon `Tai video` / `Tai anh`
- Bo link tai workflow khoi thong bao hoan tat cua Telegram
- Them debounce cho thong bao dang cho du lieu de tranh bao sai khi user gui file sat nhau
- Chot flow bot chi nhan anh dang `Document`; neu user gui theo kieu `Photo` thi bot nhac gui lai bang `Document` de giu chat luong goc
- Redeploy lai VPS va xac nhan container healthy sau ban va Telegram moi

## 2026-03-23 — Prevent premature Telegram missing-file hint in same send batch

- Sua bot theo doi so update con lai cua tung chat trong cung poll batch de khong nhac "thieu anh/workflow" khi file tiep theo dang den ngay sau do
- Tang thoi gian cho hint tu `1.2s` len `2.5s` de de dung hon voi truong hop anh `Document` upload cham do mang
- Verify local bang `compileall` va bai test nho cho dem batch update theo `chat_id`

## 2026-03-23 — Settle Telegram document batches before hinting or enqueueing

- Doi bot sang co che cho chat "yen" trong `6s` sau file document cuoi cung roi moi ket luan batch da xong
- Them `pending_activity` + enqueue debounce de chi tao `1` job sau khi batch on dinh, tranh truong hop upload cham hoac task cu chen vao
- Sua cleanup cua hint/enqueue task de task cu chi tu xoa chinh no, khong pop nham task moi hon trong race condition
- Cap nhat wording Telegram theo huong xac nhan batch da nhan du hay con thieu file gi
- Verify local bang `compileall` va bai test asyncio mo phong canh doi workflow -> anh cham, xac nhan khong phat hint sai va chi enqueue 1 lan
