from app.exchange.order_executor import BinanceOrderExecutor, OrderExecutor
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


def test_binance_executor_live_defaults_to_dry_run_without_confirmation() -> None:
    async def run() -> None:
        class FakeClient:
            async def exchange_info(self):
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

        executor = BinanceOrderExecutor(FakeClient(), mode="live")
        await executor.load_exchange_rules()
        order = await executor.market_order("BTCUSDT", SignalSide.BUY, 0.12349, 65000.0)

        assert order.status == "DRY_RUN"
        assert order.quantity == 0.123

    import asyncio

    asyncio.run(run())
