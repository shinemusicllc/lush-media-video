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
                workflow_file TEXT,
                source        TEXT    NOT NULL DEFAULT 'web',
                source_user_id TEXT,
                telegram_chat_id TEXT,
                visibility    TEXT    NOT NULL DEFAULT 'web',
                telegram_notified_at TIMESTAMP,
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
        if not await _column_exists(conn, "jobs", "workflow_file"):
            await conn.execute("ALTER TABLE jobs ADD COLUMN workflow_file TEXT")
        if not await _column_exists(conn, "jobs", "source"):
            await conn.execute("ALTER TABLE jobs ADD COLUMN source TEXT DEFAULT 'web'")
        if not await _column_exists(conn, "jobs", "source_user_id"):
            await conn.execute("ALTER TABLE jobs ADD COLUMN source_user_id TEXT")
        if not await _column_exists(conn, "jobs", "telegram_chat_id"):
            await conn.execute("ALTER TABLE jobs ADD COLUMN telegram_chat_id TEXT")
        if not await _column_exists(conn, "jobs", "visibility"):
            await conn.execute("ALTER TABLE jobs ADD COLUMN visibility TEXT DEFAULT 'web'")
        if not await _column_exists(conn, "jobs", "telegram_notified_at"):
            await conn.execute("ALTER TABLE jobs ADD COLUMN telegram_notified_at TIMESTAMP")

        # Keep old rows searchable by the new job_name field.
        await conn.execute(
            "UPDATE jobs SET job_name = COALESCE(job_name, video_name) WHERE job_name IS NULL"
        )
        await conn.execute("UPDATE jobs SET source = 'web' WHERE source IS NULL")
        await conn.execute("UPDATE jobs SET visibility = 'web' WHERE visibility IS NULL")
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
            "SELECT id, username, role, created_at FROM users WHERE role != 'telegram' ORDER BY id"
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
    workflow_file: str | None = None,
    source: str = "web",
    source_user_id: str | None = None,
    telegram_chat_id: str | None = None,
    visibility: str = "web",
):
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            """
            INSERT INTO jobs (
                id, user_id, username, input_image, job_name, video_name, workflow_name,
                workflow_file, source, source_user_id, telegram_chat_id, visibility
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                user_id,
                username,
                input_image,
                job_name,
                job_name,
                workflow_name,
                workflow_file,
                source,
                source_user_id,
                telegram_chat_id,
                visibility,
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


async def get_user_jobs(
    username: str,
    limit: int | None = 50,
    visibility: str | None = None,
) -> list:
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        where = "WHERE username = ?"
        params: list = [username]
        if visibility is not None:
            where += " AND visibility = ?"
            params.append(visibility)
        if limit is None:
            query = f"SELECT * FROM jobs {where} ORDER BY created_at DESC"
        else:
            query = f"SELECT * FROM jobs {where} ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
        async with conn.execute(query, tuple(params)) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_all_jobs(limit: int | None = 100, visibility: str | None = None) -> list:
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        where = ""
        params: list = []
        if visibility is not None:
            where = "WHERE visibility = ?"
            params.append(visibility)
        if limit is None:
            query = f"SELECT * FROM jobs {where} ORDER BY created_at DESC"
        else:
            query = f"SELECT * FROM jobs {where} ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
        async with conn.execute(query, tuple(params)) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_pending_telegram_notifications(limit: int = 20) -> list:
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            """
            SELECT *
            FROM jobs
            WHERE source = 'telegram'
              AND telegram_notified_at IS NULL
              AND status IN ('done', 'error', 'cancelled')
            ORDER BY completed_at ASC, created_at ASC
            LIMIT ?
            """,
            (limit,),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_jobs_by_ids(job_ids: list[str]) -> list:
    if not job_ids:
        return []

    placeholders = ", ".join("?" for _ in job_ids)
    query = f"SELECT * FROM jobs WHERE id IN ({placeholders})"
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(query, tuple(job_ids)) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def delete_job(job_id: str):
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        await conn.commit()


async def delete_jobs_by_ids(job_ids: list[str]) -> int:
    if not job_ids:
        return 0

    placeholders = ", ".join("?" for _ in job_ids)
    query = f"DELETE FROM jobs WHERE id IN ({placeholders})"
    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute(query, tuple(job_ids))
        await conn.commit()
        return cur.rowcount


async def clear_jobs_for_user(username: str, visibility: str | None = None) -> int:
    async with aiosqlite.connect(DB_PATH) as conn:
        if visibility is None:
            cur = await conn.execute("DELETE FROM jobs WHERE username = ?", (username,))
        else:
            cur = await conn.execute(
                "DELETE FROM jobs WHERE username = ? AND visibility = ?",
                (username, visibility),
            )
        await conn.commit()
        return cur.rowcount


async def clear_all_jobs(visibility: str | None = None) -> int:
    async with aiosqlite.connect(DB_PATH) as conn:
        if visibility is None:
            cur = await conn.execute("DELETE FROM jobs")
        else:
            cur = await conn.execute(
                "DELETE FROM jobs WHERE visibility = ?",
                (visibility,),
            )
        await conn.commit()
        return cur.rowcount
