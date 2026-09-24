import unittest

from drive_links import google_drive_file_id


class GoogleDriveLinkTests(unittest.TestCase):
    def test_extracts_shared_file_id_from_path_link(self):
        self.assertEqual(
            "Abc_123-xyz",
            google_drive_file_id(
                "https://drive.google.com/file/d/Abc_123-xyz/view?usp=sharing"
            ),
        )

    def test_extracts_shared_file_id_from_download_link(self):
        self.assertEqual(
            "Abc_123-xyz",
            google_drive_file_id(
                "https://drive.google.com/uc?export=download&id=Abc_123-xyz"
            ),
        )

    def test_rejects_non_drive_hosts_and_non_https_urls(self):
        self.assertIsNone(google_drive_file_id("https://drive.google.com.evil.test/file/d/abc/view"))
        self.assertIsNone(google_drive_file_id("http://drive.google.com/file/d/abc/view"))
        self.assertIsNone(google_drive_file_id("https://example.com/file/d/Abc_123-xyz/view"))


if __name__ == "__main__":
    unittest.main()
