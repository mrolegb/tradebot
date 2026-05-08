from __future__ import annotations

import json
from collections.abc import AsyncIterator

import websockets


async def kline_stream(base_url: str, symbol: str, interval: str) -> AsyncIterator[dict]:
    stream = f"{symbol.lower()}@kline_{interval}"
    url = f"{base_url.rstrip('/')}/ws/{stream}"
    async with websockets.connect(url) as websocket:
        async for message in websocket:
            yield json.loads(message)

