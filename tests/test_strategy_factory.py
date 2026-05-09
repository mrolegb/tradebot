import pytest

from app.strategies import build_strategy
from app.strategies.breakout import BreakoutStrategy
from app.strategies.ema_cross import EmaCrossStrategy
from app.strategies.rsi_mean_reversion import RsiMeanReversionStrategy


def test_builds_known_strategies() -> None:
    assert isinstance(build_strategy("breakout", {"lookback": 20}), BreakoutStrategy)
    assert isinstance(build_strategy("ema_cross", {"fast_period": 3, "slow_period": 8}), EmaCrossStrategy)
    assert isinstance(build_strategy("rsi_mean_reversion", {"period": 5}), RsiMeanReversionStrategy)


def test_unknown_strategy_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Unknown strategy"):
        build_strategy("missing", {})

