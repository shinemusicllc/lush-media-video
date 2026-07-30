import unittest

import workflow_guard


class LockedVideoLengthTests(unittest.TestCase):
    def _enforce(self, workflow):
        self.assertTrue(
            hasattr(workflow_guard, "enforce_locked_video_length"),
            "workflow_guard.enforce_locked_video_length is missing",
        )
        return workflow_guard.enforce_locked_video_length(workflow)

    def test_locks_api_workflow_video_length_to_61(self):
        workflow = {
            "12": {
                "class_type": "WanFirstLastFrameToVideo",
                "inputs": {"length": 73},
            }
        }

        self.assertEqual(1, self._enforce(workflow))
        self.assertEqual(61, workflow["12"]["inputs"]["length"])
        self.assertEqual(0, self._enforce(workflow))

    def test_locks_shorter_api_workflow_to_exactly_61(self):
        workflow = {
            "12": {
                "class_type": "WanFirstLastFrameToVideo",
                "inputs": {"length": 49},
            }
        }

        self.assertEqual(1, self._enforce(workflow))
        self.assertEqual(61, workflow["12"]["inputs"]["length"])

    def test_locks_ui_workflow_length_widget(self):
        workflow = {
            "nodes": [
                {
                    "type": "WanFirstLastFrameToVideo",
                    "widgets_values": [1920, 1088, 73, 1],
                }
            ]
        }

        self.assertEqual(1, self._enforce(workflow))
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
