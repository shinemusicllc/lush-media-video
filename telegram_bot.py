"""
Telegram bot integration.
Long-polling receiver that accepts image + workflow JSON, enqueues into the
shared backend queue, and sends completion notifications with download links.
"""

import asyncio
import json
import logging
import os
import tempfile
import uuid
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

import config
import database as db
from auth import create_token, hash_password

logger = logging.getLogger("telegram_bot")

FINAL_JOB_STATUSES = {"done", "error", "cancelled"}


def _guess_image_ext(filename: str | None, fallback: str = ".jpg") -> str:
    ext = Path(filename or "").suffix.lower()
    if ext in {".jpg", ".jpeg", ".png", ".webp"}:
        return ext
    return fallback


def _telegram_username(chat_id: int | str) -> str:
    return f"tg_{chat_id}"


class TelegramBotService:
    def __init__(self):
        self.token = config.TELEGRAM_BOT_TOKEN
        self.api_base = f"https://api.telegram.org/bot{self.token}" if self.token else ""
        self.file_base = f"https://api.telegram.org/file/bot{self.token}" if self.token else ""
        self._task: asyncio.Task | None = None
        self._offset = 0
        self._client: httpx.AsyncClient | None = None
        self._pending: dict[int, dict[str, Any]] = {}
        self._hint_tasks: dict[int, asyncio.Task] = {}

    @property
    def enabled(self) -> bool:
        return bool(self.token)

    async def start(self):
        if not self.enabled:
            logger.info("Telegram bot disabled: TELEGRAM_BOT_TOKEN not set")
            return
        if self._task and not self._task.done():
            return

        os.makedirs(config.TELEGRAM_PENDING_DIR, exist_ok=True)
        self._client = httpx.AsyncClient(timeout=60)
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("Telegram bot polling started")

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._client:
            await self._client.aclose()
            self._client = None

        for chat_id in list(self._pending.keys()):
            self._clear_pending(chat_id)
        for chat_id in list(self._hint_tasks.keys()):
            self._cancel_hint_task(chat_id)

    async def notify_job_result(self, job_id: str):
        if not self.enabled:
            return

        job = await db.get_job(job_id)
        if not job:
            return
        if job.get("source") != "telegram":
            return
        if job.get("telegram_notified_at"):
            return
        if job.get("status") not in FINAL_JOB_STATUSES:
            return

        chat_id = str(job.get("telegram_chat_id") or "").strip()
        if not chat_id:
            return

        try:
            message = self._build_result_message(job)
            await self._send_message(chat_id, message, parse_mode="HTML")
            await db.update_job(
                job_id,
                telegram_notified_at=self._now_iso(),
            )
        except Exception as exc:
            logger.error("Telegram notify failed for %s: %s", job_id, exc)

    async def _poll_loop(self):
        assert self._client is not None

        while True:
            try:
                updates = await self._get_updates()
                for update in updates:
                    self._offset = max(self._offset, update["update_id"] + 1)
                    await self._handle_update(update)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("Telegram polling error: %s", exc)
                await asyncio.sleep(config.TELEGRAM_POLL_INTERVAL_S)

    async def _get_updates(self) -> list[dict]:
        assert self._client is not None
        r = await self._client.get(
            f"{self.api_base}/getUpdates",
            params={
                "offset": self._offset,
                "timeout": config.TELEGRAM_POLL_TIMEOUT_S,
                "allowed_updates": json.dumps(["message"]),
            },
        )
        r.raise_for_status()
        payload = r.json()
        return payload.get("result", [])

    async def _handle_update(self, update: dict):
        message = update.get("message") or {}
        chat = message.get("chat") or {}
        from_user = message.get("from") or {}
        chat_id = chat.get("id")
        if chat_id is None:
            return

        if "text" in message:
            await self._handle_text(chat_id, message["text"])
            return

        if message.get("photo"):
            await self._handle_photo(chat_id, from_user, message)
            return

        document = message.get("document")
        if document:
            if self._is_workflow_document(document):
                await self._handle_workflow(chat_id, from_user, message)
                return
            if self._is_image_document(document):
                await self._handle_image_document(chat_id, from_user, message)
                return

    async def _handle_text(self, chat_id: int, text: str):
        cmd = (text or "").strip()
        if cmd.startswith("/start") or cmd.startswith("/help"):
            await self._send_message(
                chat_id,
                "Gửi 1 ảnh và 1 file workflow JSON trong cùng chat này.\n"
                "Khi đã nhận đủ cả hai, bot sẽ tự động xếp job vào hàng đợi chung.",
            )
            return

        if cmd.startswith("/cancel"):
            self._clear_pending(chat_id)
            await self._send_message(chat_id, "Đã xoá dữ liệu đang chờ của bạn.")
            return

        await self._send_message(
            chat_id,
            "Bot đang chờ ảnh và workflow JSON. Dùng /help để xem hướng dẫn.",
        )

    async def _handle_photo(self, chat_id: int, from_user: dict, message: dict):
        photo_sizes = message.get("photo") or []
        if not photo_sizes:
            return
        file_id = photo_sizes[-1]["file_id"]
        local_path = await self._download_to_pending(chat_id, file_id, ".jpg")
        pending = self._pending.setdefault(chat_id, {})
        self._replace_pending_file(pending.get("image_path"))
        pending["image_path"] = local_path
        pending["image_ext"] = ".jpg"
        pending["source_user_id"] = str(from_user.get("id") or "")
        caption = str(message.get("caption") or "").strip()
        if caption:
            pending["job_name"] = caption[:120]
        await self._maybe_enqueue(chat_id)

    async def _handle_image_document(self, chat_id: int, from_user: dict, message: dict):
        document = message.get("document") or {}
        ext = _guess_image_ext(document.get("file_name"))
        local_path = await self._download_to_pending(chat_id, document["file_id"], ext)
        pending = self._pending.setdefault(chat_id, {})
        self._replace_pending_file(pending.get("image_path"))
        pending["image_path"] = local_path
        pending["image_ext"] = ext
        pending["source_user_id"] = str(from_user.get("id") or "")
        caption = str(message.get("caption") or "").strip()
        if caption:
            pending["job_name"] = caption[:120]
        await self._maybe_enqueue(chat_id)

    async def _handle_workflow(self, chat_id: int, from_user: dict, message: dict):
        document = message.get("document") or {}
        workflow_name = document.get("file_name") or "workflow.json"
        raw = await self._download_bytes(document["file_id"])
        if len(raw) > 2 * 1024 * 1024:
            await self._send_message(chat_id, "Workflow JSON quá lớn. Giới hạn là 2MB.")
            return

        try:
            workflow_data = json.loads(raw.decode("utf-8-sig"))
        except Exception as exc:
            await self._send_message(chat_id, f"Workflow JSON không hợp lệ: {exc}")
            return

        if not isinstance(workflow_data, dict):
            await self._send_message(chat_id, "Workflow JSON phải là object ở cấp gốc.")
            return

        pending = self._pending.setdefault(chat_id, {})
        pending["workflow_data"] = workflow_data
        pending["workflow_name"] = Path(workflow_name).name
        pending["source_user_id"] = str(from_user.get("id") or pending.get("source_user_id") or "")
        await self._maybe_enqueue(chat_id)

    async def _maybe_enqueue(self, chat_id: int):
        pending = self._pending.get(chat_id) or {}
        image_path = pending.get("image_path")
        workflow_data = pending.get("workflow_data")
        if not image_path or workflow_data is None:
            self._schedule_missing_hint(chat_id)
            return

        self._cancel_hint_task(chat_id)
        user = await self._ensure_telegram_user(chat_id)
        job_id = str(uuid.uuid4())
        image_ext = pending.get("image_ext") or ".jpg"
        final_filename = f"{job_id}{image_ext}"
        final_image_path = os.path.join(config.UPLOAD_DIR, final_filename)
        os.makedirs(config.UPLOAD_DIR, exist_ok=True)
        os.replace(image_path, final_image_path)
        workflow_archive_file = f"{job_id}.json"
        workflow_archive_path = os.path.join(
            config.WORKFLOW_ARCHIVE_DIR, workflow_archive_file
        )
        os.makedirs(config.WORKFLOW_ARCHIVE_DIR, exist_ok=True)
        with open(workflow_archive_path, "w", encoding="utf-8") as wf:
            json.dump(workflow_data, wf, ensure_ascii=False, indent=2)

        job_name = (pending.get("job_name") or "").strip()
        if not job_name:
            job_name = f"telegram_{job_id[:8]}"

        from load_balancer import balancer

        await balancer.submit_job(
            job_id=job_id,
            user_id=user["id"],
            username=user["username"],
            image_path=final_image_path,
            image_filename=final_filename,
            job_name=job_name[:120],
            workflow_name=pending.get("workflow_name") or "workflow.json",
            workflow_file=workflow_archive_file,
            workflow_data=workflow_data,
            source="telegram",
            source_user_id=pending.get("source_user_id") or str(chat_id),
            telegram_chat_id=str(chat_id),
            visibility="hidden",
        )

        self._pending.pop(chat_id, None)
        await self._send_message(
            chat_id,
            f"Đã xếp job '{job_name[:120]}' vào hàng đợi chung.\nMã job: {job_id[:8]}",
        )

    async def _ensure_telegram_user(self, chat_id: int) -> dict:
        username = _telegram_username(chat_id)
        user = await db.get_user(username)
        if user:
            return user

        password_hash = hash_password(uuid.uuid4().hex)
        user_id = await db.create_user(username, password_hash, "telegram")
        return {
            "id": user_id,
            "username": username,
            "role": "telegram",
        }

    async def _download_to_pending(self, chat_id: int, file_id: str, ext: str) -> str:
        raw = await self._download_bytes(file_id)
        os.makedirs(config.TELEGRAM_PENDING_DIR, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(
            prefix=f"tg_{chat_id}_",
            suffix=ext,
            dir=config.TELEGRAM_PENDING_DIR,
        )
        with os.fdopen(fd, "wb") as fh:
            fh.write(raw)
        return temp_path

    async def _download_bytes(self, file_id: str) -> bytes:
        assert self._client is not None
        file_info = await self._client.get(
            f"{self.api_base}/getFile",
            params={"file_id": file_id},
        )
        file_info.raise_for_status()
        payload = file_info.json().get("result") or {}
        file_path = payload.get("file_path")
        if not file_path:
            raise RuntimeError("Không lấy được file_path từ Telegram")

        file_resp = await self._client.get(f"{self.file_base}/{file_path}")
        file_resp.raise_for_status()
        return file_resp.content

    async def _send_message(
        self,
        chat_id: int | str,
        text: str,
        parse_mode: str | None = None,
    ):
        assert self._client is not None
        payload = {
            "chat_id": str(chat_id),
            "text": text,
            "disable_web_page_preview": True,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        response = await self._client.post(
            f"{self.api_base}/sendMessage",
            json=payload,
        )
        response.raise_for_status()

    def _build_result_message(self, job: dict) -> str:
        job_name = (job.get("job_name") or job.get("video_name") or job["id"][:8]).strip()
        safe_name = escape(job_name)
        lines = [f"Job <b>{safe_name}</b> đã {self._status_label(job.get('status'))}."]

        if job.get("status") == "error" and job.get("error_msg"):
            lines.append(f"Lỗi: <code>{escape(str(job['error_msg']))}</code>")

        if job.get("status") == "done" and config.PUBLIC_BASE_URL:
            token = create_token(job["username"], "telegram")
            token_q = quote(token, safe="")
            base = config.PUBLIC_BASE_URL.rstrip("/")
            video_url = f"{base}/api/jobs/{job['id']}/video?token={token_q}"
            image_url = f"{base}/api/jobs/{job['id']}/image?token={token_q}"
            lines.append(
                f'<a href="{escape(video_url)}">Tải video</a> | '
                f'<a href="{escape(image_url)}">Tải ảnh</a>'
            )
        elif job.get("status") == "done":
            lines.append("Chưa cấu hình PUBLIC_BASE_URL nên chưa tạo được link tải.")

        return "\n".join(lines)

    @staticmethod
    def _status_label(status: str | None) -> str:
        if status == "done":
            return "hoàn tất"
        if status == "error":
            return "thất bại"
        if status == "cancelled":
            return "bị huỷ"
        return status or "cập nhật"

    @staticmethod
    def _is_workflow_document(document: dict) -> bool:
        name = str(document.get("file_name") or "").lower()
        return name.endswith(".json")

    @staticmethod
    def _is_image_document(document: dict) -> bool:
        mime = str(document.get("mime_type") or "").lower()
        if mime.startswith("image/"):
            return True
        name = str(document.get("file_name") or "").lower()
        return name.endswith((".jpg", ".jpeg", ".png", ".webp"))

    @staticmethod
    def _replace_pending_file(path: str | None):
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass

    def _clear_pending(self, chat_id: int):
        self._cancel_hint_task(chat_id)
        pending = self._pending.pop(chat_id, None)
        if not pending:
            return
        self._replace_pending_file(pending.get("image_path"))

    def _schedule_missing_hint(self, chat_id: int):
        self._cancel_hint_task(chat_id)
        self._hint_tasks[chat_id] = asyncio.create_task(self._delayed_missing_hint(chat_id))

    def _cancel_hint_task(self, chat_id: int):
        task = self._hint_tasks.pop(chat_id, None)
        if task:
            task.cancel()

    async def _delayed_missing_hint(self, chat_id: int):
        try:
            await asyncio.sleep(1.2)
            pending = self._pending.get(chat_id) or {}
            image_path = pending.get("image_path")
            workflow_data = pending.get("workflow_data")
            if image_path and workflow_data is None:
                await self._send_message(chat_id, "Đã nhận ảnh. Gửi thêm workflow JSON để xếp job.")
            elif workflow_data is not None and not image_path:
                await self._send_message(chat_id, "Đã nhận workflow. Gửi thêm ảnh để xếp job.")
        except asyncio.CancelledError:
            return
        finally:
            self._hint_tasks.pop(chat_id, None)

    @staticmethod
    def _now_iso() -> str:
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).isoformat()


telegram_bot_service = TelegramBotService()
