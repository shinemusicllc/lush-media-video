# Tiled VAE And Singleton GPU Worker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Chuyển workflow default/preset sang tiled VAE, giảm workflow 6s về
61 frame và bảo đảm GPU1 chỉ chạy một ComfyUI trên cổng 8188, kể cả sau crash
hoặc bị kill.

**Architecture:** Workflow JSON trong repo là canonical source cho app host. Windows supervisor tiếp tục dùng Scheduled Task, exclusive file lock và batch hiện có, nhưng bổ sung validation batch/config, quét process theo `ComfyDirectory` trên mọi cổng, reconciliation duplicate/orphan và launch guard.

**Tech Stack:** Python `unittest`, ComfyUI API workflow JSON, Windows PowerShell 5.1, Task Scheduler, Docker Compose trên VPS.

## Global Constraints

- Chỉ sửa 1 workflow fallback tại `config.WORKFLOW_PATH` và 5 file trong `workflows/presets`.
- Tiled VAE dùng chính xác `tile_size=512`, `overlap=64`, `temporal_size=16`, `temporal_overlap=4`.
- Ba workflow Jazz mang tên 6s dùng `length=61`, bằng workflow 5s; giữ nguyên
  tên file để không đổi API/frontend contract.
- Không migrate `/data/workflows` hoặc hai file `FULLHD_*` legacy.
- GPU1 chỉ bind `127.0.0.1:8188`; không để listener 8288.
- Backend production giữ `COMFYUI_SERVERS_JSON=[]` trong toàn bộ đợt triển khai.
- Chỉ kill ComfyUI process thuộc `D:\ComfyUI1`; không kill process ngoài phạm vi.

---

### Task 1: Workflow default và preset tiled VAE

**Files:**
- Create: `tests/test_workflow_vae_config.py`
- Modify: `workflows/Jazz & lofi 6s Khong Loop.json`
- Modify: `workflows/presets/Jazz & lofi 6s Co Loop.json`
- Modify: `workflows/presets/Jazz & lofi 6s Khong Loop.json`
- Modify: `workflows/presets/Kling Animation 5s Co Loop.json`
- Modify: `workflows/presets/Kling Animation 5s Khong Loop.json`
- Modify: `workflows/presets/Livewallpaper 5s Khong Loop.json`

**Interfaces:**
- Consumes: `config.WORKFLOW_PATH`, `config.WORKFLOW_PRESET_DIR`.
- Produces: Sáu API workflow có node `VAEDecodeTiled` theo contract cố định.

- [ ] **Step 1: Viết test workflow contract**

```python
EXPECTED_TILING = {
    "tile_size": 512,
    "overlap": 64,
    "temporal_size": 16,
    "temporal_overlap": 4,
}

def test_default_and_presets_use_temporally_tiled_vae(self):
    for path in workflow_paths():
        workflow = json.loads(path.read_text(encoding="utf-8-sig"))
        vae_nodes = [
            node for node in workflow.values()
            if isinstance(node, dict)
            and str(node.get("class_type", "")).startswith("VAEDecode")
        ]
        self.assertEqual(1, len(vae_nodes), path)
        self.assertEqual("VAEDecodeTiled", vae_nodes[0]["class_type"], path)
        for key, value in EXPECTED_TILING.items():
            self.assertEqual(value, vae_nodes[0]["inputs"].get(key), (path, key))
```

Thêm test độc lập xác nhận toàn bộ fallback/preset dùng
`WanFirstLastFrameToVideo.length=61`; trước migration test phải fail đúng ba
file Jazz đang là 73.

- [ ] **Step 2: Chạy test và xác nhận RED**

Run:

```powershell
python -m unittest tests.test_workflow_vae_config -v
```

Expected: FAIL vì các file đang dùng `VAEDecode`.

- [ ] **Step 3: Sửa tối thiểu sáu workflow**

Với mỗi node VAE:

```json
"class_type": "VAEDecodeTiled",
"inputs": {
  "samples": ["58", 0],
  "vae": ["39", 0],
  "tile_size": 512,
  "overlap": 64,
  "temporal_size": 16,
  "temporal_overlap": 4
}
```

Giữ nguyên mọi input, node và liên kết còn lại.

- [ ] **Step 4: Chạy test và full Python suite**

```powershell
python -m unittest tests.test_workflow_vae_config -v
python -m unittest discover -s tests -v
```

Expected: PASS, 0 failures.

