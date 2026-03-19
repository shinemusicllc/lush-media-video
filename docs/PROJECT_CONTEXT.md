# PROJECT CONTEXT - Lush Media Video

## Muc tieu

Web app tao video tu anh thong qua ComfyUI, ho tro dang nhap web, submit queue, theo doi job, tai thumbnail/video/workflow, va can bang tai giua 2 GPU.

## Stack

- **Frontend**: HTML/CSS/JS trong `static/`
- **Backend**: FastAPI + JWT auth + WebSocket updates
- **Data**: SQLite + filesystem persistence
- **GPU compute**: ComfyUI qua Cloudflare Tunnel
- **Current public production on 2026-03-19**: Railway tai `https://video.jazzrelaxation.com`
- **Prepared VPS runtime on 2026-03-19**: app bind noi bo `127.0.0.1:8011` tren VPS `82.197.71.6`

## Current Deploy State

- Shared Caddy dang chay tren stack SpotiCheck se publish `video.jazzrelaxation.com` sau khi Cloudflare DNS cutover sang VPS.
- App video da chay healthy tren VPS qua `http://127.0.0.1:8011/`.
- Persistent data tren VPS nam tai `/opt/lush-media-video/app/deploy/data`:
  - `comfybot.db`
  - `uploads/`
  - `workflows/`
- Backup du lieu `data/` duoc schedule moi ngay luc `03:37` gio server qua `lush-media-backup.timer`.
- GPU van la dependency ben ngoai:
  - `https://gpu0.jazzrelaxation.com`
  - `https://gpu1.jazzrelaxation.com`

## Kien truc Runtime

```text
Browser -> Cloudflare -> shared Caddy on VPS -> FastAPI app (127.0.0.1:8011) -> ComfyUI tunnels (gpu0/gpu1)
```

- Frontend chi noi chuyen voi backend.
- Backend giu auth, job persistence, upload persistence, workflow snapshots, va proxy download cho assets output.
- Output lich su khong duoc copy ve VPS; backend van tai lai video/image cu tu ComfyUI tunnels dua tren `output_info`.
- Khi xoa job khoi danh sach, app co the don file local tren VPS cho job do (`uploads/` + `workflows/`), nhung khong xoa output goc dang nam tren may GPU/ComfyUI.
- Frontend format thoi gian job theo `Asia/Ho_Chi_Minh`; cac chuoi timestamp khong co timezone duoc xem la UTC truoc khi doi sang gio Viet Nam.

## Config quan trong

- `ADMIN_USERNAME`, `ADMIN_PASSWORD`
- `JWT_SECRET`
- `COMFYUI_GPU1`, `COMFYUI_GPU2`
- `DB_PATH=/data/comfybot.db`
- `UPLOAD_DIR=/data/uploads`
- `WORKFLOW_ARCHIVE_DIR=/data/workflows`
- `COMFYUI_DOWNLOAD_TIMEOUT_S`, `COMFYUI_HISTORY_TIMEOUT_S`, `COMFYUI_WS_IDLE_TIMEOUT_S`

## Van hanh auth tren VPS

- `ADMIN_USERNAME` va `ADMIN_PASSWORD` chi duoc dung de bootstrap admin lan dau neu user do chua ton tai.
- Sau migration, doi admin username/password tren VPS phai update SQLite `users` bang helper `lushvideo set-admin`.
- Khi doi username bang helper nay, app se cap nhat them `jobs.username` va dong bo `deploy/.env` de reboot sau do khong quay lai credential cu.

## Migration Notes

- Da import du lieu lich su tu app live qua API vao ngay `2026-03-19`.
- Migration live API chi lay duoc `100` jobs gan nhat vi `GET /api/jobs` cua admin hien dang bi cap `limit=100`.
- Tai thoi diem migrate, live API chi tra ve `1` user `admin`.
- Neu can migrate day du hon sau nay, can lay truc tiep file SQLite va thu muc `/data` tu runtime cu, khong chi qua API.
