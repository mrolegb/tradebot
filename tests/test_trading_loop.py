import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from app.config.loader import load_settings
from app.runtime.state import RuntimeState
from app.runtime.trading_loop import TradingLoopOptions, run_binance_trading_loop
from app.types import Candle, Signal, SignalSide


def test_binance_trading_loop_runs_one_dry_run_cycle(tmp_path, monkeypatch) -> None:
    async def run() -> None:
        import app.runtime.trading_loop as loop_module

        class FakeClient:
            def __init__(self, config) -> None:
                self.config = config

            async def close(self) -> None:
                return None

            async def account(self) -> dict:
                return {"totalWalletBalance": "1000"}

            async def fetch_klines(self, symbol: str, interval: str, limit: int = 200) -> list[Candle]:
                start = datetime.now(timezone.utc) - timedelta(minutes=limit)
                return [
                    Candle(symbol, start + timedelta(minutes=index), 100 + index, 101 + index, 99 + index, 100 + index, 10)
                    for index in range(limit)
                ]

            async def exchange_info(self) -> dict:
                return {"symbols": [{"symbol": "BTCUSDT", "filters": [{"filterType": "LOT_SIZE", "stepSize": "0.001", "minQty": "0.001"}]}]}

            async def position_risk(self, symbol: str | None = None) -> list[dict]:
                return []

        class FakeStrategy:
            def generate_signal(self, symbol, candles):
                return Signal(symbol, SignalSide.BUY, 1.0, "test", float(candles["close"].iloc[-1]))

        monkeypatch.setattr(loop_module, "BinanceFuturesClient", FakeClient)
        monkeypatch.setattr(loop_module, "build_strategy", lambda name, params: FakeStrategy())

        settings = load_settings("configs/binance_testnet.yaml")
        settings = replace(settings, storage=replace(settings.storage, sqlite_path=str(tmp_path / "loop.sqlite3")))
        state = RuntimeState(running=True, selected_profile="binance_testnet", selected_strategy="breakout")

        await run_binance_trading_loop(settings, state, TradingLoopOptions(once=True))

        assert state.running is False
        assert state.loop_count == 1

    asyncio.run(run())
