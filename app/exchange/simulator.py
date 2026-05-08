from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone

from app.config.loader import ExchangeConfig
from app.types import Candle


class SimulatedBinanceFuturesClient:
    """Deterministic local Binance Futures imitation for tests and dry runs."""

    def __init__(
        self,
        config: ExchangeConfig,
        *,
        seed: int = 42,
        market_regime: str = "uptrend",
        base_balance: float = 1000.0,
        start_prices: dict[str, float] | None = None,
    ) -> None:
        self.config = config
        self.seed = seed
        self.market_regime = market_regime
        self.base_balance = base_balance
        self.start_prices = start_prices or {"BTCUSDT": 65000.0, "ETHUSDT": 3200.0}

    async def fetch_klines(self, symbol: str, interval: str, limit: int = 200) -> list[Candle]:
        step = _interval_to_timedelta(interval)
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        start = now - (step * limit)
        rng = random.Random(f"{self.seed}:{self.market_regime}:{symbol}:{interval}:{limit}")
        base = self.start_prices.get(symbol, 100.0)
        profile = _regime_profile(self.market_regime)

        candles: list[Candle] = []
        previous_close = base
        for index in range(limit):
            open_time = start + (step * index)
            trend = index * base * profile["drift"]
            wave = math.sin(index / profile["wave_period"]) * base * profile["wave"]
            shock = math.sin(index / 3) * base * profile["shock"]
            noise = rng.uniform(-base * profile["noise"], base * profile["noise"])
            close = max(0.01, base + trend + wave + noise)
            if profile["mean_reversion"]:
                close = previous_close + ((base - previous_close) * 0.08) + wave + noise
            close += shock
            close = max(0.01, close)
            high = max(previous_close, close) + abs(rng.uniform(0, base * profile["range"]))
            low = min(previous_close, close) - abs(rng.uniform(0, base * profile["range"]))
            volume = 100 + rng.uniform(0, 25)

            candles.append(
                Candle(
                    symbol=symbol,
                    open_time=open_time,
                    open=previous_close,
                    high=high,
                    low=max(0.01, low),
                    close=close,
                    volume=volume,
                )
            )
            previous_close = close
        return candles

    async def account(self) -> dict:
        return {
            "accountAlias": "LOCAL_SIM",
            "totalWalletBalance": str(self.base_balance),
            "availableBalance": str(self.base_balance),
            "testnet": True,
            "simulated": True,
        }

    async def close(self) -> None:
        return None


def _interval_to_timedelta(interval: str) -> timedelta:
    unit = interval[-1]
    amount = int(interval[:-1])
    if unit == "m":
        return timedelta(minutes=amount)
    if unit == "h":
        return timedelta(hours=amount)
    if unit == "d":
        return timedelta(days=amount)
    raise ValueError(f"Unsupported interval: {interval}")


def _regime_profile(regime: str) -> dict[str, float | bool]:
    profiles: dict[str, dict[str, float | bool]] = {
        "uptrend": {
            "drift": 0.00008,
            "wave": 0.0025,
            "wave_period": 8.0,
            "noise": 0.0008,
            "range": 0.001,
            "shock": 0.0,
            "mean_reversion": False,
        },
        "downtrend": {
            "drift": -0.00008,
            "wave": 0.0025,
            "wave_period": 8.0,
            "noise": 0.0008,
            "range": 0.001,
            "shock": 0.0,
            "mean_reversion": False,
        },
        "choppy": {
            "drift": 0.0,
            "wave": 0.0035,
            "wave_period": 4.0,
            "noise": 0.0015,
            "range": 0.0015,
            "shock": 0.0006,
            "mean_reversion": True,
        },
        "high_volatility": {
            "drift": 0.00002,
            "wave": 0.006,
            "wave_period": 5.0,
            "noise": 0.0035,
            "range": 0.003,
            "shock": 0.001,
            "mean_reversion": False,
        },
        "low_volatility": {
            "drift": 0.00002,
            "wave": 0.0008,
            "wave_period": 12.0,
            "noise": 0.00025,
            "range": 0.00035,
            "shock": 0.0,
            "mean_reversion": False,
        },
    }
    if regime not in profiles:
        raise ValueError(f"Unsupported market regime: {regime}")
    return profiles[regime]
