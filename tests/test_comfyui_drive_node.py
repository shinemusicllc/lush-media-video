import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from deploy.comfyui_nodes.lush_drive_image.drive_image_loader import (
    LushLoadImageFromDrive,
    _download_direct,
    google_drive_file_id,
)


class ComfyUIDriveNodeTests(unittest.TestCase):
    def test_extracts_file_id_from_shared_drive_link(self):
        self.assertEqual(
            "1v1ZUE_XPa22fOGjqduU0iunEiqP_L4A3",
            google_drive_file_id(
                "https://drive.google.com/file/d/1v1ZUE_XPa22fOGjqduU0iunEiqP_L4A3/view?usp=sharing"
            ),
        )

    def test_rejects_untrusted_link_host(self):
        self.assertIsNone(
            google_drive_file_id(
                "https://drive.google.com.evil.test/file/d/1v1ZUE_XPa22fOGjqduU0iunEiqP_L4A3/view"
            )
        )

    def test_node_exposes_comfy_image_and_mask_outputs(self):
        self.assertEqual(("IMAGE", "MASK"), LushLoadImageFromDrive.RETURN_TYPES)
        self.assertEqual("load_image", LushLoadImageFromDrive.FUNCTION)

    def test_direct_download_stream_writes_the_response(self):
        class Response:
            headers = {"content-type": "image/png", "content-length": "4"}

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def raise_for_status(self):
                return None

            def iter_content(self, chunk_size):
                self.chunk_size = chunk_size
                yield b"PNG!"

        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "source-image"
            with patch("requests.get", return_value=Response()):
                _download_direct("Abc_123-xyz", target)
            self.assertEqual(b"PNG!", target.read_bytes())


if __name__ == "__main__":
    unittest.main()
