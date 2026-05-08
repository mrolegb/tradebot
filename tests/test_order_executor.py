import pytest

from app.exchange.order_executor import OrderExecutor
from app.types import SignalSide


def test_executor_accepts_simulator_mode() -> None:
    async def run() -> None:
        executor = OrderExecutor(mode="simulator")

        order = await executor.market_order("BTCUSDT", SignalSide.BUY, 1.5, 100.0)

        assert order.status == "FILLED"
        assert order.mode == "simulator"
        assert executor.orders == [order]

    import asyncio

    asyncio.run(run())


def test_executor_rejects_live_mode_until_implemented() -> None:
    async def run() -> None:
        executor = OrderExecutor(mode="live")

        with pytest.raises(NotImplementedError):
            await executor.market_order("BTCUSDT", SignalSide.BUY, 1.0, 100.0)

    import asyncio

    asyncio.run(run())

