import pandas as pd

from app.strategies.breakout import BreakoutStrategy
from app.types import SignalSide


def test_breakout_generates_buy_signal() -> None:
    closes = [100 + index * 0.2 for index in range(60)] + [120]
    frame = pd.DataFrame(
        {
            "high": [value + 0.1 for value in closes],
            "low": [value - 0.1 for value in closes],
            "close": closes,
        }
    )

    signal = BreakoutStrategy(
        lookback=5,
        breakout_buffer_percent=0.0,
        trend_fast_period=5,
        trend_slow_period=10,
        min_trend_gap_percent=0.0,
        volatility_period=5,
        max_volatility_percent=10,
    ).generate_signal("BTCUSDT", frame)

    assert signal.side == SignalSide.BUY
