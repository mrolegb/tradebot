from __future__ import annotations

import sqlite3
from pathlib import Path

from app.storage.models import CREATE_TRADES_TABLE
from app.types import Order


class Database:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.execute(CREATE_TRADES_TABLE)
        self.connection.commit()

    def save_order(self, order: Order) -> None:
        self.connection.execute(
            "INSERT INTO trades(symbol, side, quantity, price, status, mode) VALUES (?, ?, ?, ?, ?, ?)",
            (order.symbol, order.side.value, order.quantity, order.price, order.status, order.mode),
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

