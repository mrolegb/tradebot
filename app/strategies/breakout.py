from __future__ import annotations

import pandas as pd

from app.market.indicators import ema, rolling_volatility
from app.strategies.base_strategy import BaseStrategy
from app.types import Signal, SignalSide


class BreakoutStrategy(BaseStrategy):
    def __init__(
        self,
        lookback: int = 20,
        breakout_buffer_percent: float = 0.12,
        trend_fast_period: int = 21,
        trend_slow_period: int = 55,
        min_trend_gap_percent: float = 0.03,
        volatility_period: int = 20,
        min_volatility_percent: float = 0.02,
        max_volatility_percent: float = 0.45,
        allow_shorts: bool = True,
    ) -> None:
        self.lookback = lookback
        self.breakout_buffer_percent = breakout_buffer_percent
        self.trend_fast_period = trend_fast_period
        self.trend_slow_period = trend_slow_period
        self.min_trend_gap_percent = min_trend_gap_percent
        self.volatility_period = volatility_period
        self.min_volatility_percent = min_volatility_percent
        self.max_volatility_percent = max_volatility_percent
        self.allow_shorts = allow_shorts

    def generate_signal(self, symbol: str, candles: pd.DataFrame) -> Signal:
        min_rows = max(self.lookback + 1, self.trend_slow_period + 2, self.volatility_period + 2)
        if len(candles) < min_rows:
            return Signal(symbol, SignalSide.HOLD, 0.0, "not enough candles")

        window = candles.iloc[-self.lookback - 1 : -1]
        latest = candles.iloc[-1]
        price = float(latest["close"])
        close = candles["close"]
        fast = float(ema(close, self.trend_fast_period).iloc[-1])
        slow = float(ema(close, self.trend_slow_period).iloc[-1])
        trend_gap = abs(fast - slow) / price * 100
        volatility = rolling_volatility(close, self.volatility_period).iloc[-1]

        if pd.isna(volatility):
            return Signal(symbol, SignalSide.HOLD, 0.0, "volatility unavailable", price)
        if volatility < self.min_volatility_percent:
            return Signal(symbol, SignalSide.HOLD, 0.0, f"volatility too low: {volatility:.4f}", price)
        if volatility > self.max_volatility_percent:
            return Signal(symbol, SignalSide.HOLD, 0.0, f"volatility too high: {volatility:.4f}", price)
        if trend_gap < self.min_trend_gap_percent:
            return Signal(symbol, SignalSide.HOLD, 0.0, f"trend gap too small: {trend_gap:.4f}", price)

        high_breakout = float(window["close"].max()) * (1 + self.breakout_buffer_percent / 100)
        low_breakout = float(window["close"].min()) * (1 - self.breakout_buffer_percent / 100)

        if price > high_breakout and fast > slow:
            return Signal(symbol, SignalSide.BUY, 0.75, "buffered breakout above high with trend confirmation", price)
        if self.allow_shorts and price < low_breakout and fast < slow:
            return Signal(symbol, SignalSide.SELL, 0.75, "buffered breakout below low with trend confirmation", price)
        return Signal(symbol, SignalSide.HOLD, 0.0, "no breakout", price)
