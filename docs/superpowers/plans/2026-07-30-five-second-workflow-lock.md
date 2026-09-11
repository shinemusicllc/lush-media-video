# Kế hoạch triển khai khóa workflow về 5 giây

> **Dành cho agent triển khai:** REQUIRED SUB-SKILL: Dùng
> `superpowers:executing-plans` để thực hiện tuần tự từng task và dừng kiểm tra
> tại các checkpoint.

**Mục tiêu:** Đổi toàn bộ workflow đóng gói sang tên 5s và bắt buộc mọi
workflow được app chấp nhận chạy với `61` frame.

**Kiến trúc:** Chính sách thời lượng nằm trong `workflow_guard.py`, cạnh chính
sách khóa diffusion model. Web, Telegram và `build_prompt` cùng gọi guard này;
workflow được chuẩn hóa trước khi archive và được kiểm tra lại trước khi gửi
sang ComfyUI. API preset chỉ liệt kê tên mới nhưng resolve được hai alias cũ.

**Tech stack:** Python 3, FastAPI, `unittest`, JSON workflow ComfyUI.

## Ràng buộc chung

- Giá trị khóa là `WanFirstLastFrameToVideo.length = 61`.
- Không sửa workflow lịch sử trong `/data/workflows`.
- Giữ nguyên tiled VAE `512/64/16/4`, model lock, API job và scheduler.
- Không bật production scheduling; `COMFYUI_SERVERS_JSON=[]` vẫn giữ nguyên.
- Mọi thay đổi hành vi phải đi qua chu kỳ RED → GREEN.

---

### Task 1: Guard khóa thời lượng dùng chung

**Files:**
- Create: `tests/test_workflow_guard.py`
- Modify: `config.py`
- Modify: `workflow_guard.py`

**Interfaces:**
- Produces: `enforce_locked_video_length(workflow: dict[str, Any]) -> int`
- Consumes: `config.WORKFLOW_DEFAULTS["length"] == 61`

- [ ] **Step 1: Viết test RED cho workflow dạng API**

```python
def test_locks_api_workflow_video_length_to_61(self):
    workflow = {
        "12": {
            "class_type": "WanFirstLastFrameToVideo",
            "inputs": {"length": 73},
        }
    }
    self.assertEqual(1, enforce_locked_video_length(workflow))
    self.assertEqual(61, workflow["12"]["inputs"]["length"])
    self.assertEqual(0, enforce_locked_video_length(workflow))
```

- [ ] **Step 2: Viết test RED cho workflow dạng UI và node không liên quan**

```python
def test_locks_ui_workflow_length_widget(self):
    workflow = {
        "nodes": [{
            "type": "WanFirstLastFrameToVideo",
            "widgets_values": [1920, 1088, 73, 1],
        }]
    }
    self.assertEqual(1, enforce_locked_video_length(workflow))
    self.assertEqual(61, workflow["nodes"][0]["widgets_values"][2])

def test_does_not_change_unrelated_length_input(self):
    workflow = {"1": {"class_type": "OtherNode", "inputs": {"length": 73}}}
    self.assertEqual(0, enforce_locked_video_length(workflow))
    self.assertEqual(73, workflow["1"]["inputs"]["length"])
```

- [ ] **Step 3: Chạy test để xác nhận RED**

Run:

```powershell
python -m unittest tests.test_workflow_guard -v
```

Expected: FAIL vì chưa có `enforce_locked_video_length`.

- [ ] **Step 4: Thêm cấu hình và implementation tối thiểu**

```python
WORKFLOW_DEFAULTS = {
    "width": 1920,
    "height": 1080,
    "length": 61,
}
```

```python
def enforce_locked_video_length(workflow: dict[str, Any]) -> int:
    changed = 0
    locked = config.WORKFLOW_DEFAULTS["length"]
    for node in _iter_nodes(workflow):
        if not _is_wan_video_latent(node):
            continue
        inputs = node.get("inputs")
        if isinstance(inputs, dict):
            if inputs.get("length") != locked:
                inputs["length"] = locked
                changed += 1
            continue
        widgets = node.get("widgets_values")
        if isinstance(widgets, list) and len(widgets) > 2:
            if widgets[2] != locked:
                widgets[2] = locked
                changed += 1
    return changed
```

