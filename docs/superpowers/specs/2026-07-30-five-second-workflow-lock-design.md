# Thiết kế khóa workflow về 5 giây

**Ngày:** 2026-07-30

## Mục tiêu

Biến 5 giây thành quy ước đúng giữa giao diện, file workflow và lúc vận hành.
Mọi workflow mặc định, preset hoặc do người dùng tải lên đều phải chạy với
`61` frame nguồn. Workflow 6 giây cũ không được giữ nguyên thời lượng khi đưa
vào hệ thống.

## Phạm vi

- Đổi tên workflow fallback và hai preset Jazz từ `6s` thành `5s`.
- Cập nhật `config.WORKFLOW_PATH` sang tên fallback mới.
- API preset chỉ liệt kê các tên `5s`.
- Hai tên preset Jazz `6s` cũ được giữ dưới dạng alias ẩn, trỏ tới file `5s`
  tương ứng để request cũ không bị lỗi.
- Chuẩn hóa workflow tải lên từ web, Telegram, fallback, preset và prompt cuối
  cùng thành `WanFirstLastFrameToVideo.length = 61`.
- Chỉ lưu workflow đã chuẩn hóa vào archive của job để file tải xuống khớp với
  workflow thực sự được gửi sang ComfyUI.

## Guard dùng chung

Thêm guard thời lượng cạnh guard khóa diffusion model hiện có trong
`workflow_guard.py`. Guard duyệt được cả node map dạng API và danh sách `nodes`
dạng UI. Mọi node có `class_type` hoặc `type` là
`WanFirstLastFrameToVideo` đều bị đặt `length = 61`.

Hàm trả về số node đã thay đổi để ghi log. Gọi guard nhiều lần vẫn an toàn;
sau lần chuẩn hóa đầu tiên, các lần sau không thay đổi thêm dữ liệu.

## Luồng dữ liệu

1. Web hoặc Telegram đọc workflow JSON.
2. Các guard dùng chung khóa tên diffusion model và thời lượng video.
3. Object đã chuẩn hóa được lưu vào archive và đưa vào queue.
4. `build_prompt` deep-copy workflow trong queue rồi áp dụng lại cả hai guard
   như lớp bảo vệ cuối, trước khi thay image, kích thước, seed và tên output.

Fallback cũng đi qua luồng này sau khi được đọc từ file đã đổi tên.

## Tương thích ngược

- Danh sách preset chỉ hiển thị tên `5s`.
- Request dùng hai tên preset `6s` cũ được resolve nội bộ sang file `5s` tương
  ứng và nhận về filename mới.
- Không sửa các workflow lịch sử trong `/data/workflows`.
- Tên file workflow cũ do người dùng upload có thể vẫn được giữ làm metadata
  của job, nhưng workflow archive và prompt thực thi luôn bị khóa ở `61` frame.

## Kiểm thử

- Unit test guard thời lượng với workflow dạng API, dạng UI, tính idempotent,
  giá trị cao/thấp hơn `61` và node không liên quan.
- Cập nhật test workflow đóng gói để bắt buộc tên file mới và không cho phép
  filename nào còn chứa `6s`.
- Test alias preset cũ và đường dẫn fallback mặc định.
- Xác minh web, Telegram và `build_prompt` đều gọi guard thời lượng dùng chung.
- Chạy toàn bộ Python test suite và regression test workflow JSON.

## Ngoài phạm vi

- Không viết lại workflow lịch sử trong `/data/workflows`.
- Không thay đổi tiled VAE, khóa model, bộ lập lịch worker hoặc supervisor
  ComfyUI.
- Không redeploy hoặc bật worker production trước khi thay đổi code được kiểm
  thử riêng.
