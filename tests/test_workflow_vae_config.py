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
EXPECTED_LENGTHS = {
    "Jazz & lofi 6s Khong Loop.json": 73,
    "Jazz & lofi 6s Co Loop.json": 73,
    "Kling Animation 5s Co Loop.json": 61,
    "Kling Animation 5s Khong Loop.json": 61,
    "Livewallpaper 5s Khong Loop.json": 61,
}
TILED_INPUTS = {"tile_size", "overlap", "temporal_size", "temporal_overlap"}


class WorkflowVaeConfigTests(unittest.TestCase):
    def test_default_and_all_presets_use_regular_vae(self):
        preset_paths = sorted(PRESET_DIRECTORY.glob("*.json"))
        self.assertEqual(EXPECTED_PRESETS, {path.name for path in preset_paths})
        self.assertFalse(any("Jazz & lofi 5s" in path.name for path in preset_paths))

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
                self.assertEqual("VAEDecode", vae_node["class_type"])
                self.assertTrue(TILED_INPUTS.isdisjoint(vae_node["inputs"]))
                self.assertEqual("VAE Decode", vae_node["_meta"]["title"])

    def test_default_and_presets_keep_their_named_duration(self):
        workflow_paths = [
            DEFAULT_WORKFLOW,
            *sorted(PRESET_DIRECTORY.glob("*.json")),
        ]

        for path in workflow_paths:
            with self.subTest(workflow=path.name):
                workflow = json.loads(path.read_text(encoding="utf-8-sig"))
                video_latent_nodes = [
                    node
                    for node in workflow.values()
                    if isinstance(node, dict)
                    and node.get("class_type") == "WanFirstLastFrameToVideo"
                ]

                self.assertEqual(1, len(video_latent_nodes))
                self.assertEqual(
                    EXPECTED_LENGTHS[path.name],
                    video_latent_nodes[0]["inputs"]["length"],
                )


if __name__ == "__main__":
    unittest.main()