- [ ] **Step 5: Commit**

```powershell
git add tests/test_workflow_vae_config.py workflows
git commit -m "fix: tile VAE decoding in bundled workflows"
```

---

### Task 2: Process discovery và reconciliation theo ComfyDirectory

**Files:**
- Modify: `deploy/windows/comfyui-worker-common.ps1`
- Modify: `deploy/windows/tests/comfyui-worker-common.tests.ps1`

**Interfaces:**
- Produces: `Get-ComfyProcessPort`, `Get-ComfyProcessesForDirectory`,
  `Get-ComfyProcessPlan`, `Assert-ComfyBatchContract`.
- `Get-ComfyProcessPlan` trả object có `KeepProcess` và mảng `StopProcesses`.

- [ ] **Step 1: Viết test RED cho port parsing và reconciliation**

```powershell
$correct = [pscustomobject]@{
    ProcessId = 100
    CommandLine = "python ComfyUI\main.py --port 8188"
}
$wrong = [pscustomobject]@{
    ProcessId = 200
    CommandLine = "python ComfyUI\main.py --port 8288"
}
$duplicate = [pscustomobject]@{
    ProcessId = 300
    CommandLine = "python ComfyUI\main.py --port 8188"
}

Assert-Equal 8188 (Get-ComfyProcessPort -Process $correct) "parse correct port"
$plan = Get-ComfyProcessPlan -Processes @($correct, $wrong, $duplicate) -LocalPort 8188
Assert-Equal 100 $plan.KeepProcess.ProcessId "keep one expected process"
Assert-Equal "200,300" (($plan.StopProcesses.ProcessId | Sort-Object) -join ",") "stop wrong and duplicate"
```

Thêm temp batch 8288 và xác nhận
`Assert-ComfyBatchContract -LocalPort 8188` throw; temp batch 8188 phải pass.

- [ ] **Step 2: Chạy test và xác nhận RED**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File deploy/windows/tests/comfyui-worker-common.tests.ps1
```

Expected: FAIL vì helper chưa tồn tại.

- [ ] **Step 3: Implement helper tối thiểu**

- `Get-ComfyProcessPort` parse `--port <number>`.
- `Get-ComfyProcessesForDirectory` lọc `python.exe`, `ComfyUI\main.py` và
  `ExecutablePath` nằm dưới `ComfyDirectory`.
- `Get-ComfyProcessPlan` giữ process đúng cổng có PID nhỏ nhất và yêu cầu dừng
  toàn bộ process còn lại.
- `Get-ManagedComfyProcess` tái sử dụng discovery mới.
- `Assert-ComfyBatchContract` đọc batch và từ chối port/CUDA khác config.

- [ ] **Step 4: Chạy worker common test**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File deploy/windows/tests/comfyui-worker-common.tests.ps1
```

Expected: `PASS comfyui-worker-common.tests.ps1`.

- [ ] **Step 5: Commit**

```powershell
git add deploy/windows/comfyui-worker-common.ps1 deploy/windows/tests/comfyui-worker-common.tests.ps1
git commit -m "fix: reconcile ComfyUI processes across ports"
```

---

### Task 3: Supervisor singleton và launch guard

**Files:**
- Modify: `deploy/windows/comfyui-worker-supervisor.ps1`
- Modify: `deploy/windows/worker.example.json`
- Modify: `deploy/windows/tests/comfyui-worker-scripts.tests.ps1`
- Runtime modify: `D:\ComfyUI-Autostart\gpu1.worker.json`
- Runtime modify: `D:\ComfyUI1\run_nvidia_gpu.bat`

**Interfaces:**
- Consumes: helpers từ Task 2.
- Produces: supervisor tự dọn orphan/duplicate cùng ComfyDirectory và không
  launch lại trong `LaunchGuardSeconds`.

- [ ] **Step 1: Viết static tests RED**

Test supervisor phải gọi `Get-ComfyProcessesForDirectory`,
`Get-ComfyProcessPlan`, `Assert-ComfyBatchContract` và sử dụng
`LaunchGuardSeconds`. Test config default là 30 giây.

