import pandas as pd
import pytest

from app.market.indicators import ema, rolling_volatility, rsi


def test_ema_returns_series_with_latest_value() -> None:
    values = pd.Series([1, 2, 3, 4, 5])

    result = ema(values, 3)

    assert len(result) == len(values)
    assert result.iloc[-1] > result.iloc[0]


def test_rsi_and_volatility_are_available_after_warmup() -> None:
    values = pd.Series([1, 2, 3, 2, 4, 5, 4, 6, 5, 7], dtype=float)

    assert not pd.isna(rsi(values, 3).iloc[-1])
    assert not pd.isna(rolling_volatility(values, 3).iloc[-1])


def test_indicator_period_validation() -> None:
    values = pd.Series([1, 2, 3])

    with pytest.raises(ValueError):
        ema(values, 0)
    with pytest.raises(ValueError):
        rsi(values, 0)
    with pytest.raises(ValueError):
        rolling_volatility(values, 1)
