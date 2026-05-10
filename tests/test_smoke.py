import asyncio
from dataclasses import replace

import pytest

from app.config.loader import load_settings
from app.exchange.safety import LIVE_SMOKE_CONFIRMATION
from app.runtime.smoke import run_binance_smoke
from app.types import Candle


def test_live_smoke_requires_extra_confirmation(monkeypatch) -> None:
    async def run() -> None:
        monkeypatch.delenv("BINANCE_LIVE_EXECUTION_ENABLED", raising=False)
        monkeypatch.delenv("BINANCE_LIVE_CONFIRM", raising=False)
        monkeypatch.delenv("BINANCE_LIVE_SMOKE_CONFIRM", raising=False)

        with pytest.raises(RuntimeError, match="Live smoke is blocked"):
            await run_binance_smoke("configs/binance_live.yaml")

    asyncio.run(run())


def test_binance_smoke_dry_run_flow(tmp_path, monkeypatch) -> None:
    async def run() -> None:
        import app.runtime.smoke as smoke_module

        class FakeClient:
            def __init__(self, config) -> None:
                self.config = config

            async def close(self) -> None:
                return None

            async def account(self) -> dict:
                return {"totalWalletBalance": "1000"}

            async def exchange_info(self) -> dict:
                return {
                    "symbols": [
                        {
                            "symbol": "BTCUSDT",
                            "filters": [
                                {"filterType": "LOT_SIZE", "stepSize": "0.001", "minQty": "0.001"},
                                {"filterType": "PRICE_FILTER", "tickSize": "0.01"},
                                {"filterType": "MIN_NOTIONAL", "notional": "5"},
                            ],
                        }
                    ]
                }

            async def fetch_klines(self, symbol: str, interval: str, limit: int = 2) -> list[Candle]:
                from datetime import datetime, timezone

                now = datetime.now(timezone.utc)
                return [
                    Candle(symbol, now, 100.0, 101.0, 99.0, 100.0, 1.0),
                    Candle(symbol, now, 100.0, 101.0, 99.0, 100.0, 1.0),
                ]

            async def position_risk(self, symbol: str | None = None) -> list[dict]:
                return []

        original_load_settings = smoke_module.load_settings

        def fake_load_settings(path):
            settings = original_load_settings(path)
            return replace(settings, storage=replace(settings.storage, sqlite_path=str(tmp_path / "smoke.sqlite3")))

        monkeypatch.delenv("BINANCE_TESTNET_EXECUTION_ENABLED", raising=False)
        monkeypatch.setattr(smoke_module, "BinanceFuturesClient", FakeClient)
        monkeypatch.setattr(smoke_module, "load_settings", fake_load_settings)

        result = await run_binance_smoke("configs/binance_testnet.yaml")

        assert result["status"] == "passed"
        assert result["dry_run"] is True
        assert result["opened_order_status"] == "DRY_RUN"
        assert result["quantity"] > 0

    asyncio.run(run())


def test_live_smoke_confirmation_constant_is_explicit() -> None:
    assert LIVE_SMOKE_CONFIRMATION == "PLACE_LIVE_SMOKE_ORDER"
