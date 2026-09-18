from pathlib import Path
import unittest


class BackupRetentionScriptTests(unittest.TestCase):
    def test_backup_invokes_cleanup_with_python_not_execute_bit(self):
        script = Path("deploy/scripts/backup_data.sh").read_text(encoding="utf-8")

        self.assertIn('PYTHON_BIN="${PYTHON_BIN:-python3}"', script)
        self.assertIn(
            'DATA_RETENTION_DAYS="${DATA_RETENTION_DAYS}" "${PYTHON_BIN}" "${SCRIPT_DIR}/cleanup_data.py"',
            script,
        )
        self.assertNotIn('DATA_RETENTION_DAYS="${DATA_RETENTION_DAYS}" "${SCRIPT_DIR}/cleanup_data.py"', script)
        self.assertIn('ARCHIVE_PARTIAL="${ARCHIVE_FILE}.partial"', script)
        self.assertIn('tar -czf "${ARCHIVE_PARTIAL}" -C "${DEPLOY_DIR}" data', script)
        self.assertIn('tar -tzf "${ARCHIVE_PARTIAL}" >/dev/null', script)
        self.assertIn('mv -f -- "${ARCHIVE_PARTIAL}" "${ARCHIVE_FILE}"', script)


if __name__ == "__main__":
    unittest.main()
