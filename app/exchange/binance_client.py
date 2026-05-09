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

    async def exchange_info(self, symbol: str | None = None) -> dict:
        params = {"symbol": symbol} if symbol else {}
        response = await self.http.get("/fapi/v1/exchangeInfo", params=params)
        response.raise_for_status()
        return response.json()

    async def account(self) -> dict:
        return await self._signed_get("/fapi/v2/account", {})

    async def positions(self, symbol: str | None = None) -> list[dict]:
        params = {"symbol": symbol} if symbol else {}
        result = await self._signed_get("/fapi/v2/positionRisk", params)
        return result if isinstance(result, list) else [result]

    async def open_orders(self, symbol: str | None = None) -> list[dict]:
        params = {"symbol": symbol} if symbol else {}
        result = await self._signed_get("/fapi/v1/openOrders", params)
        return result if isinstance(result, list) else [result]

    async def set_leverage(self, symbol: str, leverage: int) -> dict:
        return await self._signed_post("/fapi/v1/leverage", {"symbol": symbol, "leverage": leverage})

    async def place_order(
        self,
        *,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        reduce_only: bool = False,
        price: float | None = None,
        stop_price: float | None = None,
        time_in_force: str | None = None,
        client_order_id: str | None = None,
    ) -> dict:
        params: dict[str, str | int | float] = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": quantity,
        }
        if reduce_only:
            params["reduceOnly"] = "true"
        if price is not None:
            params["price"] = price
        if stop_price is not None:
            params["stopPrice"] = stop_price
        if time_in_force is not None:
            params["timeInForce"] = time_in_force
        if client_order_id is not None:
            params["newClientOrderId"] = client_order_id
        return await self._signed_post("/fapi/v1/order", params)

    async def cancel_order(self, *, symbol: str, order_id: int | None = None, client_order_id: str | None = None) -> dict:
        if order_id is None and client_order_id is None:
            raise ValueError("order_id or client_order_id is required")
        params: dict[str, str | int] = {"symbol": symbol}
        if order_id is not None:
            params["orderId"] = order_id
        if client_order_id is not None:
            params["origClientOrderId"] = client_order_id
        return await self._signed_delete("/fapi/v1/order", params)

    async def cancel_all_orders(self, symbol: str) -> dict:
        return await self._signed_delete("/fapi/v1/allOpenOrders", {"symbol": symbol})

    async def _signed_get(self, path: str, params: dict) -> dict:
        response = await self._signed_request("GET", path, params)
        return response.json()

    async def _signed_post(self, path: str, params: dict) -> dict:
        response = await self._signed_request("POST", path, params)
        return response.json()

    async def _signed_delete(self, path: str, params: dict) -> dict:
        response = await self._signed_request("DELETE", path, params)
        return response.json()

    async def _signed_request(self, method: str, path: str, params: dict) -> httpx.Response:
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
        return response

