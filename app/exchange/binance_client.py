from __future__ import annotations

import os
import time
from hashlib import sha256
from hmac import new as hmac_new
from urllib.parse import urlencode

import httpx

from app.config.loader import ExchangeConfig
from app.types import Candle


class BinanceFuturesClient:
    def __init__(self, config: ExchangeConfig, api_key: str | None = None, api_secret: str | None = None) -> None:
        self.config = config
        self.api_key = api_key or os.getenv("BINANCE_API_KEY")
        self.api_secret = api_secret or os.getenv("BINANCE_API_SECRET")
        self.http = httpx.AsyncClient(base_url=config.rest_url, timeout=10)

    async def close(self) -> None:
        await self.http.aclose()

    async def fetch_klines(self, symbol: str, interval: str, limit: int = 200) -> list[Candle]:
        response = await self.http.get("/fapi/v1/klines", params={"symbol": symbol, "interval": interval, "limit": limit})
        response.raise_for_status()
        return [Candle.from_sequence(symbol, row) for row in response.json()]

    async def exchange_info(self) -> dict:
        response = await self.http.get("/fapi/v1/exchangeInfo")
        response.raise_for_status()
        return response.json()

    async def account(self) -> dict:
        return await self._signed_get("/fapi/v2/account", {})

    async def position_risk(self, symbol: str | None = None) -> list[dict]:
        params = {"symbol": symbol} if symbol else {}
        data = await self._signed_get("/fapi/v2/positionRisk", params)
        return data if isinstance(data, list) else [data]

    async def change_leverage(self, symbol: str, leverage: int) -> dict:
        return await self._signed_post("/fapi/v1/leverage", {"symbol": symbol, "leverage": leverage})

    async def new_order(self, params: dict) -> dict:
        return await self._signed_post("/fapi/v1/order", params)

    async def cancel_all_open_orders(self, symbol: str) -> dict:
        return await self._signed_delete("/fapi/v1/allOpenOrders", {"symbol": symbol})

    async def _signed_get(self, path: str, params: dict) -> dict:
        if not self.api_key or not self.api_secret:
            raise RuntimeError("Binance credentials are required for signed endpoints")
        signed = dict(params)
        signed["timestamp"] = int(time.time() * 1000)
        query = urlencode(signed)
        signature = hmac_new(self.api_secret.encode(), query.encode(), sha256).hexdigest()
        response = await self.http.get(
            path,
            params={**signed, "signature": signature},
            headers={"X-MBX-APIKEY": self.api_key},
        )
        response.raise_for_status()
        return response.json()

    async def _signed_post(self, path: str, params: dict) -> dict:
        return await self._signed_request("POST", path, params)

    async def _signed_delete(self, path: str, params: dict) -> dict:
        return await self._signed_request("DELETE", path, params)

    async def _signed_request(self, method: str, path: str, params: dict) -> dict:
        if not self.api_key or not self.api_secret:
            raise RuntimeError("Binance credentials are required for signed endpoints")
        signed = dict(params)
        signed["timestamp"] = int(time.time() * 1000)
        query = urlencode(signed)
        signature = hmac_new(self.api_secret.encode(), query.encode(), sha256).hexdigest()
        response = await self.http.request(
            method,
            path,
            params={**signed, "signature": signature},
            headers={"X-MBX-APIKEY": self.api_key},
        )
        response.raise_for_status()
        return response.json()
