import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKFLOW = REPO_ROOT / "workflows" / "Jazz & lofi 6s Khong Loop.json"
PRESET_DIRECTORY = REPO_ROOT / "workflows" / "presets"
EXPECTED_PRESETS = {
    "Jazz & lofi 6s Co Loop.json",
    "Jazz & lofi 6s Khong Loop.json",
    "Kling Animation 5s Co Loop.json",
    "Kling Animation 5s Khong Loop.json",
    "Livewallpaper 5s Khong Loop.json",
}
EXPECTED_TILING = {
    "tile_size": 512,
    "overlap": 64,
    "temporal_size": 16,
    "temporal_overlap": 4,
}


class WorkflowVaeConfigTests(unittest.TestCase):
    def test_default_and_all_presets_use_temporally_tiled_vae(self):
        preset_paths = sorted(PRESET_DIRECTORY.glob("*.json"))
        self.assertEqual(EXPECTED_PRESETS, {path.name for path in preset_paths})

        for path in [DEFAULT_WORKFLOW, *preset_paths]:
            with self.subTest(workflow=path.name):
                workflow = json.loads(path.read_text(encoding="utf-8-sig"))
                vae_nodes = [
                    node
                    for node in workflow.values()
                    if isinstance(node, dict)
                    and str(node.get("class_type", "")).startswith("VAEDecode")
                ]

                self.assertEqual(1, len(vae_nodes))
                vae_node = vae_nodes[0]
                self.assertEqual("VAEDecodeTiled", vae_node["class_type"])
                for key, value in EXPECTED_TILING.items():
                    self.assertEqual(value, vae_node["inputs"].get(key), key)


if __name__ == "__main__":
    unittest.main()
