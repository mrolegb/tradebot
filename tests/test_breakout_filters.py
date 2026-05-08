import pandas as pd

from app.strategies.breakout import BreakoutStrategy
from app.types import SignalSide


def frame_from_closes(closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "high": [value + 0.1 for value in closes],
            "low": [value - 0.1 for value in closes],
            "close": closes,
        }
    )


def base_strategy(**overrides) -> BreakoutStrategy:
    params = {
        "lookback": 5,
        "breakout_buffer_percent": 0,
        "trend_fast_period": 5,
        "trend_slow_period": 10,
        "min_trend_gap_percent": 0,
        "volatility_period": 5,
        "min_volatility_percent": 0,
        "max_volatility_percent": 10,
        "allow_shorts": True,
    }
    params.update(overrides)
    return BreakoutStrategy(**params)


def test_breakout_holds_when_volatility_too_high() -> None:
    closes = [100 + ((-1) ** index * index * 2) for index in range(30)] + [170]

    signal = base_strategy(max_volatility_percent=1).generate_signal("BTCUSDT", frame_from_closes(closes))

    assert signal.side == SignalSide.HOLD
    assert "volatility too high" in signal.reason


def test_breakout_holds_when_trend_gap_too_small() -> None:
    closes = [100 + (index * 0.01) for index in range(30)] + [101]

    signal = base_strategy(min_trend_gap_percent=5).generate_signal("BTCUSDT", frame_from_closes(closes))

    assert signal.side == SignalSide.HOLD
    assert "trend gap too small" in signal.reason


def test_breakout_respects_shorts_disabled() -> None:
    closes = [120 - index for index in range(30)] + [80]

    signal = base_strategy(allow_shorts=False).generate_signal("BTCUSDT", frame_from_closes(closes))

    assert signal.side == SignalSide.HOLD


def test_breakout_generates_sell_with_downtrend_confirmation() -> None:
    closes = [120 - index * 0.5 for index in range(40)] + [90]

    signal = base_strategy().generate_signal("BTCUSDT", frame_from_closes(closes))

    assert signal.side == SignalSide.SELL
