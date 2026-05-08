from __future__ import annotations

import pandas as pd

from app.market.indicators import rsi
from app.strategies.base_strategy import BaseStrategy
from app.types import Signal, SignalSide


class RsiMeanReversionStrategy(BaseStrategy):
    def __init__(self, period: int = 14, oversold: float = 30, overbought: float = 70) -> None:
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def generate_signal(self, symbol: str, candles: pd.DataFrame) -> Signal:
        if len(candles) < self.period + 1:
            return Signal(symbol, SignalSide.HOLD, 0.0, "not enough candles")

        close = candles["close"]
        current_rsi = rsi(close, self.period).iloc[-1]
        price = float(close.iloc[-1])

        if pd.isna(current_rsi):
            return Signal(symbol, SignalSide.HOLD, 0.0, "RSI unavailable", price)
        if current_rsi <= self.oversold:
            return Signal(symbol, SignalSide.BUY, 0.65, f"RSI oversold: {current_rsi:.2f}", price)
        if current_rsi >= self.overbought:
            return Signal(symbol, SignalSide.SELL, 0.65, f"RSI overbought: {current_rsi:.2f}", price)
        return Signal(symbol, SignalSide.HOLD, 0.0, f"RSI neutral: {current_rsi:.2f}", price)

