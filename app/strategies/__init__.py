from app.strategies.base_strategy import BaseStrategy
from app.strategies.breakout import BreakoutStrategy
from app.strategies.ema_cross import EmaCrossStrategy
from app.strategies.rsi_mean_reversion import RsiMeanReversionStrategy


def build_strategy(name: str, params: dict):
    strategies: dict[str, type[BaseStrategy]] = {
        "ema_cross": EmaCrossStrategy,
        "rsi_mean_reversion": RsiMeanReversionStrategy,
        "breakout": BreakoutStrategy,
    }
    try:
        return strategies[name](**params)
    except KeyError as exc:
        raise ValueError(f"Unknown strategy: {name}") from exc

