from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from app.types import Signal


class BaseStrategy(ABC):
    @abstractmethod
    def generate_signal(self, symbol: str, candles: pd.DataFrame) -> Signal:
        """Return one signal for the latest candle."""

