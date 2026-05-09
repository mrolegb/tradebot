from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_SQLITE_PATH = Path("data/tradebot.sqlite3")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RuntimeStorage:
    """Small SQLite-backed store for runtime snapshots and audit events.

    The runtime state still lives in memory while the API process is running,
    but every state transition is persisted so a restart can restore the last
    known operator selections and status.
    """

    def __init__(self, sqlite_path: str | Path = DEFAULT_SQLITE_PATH) -> None:
        self.sqlite_path = Path(sqlite_path)
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.sqlite_path)

    def _init_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS runtime_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    snapshot_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS runtime_audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    snapshot_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def load_snapshot(self) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT snapshot_json FROM runtime_state WHERE id = 1"
            ).fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    def save_snapshot(self, snapshot: dict[str, Any], *, action: str) -> None:
        cleaned = _to_jsonable(snapshot)
        now = utc_now()
        payload = json.dumps(cleaned, sort_keys=True)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO runtime_state (id, snapshot_json, updated_at)
                VALUES (1, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    snapshot_json = excluded.snapshot_json,
                    updated_at = excluded.updated_at
                """,
                (payload, now),
            )
            connection.execute(
                """
                INSERT INTO runtime_audit_log (action, snapshot_json, created_at)
                VALUES (?, ?, ?)
                """,
                (action, payload, now),
            )

    def audit_events(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, action, snapshot_json, created_at
                FROM runtime_audit_log
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "id": row[0],
                "action": row[1],
                "snapshot": json.loads(row[2]),
                "created_at": row[3],
            }
            for row in rows
        ]


def _to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _to_jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_to_jsonable(item) for item in value]
    return value
