# GPU1 VisibleGuard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Thêm VisibleGuard an toàn cho GPU1 và tắt ComfyUI auto-launch Chrome mà không restart worker chỉ để áp dụng flag.

**Architecture:** Một guard PowerShell hidden, single-instance giám sát interactive supervisor và khởi chạy lại visible batch qua `cmd.exe`. Các detector, tunnel matching, batch mutation và launcher generation dùng helper chung để có regression test độc lập.

**Tech Stack:** Windows PowerShell 5.1, ScheduledTasks, CIM process inspection, ComfyUI HTTP queue/health API.

## Global Constraints

- Đọc runtime path và port từ `D:\ComfyUI-Autostart\gpu1.worker.json`.
- Chỉ thao tác process thuộc GPU1.
- Legacy `SYSTEM` task phải disabled; Guard chạy interactive user ở highest.
- Không sửa VPS, redeploy, scheduling, private key; không commit/push.

---

### Task 1: Regression contract

**Files:**
- Modify: `deploy/windows/tests/comfyui-worker-common.tests.ps1`
- Modify: `deploy/windows/tests/comfyui-worker-scripts.tests.ps1`

- [ ] Thêm test detector chỉ nhận supervisor qua `-File`.
- [ ] Thêm test Desktop launcher gọi `schtasks.exe /Run`.
- [ ] Thêm test `--disable-auto-launch` được chèn đúng vị trí và idempotent.
- [ ] Thêm test contract cho Guard script và per-user Guard task.
- [ ] Chạy hai suite và xác nhận RED vì implementation chưa tồn tại.

### Task 2: VisibleGuard implementation

**Files:**
- Modify: `deploy/windows/comfyui-worker-common.ps1`
- Create: `deploy/windows/comfyui-worker-visible-guard.ps1`
- Modify: `deploy/windows/install-comfyui-worker-visible-launcher.ps1`

- [ ] Thêm helper detector, tunnel matching, batch mutation và launcher generation.
- [ ] Viết guard single-instance, poll 5 giây, queue-safe orphan cleanup và visible launch throttling.
- [ ] Đăng ký Guard task interactive/highest/hidden/IgnoreNew và giữ legacy task disabled.
- [ ] Chạy PowerShell suites và xác nhận GREEN.

### Task 3: Runtime install and recovery

**Files:**
- Modify runtime only: BatchFile đọc từ `gpu1.worker.json`
- Modify runtime only: Desktop launcher, Startup shortcut và Scheduled Tasks

- [ ] Chạy toàn bộ regression suite.
- [ ] Cài Guard khi queue `0/0`, không restart worker hiện tại.
- [ ] Xác minh flag batch, task principals/actions và Guard single-instance.
- [ ] Ghi PID rồi kill đúng supervisor và parent visible shell.
- [ ] Xác minh recovery, log delta một dòng, singleton listeners, health và queue.
- [ ] Báo file/source/runtime diff; không commit/push.
