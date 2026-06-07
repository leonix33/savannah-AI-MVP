import os
import sqlite3

try:
    from content_queue.models import normalize_queue_status
except ImportError:
    def normalize_queue_status(status: str) -> str:
        normalized = (status or "queued").strip().lower()
        if normalized in ("draft", "processing"):
            return "queued" if normalized == "draft" else "publishing"
        return normalized if normalized in ("queued", "scheduled", "publishing", "posted", "failed") else "queued"

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
    _create_facebook_comments_table(c)
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
            tone TEXT,
            content TEXT,
            caption TEXT,
            hashtags TEXT,
            media_type TEXT,
            media_name TEXT,
            status TEXT DEFAULT 'queued',
            scheduled_date TEXT,
            scheduled_time TEXT,
            timezone TEXT DEFAULT 'America/New_York',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    _ensure_content_queue_columns(cursor)
    _create_publishing_logs_table(cursor)


def _create_publishing_logs_table(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS publishing_logs (
            id INTEGER PRIMARY KEY,
            queue_item_id INTEGER,
            platform TEXT,
            status TEXT,
            message TEXT,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def _create_facebook_comments_table(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS facebook_comments (
            id INTEGER PRIMARY KEY,
            facebook_post_id TEXT,
            facebook_comment_id TEXT,
            source_post TEXT,
            commenter_name TEXT,
            comment_text TEXT,
            classification TEXT,
            suggested_reply TEXT,
            status TEXT DEFAULT 'new',
            last_reply_attempt_at TEXT,
            reply_status TEXT,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    _ensure_facebook_comment_columns(cursor)
    _create_facebook_comment_reply_logs_table(cursor)


def _create_facebook_comment_reply_logs_table(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS facebook_comment_reply_logs (
            id INTEGER PRIMARY KEY,
            comment_id INTEGER,
            status TEXT,
            reply_text TEXT,
            message TEXT,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def _ensure_facebook_comment_columns(cursor) -> None:
    cursor.execute("PRAGMA table_info(facebook_comments)")
    existing = {row[1] for row in cursor.fetchall()}
    columns = {
        "facebook_post_id": "TEXT",
        "facebook_comment_id": "TEXT",
        "source_post": "TEXT",
        "commenter_name": "TEXT",
        "comment_text": "TEXT",
        "classification": "TEXT",
        "suggested_reply": "TEXT",
        "status": "TEXT DEFAULT 'new'",
        "last_reply_attempt_at": "TEXT",
        "reply_status": "TEXT",
        "error_message": "TEXT",
        "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    }
    for column, column_type in columns.items():
        if column not in existing:
            cursor.execute(f"ALTER TABLE facebook_comments ADD COLUMN {column} {column_type}")


def _ensure_content_queue_columns(cursor) -> None:
    cursor.execute("PRAGMA table_info(content_queue)")
    existing = {row[1] for row in cursor.fetchall()}
    if "tone" not in existing:
        cursor.execute("ALTER TABLE content_queue ADD COLUMN tone TEXT")
    if "content" not in existing:
        cursor.execute("ALTER TABLE content_queue ADD COLUMN content TEXT")
    if "scheduled_date" not in existing:
        cursor.execute("ALTER TABLE content_queue ADD COLUMN scheduled_date TEXT")
    if "timezone" not in existing:
        cursor.execute("ALTER TABLE content_queue ADD COLUMN timezone TEXT DEFAULT 'America/New_York'")
    cursor.execute("UPDATE content_queue SET status = 'queued' WHERE status IS NULL OR status = 'draft'")
    cursor.execute("UPDATE content_queue SET status = 'publishing' WHERE status = 'processing'")


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
    content: str = "",
    hashtags: str = "",
    tone: str = "",
    media_type: str = "text",
    media_name: str | None = None,
    status: str = "queued",
    created_at: str | None = None,
    scheduled_date: str | None = None,
    scheduled_time: str | None = None,
    timezone: str | None = "America/New_York",
    caption: str | None = None,
) -> int:
    conn = get_conn()
    c = conn.cursor()
    _create_content_queue_table(c)
    queue_content = content or caption or ""
    columns = [
        "platform",
        "tone",
        "content",
        "caption",
        "hashtags",
        "media_type",
        "media_name",
        "status",
        "scheduled_date",
        "scheduled_time",
        "timezone",
    ]
    values = [
        platform,
        tone,
        queue_content,
        queue_content,
        hashtags,
        media_type,
        media_name,
        normalize_queue_status(status),
        scheduled_date,
        scheduled_time,
        timezone,
    ]
    if created_at:
        columns.append("created_at")
        values.append(created_at)

    placeholders = ", ".join("?" for _ in columns)
    c.execute(
        f"INSERT INTO content_queue ({', '.join(columns)}) VALUES ({placeholders})",
        values,
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
        SELECT id, platform, tone, COALESCE(content, caption) AS content, hashtags, media_type, media_name, status, scheduled_date, scheduled_time, timezone, created_at
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
    timezone: str | None = None,
) -> None:
    conn = get_conn()
    c = conn.cursor()
    _create_content_queue_table(c)
    c.execute(
        """
        UPDATE content_queue
        SET status = ?,
            scheduled_date = COALESCE(?, scheduled_date),
            scheduled_time = COALESCE(?, scheduled_time),
            timezone = COALESCE(?, timezone)
        WHERE id = ?
        """,
        (normalize_queue_status(status), scheduled_date, scheduled_time, timezone, queue_id),
    )
    conn.commit()
    conn.close()


def update_queue_item_caption(queue_id: int, caption: str, hashtags: str = "") -> None:
    conn = get_conn()
    c = conn.cursor()
    _create_content_queue_table(c)
    c.execute(
        "UPDATE content_queue SET content = ?, caption = ?, hashtags = ? WHERE id = ?",
        (caption, caption, hashtags, queue_id),
    )
    conn.commit()
    conn.close()


def list_scheduled_queue_items(limit: int = 100):
    conn = get_conn()
    c = conn.cursor()
    _create_content_queue_table(c)
    c.execute(
        """
        SELECT id, platform, tone, COALESCE(content, caption) AS content, hashtags, media_type, media_name, status, scheduled_date, scheduled_time, timezone, created_at
        FROM content_queue
        WHERE status IN ('scheduled', 'publishing', 'posted', 'failed')
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


def add_publishing_log(
    queue_item_id: int,
    platform: str,
    status: str,
    message: str = "",
    error_message: str = "",
) -> int:
    conn = get_conn()
    c = conn.cursor()
    _create_publishing_logs_table(c)
    c.execute(
        """
        INSERT INTO publishing_logs (queue_item_id, platform, status, message, error_message)
        VALUES (?, ?, ?, ?, ?)
        """,
        (queue_item_id, platform, status, message, error_message),
    )
    log_id = c.lastrowid
    conn.commit()
    conn.close()
    return log_id


def list_publishing_logs(limit: int = 20):
    conn = get_conn()
    c = conn.cursor()
    _create_publishing_logs_table(c)
    c.execute(
        """
        SELECT id, queue_item_id, platform, status, message, error_message, created_at
        FROM publishing_logs
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = c.fetchall()
    conn.close()
    return rows


def ensure_facebook_comments_table() -> None:
    conn = get_conn()
    c = conn.cursor()
    _create_facebook_comments_table(c)
    conn.commit()
    conn.close()


def add_facebook_comment(
    source_post: str,
    commenter_name: str,
    comment_text: str,
    status: str = "new",
    facebook_post_id: str = "",
    facebook_comment_id: str = "",
) -> int:
    conn = get_conn()
    c = conn.cursor()
    _create_facebook_comments_table(c)
    if facebook_comment_id:
        c.execute("SELECT id FROM facebook_comments WHERE facebook_comment_id = ?", (facebook_comment_id,))
        existing = c.fetchone()
        if existing:
            conn.close()
            return existing[0]
    c.execute(
        """
        INSERT INTO facebook_comments (
            facebook_post_id, facebook_comment_id, source_post, commenter_name, comment_text, status
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (facebook_post_id, facebook_comment_id, source_post, commenter_name, comment_text, status),
    )
    comment_id = c.lastrowid
    conn.commit()
    conn.close()
    return comment_id


def list_facebook_comments(limit: int = 100):
    conn = get_conn()
    c = conn.cursor()
    _create_facebook_comments_table(c)
    c.execute(
        """
        SELECT id, source_post, commenter_name, comment_text, classification, suggested_reply,
               status, last_reply_attempt_at, reply_status, error_message, created_at, updated_at,
               facebook_post_id, facebook_comment_id
        FROM facebook_comments
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = c.fetchall()
    conn.close()
    return rows


def update_facebook_comment_classification(comment_id: int, classification: str) -> None:
    conn = get_conn()
    c = conn.cursor()
    _create_facebook_comments_table(c)
    c.execute(
        """
        UPDATE facebook_comments
        SET classification = ?, status = 'classified', updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (classification, comment_id),
    )
    conn.commit()
    conn.close()


def update_facebook_comment_reply(comment_id: int, suggested_reply: str, status: str = "reply_drafted") -> None:
    conn = get_conn()
    c = conn.cursor()
    _create_facebook_comments_table(c)
    c.execute(
        """
        UPDATE facebook_comments
        SET suggested_reply = ?, status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (suggested_reply, status, comment_id),
    )
    conn.commit()
    conn.close()


def update_facebook_comment_reply_attempt(
    comment_id: int,
    status: str,
    message: str = "",
    error_message: str = "",
) -> None:
    conn = get_conn()
    c = conn.cursor()
    _create_facebook_comments_table(c)
    c.execute(
        """
        UPDATE facebook_comments
        SET status = ?,
            reply_status = ?,
            error_message = ?,
            last_reply_attempt_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (status, status, error_message or message, comment_id),
    )
    conn.commit()
    conn.close()


def add_facebook_comment_reply_log(
    comment_id: int,
    status: str,
    reply_text: str,
    message: str = "",
    error_message: str = "",
) -> int:
    conn = get_conn()
    c = conn.cursor()
    _create_facebook_comment_reply_logs_table(c)
    c.execute(
        """
        INSERT INTO facebook_comment_reply_logs (comment_id, status, reply_text, message, error_message)
        VALUES (?, ?, ?, ?, ?)
        """,
        (comment_id, status, reply_text, message, error_message),
    )
    log_id = c.lastrowid
    conn.commit()
    conn.close()
    return log_id


def get_analytics_summary() -> dict:
    conn = get_conn()
    c = conn.cursor()
    _create_content_queue_table(c)
    _create_facebook_comments_table(c)
    c.execute("SELECT COUNT(*) FROM outputs")
    total_generated_posts = c.fetchone()[0]
    c.execute("SELECT status, COUNT(*) FROM content_queue GROUP BY status")
    queue_status_counts = {status or "unknown": count for status, count in c.fetchall()}
    c.execute("SELECT status, COUNT(*) FROM publishing_logs GROUP BY status")
    publish_status_counts = {status or "unknown": count for status, count in c.fetchall()}
    c.execute("SELECT COUNT(*) FROM facebook_comments")
    total_comments_ingested = c.fetchone()[0]
    c.execute(
        """
        SELECT COALESCE(classification, 'unclassified'), COUNT(*)
        FROM facebook_comments
        GROUP BY COALESCE(classification, 'unclassified')
        """
    )
    comments_by_category = {category: count for category, count in c.fetchall()}
    c.execute("SELECT status, COUNT(*) FROM facebook_comments GROUP BY status")
    comment_status_counts = {status or "unknown": count for status, count in c.fetchall()}
    c.execute(
        """
        SELECT COUNT(*)
        FROM facebook_comments
        WHERE status IN ('new', 'classified', 'reply_drafted', 'failed')
           OR classification = 'service_issue'
        """
    )
    comments_needing_human_review = c.fetchone()[0]
    conn.close()

    return {
        "total_generated_posts": total_generated_posts,
        "queued_posts": queue_status_counts.get("queued", 0),
        "scheduled_posts": queue_status_counts.get("scheduled", 0),
        "simulated_published_posts": queue_status_counts.get("posted", 0)
        or publish_status_counts.get("posted", 0),
        "total_comments_ingested": total_comments_ingested,
        "comments_by_category": comments_by_category,
        "replies_drafted": comment_status_counts.get("reply_drafted", 0),
        "replies_approved": comment_status_counts.get("approved", 0),
        "replies_simulated_posted": comment_status_counts.get("simulated_replied", 0),
        "comments_needing_human_review": comments_needing_human_review,
        "queue_status_counts": queue_status_counts,
        "comment_status_counts": comment_status_counts,
    }
