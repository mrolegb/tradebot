from app.config.loader import load_settings
from app.simulation.batch import _aggregate, _finite
import pytest


def test_aggregate_groups_runs_by_regime() -> None:
    settings = load_settings("configs/local_test.yaml")
    rows = [
        {
            "regime": "uptrend",
            "return_percent": 10,
            "max_drawdown_percent": -1,
            "profit_factor": 2,
            "total_trades": 5,
        },
        {
            "regime": "uptrend",
            "return_percent": -2,
            "max_drawdown_percent": -3,
            "profit_factor": 0.5,
            "total_trades": 4,
        },
        {
            "regime": "choppy",
            "return_percent": -4,
            "max_drawdown_percent": -4,
            "profit_factor": 0,
            "total_trades": 3,
        },
    ]

    aggregate = _aggregate(rows, settings)

    assert aggregate["runs"] == 3
    assert aggregate["overall"]["positive_runs"] == 1
    assert aggregate["overall"]["failure_rate_percent"] == pytest.approx(200 / 3)
    assert aggregate["by_regime"]["uptrend"]["runs"] == 2
    assert aggregate["by_regime"]["uptrend"]["positive_runs"] == 1
    assert aggregate["by_regime"]["choppy"]["failure_rate_percent"] == 100


def test_finite_converts_infinity() -> None:
    assert _finite(float("inf")) == 999999.0
    assert _finite(1.25) == 1.25
