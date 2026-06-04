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
            input TEXT,
            output TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


def save_result(task: str, input_text: str, output_text: str):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO outputs (task, input, output) VALUES (?, ?, ?)",
        (task, input_text, output_text),
    )
    conn.commit()
    conn.close()


def list_results(limit: int = 100):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT id, task, input, output, created_at FROM outputs ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    rows = c.fetchall()
    conn.close()
    return rows
