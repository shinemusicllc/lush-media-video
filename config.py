"""
Cấu hình hệ thống Web ComfyUI Bot.
Chỉnh sửa file này khi chuyển từ dev (1 GPU) sang production (2 GPU).
"""

import os
import secrets

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# ComfyUI Servers
# DEV  : http://127.0.0.1:8188 (mặc định)
# PROD : set env COMFYUI_BASE_URL=https://comfy.yourdomain.com
# Multi-GPU:
#   - set COMFYUI_GPU1 / COMFYUI_GPU2
#   - or set COMFYUI_SERVERS_JSON (JSON array) để override hoàn toàn
# ============================================================
_COMFYUI_URL = os.environ.get("COMFYUI_BASE_URL", "http://127.0.0.1:8188")
_COMFYUI_GPU1 = os.environ.get("COMFYUI_GPU1", "").strip()
_COMFYUI_GPU2 = os.environ.get("COMFYUI_GPU2", "").strip()

# Hỗ trợ multi-GPU qua JSON env (optional)
_SERVERS_JSON = os.environ.get("COMFYUI_SERVERS_JSON", "")
if _SERVERS_JSON:
    import json as _json
    COMFYUI_SERVERS = _json.loads(_SERVERS_JSON)
elif _COMFYUI_GPU1:
    # Keep canonical IDs/names so existing UI logic and historical jobs remain compatible.
    COMFYUI_SERVERS = [
        {"id": "gpu1", "url": _COMFYUI_GPU1, "name": "GPU #1"},
    ]
    if _COMFYUI_GPU2:
        COMFYUI_SERVERS.append({"id": "gpu2", "url": _COMFYUI_GPU2, "name": "GPU #2"})
else:
    COMFYUI_SERVERS = [
        {"id": "gpu1", "url": _COMFYUI_URL, "name": "GPU #1"},
    ]

# ============================================================
# Paths
# ============================================================
WORKFLOW_PATH = os.path.join(BASE_DIR, "FULLHD_6S_Loop_API.json")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
# Railway volume-friendly DB path:
# - local default: ./comfybot.db
# - production: set DB_PATH=/data/comfybot.db (mounted volume)
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "comfybot.db"))

# ============================================================
# JWT Authentication
# ============================================================
JWT_SECRET = os.environ.get("JWT_SECRET", secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24

# ============================================================
# Default Admin (tự tạo lần đầu chạy)
# ⚠️ Production: set env ADMIN_PASSWORD
# ============================================================
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

# ============================================================
# Workflow defaults (cố định — không cho user thay đổi)
# ============================================================
WORKFLOW_DEFAULTS = {
    "width": 1920,
    "height": 1088,
    "length": 73,  # frames
}
