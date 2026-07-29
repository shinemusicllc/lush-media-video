# DECISIONS LOG

| Decision                   | Reason                                          | Impact         | Date       |
| -------------------------- | ----------------------------------------------- | -------------- | ---------- |
| Normalize Wan 2.2 high/low diffusion model names at runtime | Uploaded or stale workflow files can still reference old diffusion models and fail on ComfyUI; normalize UNETLoader model names to the configured fp8 KJ high/low files before archive and prompt submission. | Workflow reliability | 2026-05-28 |
| Run one independently supervised ComfyUI worker per Windows machine | A dual-GPU single host is one failure domain; independent hosts, SSH keys, reverse ports, and watchdogs let the remaining worker continue accepting jobs when one machine restarts or fails. The backend chooses only online workers, prefers idle workers, then uses queue depth and round-robin tie-breaking. | GPU scheduling and operations | 2026-07-29 |
| Build VPS app only from clean Git commit | Dirty working trees made runtime code hard to trace; deploy now records `APP_COMMIT` and refuses dirty tracked builds. | Operations | 2026-05-20 |
| Keep `deploy/data` outside source/build context | Runtime uploads, SQLite, workflows, and backups must not appear as untracked source or enter Docker images. | Operations | 2026-05-20 |
| FastAPI thay Flask         | Async, WS native, performance tốt hơn           | Backend core   | 2026-03-03 |
| SQLite thay PostgreSQL     | Đơn giản, không cần setup, đủ cho scale nhỏ-vừa | Database       | 2026-03-03 |
| JWT auth thay session      | Stateless, dễ scale, WS compatible              | Auth           | 2026-03-03 |
| Round-robin load balancing | Đơn giản, fair cho 2 GPU cùng spec              | GPU scheduling | 2026-03-03 |
| Resolution cố định Full HD | User yêu cầu, giảm phức tạp UI                  | UI             | 2026-03-03 |
| Prompt/Seed ẩn khỏi UI     | User yêu cầu, giữ UI tối giản                   | UI             | 2026-03-03 |
| Dark theme + glassmorphism | Phù hợp AI/video context, modern                | Design         | 2026-03-03 |
| Cloudflare Tunnel          | Expose ComfyUI an toàn, miễn phí, không mở port | Networking     | 2026-03-03 |
| Railway.app cloud deploy   | Dễ deploy, Docker native, auto-deploy từ GitHub  | Infrastructure | 2026-03-03 |
| Env vars thay hardcode     | Bảo mật, flexible giữa dev/prod                 | Config         | 2026-03-03 |
| Dùng working tree hiện tại trên VPS làm nguồn sync về local | VPS đang chứa hotfix và thay đổi deploy chưa có đủ trên local/GitHub, nên cần kéo server state về để local bám đúng trạng thái vận hành thực tế. | Operations | 2026-03-23 |
| Push snapshot da doi chieu tu VPS len GitHub truoc khi tiep tuc dong bo | GitHub dang cham hon runtime VPS; can dua trang thai da xac minh tren server len `origin/main` de bien GitHub thanh moc sync chung cho local va cac may khac. | Source control | 2026-03-23 |
| Chung queue xu ly giua web va Telegram, tach kenh hien thi | Can giu FIFO duy nhat va logic xu ly duy nhat, nhung job Telegram khong nen xuat hien tren dashboard web thong thuong. | Backend + UX | 2026-03-23 |
| Dung Telegram long polling trong cung app FastAPI | Trien khai don gian hon webhook, khong can them endpoint public rieng hay service bot tach biet trong giai doan dau. | Operations | 2026-03-23 |
| Telegram bot chi nhan anh dang Document | Anh gui theo che do Photo cua Telegram bi nen va co the lam giam chat luong input, nen bot phai huong user dung Document de giu file goc. | UX + media quality | 2026-03-23 |
| Telegram bot chi chot batch sau khoang lang upload | Upload document co the den lech nhịp trong nhung giay ke tiep; cho chat on dinh roi moi thong bao/enqueue se giam nhac sai va tranh tao duplicate job. | Telegram UX + queue reliability | 2026-03-23 |
| Telegram bot enqueue ngay khi du 2 file, chi tre hint thieu file | User uu tien cam giac phan hoi nhanh; bot se chi delay nhac thieu file cho case chat hien chi thay 1 file, con khi du workflow + image thi enqueue ngay. | Telegram UX + queue reliability | 2026-03-23 |
| Telegram completion notifications phai co retry va backfill | Notify ra Telegram la outbound network call co the that bai tam thoi; can tu retry va quet job chua duoc danh dau `telegram_notified_at` de tranh rot thong bao khi nhieu chat dung dong thoi. | Telegram reliability | 2026-03-24 |
