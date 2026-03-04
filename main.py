"""
FastAPI application — Web ComfyUI Bot
Endpoints: auth, jobs CRUD, video download, cancel, WebSocket realtime.
"""

import os
import uuid
import json
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timezone

from fastapi import (
    FastAPI,
    File,
    Form,
    Header,
    UploadFile,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response, StreamingResponse

import config
import database as db
from auth import (
    hash_password,
    verify_password,
    create_token,
    get_current_user,
    require_admin,
    decode_token,
)
from models import UserLogin, UserCreate, TokenResponse
import httpx
from load_balancer import balancer
import comfyui_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("main")

app = FastAPI(title="ComfyUI Bot", version="1.0.0")


def _resolve_job_name(job_row: dict) -> str:
    name = (job_row.get("job_name") or "").strip()
    if name:
        return name
    legacy = (job_row.get("video_name") or "").strip()
    return legacy


# ── Startup / Shutdown ──────────────────────────────────────


@app.on_event("startup")
async def startup():
    os.makedirs(config.UPLOAD_DIR, exist_ok=True)
    await db.init_db()

    # Tự tạo admin lần đầu
    admin = await db.get_user(config.ADMIN_USERNAME)
    if not admin:
        hashed = hash_password(config.ADMIN_PASSWORD)
        await db.create_user(config.ADMIN_USERNAME, hashed, "admin")
        logger.info(f"Admin account created: {config.ADMIN_USERNAME}")

    await balancer.start()
    logger.info(f"🚀 ComfyUI Bot started — {len(config.COMFYUI_SERVERS)} server(s)")


@app.on_event("shutdown")
async def shutdown():
    await balancer.stop()


# ── Static files ────────────────────────────────────────────

static_dir = os.path.join(config.BASE_DIR, "static")
os.makedirs(static_dir, exist_ok=True)


# Custom static files — no cache
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response as StarletteResponse


class NoCacheStaticMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response


app.add_middleware(NoCacheStaticMiddleware)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def index():
    return FileResponse(
        os.path.join(static_dir, "index.html"),
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


# ── Auth ────────────────────────────────────────────────────


@app.post("/api/auth/login", response_model=TokenResponse)
async def login(data: UserLogin):
    user = await db.get_user(data.username)
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Sai tên đăng nhập hoặc mật khẩu")
    token = create_token(user["username"], user["role"])
    return TokenResponse(
        access_token=token,
        username=user["username"],
        role=user["role"],
    )


@app.post("/api/auth/register")
async def register(data: UserCreate, admin: dict = Depends(require_admin)):
    existing = await db.get_user(data.username)
    if existing:
        raise HTTPException(status_code=400, detail="Username đã tồn tại")
    hashed = hash_password(data.password)
    user_id = await db.create_user(data.username, hashed, data.role)
    return {"id": user_id, "username": data.username, "role": data.role}


@app.get("/api/auth/users")
async def list_users(admin: dict = Depends(require_admin)):
    return await db.list_users()


# ── Jobs ────────────────────────────────────────────────────


@app.post("/api/jobs")
async def create_job(
    file: UploadFile = File(...),
    job_name: str = Form(""),
    video_name: str = Form(""),
    workflow_file: UploadFile | None = File(None),
    user: dict = Depends(get_current_user),
):
    # Validate
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Chỉ chấp nhận file ảnh")

    # Lưu file
    job_id = str(uuid.uuid4())
    ext = Path(file.filename).suffix or ".jpg"
    safe_filename = f"{job_id}{ext}"
    save_path = os.path.join(config.UPLOAD_DIR, safe_filename)

    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)

    raw_job_name = (job_name or "").strip() or (video_name or "").strip()
    clean_job_name = raw_job_name
    if len(clean_job_name) > 120:
        raise HTTPException(status_code=400, detail="Ten job toi da 120 ky tu")
    if not clean_job_name:
        original_stem = Path(file.filename or "").stem.strip()
        clean_job_name = original_stem[:120] if original_stem else f"job_{job_id[:8]}"

    workflow_data = None
    workflow_name = Path(config.WORKFLOW_PATH).name
    if workflow_file and workflow_file.filename:
        if not workflow_file.filename.lower().endswith(".json"):
            raise HTTPException(status_code=400, detail="Workflow phai la file .json")

        raw_workflow = await workflow_file.read()
        if len(raw_workflow) > 2 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Workflow JSON qua lon (toi da 2MB)")
        try:
            workflow_data = json.loads(raw_workflow.decode("utf-8-sig"))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Workflow JSON khong hop le: {e}")
        if not isinstance(workflow_data, dict):
            raise HTTPException(
                status_code=400, detail="Workflow JSON phai la object o cap goc"
            )

        workflow_name = Path(workflow_file.filename).name

    # Submit vào load balancer
    await balancer.submit_job(
        job_id=job_id,
        user_id=user["id"],
        username=user["username"],
        image_path=save_path,
        image_filename=safe_filename,
        job_name=clean_job_name,
        workflow_name=workflow_name,
        workflow_data=workflow_data,
    )

    return {
        "job_id": job_id,
        "status": "queued",
        "job_name": clean_job_name,
        "video_name": clean_job_name,
        "workflow_name": workflow_name,
    }


@app.get("/api/jobs")
async def list_jobs(user: dict = Depends(get_current_user)):
    if user["role"] == "admin":
        jobs = await db.get_all_jobs()
    else:
        jobs = await db.get_user_jobs(user["username"])

    result = []
    for j in jobs:
        server_name = ""
        for s in balancer.servers:
            if s.id == j.get("server_id"):
                server_name = s.name
                break
        result.append(
            {
                "id": j["id"],
                "username": j["username"],
                "server_id": j.get("server_id", ""),
                "server_name": server_name,
                "status": j["status"],
                "progress": j.get("progress", 0),
                "error_msg": j.get("error_msg"),
                "input_image": j["input_image"],
                "job_name": _resolve_job_name(j),
                "video_name": _resolve_job_name(j),
                "workflow_name": j.get("workflow_name"),
                "created_at": j["created_at"],
                "completed_at": j.get("completed_at"),
                "has_output": j.get("output_info") is not None,
            }
        )
    return result


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str, user: dict = Depends(get_current_user)):
    job = await db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job không tồn tại")
    if job["username"] != user["username"] and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Không có quyền")
    return job


