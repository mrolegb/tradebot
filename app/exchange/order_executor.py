from __future__ import annotations

from app.types import Order, SignalSide


class OrderExecutor:
    PAPER_MODES = {"paper", "mock", "simulator", "local"}

    def __init__(self, mode: str = "paper") -> None:
        self.mode = mode
        self.orders: list[Order] = []

    async def market_order(self, symbol: str, side: SignalSide, quantity: float, price: float) -> Order:
        if self.mode not in self.PAPER_MODES:
            raise NotImplementedError("Live testnet order placement is intentionally gated in MVP")
        order = Order(symbol=symbol, side=side, quantity=quantity, price=price, status="FILLED", mode=self.mode)
        self.orders.append(order)
        return order
