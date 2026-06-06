"""
database.py — SQLite setup and query helpers for AI Work Report Generator
Creates and manages the work_activity.db SQLite database.
"""

import sqlite3
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "work_activity.db")


def get_connection() -> sqlite3.Connection:
    """Return a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # allows dict-like row access
    return conn


def init_db():
    """Create tables if they don't already exist."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activity_logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT    NOT NULL,
            event_type  TEXT    NOT NULL,
            details     TEXT    NOT NULL,
            category    TEXT    DEFAULT 'Uncategorised'
        )
    """)

    # Tracker state table — stores pause/resume state
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tracker_state (
            key     TEXT PRIMARY KEY,
            value   TEXT NOT NULL
        )
    """)

    # Seed default tracker state if not present
    cursor.execute("""
        INSERT OR IGNORE INTO tracker_state (key, value)
        VALUES ('status', 'stopped')
    """)

    conn.commit()
    conn.close()
    print(f"[DB] Database initialised at: {DB_PATH}")


def log_event(event_type: str, details: str, category: str = "Uncategorised"):
    """
    Insert a single activity event into activity_logs.

    Args:
        event_type: 'file_change' | 'active_app' | 'manual'
        details:    Human-readable description of the event
        category:   One of Coding / Research / Meeting / Debugging /
                    Documentation / Code Review / Uncategorised
    """
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO activity_logs (timestamp, event_type, details, category)
        VALUES (?, ?, ?, ?)
        """,
        (datetime.now().isoformat(), event_type, details, category),
    )
    conn.commit()
    conn.close()


def get_today_logs() -> list[dict]:
    """Return all activity logs for today as a list of dicts."""
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT id, timestamp, event_type, details, category
        FROM activity_logs
        WHERE timestamp LIKE ?
        ORDER BY timestamp ASC
        """,
        (f"{today}%",),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_logs_for_range(start_date: str, end_date: str) -> list[dict]:
    """
    Return activity logs between start_date and end_date (inclusive).
    Dates should be in 'YYYY-MM-DD' format.
    """
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT id, timestamp, event_type, details, category
        FROM activity_logs
        WHERE date(timestamp) BETWEEN ? AND ?
        ORDER BY timestamp ASC
        """,
        (start_date, end_date),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_week_logs() -> list[dict]:
    """Return activity logs for the past 7 days."""
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d")
    return get_logs_for_range(start, end)


def get_all_logs(limit: int = 200) -> list[dict]:
    """Return the most recent N activity log entries."""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT id, timestamp, event_type, details, category
        FROM activity_logs
        ORDER BY timestamp DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def set_tracker_state(value: str):
    """Set tracker status: 'running' | 'paused' | 'stopped'."""
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO tracker_state (key, value) VALUES ('status', ?)",
        (value,),
    )
    conn.commit()
    conn.close()


def get_tracker_state() -> str:
    """Get current tracker status."""
    conn = get_connection()
    row = conn.execute(
        "SELECT value FROM tracker_state WHERE key = 'status'"
    ).fetchone()
    conn.close()
    return row["value"] if row else "stopped"


def clear_today_logs():
    """Delete all logs for today — useful for testing."""
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_connection()
    conn.execute(
        "DELETE FROM activity_logs WHERE timestamp LIKE ?",
        (f"{today}%",),
    )
    conn.commit()
    conn.close()
    print(f"[DB] Cleared all logs for {today}.")


if __name__ == "__main__":
    init_db()