@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str, user: dict = Depends(get_current_user)):
    """Xóa job khỏi danh sách (chỉ cho done/error)."""
    job = await db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job không tồn tại")
    if job["username"] != user["username"] and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Không có quyền")
    if job["status"] == "running":
        raise HTTPException(status_code=400, detail="Không thể xóa job đang chạy")
    await db.delete_job(job_id)
    return {"status": "deleted"}


@app.get("/api/jobs/{job_id}/video")
async def download_video(
    job_id: str,
    token: str = "",
    authorization: str | None = Header(default=None),
):
    """Download video — hỗ trợ cả Authorization: Bearer và ?token= query param."""
    user = None
    access_token = (token or "").strip()

    if not access_token and authorization:
        parts = authorization.strip().split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            access_token = parts[1].strip()

    if access_token:
        try:
            payload = decode_token(access_token)
            user = await db.get_user(payload["sub"])
        except Exception:
            user = None

    if not user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    job = await db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job không tồn tại")
    if job["username"] != user["username"] and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Không có quyền")
    if job["status"] != "done" or not job.get("output_info"):
        raise HTTPException(status_code=400, detail="Video chưa sẵn sàng")

    output_info = json.loads(job["output_info"])

    server_url = None
    for s in config.COMFYUI_SERVERS:
        if s["id"] == job.get("server_id"):
            server_url = s["url"]
            break
    if not server_url:
        raise HTTPException(status_code=500, detail="Server không tìm thấy")

    params = {
        "filename": output_info["filename"],
        "subfolder": output_info.get("subfolder", ""),
        "type": output_info.get("type", "output"),
    }
    timeout_s = int(os.environ.get("COMFYUI_DOWNLOAD_TIMEOUT_S", "900"))
    headers = comfyui_client._get_tunnel_headers()

    async def video_stream():
        async with httpx.AsyncClient(timeout=timeout_s, headers=headers) as client:
            async with client.stream("GET", f"{server_url}/view", params=params) as r:
                r.raise_for_status()
                async for chunk in r.aiter_bytes():
                    yield chunk

    return StreamingResponse(
        video_stream(),
        media_type="video/mp4",
        headers={
            "Content-Disposition": f'attachment; filename="{output_info["filename"]}"'
        },
    )