- [ ] **Step 2: Chạy test và xác nhận RED**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File deploy/windows/tests/comfyui-worker-scripts.tests.ps1
```

Expected: FAIL vì supervisor chưa có reconciliation/launch guard.

- [ ] **Step 3: Implement supervisor policy**

Trước health check mỗi vòng:

1. Lấy toàn bộ ComfyUI cùng thư mục.
2. Lập plan theo cổng 8188.
3. Stop từng PID trong `StopProcesses` sau khi tái xác nhận PID vẫn thuộc đúng
   thư mục.
4. Chỉ launch nếu không còn managed process, cổng trống và lần launch trước đã
   quá `LaunchGuardSeconds`.

Validate batch/config một lần trước vòng lặp.

- [ ] **Step 4: Sửa runtime config và batch**

- Thêm `"LaunchGuardSeconds": 30` vào
  `D:\ComfyUI-Autostart\gpu1.worker.json`.
- Đổi duy nhất `--port 8288` thành `--port 8188` trong
  `D:\ComfyUI1\run_nvidia_gpu.bat`.

- [ ] **Step 5: Chạy toàn bộ worker tests**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File deploy/windows/tests/comfyui-worker-common.tests.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File deploy/windows/tests/comfyui-worker-scripts.tests.ps1
```

Expected: cả hai PASS.

- [ ] **Step 6: Commit**

```powershell
git add deploy/windows
git commit -m "fix: enforce one ComfyUI instance per worker"
```

---

### Task 4: Runtime test cổng 8188

**Files:**
- Read: `D:\ComfyUI-Autostart\gpu1-watchdog.log`
- Read: `D:\ComfyUI-Autostart\gpu1-comfy-output.log`
- Read: `D:\ComfyUI-Autostart\gpu1-comfy-error.log`
- Read: `D:\ComfyUI1\ComfyUI\output\`

**Interfaces:**
- Consumes: Scheduled Task `LushMedia-ComfyUI-gpu1`, local ComfyUI HTTP API.
- Produces: bằng chứng job success và singleton recovery.

- [ ] **Step 1: Xác nhận queue 8288 rỗng và kill đúng PID**

Chỉ stop PID có command line thuộc `D:\ComfyUI1` và `--port 8288`.

- [ ] **Step 2: Enable/start Scheduled Task và chờ health theo điều kiện**

Poll `/system_stats` 8188 tối đa 10 phút; không dùng sleep dài cố định.

- [ ] **Step 3: Submit job 73 frame**

Dùng workflow default đã sửa, input `k39.png`, theo dõi WebSocket/history đến
terminal state. Expected: `success`, output MP4 tồn tại.

- [ ] **Step 4: Kill/restart test**

Sau khi queue rỗng, kill PID 8188; poll cho tới khi xuất hiện PID mới và health
200. Expected: PID thay đổi, process count=1, listener 8188=1, listener
8288=0, supervisor count=1.

- [ ] **Step 5: Kiểm tra launch log**

Trong cửa sổ thời gian test, chỉ có một log
`Starting ComfyUI on CUDA 0, port 8188` cho lần phục hồi.

---

### Task 5: Push, deploy VPS và xác minh source of truth

**Files:**
- Modify: `docs/modules/gpu-workers.md`
- Modify: `docs/DECISIONS_INDEX.md`
- Modify: `docs/DECISIONS.md`
- Modify: `docs/CHANGELOG.md`

**Interfaces:**
- Produces: `origin/main`, VPS checkout và container cùng commit.

- [ ] **Step 1: Cập nhật docs vận hành**

Ghi tiled VAE contract, singleton across ports, batch/config port invariant và
trạng thái GPU1 tested trên 8188.

- [ ] **Step 2: Chạy fresh verification**

```powershell
python -m unittest discover -s tests -v
powershell -NoProfile -ExecutionPolicy Bypass -File deploy/windows/tests/comfyui-worker-common.tests.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File deploy/windows/tests/comfyui-worker-scripts.tests.ps1
git diff --check
git status --short
```

- [ ] **Step 3: Commit docs và push**

```powershell
git add docs
git commit -m "docs: record tiled VAE worker invariants"
git push origin main
```

- [ ] **Step 4: Đồng bộ và rebuild VPS**

Dùng `deploy/scripts/update_app.sh`/`redeploy.sh` từ checkout sạch, giữ nguyên
`deploy/.env` và `deploy/data`.

- [ ] **Step 5: Xác minh production**

- Container healthy và `APP_COMMIT` khớp `origin/main`.
- `COMFYUI_SERVERS_JSON=[]`.
- API default/preset trả `VAEDecodeTiled` với đúng bốn giá trị.
- Không có thay đổi trong `/data/workflows`.
