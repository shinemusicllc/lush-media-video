import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

import httpx

from comfyui_client import _classify_history_item, build_prompt, upload_image


class _UploadResponse:
    status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return {"name": "uploaded.png"}


class _RetryingUploadClient:
    attempts = 0
    file_offsets = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def post(self, url, files, data):
        type(self).attempts += 1
        file_obj = files["image"][1]
        type(self).file_offsets.append(file_obj.tell())
        if type(self).attempts == 1:
            file_obj.read(2)
            raise httpx.WriteTimeout("simulated slow tunnel")
        return _UploadResponse()


class UploadImageTests(unittest.IsolatedAsyncioTestCase):
    async def test_transport_failure_reopens_file_and_retries(self):
        _RetryingUploadClient.attempts = 0
        _RetryingUploadClient.file_offsets = []
        sleep = AsyncMock()
        fd, path = tempfile.mkstemp(suffix=".png")
        try:
            os.write(fd, b"abcdef")
            os.close(fd)
            fd = -1
            with (
                patch("comfyui_client.httpx.AsyncClient", _RetryingUploadClient),
                patch("comfyui_client.asyncio.sleep", sleep),
                patch("comfyui_client.COMFYUI_UPLOAD_MAX_ATTEMPTS", 2),
                patch("comfyui_client.COMFYUI_UPLOAD_RETRY_DELAY_S", 0.1),
            ):
                result = await upload_image("http://gpu", path, "input.png")

            self.assertEqual("uploaded.png", result)
            self.assertEqual([0, 0], _RetryingUploadClient.file_offsets)
            sleep.assert_awaited_once_with(0.1)
        finally:
            if fd >= 0:
                os.close(fd)
            os.unlink(path)


class ClassifyHistoryItemTests(unittest.TestCase):
    def test_completed_history_is_done(self):
        self.assertEqual(
            _classify_history_item({"status": {"completed": True}}),
            ("done", None),
        )

    def test_outputs_are_done_when_completed_flag_is_missing(self):
        self.assertEqual(
            _classify_history_item({"status": {}, "outputs": {"9": {}}}),
            ("done", None),
        )

    def test_success_status_is_done(self):
        self.assertEqual(
            _classify_history_item({"status": {"status_str": "success"}}),
            ("done", None),
        )

    def test_error_status_is_not_reported_as_success(self):
        self.assertEqual(
            _classify_history_item(
                {
                    "status": {
                        "status_str": "error",
                        "messages": [
                            ["execution_error", {"exception_message": "OOM"}]
                        ],
                    }
                }
            ),
            ("error", "OOM"),
        )

    def test_active_history_is_not_terminal(self):
        self.assertIsNone(
            _classify_history_item({"status": {"status_str": "running"}})
        )


class BuildPromptPolicyTests(unittest.TestCase):
    def test_build_prompt_preserves_five_second_video_length(self):
        workflow = {
            "1": {
                "class_type": "LoadImage",
                "inputs": {"image": "old.png"},
            },
            "2": {
                "class_type": "WanFirstLastFrameToVideo",
                "inputs": {"length": 61},
            },
        }

        prompt = build_prompt("new.png", seed=1, workflow_data=workflow)

        self.assertEqual(61, prompt["2"]["inputs"]["length"])
        self.assertEqual(61, workflow["2"]["inputs"]["length"])

    def test_build_prompt_caps_overlong_video_at_73_frames(self):
        workflow = {
            "1": {
                "class_type": "LoadImage",
                "inputs": {"image": "old.png"},
            },
            "2": {
                "class_type": "WanFirstLastFrameToVideo",
                "inputs": {"length": 85},
            },
        }

        prompt = build_prompt("new.png", seed=1, workflow_data=workflow)

        self.assertEqual(73, prompt["2"]["inputs"]["length"])
        self.assertEqual(85, workflow["2"]["inputs"]["length"])


if __name__ == "__main__":
    unittest.main()