@app.post("/api/jobs/{job_id}/cancel")
async def cancel_job(job_id: str, user: dict = Depends(get_current_user)):
    """Hủy job — nếu đang chạy sẽ interrupt ComfyUI + xóa khỏi queue."""
    job = await db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job không tồn tại")
    if job["username"] != user["username"] and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Không có quyền")
    if job["status"] in ("done", "error", "cancelled"):
        raise HTTPException(status_code=400, detail="Job đã kết thúc")

    server_url = None
    for s in config.COMFYUI_SERVERS:
        if s["id"] == job.get("server_id"):
            server_url = s["url"]
            break

    if server_url and job.get("prompt_id"):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # 1. Gọi /interrupt để dừng execution hiện tại
                await client.post(f"{server_url}/interrupt")
                logger.info(f"Sent interrupt for job {job_id[:8]}…")

                # 2. Xóa prompt khỏi queue (nếu chưa chạy)
                await client.post(
                    f"{server_url}/queue",
                    json={"delete": [job["prompt_id"]]},
                )
                logger.info(f"Deleted prompt {job['prompt_id'][:8]}… from queue")
        except Exception as e:
            logger.warning(f"Cancel ComfyUI failed: {e}")
    elif server_url:
        # Job chưa có prompt_id (chưa queue lên ComfyUI) → chỉ cần update DB
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(f"{server_url}/interrupt")
        except Exception:
            pass

    now = datetime.now(timezone.utc).isoformat()
    await db.update_job(job_id, status="cancelled", completed_at=now)

    # Broadcast update
    for sq in balancer.servers:
        if sq.id == job.get("server_id"):
            await balancer._broadcast_job_update(job_id, sq)
            break

    return {"status": "cancelled"}


@app.get("/api/jobs/{job_id}/thumbnail")
async def get_thumbnail(job_id: str):
    """Trả ảnh input để hiển thị thumbnail trên UI."""
    job = await db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404)
    image_path = os.path.join(config.UPLOAD_DIR, job["input_image"])
    if not os.path.exists(image_path):
        raise HTTPException(status_code=404)
    return FileResponse(image_path)


# ── Admin ───────────────────────────────────────────────────


@app.get("/api/admin/servers")
async def admin_servers(admin: dict = Depends(require_admin)):
    statuses = balancer.get_servers_status()
    # Thêm health check realtime
    for s_status in statuses:
        for sq in balancer.servers:
            if sq.id == s_status["id"]:
                sq.is_online = await comfyui_client.check_server(sq.url)
                s_status["status"] = sq.status
    return statuses


# ── WebSocket realtime ──────────────────────────────────────


@app.websocket("/ws/jobs")
async def ws_jobs(websocket: WebSocket, token: str = ""):
    # Auth qua query param
    try:
        payload = decode_token(token)
        user = await db.get_user(payload["sub"])
        if not user:
            await websocket.close(code=4001)
            return
    except Exception:
        await websocket.close(code=4001)
        return

    await websocket.accept()
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    balancer.register_ws(user["username"], queue)

    try:
        # Gửi trạng thái server ban đầu
        await websocket.send_json(
            {
                "type": "servers_status",
                "servers": balancer.get_servers_status(),
            }
        )

        async def sender():
            while True:
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=8)
                    await websocket.send_json(data)
                except asyncio.TimeoutError:
                    # Push periodic server status so UI reflects GPU recovery.
                    statuses = []
                    for sq in balancer.servers:
                        sq.is_online = await comfyui_client.check_server(sq.url)
                        statuses.append(sq.to_dict())
                    await websocket.send_json(
                        {"type": "servers_status", "servers": statuses}
                    )

        async def receiver():
            while True:
                try:
                    await websocket.receive_text()
                except WebSocketDisconnect:
                    raise

        send_task = asyncio.create_task(sender())
        recv_task = asyncio.create_task(receiver())

        done, pending = await asyncio.wait(
            [send_task, recv_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for t in pending:
            t.cancel()

    except (WebSocketDisconnect, Exception):
        pass
    finally:
        balancer.unregister_ws(user["username"], queue)


# ── Run ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
