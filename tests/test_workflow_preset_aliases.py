import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import config
import main


class WorkflowPresetAliasTests(unittest.TestCase):
    def test_default_workflow_uses_six_second_filename(self):
        self.assertEqual(
            "Jazz & lofi 6s Khong Loop.json",
            Path(config.WORKFLOW_PATH).name,
        )

    def test_old_five_second_jazz_names_resolve_to_six_second_files(self):
        aliases = {
            "Jazz & lofi 5s Co Loop.json": "Jazz & lofi 6s Co Loop.json",
            "Jazz & lofi 5s Khong Loop.json": "Jazz & lofi 6s Khong Loop.json",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            preset_dir = Path(temp_dir)
            for new_name in aliases.values():
                (preset_dir / new_name).write_text("{}", encoding="utf-8")

            with patch.object(main.config, "WORKFLOW_PRESET_DIR", temp_dir):
                for old_name, new_name in aliases.items():
                    with self.subTest(old_name=old_name):
                        resolved = main._resolve_workflow_preset(old_name)
                        self.assertIsNotNone(resolved)
                        self.assertEqual(new_name, resolved.name)


if __name__ == "__main__":
    unittest.main()
