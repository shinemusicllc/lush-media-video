import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import aiosqlite
import database
from load_balancer import LoadBalancer


class DriveJobPersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_database_adds_drive_file_id_and_persists_it(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = str(Path(temp_dir) / "jobs.db")
            with patch.object(database, "DB_PATH", db_path):
                await database.init_db()
                async with aiosqlite.connect(db_path) as conn:
                    await conn.execute("ALTER TABLE jobs DROP COLUMN drive_file_id")
                    await conn.commit()
                await database.init_db()
                await database.create_job(
                    "drive-job",
                    1,
                    "tester",
                    "",
                    job_name="Drive job",
                    drive_file_id="Abc_123-xyz",
                )
                job = await database.get_job("drive-job")

        self.assertEqual("Abc_123-xyz", job["drive_file_id"])
        self.assertEqual("", job["input_image"])

    async def test_queued_drive_job_can_be_rebuilt_after_restart(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workflow_dir = Path(temp_dir) / "workflows"
            workflow_dir.mkdir()
            workflow = {"1": {"class_type": "LoadImage", "inputs": {"image": "old.png"}}}
            (workflow_dir / "drive-job.json").write_text(
                json.dumps(workflow), encoding="utf-8"
            )
            with (
                patch("load_balancer.config.UPLOAD_DIR", str(Path(temp_dir) / "uploads")),
                patch("load_balancer.config.WORKFLOW_ARCHIVE_DIR", str(workflow_dir)),
            ):
                payload = LoadBalancer()._build_job_payload(
                    {
                        "id": "drive-job",
                        "username": "tester",
                        "input_image": "",
                        "drive_file_id": "Abc_123-xyz",
                        "workflow_file": "drive-job.json",
                    }
                )

        self.assertEqual("Abc_123-xyz", payload["drive_file_id"])
        self.assertEqual("", payload["image_path"])
        self.assertEqual("LoadImage", payload["workflow_data"]["1"]["class_type"])


if __name__ == "__main__":
    unittest.main()
