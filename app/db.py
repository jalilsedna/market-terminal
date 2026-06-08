"""SQLite persistence (ROADMAP C2).

A tiny, dependency-free storage layer (stdlib `sqlite3`) that survives process
restarts — and survives Railway redeploys when `db_path` points at a mounted
volume. Backs the custom watchlist (C6) and a generic time-series **history**
table (groundwork for C5 charts/alerts), plus a key/value store.

Deliberately connect-per-call: our write volume is tiny (a few watchlist edits, a
periodic snapshot), so a fresh connection each time avoids cross-thread/stale
state with no measurable cost. WAL mode keeps reads concurrent with the
pre-cache warmer's writes. No OpenBB / heavy deps — unit-tested in CI.
"""

from __future__ import annotations

import contextlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from config import get_settings

_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
    """CREATE TABLE IF NOT EXISTS watchlist (
           id TEXT PRIMARY KEY, asset TEXT NOT NULL, symbol TEXT NOT NULL,
           label TEXT, added_at TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS snapshots (
           series TEXT NOT NULL, ts TEXT NOT NULL, value TEXT NOT NULL)""",
    "CREATE INDEX IF NOT EXISTS ix_snap_series_ts ON snapshots (series, ts)",
    """CREATE TABLE IF NOT EXISTS users (
           username TEXT PRIMARY KEY, pw_hash TEXT NOT NULL,
           role TEXT NOT NULL DEFAULT 'user', disabled INTEGER NOT NULL DEFAULT 0,
           created_at TEXT NOT NULL)""",
)


@contextlib.contextmanager
def _db():
    path = Path(get_settings().db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        for stmt in _SCHEMA:
            conn.execute(stmt)
        conn.row_factory = sqlite3.Row
        yield conn
        conn.commit()
    finally:
        conn.close()


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


# --- key/value ------------------------------------------------------------- #
def kv_get(key: str, default: Any = None) -> Any:
    with _db() as conn:
        row = conn.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
    return json.loads(row["value"]) if row else default


def kv_set(key: str, value: Any) -> None:
    with _db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO kv (key, value) VALUES (?, ?)", (key, json.dumps(value))
        )


# --- watchlist (backs services/custom_store) ------------------------------- #
def watchlist_list() -> list[dict]:
    with _db() as conn:
        rows = conn.execute(
            "SELECT id, asset, symbol, label FROM watchlist ORDER BY added_at"
        ).fetchall()
    return [dict(r) for r in rows]


def watchlist_add(item_id: str, asset: str, symbol: str, label: str) -> None:
    with _db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO watchlist (id, asset, symbol, label, added_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (item_id, asset, symbol, label, _now()),
        )


def watchlist_remove(item_id: str) -> bool:
    with _db() as conn:
        cur = conn.execute("DELETE FROM watchlist WHERE id=?", (item_id,))
    return cur.rowcount > 0


# --- history snapshots (groundwork for C5) --------------------------------- #
def record_snapshot(series: str, value: Any, ts: str | None = None) -> None:
    """Append a timestamped value to a named series (e.g. 'vol:GC')."""
    with _db() as conn:
        conn.execute(
            "INSERT INTO snapshots (series, ts, value) VALUES (?, ?, ?)",
            (series, ts or _now(), json.dumps(value)),
        )


def history(series: str, limit: int = 365) -> list[dict]:
    """Most-recent-first snapshots for a series: [{ts, value}, …]."""
    with _db() as conn:
        rows = conn.execute(
            "SELECT ts, value FROM snapshots WHERE series=? ORDER BY ts DESC LIMIT ?",
            (series, limit),
        ).fetchall()
    return [{"ts": r["ts"], "value": json.loads(r["value"])} for r in rows]


def record_snapshot_daily(series: str, value: Any, today: str | None = None) -> bool:
    """Record a snapshot only if `series` has none for today (UTC date) — so the
    pre-cache warmer (every 30 min) yields one point per day. True if recorded."""
    day = today or datetime.now(UTC).date().isoformat()
    ts = f"{day}T00:00:00+00:00" if today else _now()
    with _db() as conn:
        existing = conn.execute(
            "SELECT 1 FROM snapshots WHERE series=? AND substr(ts, 1, 10)=? LIMIT 1",
            (series, day),
        ).fetchone()
        if existing:
            return False
        conn.execute(
            "INSERT INTO snapshots (series, ts, value) VALUES (?, ?, ?)",
            (series, ts, json.dumps(value)),
        )
    return True


def series_list() -> list[str]:
    """Distinct snapshot series names recorded so far."""
    with _db() as conn:
        rows = conn.execute("SELECT DISTINCT series FROM snapshots ORDER BY series").fetchall()
    return [r["series"] for r in rows]


# --- users (ROADMAP F2) ---------------------------------------------------- #
def user_create(username: str, pw_hash: str, role: str = "user") -> bool:
    """Insert a user. False if the username already exists."""
    with _db() as conn:
        try:
            conn.execute(
                "INSERT INTO users (username, pw_hash, role, disabled, created_at) "
                "VALUES (?, ?, ?, 0, ?)",
                (username, pw_hash, role, _now()),
            )
        except sqlite3.IntegrityError:
            return False
    return True


def user_get(username: str) -> dict | None:
    with _db() as conn:
        row = conn.execute(
            "SELECT username, pw_hash, role, disabled FROM users WHERE username=?", (username,)
        ).fetchone()
    return dict(row) if row else None


def user_list() -> list[dict]:
    """All users (no password hashes)."""
    with _db() as conn:
        rows = conn.execute(
            "SELECT username, role, disabled, created_at FROM users ORDER BY created_at"
        ).fetchall()
    return [dict(r) for r in rows]


def user_set_disabled(username: str, disabled: bool) -> bool:
    with _db() as conn:
        cur = conn.execute(
            "UPDATE users SET disabled=? WHERE username=?", (1 if disabled else 0, username)
        )
    return cur.rowcount > 0
