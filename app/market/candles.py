from __future__ import annotations

import pandas as pd

from app.types import Candle


def candles_to_frame(candles: list[Candle]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "symbol": c.symbol,
                "open_time": c.open_time,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume,
            }
            for c in candles
        ]
    )

