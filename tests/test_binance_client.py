import asyncio

import pytest

from app.config.loader import ExchangeConfig
from app.exchange.binance_client import BinanceFuturesClient


def test_signed_endpoint_requires_credentials(monkeypatch) -> None:
    async def run() -> None:
        monkeypatch.delenv("BINANCE_API_KEY", raising=False)
        monkeypatch.delenv("BINANCE_API_SECRET", raising=False)
        client = BinanceFuturesClient(ExchangeConfig(rest_url="https://example.invalid"), api_key=None, api_secret=None)
        try:
            with pytest.raises(RuntimeError, match="credentials"):
                await client.account()
        finally:
            await client.close()

    asyncio.run(run())

