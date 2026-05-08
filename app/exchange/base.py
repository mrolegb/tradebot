from __future__ import annotations

from typing import Protocol

from app.types import Candle


class MarketDataClient(Protocol):
    async def fetch_klines(self, symbol: str, interval: str, limit: int = 200) -> list[Candle]:
        """Fetch candles using the exchange-compatible kline contract."""

    async def account(self) -> dict:
        """Return account state."""

    async def close(self) -> None:
        """Release client resources."""

