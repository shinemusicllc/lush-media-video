# Single-GPU Worker over VPS Reverse SSH Tunnel

## Mục tiêu

Đưa máy Windows hiện tại, có một NVIDIA GeForce RTX 5090, vào hệ thống Lush Media Video dưới vai trò `gpu1`. Web app tại `video.lushmedia.net` phải nhận GPU này qua kết nối nội bộ trên VPS, phân phối job theo tải với round-robin khi các worker ngang nhau, và tự phục hồi khi ComfyUI hoặc tunnel bị dừng.

Phạm vi hiện tại chỉ triển khai `gpu1`. Tài liệu bàn giao phải đủ để Codex trên máy thứ hai bổ sung `gpu2` sau này mà không thay đổi API hoặc kiến trúc backend.

## Trạng thái đã xác minh

- Local checkout: `D:\web app comfyui\comfyui_bot`.
- Git remote chuẩn: `origin = https://github.com/shinemusicllc/lush-media-video.git`.
- Local branch `main` đang chậm `origin/main` bốn commit tại thời điểm khảo sát.
- Local có thay đổi chưa commit trong `comfyui_client.py`, logo và một số file demo/backup.
- Máy hiện tại có một RTX 5090 32 GB, CUDA device `0`.
- ComfyUI nằm tại `D:\ComfyUI1` và chạy trên `127.0.0.1:8188`.
- Chưa có ComfyUI listener hoặc Scheduled Task đang hoạt động tại thời điểm khảo sát.
- Bộ script cũ vẫn giả định hai GPU trên cùng máy và phải được thay bằng cấu hình một worker cho mỗi máy.

## Quyết định kiến trúc

Sử dụng reverse SSH tunnel từ từng máy GPU tới VPS. Không public ComfyUI qua Cloudflare Tunnel hoặc mở port ComfyUI trực tiếp ra Internet.

Luồng `gpu1`:

```text
Browser
  -> video.lushmedia.net
  -> reverse proxy trên VPS
  -> FastAPI container
  -> http://172.19.0.1:18188
  -> reverse SSH tunnel
  -> 127.0.0.1:8188 trên máy GPU #1
  -> ComfyUI / CUDA device 0
```

Contract dành cho worker:

| Worker | Backend ID | Local ComfyUI | Remote VPS bind |
| --- | --- | --- | --- |
| Máy hiện tại | `gpu1` | `127.0.0.1:8188` | `172.19.0.1:18188` |
| Máy thứ hai | `gpu2` | `127.0.0.1:8188` | `172.19.0.1:18288` |

Trước khi áp dụng, deployment phải xác minh Docker gateway mà container `lushvideo-app-1` dùng. Giá trị `172.19.0.1` chỉ được giữ khi khớp với network runtime hiện tại.

## Phân phối job

Backend giữ một async queue và một worker tuần tự cho mỗi ComfyUI server. Mỗi worker chỉ chạy một job tại một thời điểm.

Khi có job mới:

1. Chỉ ưu tiên server có health check thành công.
2. Chọn server rảnh trước server bận.
3. Nếu cùng trạng thái, chọn queue ngắn hơn.
4. Nếu vẫn ngang nhau, dùng thứ tự round-robin để tránh thiên lệch.

Job đã gắn với một worker không được tự động gửi trùng sang worker khác khi mất kết nối tạm thời. Worker chờ phục hồi, kiểm tra queue/history của ComfyUI, rồi mới quyết định hoàn tất, tiếp tục theo dõi hoặc báo lỗi.

Khi chỉ có `gpu1`, mọi job hợp lệ vào queue của `gpu1`. Khi thêm `gpu2`, cùng thuật toán tự sử dụng cả hai worker mà không đổi route hoặc payload của web app.

## Watchdog trên máy GPU

Một PowerShell supervisor duy nhất quản lý hai tiến trình độc lập:

- ComfyUI trên `127.0.0.1:8188`.
- Reverse SSH tunnel từ VPS port `18188` về local port `8188`.

Supervisor phải:

- Dùng file lock để ngăn hai instance chạy đồng thời.
- Khởi động ComfyUI bằng `D:\ComfyUI1\run_nvidia_gpu.bat`.
- Xác minh đúng một CUDA device và dùng `--cuda-device 0`.
- Gọi `/system_stats` định kỳ thay vì chỉ kiểm tra process tồn tại.
- Chỉ dừng process khi đường dẫn, command line và port đều khớp ComfyUI được quản lý.
- Cho phép thời gian tải model/startup trước khi kết luận health check thất bại.
- Chỉ restart ComfyUI sau nhiều health check thất bại liên tiếp.
- Quản lý tunnel riêng; tunnel chết không được kéo theo restart ComfyUI.
- Reconnect tunnel với exponential backoff và SSH keepalive.
- Dùng `BatchMode=yes`, `IdentitiesOnly=yes` và private key có ACL chỉ cho tài khoản chạy task.
- Chạy ẩn bằng Windows Scheduled Task lúc boot, kể cả chưa có người đăng nhập.
- Ghi log riêng cho supervisor, ComfyUI stdout/stderr và SSH stderr.
- Giới hạn hoặc xoay log để máy chạy 24/7 không làm đầy ổ đĩa.

Các script supervisor hai-GPU cũ không được chạy song song với supervisor mới.

## SSH và bảo mật

