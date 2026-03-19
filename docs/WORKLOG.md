# WORKLOG

## 2026-03-19 - Add admin credential rotation helper

- Xac nhan `ADMIN_USERNAME` / `ADMIN_PASSWORD` trong config chi bootstrap admin o startup neu user do chua ton tai.
- Them `deploy/scripts/set_admin_credentials.sh` de doi persisted admin username/password truc tiep trong SQLite bang chinh hash flow cua app, dong bo `deploy/.env`, va cap nhat `jobs.username` khi admin doi username.
- Mo rong wrapper `lushvideo` va docs deploy de ho tro lenh 1 dong khi can doi credential tren VPS.

## 2026-03-03 - Initial Build

- Phan tich workflow `FULLHD_6S_Loop_API.json` va mapping node can dung cho image-to-video.
- Trien khai backend FastAPI, auth, database layer, ComfyUI client, load balancer, va static frontend.
- Test local login API va dashboard render thanh cong.

## 2026-03-03 - Cloud Deploy Setup

- Dua config sang env vars cho `COMFYUI_BASE_URL`, `ADMIN_PASSWORD`, `JWT_SECRET`, va `PORT`.
- Tao `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `railway.json`, `.env.example`.
- Bo sung docs cho Cloudflare Tunnel va Railway deploy.

## 2026-03-19 - VPS rollout prep va live migration

- Tao root `AGENTS.md`, bootstrap `docs/CHANGELOG.md`, va bo `deploy/` rieng cho VPS rollout.
- Tao stack deploy moi cho VPS chi gom `1` app container bind noi bo `127.0.0.1:8011` va volume `deploy/data`.
- Tao helper command `lushvideo`, backup timer `lush-media-backup.timer`, va script `migrate_from_live_api.py`.
- Clone repo len VPS tai `/opt/lush-media-video/app`, tao `.env`, build image, va deploy stack app voi project name rieng `lushvideo`.
- Import du lieu lich su tu `https://video.jazzrelaxation.com` vao VPS data dir: `1` user, `100` jobs, thumbnails, workflow snapshots.
- Phat hien su co trung Docker Compose project name `deploy` voi stack Spotify, sau do sua compose file cua app video sang project name rieng `lushvideo` va redeploy lai de tach biet hai stack.
- Xac nhan app video tren VPS login duoc voi `admin / lushmedia1243`, health UI tai `http://127.0.0.1:8011/`, va backup timer dang active.

## 2026-03-19 - Job deletion cleanup va page-scoped clear

- Sua backend de khi xoa tung job se don ca file local tren VPS trong `uploads/` va `workflows/`.
- Them che do `clear` theo danh sach `job_ids`, dung cho viec chi xoa cac job dang hien thi tren page hien tai.
- Sua frontend de nut `Clear List` thanh hanh vi `Xóa trang này`, chi gui job ids cua page dang xem thay vi clear toan bo list.
- Redeploy app len VPS va chay bai test thuc te bang job mau: xoa 1 job + clear 2 job, xac nhan DB row va file local deu bi xoa.

## 2026-03-19 - Fix gio Viet Nam va label phan trang

- Sua frontend parse timestamp de xem cac chuoi khong co timezone la UTC, sau do format bang `Asia/Ho_Chi_Minh`.
- Doi nhan phan trang `Truoc` thanh `Trước`.
- Redeploy app len VPS va xac nhan HTML moi da duoc serve voi label phan trang cap nhat.
