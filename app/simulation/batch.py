from __future__ import annotations

import argparse
import asyncio
import json
import math
from dataclasses import replace
from pathlib import Path
from statistics import mean, median
from typing import Any

from dotenv import load_dotenv

from app.config.loader import load_settings
from app.simulation.report import write_csv, write_json
from app.simulation.runner import run_simulation
from app.utils.logger import configure_logging


async def run_batch(config_path: str, base_settings=None) -> dict[str, Any]:
    load_dotenv()
    base_settings = base_settings or load_settings(config_path)
    configure_logging(base_settings.app.log_level)

    batch_root = Path(base_settings.simulation.output_dir) / "batch"
    rows: list[dict[str, Any]] = []

    for regime in base_settings.simulation.batch_regimes:
        for seed in base_settings.simulation.batch_seeds:
            output_dir = batch_root / regime / f"seed_{seed}"
            settings = replace(
                base_settings,
                simulation=replace(
                    base_settings.simulation,
                    seed=seed,
                    market_regime=regime,
                    output_dir=str(output_dir),
                ),
            )
            summary = await run_simulation(settings)
            rows.append(
                {
                    "regime": regime,
                    "seed": seed,
                    "return_percent": summary["return_percent"],
                    "net_pnl": summary["net_pnl"],
                    "final_balance": summary["final_balance"],
                    "total_trades": summary["total_trades"],
                    "win_rate_percent": summary["win_rate_percent"],
                    "profit_factor": _finite(summary["profit_factor"]),
                    "max_drawdown_percent": summary["max_drawdown_percent"],
                    "average_trade_pnl": summary["average_trade_pnl"],
                    "best_trade_pnl": summary["best_trade_pnl"],
                    "worst_trade_pnl": summary["worst_trade_pnl"],
                    "report_dir": str(output_dir),
                }
            )

    aggregate = _aggregate(rows, base_settings)
    write_csv(batch_root / "runs.csv", rows)
    write_json(batch_root / "aggregate.json", aggregate)
    return aggregate


def _aggregate(rows: list[dict[str, Any]], settings) -> dict[str, Any]:
    by_regime: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_regime.setdefault(row["regime"], []).append(row)

    regimes = {}
    for regime, regime_rows in by_regime.items():
        returns = [float(row["return_percent"]) for row in regime_rows]
        drawdowns = [float(row["max_drawdown_percent"]) for row in regime_rows]
        regimes[regime] = {
            "runs": len(regime_rows),
            "positive_runs": sum(1 for value in returns if value > 0),
            "failure_rate_percent": _percent(sum(1 for value in returns if value <= 0), len(returns)),
            "mean_return_percent": mean(returns),
            "median_return_percent": median(returns),
            "best_return_percent": max(returns),
            "worst_return_percent": min(returns),
            "mean_max_drawdown_percent": mean(drawdowns),
            "worst_max_drawdown_percent": min(drawdowns),
            "mean_profit_factor": mean(float(row["profit_factor"]) for row in regime_rows),
            "mean_trades": mean(float(row["total_trades"]) for row in regime_rows),
        }

    all_returns = [float(row["return_percent"]) for row in rows]
    all_drawdowns = [float(row["max_drawdown_percent"]) for row in rows]
    return {
        "strategy": settings.strategy.name,
        "symbols": settings.trading.symbols,
        "timeframe": settings.trading.timeframe,
        "runs": len(rows),
        "regimes": list(by_regime.keys()),
        "seeds": settings.simulation.batch_seeds,
        "overall": {
            "positive_runs": sum(1 for value in all_returns if value > 0),
            "failure_rate_percent": _percent(sum(1 for value in all_returns if value <= 0), len(all_returns)),
            "mean_return_percent": mean(all_returns),
            "median_return_percent": median(all_returns),
            "best_return_percent": max(all_returns),
            "worst_return_percent": min(all_returns),
            "mean_max_drawdown_percent": mean(all_drawdowns),
            "worst_max_drawdown_percent": min(all_drawdowns),
        },
        "by_regime": regimes,
        "report_files": {
            "aggregate": f"{settings.simulation.output_dir}/batch/aggregate.json",
            "runs": f"{settings.simulation.output_dir}/batch/runs.csv",
        },
    }


def _finite(value: float) -> float:
    if math.isinf(value):
        return 999999.0
    return value


def _percent(value: float, base: float) -> float:
    return 0.0 if base == 0 else value / base * 100


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/local_test.yaml")
    args = parser.parse_args()
    aggregate = asyncio.run(run_batch(args.config))
    print(json.dumps(aggregate, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
