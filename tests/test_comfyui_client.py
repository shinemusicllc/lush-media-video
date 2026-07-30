import unittest

from comfyui_client import _classify_history_item, build_prompt


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
