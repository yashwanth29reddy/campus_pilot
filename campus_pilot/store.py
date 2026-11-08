"""SQLite-backed dedup + audit state.

We record every Gmail message we've already processed so re-runs only
consider new mail, and we remember which calendar event each message
produced (useful for rolling back / debugging).
"""

from __future__ import annotations

import datetime as dt
import sqlite3
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_DIR / "campus_pilot.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS processed (
    message_id       TEXT PRIMARY KEY,
    thread_id        TEXT,
    processed_at     TEXT NOT NULL,
    calendar_event_id TEXT,
    category         TEXT,
    event_name       TEXT,
    status           TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS seen_events (
    event_key        TEXT PRIMARY KEY,
    message_id       TEXT,
    created_at       TEXT NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA journal_mode = WAL;")
    con.executescript(SCHEMA)
    return con


def is_processed(message_id: str) -> bool:
    with _connect() as con:
        row = con.execute(
            "SELECT 1 FROM processed WHERE message_id = ?", (message_id,)
        ).fetchone()
    return row is not None


def mark_processed(
    message_id: str,
    thread_id: str,
    status: str,
    category: str = "",
    event_name: str = "",
    calendar_event_id: str = "",
) -> None:
    with _connect() as con:
        con.execute(
            """
            INSERT OR REPLACE INTO processed
            (message_id, thread_id, processed_at, calendar_event_id, category, event_name, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message_id,
                thread_id,
                dt.datetime.now().isoformat(timespec="seconds"),
                calendar_event_id,
                category,
                event_name,
                status,
            ),
        )


def event_key_exists(event_key: str) -> bool:
    with _connect() as con:
        row = con.execute(
            "SELECT 1 FROM seen_events WHERE event_key = ?", (event_key,)
        ).fetchone()
    return row is not None


def record_event(event_key: str, message_id: str) -> None:
    with _connect() as con:
        con.execute(
            "INSERT OR IGNORE INTO seen_events (event_key, message_id, created_at) VALUES (?, ?, ?)",
            (event_key, message_id, dt.datetime.now().isoformat(timespec="seconds")),
        )


def summary() -> list[tuple]:
    """Return (status, category, event_name, calendar_event_id, processed_at) rows."""
    with _connect() as con:
        return con.execute(
            "SELECT status, category, event_name, calendar_event_id, processed_at "
            "FROM processed ORDER BY processed_at DESC LIMIT 50"
        ).fetchall()