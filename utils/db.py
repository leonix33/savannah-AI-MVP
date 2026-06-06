import os
import sqlite3

try:
    from content_queue.models import normalize_queue_status
except ImportError:
    def normalize_queue_status(status: str) -> str:
        normalized = (status or "draft").strip().lower()
        return normalized if normalized in ("draft", "scheduled", "processing", "posted", "failed") else "draft"

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "history.db")


def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS outputs (
            id INTEGER PRIMARY KEY,
            task TEXT,
            platform TEXT,
            tone TEXT,
            input TEXT,
            output TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    _create_content_queue_table(c)
    conn.commit()
    _ensure_columns(c)
    conn.commit()
    conn.close()


def _ensure_columns(cursor):
    cursor.execute("PRAGMA table_info(outputs)")
    existing = {row[1] for row in cursor.fetchall()}
    if "platform" not in existing:
        cursor.execute("ALTER TABLE outputs ADD COLUMN platform TEXT")
    if "tone" not in existing:
        cursor.execute("ALTER TABLE outputs ADD COLUMN tone TEXT")


def _create_content_queue_table(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS content_queue (
            id INTEGER PRIMARY KEY,
            platform TEXT,
            caption TEXT,
            hashtags TEXT,
            media_type TEXT,
            media_name TEXT,
            status TEXT DEFAULT 'draft',
            scheduled_date TEXT,
            scheduled_time TEXT,
            timezone TEXT DEFAULT 'America/New_York',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    _ensure_content_queue_columns(cursor)


def _ensure_content_queue_columns(cursor) -> None:
    cursor.execute("PRAGMA table_info(content_queue)")
    existing = {row[1] for row in cursor.fetchall()}
    if "scheduled_date" not in existing:
        cursor.execute("ALTER TABLE content_queue ADD COLUMN scheduled_date TEXT")
    if "timezone" not in existing:
        cursor.execute("ALTER TABLE content_queue ADD COLUMN timezone TEXT DEFAULT 'America/New_York'")


def ensure_content_queue_table() -> None:
    conn = get_conn()
    c = conn.cursor()
    _create_content_queue_table(c)
    conn.commit()
    conn.close()


def save_result(task: str, platform: str, tone: str, input_text: str, output_text: str):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO outputs (task, platform, tone, input, output) VALUES (?, ?, ?, ?, ?)",
        (task, platform, tone, input_text, output_text),
    )
    conn.commit()
    conn.close()


def list_results(limit: int = 100):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT id, task, platform, tone, input, output, created_at FROM outputs ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    rows = c.fetchall()
    conn.close()
    return rows


def delete_result(result_id: int) -> None:
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM outputs WHERE id = ?", (result_id,))
    conn.commit()
    conn.close()


def add_queue_item(
    platform: str,
    caption: str,
    hashtags: str = "",
    media_type: str = "text",
    media_name: str | None = None,
    status: str = "draft",
    scheduled_date: str | None = None,
    scheduled_time: str | None = None,
    timezone: str = "America/New_York",
) -> int:
    conn = get_conn()
    c = conn.cursor()
    _create_content_queue_table(c)
    c.execute(
        """
        INSERT INTO content_queue
            (platform, caption, hashtags, media_type, media_name, status, scheduled_date, scheduled_time, timezone)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            platform,
            caption,
            hashtags,
            media_type,
            media_name,
            normalize_queue_status(status),
            scheduled_date,
            scheduled_time,
            timezone,
        ),
    )
    queue_id = c.lastrowid
    conn.commit()
    conn.close()
    return queue_id


def list_queue_items(limit: int = 100):
    conn = get_conn()
    c = conn.cursor()
    _create_content_queue_table(c)
    c.execute(
        """
        SELECT id, platform, caption, hashtags, media_type, media_name, status, scheduled_date, scheduled_time, timezone, created_at
        FROM content_queue
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = c.fetchall()
    conn.close()
    return rows


def update_queue_status(
    queue_id: int,
    status: str,
    scheduled_date: str | None = None,
    scheduled_time: str | None = None,
    timezone: str = "America/New_York",
) -> None:
    conn = get_conn()
    c = conn.cursor()
    _create_content_queue_table(c)
    c.execute(
        """
        UPDATE content_queue
        SET status = ?, scheduled_date = ?, scheduled_time = ?, timezone = ?
        WHERE id = ?
        """,
        (normalize_queue_status(status), scheduled_date, scheduled_time, timezone, queue_id),
    )
    conn.commit()
    conn.close()


def list_scheduled_queue_items(limit: int = 100):
    conn = get_conn()
    c = conn.cursor()
    _create_content_queue_table(c)
    c.execute(
        """
        SELECT id, platform, caption, hashtags, media_type, media_name, status, scheduled_date, scheduled_time, timezone, created_at
        FROM content_queue
        WHERE status IN ('scheduled', 'processing', 'posted', 'failed')
        ORDER BY scheduled_date IS NULL, scheduled_date ASC, scheduled_time IS NULL, scheduled_time ASC, id DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = c.fetchall()
    conn.close()
    return rows


def delete_queue_item(queue_id: int) -> None:
    conn = get_conn()
    c = conn.cursor()
    _create_content_queue_table(c)
    c.execute("DELETE FROM content_queue WHERE id = ?", (queue_id,))
    conn.commit()
    conn.close()
