import asyncio

from app.config.loader import load_settings
from app.exchange.factory import build_market_data_client
from app.exchange.simulator import SimulatedBinanceFuturesClient


def test_local_test_config_uses_simulator() -> None:
    settings = load_settings("configs/local_test.yaml")

    client = build_market_data_client(settings)

    assert isinstance(client, SimulatedBinanceFuturesClient)


def test_simulator_returns_binance_like_candles() -> None:
    async def run() -> None:
        settings = load_settings("configs/local_test.yaml")
        client = build_market_data_client(settings)
        candles = await client.fetch_klines("BTCUSDT", "5m", limit=50)
        account = await client.account()

        assert len(candles) == 50
        assert candles[-1].symbol == "BTCUSDT"
        assert candles[-1].high >= candles[-1].low
        assert account["simulated"] is True

    asyncio.run(run())

