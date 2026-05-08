from __future__ import annotations

import pandas as pd


def ema(values: pd.Series, period: int) -> pd.Series:
    if period <= 0:
        raise ValueError("EMA period must be positive")
    return values.ewm(span=period, adjust=False).mean()


def rsi(values: pd.Series, period: int = 14) -> pd.Series:
    if period <= 0:
        raise ValueError("RSI period must be positive")
    delta = values.diff()
    gain = delta.clip(lower=0).rolling(window=period).mean()
    loss = -delta.clip(upper=0).rolling(window=period).mean()
    rs = gain / loss.replace(0, pd.NA)
    return 100 - (100 / (1 + rs))


def rolling_volatility(values: pd.Series, period: int = 20) -> pd.Series:
    if period <= 1:
        raise ValueError("Volatility period must be greater than one")
    return values.pct_change().rolling(window=period).std() * 100
