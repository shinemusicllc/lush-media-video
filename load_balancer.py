"""
Round-Robin Load Balancer cho nhiều ComfyUI servers.
Mỗi server có queue riêng, worker xử lý tuần tự (1 job/lần).
"""

import asyncio
import uuid
import json
import logging
import os
from datetime import datetime, timezone

import config
from config import COMFYUI_SERVERS
import comfyui_client
import database as db

logger = logging.getLogger("load_balancer")

SERVER_RECOVERY_RETRIES = int(os.environ.get("COMFYUI_SERVER_RECOVERY_RETRIES", "36"))
SERVER_RECOVERY_INTERVAL_S = int(
    os.environ.get("COMFYUI_SERVER_RECOVERY_INTERVAL_S", "5")
)
HEALTH_CHECK_INTERVAL_S = int(os.environ.get("COMFYUI_HEALTH_CHECK_INTERVAL_S", "8"))


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
        self._health_task: asyncio.Task | None = None

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
        self._health_task = asyncio.create_task(self._health_monitor())

    async def stop(self):
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass
        for sq in self.servers:
            if sq._worker_task:
                sq._worker_task.cancel()
                try:
                    await sq._worker_task
                except asyncio.CancelledError:
                    pass

    async def recover_active_jobs(self):
        """Restore queued/running DB jobs after an app restart."""
        active_jobs = await db.get_jobs_by_status(("queued", "running"))
        if not active_jobs:
            return

        restored = 0
        for job in active_jobs:
            server = self._server_by_id(job.get("server_id")) or await self._select_server()
            if not server:
                break

            prompt_id = (job.get("prompt_id") or "").strip()
            if job.get("status") == "running" and prompt_id:
                completed = await self._complete_from_history(server, job["id"], prompt_id)
                if completed:
                    continue
                if not await comfyui_client.is_prompt_active(server.url, prompt_id):
                    logger.info(
                        f"Job {job['id'][:8]} prompt is not active; requeueing"
                    )
                    prompt_id = ""

            payload = self._build_job_payload(job)
            if not payload:
                now = datetime.now(timezone.utc).isoformat()
                await db.update_job(
                    job["id"],
                    status="error",
                    error_msg="Cannot recover job: input file missing",
                    completed_at=now,
                )
                continue

            if job.get("status") == "running" and prompt_id:
                payload["existing_prompt_id"] = prompt_id
                await db.update_job(job["id"], error_msg=None)
            else:
                await db.update_job(
                    job["id"],
                    status="queued",
                    progress=0,
                    prompt_id=None,
                    server_id=server.id,
                    error_msg=None,
                    completed_at=None,
                )

            await server.queue.put(payload)
            restored += 1

        if restored:
            logger.info(f"Recovered {restored} queued/running job(s) after startup")

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
        workflow_file: str | None = None,
        workflow_data: dict | None = None,
        source: str = "web",
        source_user_id: str | None = None,
        telegram_chat_id: str | None = None,
        visibility: str = "web",
    ):
        """Submit a new job, preferring online servers with shorter queues."""
        async with self._lock:
            server = await self._select_server()
            if not server:
                raise RuntimeError("No ComfyUI servers configured")

        await db.create_job(
            job_id,
            user_id,
            username,
            image_filename,
            job_name=job_name,
            workflow_name=workflow_name,
            workflow_file=workflow_file,
            source=source,
            source_user_id=source_user_id,
            telegram_chat_id=telegram_chat_id,
            visibility=visibility,
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

    async def _select_server(self) -> ServerQueue | None:
        if not self.servers:
            return None

        await asyncio.gather(
            *(self._refresh_server_status(s) for s in self.servers),
            return_exceptions=True,
        )

        ordered = [
            self.servers[(self._next_index + i) % len(self.servers)]
            for i in range(len(self.servers))
        ]
        online = [s for s in ordered if s.is_online]
        candidates = online or ordered
        server = min(candidates, key=lambda s: (1 if s.current_job else 0, s.queue.qsize()))
        self._next_index = (self.servers.index(server) + 1) % len(self.servers)
        return server

    async def _refresh_server_status(self, server: ServerQueue):
        server.is_online = await comfyui_client.check_server(server.url)

    async def _health_monitor(self):
        while True:
            await asyncio.gather(
                *(self._refresh_server_status(s) for s in self.servers),
                return_exceptions=True,
            )
            await asyncio.sleep(HEALTH_CHECK_INTERVAL_S)

    def _server_by_id(self, server_id: str | None) -> ServerQueue | None:
        if not server_id:
            return None
        for server in self.servers:
            if server.id == server_id:
                return server
        return None

    def _build_job_payload(self, job: dict) -> dict | None:
        image_filename = job.get("input_image")
        if not image_filename:
            return None

        image_path = os.path.join(config.UPLOAD_DIR, image_filename)
        if not os.path.exists(image_path):
            return None

        workflow_data = None
        workflow_file = (job.get("workflow_file") or "").strip()
        if workflow_file:
            workflow_path = os.path.join(config.WORKFLOW_ARCHIVE_DIR, workflow_file)
            if os.path.exists(workflow_path):
                with open(workflow_path, "r", encoding="utf-8-sig") as wf:
                    workflow_data = json.load(wf)

        return {
            "job_id": job["id"],
            "image_path": image_path,
            "image_filename": image_filename,
            "username": job["username"],
            "workflow_data": workflow_data,
        }

    async def _complete_from_history(
        self, server: ServerQueue, job_id: str, prompt_id: str
    ) -> bool:
        try:
            history = await comfyui_client.get_history(server.url, prompt_id)
            output_info = comfyui_client.extract_output_info(history, prompt_id)
        except Exception:
            return False

        if not output_info:
            return False

        now = datetime.now(timezone.utc).isoformat()
        await db.update_job(
            job_id,
            status="done",
            progress=100,
            output_info=json.dumps(output_info),
            completed_at=now,
        )
        await self._broadcast_job_update(job_id, server)
        logger.info(f"Job {job_id[:8]} recovered from ComfyUI history")
        return True

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
                    recovered = await self._wait_until_online(server)
                    if not recovered:
                        raise ConnectionError(f"Server {server.name} offline")

                # → running
                await db.update_job(job_id, status="running")
                await self._broadcast_job_update(job_id, server)

                prompt_id = job_data.get("existing_prompt_id")

                if not prompt_id:
                    image_name = await comfyui_client.upload_image(
                        server.url,
                        job_data["image_path"],
                        job_data["image_filename"],
                    )

                    job_check = await db.get_job(job_id)
                    if job_check and job_check["status"] == "cancelled":
                        logger.info(f"Job {job_id[:8]} cancelled after upload")
                        continue

                    prompt = comfyui_client.build_prompt(
                        image_name,
                        workflow_data=job_data.get("workflow_data"),
                    )

                    prompt_id = await comfyui_client.queue_prompt(
                        server.url, prompt, client_id
                    )
                    await db.update_job(job_id, prompt_id=prompt_id)
                else:
                    logger.info(f"Job {job_id[:8]} monitoring existing prompt")

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
                    completed = await self._complete_from_history(
                        server, job_id, prompt_id
                    )
                    if completed:
                        continue
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
                await self._notify_integrations(job_id)
                logger.info(f"Job {job_id[:8]}… DONE ✓ on {server.name}")

            except Exception as e:
                # Check nếu job đã bị cancelled (interrupt gây exception)
                job_check = await db.get_job(job_id)
                if job_check and job_check["status"] == "cancelled":
                    logger.info(f"Job {job_id[:8]}… cancelled (interrupt caught)")
                    await self._broadcast_job_update(job_id, server)
                else:
                    prompt_id = None
                    if job_check:
                        prompt_id = (job_check.get("prompt_id") or "").strip()
                    if prompt_id:
                        completed = await self._complete_from_history(
                            server, job_id, prompt_id
                        )
                        if completed:
                            continue

                    logger.error(f"Job {job_id[:8]}… ERROR ✗: {e}")
                    now = datetime.now(timezone.utc).isoformat()
                    await db.update_job(
                        job_id,
                        status="error",
                        error_msg=str(e),
                        completed_at=now,
                    )
                    await self._broadcast_job_update(job_id, server)
                    await self._notify_integrations(job_id)

            finally:
                server.current_job = None
                server.queue.task_done()

    async def _wait_until_online(self, server: ServerQueue) -> bool:
        """Wait for server to recover after restart before failing the job."""
        for attempt in range(1, SERVER_RECOVERY_RETRIES + 1):
            await asyncio.sleep(SERVER_RECOVERY_INTERVAL_S)
            server.is_online = await comfyui_client.check_server(server.url)
            if server.is_online:
                logger.info(
                    f"{server.name} back online after retry {attempt}/"
                    f"{SERVER_RECOVERY_RETRIES}"
                )
                return True
        return False

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
        if job and (job.get("visibility") or "web") == "web":
            data = self._format_job(job, server)
            await self._broadcast(job["username"], data)

    async def _notify_integrations(self, job_id: str):
        try:
            from telegram_bot import telegram_bot_service

            await telegram_bot_service.notify_job_result(job_id)
        except Exception as exc:
            logger.warning("Integration notify failed for %s: %s", job_id, exc)

    @staticmethod
    def _resolve_job_name(job: dict) -> str:
        name = (job.get("job_name") or "").strip()
        if name:
            return name
        legacy = (job.get("video_name") or "").strip()
        return legacy

    @staticmethod
    def _resolve_output_assets(job: dict) -> tuple[dict | None, dict | None]:
        raw = job.get("output_info")
        if not raw:
            return None, None
        try:
            payload = json.loads(raw)
        except Exception:
            return None, None

        if isinstance(payload, dict) and "video" in payload:
            return payload.get("video"), payload.get("image")

        if isinstance(payload, dict) and payload.get("filename"):
            return payload, None

        return None, None

    def _format_job(self, job: dict, server: ServerQueue | None = None) -> dict:
        server_name = ""
        if server:
            server_name = server.name
        else:
            for s in self.servers:
                if s.id == job.get("server_id"):
                    server_name = s.name
                    break

        video_info, image_info = self._resolve_output_assets(job)

        workflow_file = (job.get("workflow_file") or "").strip()
        if not workflow_file:
            job_id = str(job.get("id") or "").strip()
            if job_id:
                legacy_name = f"{job_id}.json"
                legacy_path = os.path.join(config.WORKFLOW_ARCHIVE_DIR, legacy_name)
                if os.path.exists(legacy_path):
                    workflow_file = legacy_name

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
                "workflow_file": workflow_file,
                "has_workflow": bool(workflow_file),
                "source": job.get("source", "web"),
                "visibility": job.get("visibility", "web"),
                "created_at": job["created_at"],
                "completed_at": job.get("completed_at"),
                "has_output": job.get("output_info") is not None,
                "has_video": video_info is not None,
                "has_image": image_info is not None,
            },
        }

    def get_servers_status(self) -> list:
        return [s.to_dict() for s in self.servers]


# ── Singleton ───────────────────────────────────────────────
balancer = LoadBalancer()
