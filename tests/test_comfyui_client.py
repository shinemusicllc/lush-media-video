import os
import json
import tempfile
import unittest
from pathlib import Path
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

    def test_build_prompt_replaces_load_image_with_drive_loader(self):
        workflow = {
            "1": {
                "class_type": "LoadImage",
                "inputs": {"image": "old.png"},
            },
            "2": {
                "class_type": "WanFirstLastFrameToVideo",
                "inputs": {"length": 73, "start_image": ["1", 0], "end_image": ["1", 0]},
            },
        }

        prompt = build_prompt(
            None,
            workflow_data=workflow,
            drive_url="https://drive.google.com/file/d/Abc_123-xyz/view",
        )

        self.assertEqual("LushLoadImageFromDrive", prompt["1"]["class_type"])
        self.assertEqual(
            "https://drive.google.com/file/d/Abc_123-xyz/view",
            prompt["1"]["inputs"]["drive_url"],
        )
        self.assertNotIn("image", prompt["1"]["inputs"])
        self.assertEqual(["1", 0], prompt["2"]["inputs"]["start_image"])
        self.assertEqual("LoadImage", workflow["1"]["class_type"])

    def test_build_prompt_replaces_universal_loader_and_maps_filename_prefix(self):
        workflow = {
            "140": {
                "class_type": "UniversalImageLoader",
                "inputs": {
                    "image": "old.png",
                    "use_upload": True,
                    "image_path": "",
                },
            },
            "82": {
                "class_type": "VHS_VideoCombine",
                "inputs": {"filename_prefix": ["140", 2]},
            },
            "95": {
                "class_type": "WanFirstLastFrameToVideo",
                "inputs": {"start_image": ["140", 0]},
            },
        }

        prompt = build_prompt(
            None,
            workflow_data=workflow,
            drive_url="https://drive.google.com/file/d/Abc_123-xyz/view",
        )

        self.assertEqual("LushLoadImageFromDrive", prompt["140"]["class_type"])
        self.assertEqual(
            {"drive_url": "https://drive.google.com/file/d/Abc_123-xyz/view"},
            prompt["140"]["inputs"],
        )
        self.assertEqual(["140", 0], prompt["95"]["inputs"]["start_image"])
        self.assertEqual("drive_image", prompt["82"]["inputs"]["filename_prefix"])
        self.assertEqual("UniversalImageLoader", workflow["140"]["class_type"])

    def test_drive_source_is_supported_by_fallback_and_every_bundled_preset(self):
        workflow_root = Path(__file__).resolve().parents[1] / "workflows"
        workflow_paths = [
            workflow_root / "Jazz & lofi 6s Khong Loop.json",
            *sorted((workflow_root / "presets").glob("*.json")),
        ]
        self.assertGreaterEqual(len(workflow_paths), 6)

        for workflow_path in workflow_paths:
            with self.subTest(workflow=workflow_path.name):
                workflow = json.loads(workflow_path.read_text(encoding="utf-8-sig"))
                prompt = build_prompt(
                    None,
                    workflow_data=workflow,
                    drive_url="https://drive.google.com/file/d/Abc_123-xyz/view",
                )
                drive_nodes = [
                    node
                    for node in prompt.values()
                    if isinstance(node, dict)
                    and node.get("class_type") == "LushLoadImageFromDrive"
                ]
                self.assertEqual(1, len(drive_nodes))


if __name__ == "__main__":
    unittest.main()
