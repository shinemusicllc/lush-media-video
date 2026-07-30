# Regular VAE And Six-Second Workflows Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Khôi phục Jazz 6 giây và regular VAE, giữ Kling/Livewallpaper 5 giây, đồng thời đổi policy upload thành giới hạn tối đa 73 frame.

**Architecture:** `workflow_guard.py` chuẩn hóa frame tại mọi ingress bằng một giới hạn trên dùng chung từ `config.py`. Các JSON workflow đóng gói giữ duration riêng theo preset nhưng cùng dùng `VAEDecode` thường; tên cũ được xử lý ở lớp preset alias trong `main.py`.

**Tech Stack:** Python 3, FastAPI, unittest, ComfyUI API workflow JSON, PowerShell worker supervisor.

## Global Constraints

- Giữ nguyên workflow có `length` nguyên và không lớn hơn 73.
- Chỉ hạ `length` lớn hơn 73 về 73; giá trị thiếu hoặc không hợp lệ dùng 73.
- Jazz fallback/preset dùng 73 frame và tên `6s`.
- Kling/Livewallpaper giữ 61 frame và tên `5s`.
- Tất cả workflow đóng gói dùng `VAEDecode`, không dùng `VAEDecodeTiled`.
- Không thay node ID, link, model hoặc các thông số workflow không liên quan.
- Production giữ `COMFYUI_SERVERS_JSON=[]` trong toàn bộ đợt triển khai.

---

### Task 1: Frame-limit policy

**Files:**
- Modify: `config.py`
- Modify: `workflow_guard.py`
- Modify: `comfyui_client.py`
- Modify: `main.py`
- Modify: `telegram_bot.py`
- Test: `tests/test_workflow_guard.py`
- Test: `tests/test_comfyui_client.py`
- Test: `tests/test_workflow_ingress.py`

**Interfaces:**
- Consumes: `config.WORKFLOW_DEFAULTS["length"]`.
- Produces: `enforce_max_video_length(workflow: dict[str, Any]) -> int`, trả số node đã được sửa.

- [ ] **Step 1: Viết test RED cho giới hạn tối đa 73**

  Sửa test để khẳng định các giá trị 61 và 73 được giữ nguyên, 85 bị hạ xuống
  73, còn giá trị thiếu/không hợp lệ nhận 73 ở API workflow và UI workflow.

- [ ] **Step 2: Chạy test và xác nhận thất bại đúng nguyên nhân**

  Run:
  `python -m unittest tests.test_workflow_guard tests.test_comfyui_client tests.test_workflow_ingress -v`

  Expected: FAIL vì code hiện ép mọi workflow thành 61.

- [ ] **Step 3: Cài đặt policy tối thiểu**

  Đặt `WORKFLOW_DEFAULTS["length"] = 73`, thay guard khóa cứng bằng
  `enforce_max_video_length`, và cập nhật Web, Telegram, `build_prompt` sử dụng
  guard mới. Guard chỉ thay giá trị lớn hơn 73 hoặc không phải số nguyên hợp lệ.

- [ ] **Step 4: Chạy lại nhóm test**

  Run:
  `python -m unittest tests.test_workflow_guard tests.test_comfyui_client tests.test_workflow_ingress -v`

  Expected: PASS.

- [ ] **Step 5: Commit**

  Run:
  `git add config.py workflow_guard.py comfyui_client.py main.py telegram_bot.py tests/test_workflow_guard.py tests/test_comfyui_client.py tests/test_workflow_ingress.py && git commit -m "fix: cap workflow videos at six seconds"`

### Task 2: Bundled workflow restoration

**Files:**
- Rename: `workflows/Jazz & lofi 5s Khong Loop.json`
- Rename: `workflows/presets/Jazz & lofi 5s Co Loop.json`
- Rename: `workflows/presets/Jazz & lofi 5s Khong Loop.json`
- Modify: `workflows/presets/Kling Animation 5s Co Loop.json`
- Modify: `workflows/presets/Kling Animation 5s Khong Loop.json`
- Modify: `workflows/presets/Livewallpaper 5s Khong Loop.json`
- Modify: `config.py`
- Modify: `main.py`
- Test: `tests/test_workflow_vae_config.py`
- Test: `tests/test_workflow_preset_aliases.py`

