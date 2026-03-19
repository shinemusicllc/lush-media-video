import argparse
import json
import os
import shutil
import sqlite3
from pathlib import Path

import bcrypt
import httpx


def ensure_dirs(data_dir: Path) -> tuple[Path, Path, Path]:
    uploads_dir = data_dir / "uploads"
    workflows_dir = data_dir / "workflows"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    workflows_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "comfybot.db", uploads_dir, workflows_dir


def init_schema(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT    UNIQUE NOT NULL,
                password_hash TEXT    NOT NULL,
                role          TEXT    NOT NULL DEFAULT 'user',
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id            TEXT PRIMARY KEY,
                user_id       INTEGER NOT NULL,
                username      TEXT    NOT NULL,
                server_id     TEXT,
                prompt_id     TEXT,
                status        TEXT    NOT NULL DEFAULT 'queued',
                progress      INTEGER DEFAULT 0,
                error_msg     TEXT,
                input_image   TEXT    NOT NULL,
                job_name      TEXT,
                video_name    TEXT,
                workflow_name TEXT,
                workflow_file TEXT,
                output_info   TEXT,
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at  TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def backup_existing(data_dir: Path) -> None:
    if not data_dir.exists():
        return
    backup_dir = data_dir.parent / f"data-backup-before-live-import"
    if backup_dir.exists():
        shutil.rmtree(backup_dir)
    shutil.copytree(data_dir, backup_dir)


def login(base_url: str, username: str, password: str) -> str:
    with httpx.Client(base_url=base_url, timeout=60) as client:
        resp = client.post("/api/auth/login", json={"username": username, "password": password})
        resp.raise_for_status()
        payload = resp.json()
        return payload["access_token"]


def fetch_json(client: httpx.Client, path: str) -> dict | list:
    resp = client.get(path)
    resp.raise_for_status()
    return resp.json()


def download_file(client: httpx.Client, path: str, dest: Path) -> bool:
    resp = client.get(path)
    if resp.status_code == 404:
        return False
    resp.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(resp.content)
    return True


def map_status(status: str) -> str:
    if status in {"running", "queued"}:
        return "cancelled"
    return status


def resolve_password_hash(admin_password: str, admin_password_hash: str | None) -> str:
    if admin_password_hash:
        return admin_password_hash
    return bcrypt.hashpw(admin_password.encode(), bcrypt.gensalt()).decode()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--admin-username", required=True)
    parser.add_argument("--admin-password", required=True)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--admin-password-hash")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    db_path, uploads_dir, workflows_dir = ensure_dirs(data_dir)
    backup_existing(data_dir)
    init_schema(db_path)
    password_hash = resolve_password_hash(args.admin_password, args.admin_password_hash)

    token = login(args.base_url.rstrip("/"), args.admin_username, args.admin_password)
    headers = {"Authorization": f"Bearer {token}"}

    with httpx.Client(base_url=args.base_url.rstrip("/"), headers=headers, timeout=120) as client:
        users = fetch_json(client, "/api/auth/users")
        jobs = fetch_json(client, "/api/jobs")

        conn = sqlite3.connect(db_path)
        try:
            conn.execute("DELETE FROM jobs")
            conn.execute("DELETE FROM users")
            conn.execute(
                "INSERT INTO users (id, username, password_hash, role, created_at) VALUES (?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP))",
                (1, args.admin_username, password_hash, "admin", None),
            )

            imported_jobs = 0
            for job in jobs:
                full_job = fetch_json(client, f"/api/jobs/{job['id']}")

                input_name = full_job["input_image"]
                download_file(client, f"/api/jobs/{job['id']}/thumbnail", uploads_dir / input_name)

                workflow_file = full_job.get("workflow_file")
                if workflow_file:
                    download_file(client, f"/api/jobs/{job['id']}/workflow", workflows_dir / workflow_file)

                conn.execute(
                    """
                    INSERT OR REPLACE INTO jobs (
                        id, user_id, username, server_id, prompt_id, status, progress, error_msg,
                        input_image, job_name, video_name, workflow_name, workflow_file,
                        output_info, created_at, completed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        full_job["id"],
                        1,
                        full_job["username"],
                        full_job.get("server_id"),
                        full_job.get("prompt_id"),
                        map_status(full_job.get("status", "queued")),
                        full_job.get("progress", 0),
                        full_job.get("error_msg"),
                        full_job["input_image"],
                        full_job.get("job_name"),
                        full_job.get("video_name"),
                        full_job.get("workflow_name"),
                        full_job.get("workflow_file"),
                        full_job.get("output_info"),
                        full_job.get("created_at"),
                        full_job.get("completed_at"),
                    ),
                )
                imported_jobs += 1

            conn.commit()
        finally:
            conn.close()

    print(json.dumps({"imported_jobs": imported_jobs, "users_seen": len(users)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
