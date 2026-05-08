import asyncio

from app.config.loader import load_settings
from app.simulation.runner import run_simulation


def test_simulation_writes_report_files(tmp_path) -> None:
    async def run() -> None:
        settings = load_settings("configs/local_test.yaml")
        settings = settings.__class__(
            app=settings.app,
            exchange=settings.exchange,
            trading=settings.trading,
            risk=settings.risk,
            cooldown=settings.cooldown,
            storage=settings.storage,
            strategy=settings.strategy,
            simulation=settings.simulation.__class__(
                candles_limit=120,
                output_dir=str(tmp_path),
                stop_loss_percent=settings.simulation.stop_loss_percent,
                take_profit_percent=settings.simulation.take_profit_percent,
                fee_rate_percent=settings.simulation.fee_rate_percent,
            ),
        )

        summary = await run_simulation(settings)

        assert summary["total_trades"] >= 0
        assert (tmp_path / "summary.json").exists()
        assert (tmp_path / "trades.csv").exists()
        assert (tmp_path / "signals.csv").exists()
        assert (tmp_path / "equity_curve.csv").exists()

    asyncio.run(run())
