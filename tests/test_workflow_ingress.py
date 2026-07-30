import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi import UploadFile
from starlette.datastructures import Headers

import main
from telegram_bot import TelegramBotService


def make_legacy_workflow():
    return {
        "1": {
            "class_type": "LoadImage",
            "inputs": {"image": "old.png"},
        },
        "2": {
            "class_type": "WanFirstLastFrameToVideo",
            "inputs": {"length": 73},
        },
    }


class WebWorkflowIngressTests(unittest.IsolatedAsyncioTestCase):
    async def test_web_archives_and_queues_locked_workflow(self):
        workflow_bytes = json.dumps(make_legacy_workflow()).encode("utf-8")
        image = UploadFile(
            io.BytesIO(b"image"),
            filename="input.png",
            headers=Headers({"content-type": "image/png"}),
        )
        workflow = UploadFile(
            io.BytesIO(workflow_bytes),
            filename="legacy 6s.json",
            headers=Headers({"content-type": "application/json"}),
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            upload_dir = Path(temp_dir) / "uploads"
            archive_dir = Path(temp_dir) / "workflows"
            upload_dir.mkdir()
            archive_dir.mkdir()

            submit_job = AsyncMock()
            with (
                patch.object(main.config, "UPLOAD_DIR", str(upload_dir)),
                patch.object(
                    main.config,
                    "WORKFLOW_ARCHIVE_DIR",
                    str(archive_dir),
                ),
                patch.object(main.balancer, "submit_job", submit_job),
            ):
                await main.create_job(
                    file=image,
                    job_name="",
                    video_name="",
                    workflow_file=workflow,
                    user={"id": 1, "username": "tester"},
                )

            queued_workflow = submit_job.await_args.kwargs["workflow_data"]
            self.assertEqual(61, queued_workflow["2"]["inputs"]["length"])

            archive_files = list(archive_dir.glob("*.json"))
            self.assertEqual(1, len(archive_files))
            archived = json.loads(archive_files[0].read_text(encoding="utf-8"))
            self.assertEqual(61, archived["2"]["inputs"]["length"])


class TelegramWorkflowIngressTests(unittest.IsolatedAsyncioTestCase):
    async def test_telegram_stores_locked_workflow_in_pending_batch(self):
        service = TelegramBotService()
        service._download_bytes = AsyncMock(
            return_value=json.dumps(make_legacy_workflow()).encode("utf-8")
        )
        service._maybe_enqueue = AsyncMock()

        await service._handle_workflow(
            chat_id=123,
            from_user={"id": 456},
            message={
                "document": {
                    "file_id": "workflow-file",
                    "file_name": "legacy 6s.json",
                }
            },
        )

        pending_workflow = service._pending[123]["workflow_data"]
        self.assertEqual(61, pending_workflow["2"]["inputs"]["length"])
        service._maybe_enqueue.assert_awaited_once_with(123)


if __name__ == "__main__":
    unittest.main()
