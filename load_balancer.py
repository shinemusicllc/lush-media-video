"""
Round-Robin Load Balancer cho nhiều ComfyUI servers.
Mỗi server có queue riêng, worker xử lý tuần tự (1 job/lần).
"""

import asyncio
import uuid
import json
import logging
from datetime import datetime, timezone

from config import COMFYUI_SERVERS
import comfyui_client
import database as db

logger = logging.getLogger("load_balancer")


class ServerQueue:
    """Queue và trạng thái cho 1 ComfyUI server."""

    def __init__(self, server_config: dict):
        self.id: str = server_config["id"]
        self.url: str = server_config["url"]
        self.name: str = server_config["name"]
        self.queue: asyncio.Queue = asyncio.Queue()
        self.current_job: str | None = None
        self.is_online: bool = False
        self._worker_task: asyncio.Task | None = None

    @property
    def status(self) -> str:
        if not self.is_online:
            return "offline"
        return "busy" if self.current_job else "idle"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "current_job": self.current_job,
            "queue_size": self.queue.qsize(),
        }


class LoadBalancer:
    """Round-robin load balancer với per-server async workers."""

    def __init__(self):
        self.servers: list[ServerQueue] = []
        self._next_index = 0
        self._ws_clients: dict[str, set[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    # ── Lifecycle ───────────────────────────────────────────

    async def start(self):
        """Khởi tạo servers và start workers."""
        for cfg in COMFYUI_SERVERS:
            sq = ServerQueue(cfg)
            sq.is_online = await comfyui_client.check_server(sq.url)
            self.servers.append(sq)
            sq._worker_task = asyncio.create_task(self._worker(sq))
            state = "ONLINE ✓" if sq.is_online else "OFFLINE ✗"
            logger.info(f"  {sq.name} ({sq.url}): {state}")

    async def stop(self):
        for sq in self.servers:
            if sq._worker_task:
                sq._worker_task.cancel()
                try:
                    await sq._worker_task
                except asyncio.CancelledError:
                    pass

    # ── Submit job ──────────────────────────────────────────

    async def submit_job(
        self,
        job_id: str,
        user_id: int,
        username: str,
        image_path: str,
        image_filename: str,
        job_name: str | None = None,
        workflow_name: str | None = None,
        workflow_data: dict | None = None,
    ):
        """Submit job mới — round-robin phân bổ giữa các server."""
        async with self._lock:
            server = self.servers[self._next_index % len(self.servers)]
            self._next_index = (self._next_index + 1) % len(self.servers)

        await db.create_job(
            job_id,
            user_id,
            username,
            image_filename,
            job_name=job_name,
            workflow_name=workflow_name,
        )
        await db.update_job(job_id, server_id=server.id)

        await server.queue.put(
            {
                "job_id": job_id,
                "image_path": image_path,
                "image_filename": image_filename,
                "username": username,
                "workflow_data": workflow_data,
            }
        )

        await self._broadcast_job_update(job_id, server)
        logger.info(
            f"Job {job_id[:8]}… → {server.name} (queue: {server.queue.qsize()})"
        )

    # ── Worker (1 per server) ───────────────────────────────

    async def _worker(self, server: ServerQueue):
        """Xử lý job tuần tự cho 1 ComfyUI server."""
        logger.info(f"Worker started: {server.name}")

        while True:
            job_data = await server.queue.get()
            job_id = job_data["job_id"]
            server.current_job = job_id
            client_id = str(uuid.uuid4())

            try:
                # Check trạng thái — có thể đã bị cancel trong lúc queue
                job_check = await db.get_job(job_id)
                if job_check and job_check["status"] == "cancelled":
                    logger.info(f"Job {job_id[:8]}… already cancelled, skipping")
                    continue

                # Kiểm tra server
                server.is_online = await comfyui_client.check_server(server.url)
                if not server.is_online:
                    raise ConnectionError(f"Server {server.name} offline")

                # → running
                await db.update_job(job_id, status="running")
                await self._broadcast_job_update(job_id, server)

                # 1. Upload ảnh
                image_name = await comfyui_client.upload_image(
                    server.url,
                    job_data["image_path"],
                    job_data["image_filename"],
                )

                # Check trạng thái sau upload
                job_check = await db.get_job(job_id)
                if job_check and job_check["status"] == "cancelled":
                    logger.info(f"Job {job_id[:8]}… cancelled after upload")
                    continue

                # 2. Build prompt (patch workflow)
                prompt = comfyui_client.build_prompt(
                    image_name,
                    workflow_data=job_data.get("workflow_data"),
                )

                # 3. Queue prompt
                prompt_id = await comfyui_client.queue_prompt(
                    server.url, prompt, client_id
                )
                await db.update_job(job_id, prompt_id=prompt_id)

                # 4. Theo dõi progress qua WebSocket
                async def on_progress(pct):
                    # Check cancelled trước khi update
                    jc = await db.get_job(job_id)
                    if jc and jc["status"] == "cancelled":
                        return
                    await db.update_job(job_id, progress=pct)
                    await self._broadcast_job_update(job_id, server)

                result = await comfyui_client.listen_progress(
                    server.url, prompt_id, client_id, on_progress=on_progress
                )

                # Check cancelled sau listen
                job_check = await db.get_job(job_id)
                if job_check and job_check["status"] == "cancelled":
                    logger.info(f"Job {job_id[:8]}… cancelled during execution")
                    await self._broadcast_job_update(job_id, server)
                    continue

                if result["status"] == "error":
                    raise Exception(result.get("error", "ComfyUI execution error"))

                # 5. Lấy output
                history = await comfyui_client.get_history(server.url, prompt_id)
                output_info = comfyui_client.extract_output_info(history, prompt_id)

                # 6. ✅ Done
                now = datetime.now(timezone.utc).isoformat()
                output_json = json.dumps(output_info) if output_info else None
                await db.update_job(
                    job_id,
                    status="done",
                    progress=100,
                    output_info=output_json,
                    completed_at=now,
                )
                await self._broadcast_job_update(job_id, server)
                logger.info(f"Job {job_id[:8]}… DONE ✓ on {server.name}")

            except Exception as e:
                # Check nếu job đã bị cancelled (interrupt gây exception)
                job_check = await db.get_job(job_id)
                if job_check and job_check["status"] == "cancelled":
                    logger.info(f"Job {job_id[:8]}… cancelled (interrupt caught)")
                    await self._broadcast_job_update(job_id, server)
                else:
                    logger.error(f"Job {job_id[:8]}… ERROR ✗: {e}")
                    now = datetime.now(timezone.utc).isoformat()
                    await db.update_job(
                        job_id,
                        status="error",
                        error_msg=str(e),
                        completed_at=now,
                    )
                    await self._broadcast_job_update(job_id, server)

            finally:
                server.current_job = None
                server.queue.task_done()

    # ── WebSocket broadcast ─────────────────────────────────

    def register_ws(self, username: str, queue: asyncio.Queue):
        if username not in self._ws_clients:
            self._ws_clients[username] = set()
        self._ws_clients[username].add(queue)

    def unregister_ws(self, username: str, queue: asyncio.Queue):
        if username in self._ws_clients:
            self._ws_clients[username].discard(queue)
            if not self._ws_clients[username]:
                del self._ws_clients[username]

    async def _broadcast(self, username: str, data: dict):
        """Gửi update cho tất cả WS clients của user + admin."""
        targets = set()
        if username in self._ws_clients:
            targets.update(self._ws_clients[username])
        if "admin" in self._ws_clients and username != "admin":
            targets.update(self._ws_clients["admin"])

        for q in targets:
            try:
                q.put_nowait(data)
            except asyncio.QueueFull:
                pass

    async def _broadcast_job_update(self, job_id: str, server: ServerQueue):
        job = await db.get_job(job_id)
        if job:
            data = self._format_job(job, server)
            await self._broadcast(job["username"], data)

    @staticmethod
    def _resolve_job_name(job: dict) -> str:
        name = (job.get("job_name") or "").strip()
        if name:
            return name
        legacy = (job.get("video_name") or "").strip()
        return legacy

    def _format_job(self, job: dict, server: ServerQueue | None = None) -> dict:
        server_name = ""
        if server:
            server_name = server.name
        else:
            for s in self.servers:
                if s.id == job.get("server_id"):
                    server_name = s.name
                    break

        return {
            "type": "job_update",
            "job": {
                "id": job["id"],
                "username": job["username"],
                "server_id": job.get("server_id", ""),
                "server_name": server_name,
                "status": job["status"],
                "progress": job.get("progress", 0),
                "error_msg": job.get("error_msg"),
                "input_image": job["input_image"],
                "job_name": self._resolve_job_name(job),
                "video_name": self._resolve_job_name(job),
                "workflow_name": job.get("workflow_name"),
                "created_at": job["created_at"],
                "completed_at": job.get("completed_at"),
                "has_output": job.get("output_info") is not None,
            },
        }

    def get_servers_status(self) -> list:
        return [s.to_dict() for s in self.servers]


# ── Singleton ───────────────────────────────────────────────
balancer = LoadBalancer()
