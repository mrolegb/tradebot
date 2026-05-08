from __future__ import annotations

import pandas as pd

from app.market.indicators import ema
from app.strategies.base_strategy import BaseStrategy
from app.types import Signal, SignalSide


class EmaCrossStrategy(BaseStrategy):
    def __init__(self, fast_period: int = 9, slow_period: int = 21) -> None:
        if fast_period >= slow_period:
            raise ValueError("fast_period must be lower than slow_period")
        self.fast_period = fast_period
        self.slow_period = slow_period

    def generate_signal(self, symbol: str, candles: pd.DataFrame) -> Signal:
        min_rows = self.slow_period + 2
        if len(candles) < min_rows:
            return Signal(symbol, SignalSide.HOLD, 0.0, "not enough candles")

        close = candles["close"]
        fast = ema(close, self.fast_period)
        slow = ema(close, self.slow_period)
        price = float(close.iloc[-1])

        previous_fast, current_fast = fast.iloc[-2], fast.iloc[-1]
        previous_slow, current_slow = slow.iloc[-2], slow.iloc[-1]

        if previous_fast <= previous_slow and current_fast > current_slow:
            return Signal(symbol, SignalSide.BUY, 0.75, "fast EMA crossed above slow EMA", price)
        if previous_fast >= previous_slow and current_fast < current_slow:
            return Signal(symbol, SignalSide.SELL, 0.75, "fast EMA crossed below slow EMA", price)
        return Signal(symbol, SignalSide.HOLD, 0.0, "no EMA crossover", price)