- [ ] **Step 5: Chạy test GREEN và commit**

```powershell
python -m unittest tests.test_workflow_guard -v
git add config.py workflow_guard.py tests/test_workflow_guard.py
git commit -m "feat: lock uploaded workflows to 61 frames"
```

### Task 2: Đổi tên workflow đóng gói và thêm alias preset

**Files:**
- Rename: `workflows/Jazz & lofi 6s Khong Loop.json`
  → `workflows/Jazz & lofi 5s Khong Loop.json`
- Rename: `workflows/presets/Jazz & lofi 6s Co Loop.json`
  → `workflows/presets/Jazz & lofi 5s Co Loop.json`
- Rename: `workflows/presets/Jazz & lofi 6s Khong Loop.json`
  → `workflows/presets/Jazz & lofi 5s Khong Loop.json`
- Modify: `config.py`
- Modify: `main.py`
- Modify: `tests/test_workflow_vae_config.py`
- Create: `tests/test_workflow_preset_aliases.py`

**Interfaces:**
- Produces: `_WORKFLOW_PRESET_ALIASES: dict[str, str]`
- Produces: `_resolve_workflow_preset(name: str) -> Path | None`
- Consumes: năm preset có filename chứa `5s`, không preset nào chứa `6s`

- [ ] **Step 1: Đổi expectation trong test sang tên 5s**

```python
DEFAULT_WORKFLOW = REPO_ROOT / "workflows" / "Jazz & lofi 5s Khong Loop.json"
EXPECTED_PRESETS = {
    "Jazz & lofi 5s Co Loop.json",
    "Jazz & lofi 5s Khong Loop.json",
    "Kling Animation 5s Co Loop.json",
    "Kling Animation 5s Khong Loop.json",
    "Livewallpaper 5s Khong Loop.json",
}
```

Thêm assertion:

```python
self.assertFalse(any("6s" in path.name for path in preset_paths))
```

- [ ] **Step 2: Viết test alias RED**

Trong temporary preset directory, tạo hai file tên 5s, patch
`config.WORKFLOW_PRESET_DIR`, rồi xác nhận:

```python
self.assertEqual(
    "Jazz & lofi 5s Co Loop.json",
    main._resolve_workflow_preset("Jazz & lofi 6s Co Loop.json").name,
)
self.assertEqual(
    "Jazz & lofi 5s Khong Loop.json",
    main._resolve_workflow_preset("Jazz & lofi 6s Khong Loop.json").name,
)
```

- [ ] **Step 3: Chạy test để xác nhận RED**

```powershell
python -m unittest tests.test_workflow_vae_config tests.test_workflow_preset_aliases -v
```

Expected: FAIL vì file 5s và alias chưa tồn tại.

- [ ] **Step 4: Rename file, đổi fallback và thêm alias tối thiểu**

```python
_WORKFLOW_PRESET_ALIASES = {
    "Jazz & lofi 6s Co Loop.json": "Jazz & lofi 5s Co Loop.json",
    "Jazz & lofi 6s Khong Loop.json": "Jazz & lofi 5s Khong Loop.json",
}
```

Trong `_resolve_workflow_preset`, map `candidate_name` qua dictionary trước khi
resolve path. Đổi default `WORKFLOW_PATH` sang
`Jazz & lofi 5s Khong Loop.json`.

- [ ] **Step 5: Chạy test GREEN và commit**

```powershell
python -m unittest tests.test_workflow_vae_config tests.test_workflow_preset_aliases -v
git add config.py main.py tests workflows
git commit -m "feat: rename bundled Jazz workflows to 5s"
```

### Task 3: Áp dụng guard cho web, Telegram và prompt cuối

**Files:**
- Modify: `main.py`
- Modify: `telegram_bot.py`
- Modify: `comfyui_client.py`
- Modify: `tests/test_comfyui_client.py`
- Modify: `tests/test_workflow_guard.py`

