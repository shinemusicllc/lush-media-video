import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "static" / "app.js"
INDEX_HTML = ROOT / "static" / "index.html"


class ServerLabelTests(unittest.TestCase):
    def test_dashboard_displays_may_labels_but_keeps_gpu_input_mapping(self):
        source = APP_JS.read_text(encoding="utf-8")

        self.assertIn("{ name: 'Máy 1', status: 'offline' }", source)
        self.assertIn("{ name: 'Máy 2', status: 'offline' }", source)
        self.assertIn("return 'Máy 1'", source)
        self.assertIn("return 'Máy 2'", source)
        self.assertIn("normalized.includes('gpu1')", source)
        self.assertIn("normalized.includes('gpu2')", source)
        self.assertIn(
            "const canonicalName = getServerDisplayName(s.name)",
            source,
        )
        self.assertIn("const primaryOrder = ['máy 1', 'máy 2']", source)
        self.assertIn("function getServerDisplayName", source)

    def test_job_badge_uses_the_same_machine_name_mapping(self):
        source = APP_JS.read_text(encoding="utf-8")

        self.assertIn(
            "${escapeHTML(getServerDisplayName(job.server_name))}",
            source,
        )
        self.assertNotIn(
            "${escapeHTML(job.server_name || 'N/A')}",
            source,
        )

    def test_login_footer_uses_the_same_machine_labels(self):
        source = INDEX_HTML.read_text(encoding="utf-8")

        self.assertIn("<span>Máy 1 · Máy 2</span>", source)
        self.assertNotIn("<span>GPU #1 · GPU #2</span>", source)


if __name__ == "__main__":
    unittest.main()
