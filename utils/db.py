import os
import sqlite3

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
