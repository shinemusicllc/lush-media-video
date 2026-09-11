import unittest

import workflow_guard


class MaximumVideoLengthTests(unittest.TestCase):
    def _enforce(self, workflow):
        self.assertTrue(
            hasattr(workflow_guard, "enforce_max_video_length"),
            "workflow_guard.enforce_max_video_length is missing",
        )
        return workflow_guard.enforce_max_video_length(workflow)

    def test_preserves_api_workflow_at_61_frames(self):
        workflow = {
            "12": {
                "class_type": "WanFirstLastFrameToVideo",
                "inputs": {"length": 61},
            }
        }

        self.assertEqual(0, self._enforce(workflow))
        self.assertEqual(61, workflow["12"]["inputs"]["length"])

    def test_preserves_api_workflow_at_73_frames(self):
        workflow = {
            "12": {
                "class_type": "WanFirstLastFrameToVideo",
                "inputs": {"length": 73},
            }
        }

        self.assertEqual(0, self._enforce(workflow))
        self.assertEqual(73, workflow["12"]["inputs"]["length"])

    def test_caps_overlong_api_workflow_at_73_frames(self):
        workflow = {
            "12": {
                "class_type": "WanFirstLastFrameToVideo",
                "inputs": {"length": 85},
            }
        }

        self.assertEqual(1, self._enforce(workflow))
        self.assertEqual(73, workflow["12"]["inputs"]["length"])
        self.assertEqual(0, self._enforce(workflow))

    def test_defaults_missing_api_length_to_73_frames(self):
        workflow = {
            "12": {
                "class_type": "WanFirstLastFrameToVideo",
                "inputs": {},
            }
        }

        self.assertEqual(1, self._enforce(workflow))
        self.assertEqual(73, workflow["12"]["inputs"]["length"])

    def test_defaults_invalid_api_length_to_73_frames(self):
        workflow = {
            "12": {
                "class_type": "WanFirstLastFrameToVideo",
                "inputs": {"length": "61"},
            }
        }

        self.assertEqual(1, self._enforce(workflow))
        self.assertEqual(73, workflow["12"]["inputs"]["length"])

    def test_caps_ui_workflow_length_widget_at_73_frames(self):
        workflow = {
            "nodes": [
                {
                    "type": "WanFirstLastFrameToVideo",
                    "widgets_values": [1920, 1088, 85, 1],
                }
            ]
        }

        self.assertEqual(1, self._enforce(workflow))
        self.assertEqual(73, workflow["nodes"][0]["widgets_values"][2])

    def test_preserves_ui_workflow_at_61_frames(self):
        workflow = {
            "nodes": [
                {
                    "type": "WanFirstLastFrameToVideo",
                    "widgets_values": [1920, 1088, 61, 1],
                }
            ]
        }

        self.assertEqual(0, self._enforce(workflow))
        self.assertEqual(61, workflow["nodes"][0]["widgets_values"][2])

    def test_does_not_change_unrelated_length_input(self):
        workflow = {
            "1": {
                "class_type": "OtherNode",
                "inputs": {"length": 73},
            }
        }

        self.assertEqual(0, self._enforce(workflow))
        self.assertEqual(73, workflow["1"]["inputs"]["length"])


if __name__ == "__main__":
    unittest.main()
