import asyncio

from app.config.loader import load_settings
from app.simulation.runner import OpenPosition, _exit_reason_and_price
from app.simulation.runner import run_simulation
from app.types import SignalSide


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


def test_exit_checks_intracandle_high_low() -> None:
    long_position = OpenPosition(
        symbol="BTCUSDT",
        side=SignalSide.BUY,
        entry_time="2026-01-01T00:00:00+00:00",
        entry_price=100.0,
        raw_entry_price=100.0,
        quantity=1.0,
        stop_loss=95.0,
        take_profit=110.0,
        entry_fee=0.0,
    )

    reason, price = _exit_reason_and_price(long_position, SignalSide.HOLD, price=100.0, high=101.0, low=94.0)

    assert reason == "stop_loss"
    assert price == 95.0
