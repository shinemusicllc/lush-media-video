"""SQLite database — users + jobs."""

import aiosqlite
from config import DB_PATH


async def _column_exists(conn: aiosqlite.Connection, table: str, column: str) -> bool:
    async with conn.execute(f"PRAGMA table_info({table})") as cur:
        rows = await cur.fetchall()
    return any(r[1] == column for r in rows)


async def init_db():
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT    UNIQUE NOT NULL,
                password_hash TEXT    NOT NULL,
                role          TEXT    NOT NULL DEFAULT 'user',
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.execute("""
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
                output_info   TEXT,
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at  TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        # Backward-compatible migration for existing DBs.
        if not await _column_exists(conn, "jobs", "job_name"):
            await conn.execute("ALTER TABLE jobs ADD COLUMN job_name TEXT")
        if not await _column_exists(conn, "jobs", "video_name"):
            await conn.execute("ALTER TABLE jobs ADD COLUMN video_name TEXT")
        if not await _column_exists(conn, "jobs", "workflow_name"):
            await conn.execute("ALTER TABLE jobs ADD COLUMN workflow_name TEXT")

        # Keep old rows searchable by the new job_name field.
        await conn.execute(
            "UPDATE jobs SET job_name = COALESCE(job_name, video_name) WHERE job_name IS NULL"
        )
        await conn.commit()


# ── Users ──────────────────────────────────────────────────


async def get_user(username: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def create_user(username: str, password_hash: str, role: str = "user") -> int:
    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, password_hash, role),
        )
        await conn.commit()
        return cur.lastrowid


async def list_users() -> list:
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT id, username, role, created_at FROM users ORDER BY id"
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


# ── Jobs ───────────────────────────────────────────────────


async def create_job(
    job_id: str,
    user_id: int,
    username: str,
    input_image: str,
    job_name: str | None = None,
    workflow_name: str | None = None,
):
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            """
            INSERT INTO jobs (
                id, user_id, username, input_image, job_name, video_name, workflow_name
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                user_id,
                username,
                input_image,
                job_name,
                job_name,
                workflow_name,
            ),
        )
        await conn.commit()


async def update_job(job_id: str, **kwargs):
    if not kwargs:
        return
    cols = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values()) + [job_id]
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(f"UPDATE jobs SET {cols} WHERE id = ?", vals)
        await conn.commit()


async def get_job(job_id: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_user_jobs(username: str, limit: int = 50) -> list:
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT * FROM jobs WHERE username = ? ORDER BY created_at DESC LIMIT ?",
            (username, limit),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_all_jobs(limit: int = 100) -> list:
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def delete_job(job_id: str):
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        await conn.commit()
