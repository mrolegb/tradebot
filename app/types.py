from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum


class SignalSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass(frozen=True)
class Candle:
    symbol: str
    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    @classmethod
    def from_sequence(cls, symbol: str, row: list | tuple) -> "Candle":
        timestamp = int(row[0])
        return cls(
            symbol=symbol,
            open_time=datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc),
            open=float(row[1]),
            high=float(row[2]),
            low=float(row[3]),
            close=float(row[4]),
            volume=float(row[5]),
        )


@dataclass(frozen=True)
class Signal:
    symbol: str
    side: SignalSide
    confidence: float
    reason: str
    price: float | None = None


@dataclass(frozen=True)
class PositionRequest:
    symbol: str
    side: SignalSide
    entry_price: float
    stop_loss_price: float
    account_equity: float


@dataclass(frozen=True)
class RiskDecision:
    allowed: bool
    quantity: float = 0.0
    reason: str = ""


@dataclass(frozen=True)
class Order:
    symbol: str
    side: SignalSide
    quantity: float
    price: float
    status: str
    mode: str
    exchange_order_id: str | None = None
