# Regular VAE And Six-Second Workflows Design

## Mục tiêu

Khôi phục chất lượng video ổn định bằng `VAEDecode` thường, đưa các workflow
Jazz về đúng thời lượng 6 giây như trước, đồng thời giữ nguyên workflow 5 giây
Kling/Livewallpaper và workflow người dùng có số frame hợp lệ.

## Bằng chứng và nguyên nhân

- So sánh cùng latent 73 frame cho thấy `VAEDecodeTiled` tạo biến thiên độ sáng
  p95 cao hơn khoảng 23 lần so với `VAEDecode`.
- GPU2 có 128 GB RAM đã chạy `VAEDecode` thường thành công, không OOM, không đổi
  PID và không gây lag quan sát được.
- Commit trước khi áp dụng tiled VAE xác nhận:
  - Jazz mặc định và hai preset Jazz dùng 73 frame, tên 6 giây.
  - Hai preset Kling và Livewallpaper dùng 61 frame, tên 5 giây.
  - Tất cả workflow trên dùng `VAEDecode` thường.

## Contract workflow đóng gói

- Fallback:
  `workflows/Jazz & lofi 6s Khong Loop.json`, 73 frame.
- Preset:
  - `Jazz & lofi 6s Co Loop.json`, 73 frame.
  - `Jazz & lofi 6s Khong Loop.json`, 73 frame.
  - `Kling Animation 5s Co Loop.json`, 61 frame.
  - `Kling Animation 5s Khong Loop.json`, 61 frame.
  - `Livewallpaper 5s Khong Loop.json`, 61 frame.
- Mỗi workflow chỉ có một node decode và node đó phải là `VAEDecode`.
- Xóa các input chỉ dành cho tiled decode:
  `tile_size`, `overlap`, `temporal_size`, `temporal_overlap`.
- Giữ nguyên node ID, liên kết, model, seed và các thông số khác.

## Policy workflow người dùng

- `WanFirstLastFrameToVideo.length` là giới hạn trên, không phải giá trị khóa.
- Giá trị nguyên không lớn hơn 73 được giữ nguyên, gồm 49, 61 và 73.
- Giá trị lớn hơn 73 bị hạ xuống 73 trước khi archive và submit.
- Giá trị thiếu hoặc không phải số nguyên hợp lệ nhận mặc định 73 để giữ prompt
  ComfyUI hợp lệ.
- Policy áp dụng đồng nhất tại Web, Telegram và `build_prompt`.

## Tương thích tên preset

- API danh sách preset chỉ hiển thị tên Jazz `6s`.
- Hai tên Jazz `5s` từng phát hành được giữ làm alias ẩn trỏ sang file `6s`,
  tránh làm hỏng bookmark hoặc client cũ.

## Kiểm thử

- Automated tests xác nhận đúng tên preset, đúng frame theo từng workflow và chỉ
  dùng `VAEDecode` thường.
- Unit/integration tests xác nhận 61 frame được giữ nguyên, 73 được giữ nguyên,
  giá trị lớn hơn 73 bị hạ xuống 73 tại cả ba ingress.
- Chạy đầy đủ Python và PowerShell regression suites.
- Khi app vẫn maintenance, submit trực tiếp một Kling 5 giây dùng
  `VAEDecode` thường lên GPU2; theo dõi RAM, VRAM, PID, queue, output và đo biến
  thiên temporal/brightness để xác nhận không còn nhấp nháy bất thường.

## Triển khai an toàn

- Không gỡ `COMFYUI_SERVERS_JSON=[]` trong đợt thay đổi này.
- Không bật scheduler GPU1/GPU2.
- Deploy code mới khi test đạt, sau đó xác nhận container healthy, domain HTTP
  200, commit runtime khớp và backend vẫn có 0 worker.

## GPU1 visible launcher

- GPU1 không tiếp tục chạy supervisor bằng Scheduled Task dưới `SYSTEM`.
- Scheduled Task `LushMedia-ComfyUI-gpu1` được stop và disable, không xóa để còn
  đường rollback rõ ràng.
- Desktop có file `START LushMedia GPU1.bat`; cùng launcher được gọi từ Startup
  của tài khoản `Admin` sau khi đăng nhập Windows.
- Launcher gọi supervisor với chế độ `-Interactive`. ComfyUI batch chạy chung
  console bằng `-NoNewWindow`, nên log ComfyUI hiện ngay trong cửa sổ launcher.
- File lock và process reconciliation hiện có tiếp tục bảo đảm một supervisor,
  một ComfyUI process và một listener `8188`; double-click nhiều lần không tạo
  worker trùng.
- Reverse SSH tunnel vẫn là process ẩn do không cần người vận hành tương tác.
- Private key chỉ được cấp quyền đọc cho đúng tài khoản tương tác đang chạy
  launcher; không mở ACL cho nhóm người dùng rộng.
- Cơ chế visible launcher chỉ tự chạy sau khi tài khoản Windows đăng nhập. Nếu
  máy reboot nhưng chưa có ai đăng nhập thì GPU1 chưa online; đây là trade-off
  được chấp nhận để đổi lấy cửa sổ dễ quan sát và phục hồi thủ công.
- Máy 2 chưa thay runtime trong đợt này; repo và tài liệu cung cấp cùng installer
  để Codex máy 2 áp dụng sau.