- Tunnel đăng nhập VPS bằng user `deploy`, không dùng `root`.
- SSH key hiện có phải được kiểm tra fingerprint và sửa ACL trước khi dùng.
- Public key trên VPS chỉ được cấp quyền cần thiết cho reverse forwarding.
- ComfyUI chỉ listen trên `127.0.0.1`; không listen trên `0.0.0.0`.
- VPS chỉ expose endpoint tunnel tới Docker network cần dùng, không expose trên public interface.
- Không ghi private key, mật khẩu, token hoặc nội dung `deploy/.env` vào Git hay log.
- Mật khẩu root đã xuất hiện trong hội thoại phải được rotate sau khi triển khai và xác minh xong.

## Đồng bộ Git và VPS

`origin/main` là source of truth cho code production.

Trình tự đồng bộ:

1. Ghi lại HEAD, status và diff của local checkout.
2. Tạo backup có thể khôi phục cho toàn bộ thay đổi tracked và untracked hiện tại.
3. Fast-forward local `main` tới `origin/main`.
4. Review riêng bản vá `comfyui_client.py`; chỉ áp dụng lại phần polling history nếu upstream chưa có hành vi tương đương.
5. Không tự động đưa logo, demo login hoặc file workflow backup cục bộ vào production.
6. Chạy syntax/smoke verification trước khi commit và push thay đổi mới.
7. Trên VPS, backup Git status/diff và xác minh `deploy/.env`, `deploy/data/`.
8. Đồng bộ VPS checkout về đúng commit trên `origin/main`.
9. Rebuild container bằng deploy helper hiện có và xác minh `APP_COMMIT`.

Không thay đổi `DB_PATH`, `UPLOAD_DIR`, `WORKFLOW_ARCHIVE_DIR`, admin credentials hoặc `JWT_SECRET`. Runtime data trong `deploy/data/` phải tồn tại qua toàn bộ quá trình.

## Cấu hình backend

Giai đoạn đầu cấu hình một server:

```json
[
  {
    "id": "gpu1",
    "name": "GPU #1",
    "url": "http://172.19.0.1:18188"
  }
]
```

Khi máy thứ hai sẵn sàng, mở rộng thành:

```json
[
  {
    "id": "gpu1",
    "name": "GPU #1",
    "url": "http://172.19.0.1:18188"
  },
  {
    "id": "gpu2",
    "name": "GPU #2",
    "url": "http://172.19.0.1:18288"
  }
]
```

Cấu hình thực tế nằm trong secret/runtime env trên VPS. JSON trên là contract, không phải file chứa secret được commit.

## Recovery và lỗi

- ComfyUI chết: supervisor khởi động lại sau ngưỡng health failure.
- Tunnel chết: tunnel tự reconnect; ComfyUI tiếp tục chạy.
- VPS/web app restart: backend đọc các job `queued`/`running`, kiểm tra ComfyUI history và active queue trước khi requeue.
- Worker offline khi nhận job mới: backend chọn worker online còn lại; nếu không có worker online, API phải báo không có ComfyUI server khả dụng thay vì âm thầm mất job.
- Worker offline giữa job: giữ binding ban đầu trong thời gian recovery; không chạy song song cùng job trên máy khác.
- WebSocket không phát sự kiện cuối: polling history định kỳ giải phóng worker khi history đã `completed`, có output hoặc kết thúc với trạng thái terminal.

## Xác minh và tiêu chí hoàn tất

### Local worker

- `nvidia-smi` thấy đúng RTX 5090 tại index `0`.
- `http://127.0.0.1:8188/system_stats` trả HTTP 200.
- Chỉ một supervisor hoạt động.
- Scheduled Task tự chạy sau reboot khi chưa đăng nhập.
- Kill ComfyUI có kiểm soát dẫn tới tự restart.
- Kill tunnel có kiểm soát dẫn tới tự reconnect mà ComfyUI không restart.

### VPS và backend

- Container gọi được `http://172.19.0.1:18188/system_stats`.
- `/api/admin/servers` hiển thị `gpu1` online/idle khi rảnh.
- Local, GitHub, VPS checkout và `APP_COMMIT` cùng một commit.
- Login, job list và authenticated API request vẫn hoạt động.
- `deploy/data/` và dữ liệu lịch sử còn nguyên.

### End-to-end

- Submit một job thực từ web app.
- Job chuyển `queued -> running -> done`, progress cập nhật và video tải được.
- Job thứ hai được nhận sau khi job thứ nhất giải phóng worker.
- Restart web app trong một bài kiểm tra có kiểm soát không tạo prompt trùng.

## Bàn giao máy GPU #2

Runbook phải yêu cầu Codex trên máy thứ hai:

1. Xác minh một GPU tại CUDA index `0`.
2. Chạy ComfyUI local tại `127.0.0.1:8188`.
3. Tạo SSH key riêng, không sao chép private key của `gpu1`.
4. Cài supervisor cùng contract với `WORKER_ID=gpu2`.
5. Dùng remote port `18288`.
6. Xác minh VPS listener và health từ container.
7. Chỉ sau khi worker online mới thêm entry `gpu2` vào backend env và redeploy.
8. Chạy test hai job đồng thời để chứng minh mỗi máy nhận một job, sau đó chạy thêm job để chứng minh máy rảnh trước nhận tiếp.

## Ngoài phạm vi

- Xây agent protocol hoặc distributed message broker mới.
- Public ComfyUI bằng Cloudflare Tunnel.
- Thay đổi giao diện web, API payload hoặc SQLite schema.
- Thiết lập phần cứng/phần mềm cụ thể trên máy GPU #2 trong phiên này.
