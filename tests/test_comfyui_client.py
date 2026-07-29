import unittest

from comfyui_client import _classify_history_item


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


if __name__ == "__main__":
    unittest.main()
