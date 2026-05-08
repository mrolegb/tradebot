from __future__ import annotations

import pandas as pd

from app.strategies.base_strategy import BaseStrategy
from app.types import SignalSide


class BacktestEngine:
    def __init__(self, strategy: BaseStrategy, initial_balance: float = 1000.0) -> None:
        self.strategy = strategy
        self.initial_balance = initial_balance

    def run(self, symbol: str, candles: pd.DataFrame) -> dict:
        balance = self.initial_balance
        position_side: SignalSide | None = None
        entry_price = 0.0
        trades = 0

        for end in range(2, len(candles) + 1):
            window = candles.iloc[:end]
            signal = self.strategy.generate_signal(symbol, window)
            price = float(window["close"].iloc[-1])
            if position_side is None and signal.side in {SignalSide.BUY, SignalSide.SELL}:
                position_side = signal.side
                entry_price = price
                trades += 1
            elif position_side == SignalSide.BUY and signal.side == SignalSide.SELL:
                balance += price - entry_price
                position_side = None
            elif position_side == SignalSide.SELL and signal.side == SignalSide.BUY:
                balance += entry_price - price
                position_side = None

        return {"initial_balance": self.initial_balance, "final_balance": balance, "trades": trades}

