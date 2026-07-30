# Tiled VAE And Singleton GPU Worker Design

## Mục tiêu

- Mọi workflow mặc định và preset do app phân phối phải dùng
  `VAEDecodeTiled` với cấu hình đã chạy thành công trên RTX 5090.
- GPU1 chỉ được có một ComfyUI thuộc `D:\ComfyUI1`, lắng nghe duy nhất tại
  `127.0.0.1:8188`.
- Nếu ComfyUI crash hoặc bị kill, Scheduled Task phải khởi động lại đúng một
  instance, không tạo thêm process ở cổng khác.
- Trong giai đoạn kiểm thử, backend production vẫn giữ
  `COMFYUI_SERVERS_JSON=[]` để không giao job mới cho GPU1.

## Phạm vi workflow

App dùng `config.WORKFLOW_PATH` cho workflow mặc định và
`config.WORKFLOW_PRESET_DIR` cho danh sách preset. Vì vậy thay đổi đúng sáu
file sau:

- `workflows/Jazz & lofi 6s Khong Loop.json`
- `workflows/presets/Jazz & lofi 6s Co Loop.json`
- `workflows/presets/Jazz & lofi 6s Khong Loop.json`
- `workflows/presets/Kling Animation 5s Co Loop.json`
- `workflows/presets/Kling Animation 5s Khong Loop.json`
- `workflows/presets/Livewallpaper 5s Khong Loop.json`

Không thay đổi workflow đã lưu theo job trong `/data/workflows` và không đưa
hai file `FULLHD_*` legacy vào migration này vì app hiện không dùng chúng làm
default hoặc preset.

Trong mỗi file, node `VAEDecode` hiện tại được đổi thành `VAEDecodeTiled`, giữ
nguyên liên kết `samples` và `vae`, đồng thời thêm:

```json
{
  "tile_size": 512,
  "overlap": 64,
  "temporal_size": 16,
  "temporal_overlap": 4
}
```

## Cơ chế singleton

Nguồn lỗi hiện tại là cấu hình worker đặt `LocalPort=8188` nhưng batch runtime
lại hardcode `--port 8288`. Supervisor chỉ tìm process đúng cổng cấu hình nên
không nhìn thấy process 8288 và có thể tiếp tục gọi batch.

Phương án triển khai:

1. Sửa batch runtime GPU1 về `--port 8188`.
2. Bổ sung helper liệt kê toàn bộ ComfyUI process thuộc đúng
   `ComfyDirectory`, không phụ thuộc cổng.
3. Trước khi khởi động, supervisor dừng mọi process cùng thư mục nhưng sai
   cổng; nếu có nhiều process đúng cổng thì chỉ giữ một.
4. Thêm launch guard theo thời điểm gọi batch để không gọi lặp trong khoảng
   process Python đang hình thành.
5. Giữ hai lớp singleton hiện có:
   Scheduled Task `MultipleInstances=IgnoreNew` và file lock exclusive.
6. Nếu cổng 8188 do process không thuộc worker chiếm giữ, supervisor từ chối
   can thiệp và ghi log thay vì kill process ngoài phạm vi.

## Kiểm thử

### Automated

- Test helper nhận diện ComfyUI cùng thư mục trên cả cổng đúng và sai.
- Test policy chọn process cần giữ/dừng khi có orphan hoặc duplicate.
- Test supervisor có launch guard, file lock và batch/config port contract.
- Test toàn bộ sáu workflow chỉ chứa `VAEDecodeTiled` với đúng bốn tham số.

### Runtime

1. Xác nhận queue 8288 rỗng rồi kill process 8288.
2. Bật Scheduled Task và chờ `http://127.0.0.1:8188/system_stats` trả HTTP 200.
3. Chạy workflow 73 frame đã tái hiện lỗi, xác nhận history `success` và có
   file video output.
4. Khi queue 8188 rỗng, kill process 8188.
5. Chờ watchdog phục hồi, sau đó xác nhận:
   - đúng một ComfyUI process thuộc `D:\ComfyUI1`;
   - chỉ cổng 8188 lắng nghe;
   - không có listener 8288;
   - không có nhiều supervisor;
   - watchdog log chỉ có một lần khởi động cho lần phục hồi.

## Triển khai app host

- Commit và push thay đổi lên `origin/main`.
- Đồng bộ checkout `/opt/lush-media-video/app` từ GitHub theo deploy helper.
- Rebuild container từ commit sạch.
- Xác nhận container `APP_COMMIT` khớp commit mới và API preset trả workflow
  tiled.
- Không bật lại scheduling GPU trong bước này; production tiếp tục dùng
  `COMFYUI_SERVERS_JSON=[]`.

## Tiêu chí hoàn tất

- Sáu workflow nguồn trong repo và container production có cấu hình tiled đã
  chốt.
- Job 73 frame hoàn tất trên cổng 8188.
- Bài test kill/restart tạo lại đúng một process 8188.
- Cổng 8288 không còn listener.
- Backend production chưa giao job mới cho GPU1.
