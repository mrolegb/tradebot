import pandas as pd

from app.backtest.engine import BacktestEngine
from app.strategies.breakout import BreakoutStrategy


def test_backtest_returns_balance_and_trade_count() -> None:
    closes = [100 + index * 0.2 for index in range(80)] + [125, 124, 123]
    frame = pd.DataFrame(
        {
            "high": [value + 0.2 for value in closes],
            "low": [value - 0.2 for value in closes],
            "close": closes,
        }
    )
    strategy = BreakoutStrategy(
        lookback=5,
        breakout_buffer_percent=0,
        trend_fast_period=5,
        trend_slow_period=10,
        min_trend_gap_percent=0,
        volatility_period=5,
        max_volatility_percent=10,
    )

    result = BacktestEngine(strategy, initial_balance=1000).run("BTCUSDT", frame)

    assert result["initial_balance"] == 1000
    assert "final_balance" in result
    assert result["trades"] >= 1

