# GPU1 VisibleGuard Design

## Mục tiêu

Giữ visible worker của GPU1 tự phục hồi ngay cả khi cả cửa sổ `cmd.exe` và
interactive supervisor bị đóng, đồng thời không tạo nhiều cửa sổ, không đụng
worker khác và không làm mất job đang chạy.

## Thiết kế

- Thêm `comfyui-worker-visible-guard.ps1` chạy hidden trong per-user Scheduled
  Task `LushMedia-ComfyUI-gpu1-VisibleGuard`.
- Guard dùng file lock riêng, poll mỗi 5 giây và chỉ công nhận PowerShell chạy
  supervisor qua `-File`; `-Command` và `-EncodedCommand` luôn bị loại.
- Khi supervisor thật biến mất, guard dừng đúng tunnel khớp private key,
  reverse forward `18188` và remote host của config.
- Guard chỉ dừng ComfyUI thuộc đúng `ComfyDirectory` khi đọc được queue và cả
  `queue_running`/`queue_pending` đều rỗng. Queue bận hoặc không đọc được thì
  giữ ComfyUI để supervisor mới nhận lại.
- Guard mở visible batch bằng `cmd.exe /d /c call ...`, `-WindowStyle Normal`
  và dùng `LaunchGuardSeconds` để chống spam.
- Desktop launcher chỉ gọi `schtasks.exe /Run` cho Guard task; Startup shortcut
  tiếp tục trỏ vào Desktop launcher.
- Installer visible đăng ký Guard task bằng interactive user, `LogonType`
  `Interactive`, `RunLevel Highest`, hidden action và `MultipleInstances
  IgnoreNew`; legacy `SYSTEM` task vẫn disabled.
- Batch runtime được bổ sung một lần `--disable-auto-launch` ngay sau
  `--windows-standalone-build`; không restart worker đang chạy.

## Phạm vi an toàn

- Đọc `ComfyDirectory`, `BatchFile`, private key và port từ worker config.
- Không thay private key, không sửa VPS, không redeploy, không đổi production
  scheduling.
- Không commit hoặc push.

## Kiểm thử

- Test RED/GREEN cho detector, launcher `schtasks`, flag idempotent và asset
  Guard/installer contract.
- Chạy toàn bộ Python và hai PowerShell regression suites.
- Khi queue `0/0`, ghi PID rồi kill đúng supervisor GPU1 và parent visible
  `cmd.exe`; xác minh cùng Guard PID tự mở một visible window mới, sinh PID
  supervisor/ComfyUI/tunnel mới, đúng một log launch, một listener `8188`,
  không có `8288`, health `200`, queue cuối `0/0`.
