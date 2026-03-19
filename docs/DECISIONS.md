# DECISIONS LOG

| Decision | Reason | Impact | Date |
| --- | --- | --- | --- |
| FastAPI thay Flask | Async, WebSocket native, va hop voi update realtime job. | Backend core | 2026-03-03 |
| SQLite thay PostgreSQL | Don gian, khong can setup server DB rieng, du cho scope hien tai. | Database | 2026-03-03 |
| JWT auth thay session | Stateless, hop voi API va WebSocket auth. | Auth | 2026-03-03 |
| Round-robin load balancing | Don gian, cong bang cho 2 GPU cung chuc nang. | GPU scheduling | 2026-03-03 |
| Cloudflare Tunnel cho GPU endpoints | Khong expose thang ComfyUI ra internet va khong can mo port tren may GPU. | Networking | 2026-03-03 |
| Railway la public runtime ban dau | De deploy nhanh tu GitHub trong giai doan dau. | Infrastructure | 2026-03-03 |
| Bind app tren VPS tai `127.0.0.1:8011` sau shared Caddy | VPS da co Caddy phuc vu domain Spotify, nen app video can chay o cong noi bo rieng de tranh tranh chap `80/443` va tai su dung reverse proxy san co. | Infrastructure | 2026-03-19 |
| Migrate lich su qua live API truoc khi co file SQLite goc | User chua cung cap duoc volume runtime Railway, nen migration qua live API la cach nhanh nhat de co lai user/jobs co ban tren VPS. | Data migration | 2026-03-19 |
| Dung project name `lushvideo` cho Docker Compose | Repo nay khong duoc dung project name mac dinh `deploy`, neu khong se co nguy co de service cua repo khac tren cung VPS. | Operations | 2026-03-19 |
| Xoa job phai don ca file local cua job va `Clear List` chi tac dong page hien tai | User muon khi xoa danh sach thi VPS cung sach file input/workflow, dong thoi tranh viec nut clear quet sach ca cac page khong dang xem. | UX + data hygiene | 2026-03-19 |
| Parse timestamp khong timezone nhu UTC truoc khi format gio Viet Nam | Du lieu job tu SQLite va migrate co the luu chuoi thoi gian khong kem offset, neu de browser tu hieu se de bi lech gio tren UI. | UX | 2026-03-19 |
| Rotate admin login via `lushvideo set-admin` against SQLite instead of changing env only | `ADMIN_USERNAME` / `ADMIN_PASSWORD` bootstrap the first admin only; after migration, persisted auth changes must update the existing `users` row. | Operations | 2026-03-19 |
