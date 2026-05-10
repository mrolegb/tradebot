from __future__ import annotations

import sqlite3
import json
from pathlib import Path

from app.storage.models import CREATE_POSITIONS_TABLE, CREATE_RUNTIME_STATE_TABLE, CREATE_TRADES_TABLE
from app.types import Order


class Database:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.execute(CREATE_TRADES_TABLE)
        self.connection.execute(CREATE_RUNTIME_STATE_TABLE)
        self.connection.execute(CREATE_POSITIONS_TABLE)
        self.connection.commit()

    def save_order(self, order: Order) -> None:
        self.connection.execute(
            "INSERT INTO trades(symbol, side, quantity, price, status, mode) VALUES (?, ?, ?, ?, ?, ?)",
            (order.symbol, order.side.value, order.quantity, order.price, order.status, order.mode),
        )
        self.connection.commit()

    def save_runtime_state(self, snapshot: dict) -> None:
        self.connection.execute(
            """
            INSERT INTO runtime_state(key, value, updated_at)
            VALUES ('snapshot', ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
            """,
            (json.dumps(snapshot, sort_keys=True),),
        )
        self.connection.commit()

    def load_runtime_state(self) -> dict:
        row = self.connection.execute("SELECT value FROM runtime_state WHERE key = 'snapshot'").fetchone()
        return json.loads(row[0]) if row else {}

    def upsert_position(self, symbol: str, side: str, quantity: float, entry_price: float, mode: str) -> None:
        self.connection.execute(
            """
            INSERT INTO positions(symbol, side, quantity, entry_price, mode)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                side = excluded.side,
                quantity = excluded.quantity,
                entry_price = excluded.entry_price,
                mode = excluded.mode,
                updated_at = CURRENT_TIMESTAMP
            """,
            (symbol, side, quantity, entry_price, mode),
        )
        self.connection.commit()

    def delete_position(self, symbol: str) -> None:
        self.connection.execute("DELETE FROM positions WHERE symbol = ?", (symbol,))
        self.connection.commit()

    def list_positions(self) -> list[dict]:
        rows = self.connection.execute(
            "SELECT symbol, side, quantity, entry_price, mode, opened_at, updated_at FROM positions ORDER BY symbol"
        ).fetchall()
        return [
            {
                "symbol": row[0],
                "side": row[1],
                "quantity": row[2],
                "entry_price": row[3],
                "mode": row[4],
                "opened_at": row[5],
                "updated_at": row[6],
            }
            for row in rows
        ]

    def close(self) -> None:
        self.connection.close()