**Interfaces:**
- Consumes: ComfyUI API workflow JSON contract.
- Produces: một fallback và năm preset có tên, frame count và decode node đúng spec.

- [ ] **Step 1: Viết test RED cho tên, duration và regular VAE**

  Test phải yêu cầu ba file Jazz tên `6s`, Jazz có 73 frame,
  Kling/Livewallpaper có 61 frame, và mỗi file có đúng một node
  `class_type == "VAEDecode"` không chứa input tiled.

- [ ] **Step 2: Chạy test và xác nhận thất bại**

  Run:
  `python -m unittest tests.test_workflow_vae_config tests.test_workflow_preset_aliases -v`

  Expected: FAIL vì file hiện mang tên Jazz `5s` và dùng `VAEDecodeTiled`.

- [ ] **Step 3: Khôi phục JSON và alias**

  Đổi tên ba file Jazz về `6s`; đặt Jazz về 73 frame; thay node tiled của cả sáu
  file bằng `VAEDecode`, chỉ giữ `samples` và `vae`, đặt title `VAE Decode`.
  Cập nhật fallback path và alias ẩn từ tên Jazz `5s` sang `6s`.

- [ ] **Step 4: Chạy lại test workflow**

  Run:
  `python -m unittest tests.test_workflow_vae_config tests.test_workflow_preset_aliases -v`

  Expected: PASS.

- [ ] **Step 5: Commit**

  Run:
  `git add config.py main.py workflows tests/test_workflow_vae_config.py tests/test_workflow_preset_aliases.py && git commit -m "fix: restore regular VAE workflows"`

### Task 3: Memory and full regression

**Files:**
- Modify: `docs/modules/workflows.md`
- Modify: `docs/DECISIONS_INDEX.md`
- Modify: `docs/DECISIONS.md`
- Modify: `docs/CHANGELOG.md`

**Interfaces:**
- Consumes: verified runtime contract from Tasks 1-2.
- Produces: concise canonical memory for future GPU1/GPU2 work.

- [ ] **Step 1: Cập nhật canonical memory**

  Ghi regular VAE, duration theo preset, max 73 policy, bằng chứng flicker và yêu
  cầu 128 GB RAM; thay thế quyết định tiled VAE/khóa 61 frame đã lỗi thời.

- [ ] **Step 2: Chạy full Python suite**

  Run: `python -m unittest discover -s tests -v`

  Expected: toàn bộ test PASS.

- [ ] **Step 3: Chạy hai PowerShell worker suites**

  Run:
  `powershell -NoProfile -ExecutionPolicy Bypass -File deploy/windows/tests/comfyui-worker-common.tests.ps1`

  Run:
  `powershell -NoProfile -ExecutionPolicy Bypass -File deploy/windows/tests/comfyui-worker-scripts.tests.ps1`

  Expected: cả hai suite PASS.

- [ ] **Step 4: Kiểm tra JSON và diff**

  Parse toàn bộ `workflows/**/*.json`, chạy `git diff --check`, và xác nhận chỉ
  các file trong scope thay đổi.

- [ ] **Step 5: Commit**

  Run:
  `git add docs/modules/workflows.md docs/DECISIONS_INDEX.md docs/DECISIONS.md docs/CHANGELOG.md && git commit -m "docs: record regular VAE workflow policy"`

### Task 4: GPU1 visible launcher

**Files:**
- Modify: `deploy/windows/comfyui-worker-supervisor.ps1`
- Create: `deploy/windows/install-comfyui-worker-visible-launcher.ps1`
- Create: `deploy/windows/start-comfyui-worker-visible.bat`
- Modify: `deploy/windows/tests/comfyui-worker-scripts.tests.ps1`
- Modify: `docs/modules/gpu-workers.md`

**Interfaces:**
- Consumes: existing worker JSON and singleton supervisor contract.
- Produces: an interactive `-Interactive` supervisor mode, Desktop batch and Startup shortcut.

- [ ] **Step 1: Viết test RED cho visible launcher**

  Test parser và source contract phải yêu cầu launcher/installer tồn tại,
  supervisor có switch `Interactive`, interactive ComfyUI dùng `-NoNewWindow`,
  installer disable Scheduled Task cũ và tạo Startup shortcut.