**Interfaces:**
- Consumes: `enforce_locked_video_length(workflow) -> int`
- Produces: workflow archive và prompt ComfyUI luôn có `length = 61`

- [ ] **Step 1: Viết test RED cho `build_prompt`**

```python
def test_build_prompt_locks_video_length(self):
    workflow = {
        "1": {"class_type": "LoadImage", "inputs": {"image": "old.png"}},
        "2": {
            "class_type": "WanFirstLastFrameToVideo",
            "inputs": {"length": 73},
        },
    }
    prompt = build_prompt("new.png", seed=1, workflow_data=workflow)
    self.assertEqual(61, prompt["2"]["inputs"]["length"])
```

- [ ] **Step 2: Viết test RED xác nhận web/Telegram dùng shared guard**

Patch `enforce_locked_video_length` tại module nhận dữ liệu và xác nhận guard
được gọi trước khi object được archive/đưa vào pending. Test web dùng temporary
upload/archive directories và `AsyncMock` cho `balancer.submit_job`; test
Telegram mock `_download_bytes` và `_maybe_enqueue`.

- [ ] **Step 3: Chạy test để xác nhận RED**

```powershell
python -m unittest tests.test_comfyui_client tests.test_workflow_guard -v
```

Expected: FAIL vì ba entry point chưa áp dụng guard.

- [ ] **Step 4: Nối guard vào ba entry point**

Trong `main.py` và `telegram_bot.py`, gọi guard ngay cạnh
`enforce_locked_diffusion_models`, trước khi archive. Trong `build_prompt`, gọi
guard sau deep-copy/load file và trước vòng patch node. Ghi log số node bị khóa
nếu kết quả lớn hơn 0.

- [ ] **Step 5: Chạy test GREEN và commit**

```powershell
python -m unittest tests.test_comfyui_client tests.test_workflow_guard -v
git add main.py telegram_bot.py comfyui_client.py tests
git commit -m "fix: enforce five-second workflow policy at ingress"
```

### Task 4: Memory, regression và triển khai an toàn

**Files:**
- Modify: `docs/modules/workflows.md`
- Modify: `docs/DECISIONS_INDEX.md`
- Modify: `docs/DECISIONS.md`
- Modify: `docs/CHANGELOG.md`

**Interfaces:**
- Produces: `WORKFLOW-003` mô tả chính sách khóa mọi workflow ở 61 frame

- [ ] **Step 1: Cập nhật memory ngắn gọn**

Ghi tên fallback/preset mới, alias ẩn, guard ở cả web/Telegram/prompt và bất
biến `length = 61`. Không sao chép lịch sử dài.

- [ ] **Step 2: Chạy full regression**

```powershell
python -m unittest discover -s tests -v
powershell -NoProfile -ExecutionPolicy Bypass -File deploy/windows/tests/comfyui-worker-common.tests.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File deploy/windows/tests/comfyui-worker-scripts.tests.ps1
git diff --check
```

Expected: toàn bộ test PASS, `git diff --check` không có output.

- [ ] **Step 3: Commit docs và xác minh tree**

```powershell
git add docs
git commit -m "docs: record five-second workflow policy"
git status --short
```

Expected: worktree sạch.

- [ ] **Step 4: Push và cập nhật VPS trong maintenance**

```powershell
git push origin main
```

Trên VPS: xác nhận queue không có job, giữ
`COMFYUI_SERVERS_JSON=[]`, pull đúng commit và chạy redeploy helper. Không thêm
GPU1/GPU2 vào env trong task này.

- [ ] **Step 5: Xác minh production**

Xác nhận:

- Local HEAD = `origin/main` = VPS HEAD = container `APP_COMMIT`.
- Container healthy và domain trả HTTP 200.
- `/api/workflow-presets` chỉ liệt kê tên `5s`.
- Download bằng hai alias `6s` cũ trả file `5s`.
- `COMFYUI_SERVERS_JSON=[]` vẫn giữ nguyên.
