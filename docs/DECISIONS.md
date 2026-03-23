# DECISIONS LOG

| Decision                   | Reason                                          | Impact         | Date       |
| -------------------------- | ----------------------------------------------- | -------------- | ---------- |
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
