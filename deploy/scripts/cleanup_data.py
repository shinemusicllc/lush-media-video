#!/usr/bin/env python3
"""Prune old ComfyUIBot job history and local assets."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    return int(raw)


SCRIPT_DIR = Path(__file__).resolve().parent
DEPLOY_DIR = SCRIPT_DIR.parent
DATA_DIR = Path(os.environ.get("DATA_DIR", DEPLOY_DIR / "data")).resolve()
DB_PATH = Path(os.environ.get("DB_PATH_HOST", DATA_DIR / "comfybot.db")).resolve()
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR_HOST", DATA_DIR / "uploads")).resolve()
WORKFLOW_DIR = Path(os.environ.get("WORKFLOW_ARCHIVE_DIR_HOST", DATA_DIR / "workflows")).resolve()
RETENTION_DAYS = _env_int("DATA_RETENTION_DAYS", 7)


def _safe_child(base: Path, candidate: str | None) -> Path | None:
    if not candidate:
        return None
    path = (base / candidate).resolve()
    if path == base or base not in path.parents:
        return None
    return path


def _remove_file(path: Path | None) -> bool:
    if path is None or not path.is_file():
        return False
    path.unlink()
    return True


def _iter_files(base: Path):
    if not base.is_dir():
        return
    for path in base.rglob("*"):
        if path.is_file():
            yield path


def main() -> None:
    if RETENTION_DAYS <= 0:
        print("Data cleanup skipped: DATA_RETENTION_DAYS <= 0")
        return
    if not DB_PATH.is_file():
        print(f"Data cleanup skipped: DB not found at {DB_PATH}")
        return

    cutoff_dt = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
    cutoff_sql = cutoff_dt.strftime("%Y-%m-%d %H:%M:%S")
    cutoff_ts = cutoff_dt.timestamp()

    removed_uploads = 0
    removed_workflows = 0
    removed_orphans = 0

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        old_jobs = conn.execute(
            """
            SELECT id, input_image, workflow_file
            FROM jobs
            WHERE datetime(COALESCE(completed_at, created_at)) < datetime(?)
            """,
            (cutoff_sql,),
        ).fetchall()

        for job in old_jobs:
            if _remove_file(_safe_child(UPLOAD_DIR, job["input_image"])):
                removed_uploads += 1

            workflow_candidates = {job["workflow_file"], f"{job['id']}.json"}
            for workflow_file in workflow_candidates:
                if _remove_file(_safe_child(WORKFLOW_DIR, workflow_file)):
                    removed_workflows += 1

        if old_jobs:
            job_ids = [job["id"] for job in old_jobs]
            placeholders = ", ".join("?" for _ in job_ids)
            conn.execute(f"DELETE FROM jobs WHERE id IN ({placeholders})", job_ids)
            conn.commit()

            # The DB is small, but this returns disk to the OS after large cleanups.
            conn.execute("VACUUM")

        remaining_uploads = {
            row[0]
            for row in conn.execute(
                "SELECT DISTINCT input_image FROM jobs WHERE input_image IS NOT NULL AND input_image != ''"
            ).fetchall()
        }
        remaining_workflows = {
            row[0]
            for row in conn.execute(
                "SELECT DISTINCT workflow_file FROM jobs WHERE workflow_file IS NOT NULL AND workflow_file != ''"
            ).fetchall()
        }
        remaining_workflows.update(f"{row[0]}.json" for row in conn.execute("SELECT id FROM jobs").fetchall())

    for path in _iter_files(UPLOAD_DIR) or ():
        if path.stat().st_mtime < cutoff_ts and path.name not in remaining_uploads:
            path.unlink()
            removed_orphans += 1

    for path in _iter_files(WORKFLOW_DIR) or ():
        if path.stat().st_mtime < cutoff_ts and path.name not in remaining_workflows:
            path.unlink()
            removed_orphans += 1

    print(
        "Data cleanup complete: "
        f"retention_days={RETENTION_DAYS}, "
        f"deleted_jobs={len(old_jobs)}, "
        f"removed_uploads={removed_uploads}, "
        f"removed_workflows={removed_workflows}, "
        f"removed_orphans={removed_orphans}"
    )


if __name__ == "__main__":
    main()