- [ ] **Step 2: Chạy PowerShell test và xác nhận thất bại**

  Run:
  `powershell -NoProfile -ExecutionPolicy Bypass -File deploy/windows/tests/comfyui-worker-scripts.tests.ps1`

  Expected: FAIL vì visible launcher chưa tồn tại.

- [ ] **Step 3: Cài đặt visible mode tối thiểu**

  Thêm nhánh launch interactive không redirect output, dùng cùng console và giữ
  nguyên hidden mode cho Scheduled Task legacy. Installer tạo Desktop batch,
  Startup shortcut, cấp quyền private-key cho đúng interactive account, đồng
  thời stop/disable task cũ khi queue rỗng.

- [ ] **Step 4: Chạy lại PowerShell suites**

  Run:
  `powershell -NoProfile -ExecutionPolicy Bypass -File deploy/windows/tests/comfyui-worker-common.tests.ps1`

  Run:
  `powershell -NoProfile -ExecutionPolicy Bypass -File deploy/windows/tests/comfyui-worker-scripts.tests.ps1`

  Expected: cả hai PASS.

- [ ] **Step 5: Commit**

  Run:
  `git add deploy/windows docs/modules/gpu-workers.md && git commit -m "feat: add visible GPU worker launcher"`

### Task 5: GPU2 Kling 5-second validation

**Files:**
- Runtime-only telemetry under `D:\ComfyUI-Autostart\`; do not commit test output.

**Interfaces:**
- Consumes: `Kling Animation 5s Khong Loop.json`, a valid test image, GPU2 direct ComfyUI endpoint.
- Produces: prompt ID, history result, output MP4, RAM/VRAM/PID samples and flicker metrics.

- [ ] **Step 1: Preflight GPU2**

  Xác nhận queue rỗng, local/reverse endpoint healthy, đúng một ComfyUI PID và
  đủ RAM trước khi submit.

- [ ] **Step 2: Submit regular-VAE Kling job**

  Dùng workflow 61 frame, đổi seed để tránh cache sampling, submit trực tiếp
  ComfyUI; không đi qua scheduler đang maintenance.

- [ ] **Step 3: Theo dõi đến terminal history**

  Poll queue/history và ghi RAM available, ComfyUI private memory, system
  commit, VRAM free, PID cùng output path. Dừng và báo nếu PID đổi hoặc RAM xuống
  ngưỡng nguy hiểm.

- [ ] **Step 4: Đo và đối chiếu nhấp nháy**

  Tính brightness delta và temporal difference trên output; đối chiếu với số
  liệu Kling tiled nếu có, đồng thời báo rõ giới hạn nếu không có baseline cùng
  input/seed.

### Task 6: Deploy while maintenance remains active

**Files:**
- No new source files.

**Interfaces:**
- Consumes: clean tested Git commit and VPS env with `COMFYUI_SERVERS_JSON=[]`.
- Produces: healthy production container on the same commit with zero configured workers.

- [ ] **Step 1: Push/integrate approved branch**

  Chỉ tích hợp theo lựa chọn branch của người dùng; không force-push.

- [ ] **Step 2: Kiểm tra maintenance trước deploy**

  Backup VPS `.env`, xác nhận đúng một dòng `COMFYUI_SERVERS_JSON=[]`, và xác
  nhận app container đang có 0 worker.

- [ ] **Step 3: Update và redeploy**

  Pull đúng commit từ `origin/main`, chạy tracked `deploy/scripts/redeploy.sh`.

- [ ] **Step 4: Post-deploy verification**

  Xác nhận container healthy, `APP_COMMIT` khớp Git, domain HTTP 200, danh sách
  preset đúng và backend vẫn có 0 worker. Không submit job qua app.

- [ ] **Step 5: Chuyển GPU1 runtime sang visible launcher**

  Khi queue local rỗng, chạy installer cho `gpu1.worker.json`, xác nhận Scheduled
  Task bị disable, launcher Desktop/Startup tồn tại, rồi mở launcher visible.
  Xác nhận đúng một supervisor, một ComfyUI PID, listener 8188 duy nhất, không
  có 8288, local health HTTP 200 và tunnel phục hồi.
