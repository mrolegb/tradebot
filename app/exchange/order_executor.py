from __future__ import annotations

from decimal import Decimal, ROUND_DOWN
from typing import Any

from app.exchange.binance_client import BinanceFuturesClient
from app.exchange.safety import execution_guard_error
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


class BinanceOrderExecutor:
    def __init__(self, client: BinanceFuturesClient, mode: str, *, dry_run: bool | None = None) -> None:
        self.client = client
        self.mode = mode
        self.dry_run = execution_guard_error(mode) is not None if dry_run is None else dry_run
        self._rules: dict[str, dict[str, Decimal]] = {}

    async def load_exchange_rules(self) -> None:
        info = await self.client.exchange_info()
        for symbol in info.get("symbols", []):
            filters = {item["filterType"]: item for item in symbol.get("filters", [])}
            lot = filters.get("LOT_SIZE", {})
            price_filter = filters.get("PRICE_FILTER", {})
            min_notional = filters.get("MIN_NOTIONAL", {}) or filters.get("NOTIONAL", {})
            self._rules[symbol["symbol"]] = {
                "step_size": Decimal(str(lot.get("stepSize", "0.001"))),
                "min_qty": Decimal(str(lot.get("minQty", "0"))),
                "tick_size": Decimal(str(price_filter.get("tickSize", "0.01"))),
                "min_notional": Decimal(str(min_notional.get("notional", min_notional.get("minNotional", "0")))),
            }

    async def prepare_symbol(self, symbol: str, leverage: int) -> None:
        if self.dry_run:
            return
        await self.client.change_leverage(symbol, leverage)

    async def market_order(self, symbol: str, side: SignalSide, quantity: float, price: float) -> Order:
        quantity_value = self.normalize_quantity(symbol, quantity)
        if quantity_value <= 0:
            raise ValueError(f"Quantity for {symbol} is below exchange limits")
        if self._min_notional(symbol) and Decimal(str(price)) * Decimal(str(quantity_value)) < self._min_notional(symbol):
            raise ValueError(f"Order notional for {symbol} is below exchange minimum")

        if self.dry_run:
            order = Order(symbol=symbol, side=side, quantity=quantity_value, price=price, status="DRY_RUN", mode=self.mode)
            return order

        response = await self.client.new_order(
            {
                "symbol": symbol,
                "side": side.value,
                "type": "MARKET",
                "quantity": self._format_decimal(quantity_value),
                "newOrderRespType": "RESULT",
            }
        )
        return Order(
            symbol=symbol,
            side=side,
            quantity=quantity_value,
            price=float(response.get("avgPrice") or price),
            status=str(response.get("status", "NEW")),
            mode=self.mode,
            exchange_order_id=str(response.get("orderId")) if response.get("orderId") is not None else None,
        )

    async def close_position(self, symbol: str, position: dict[str, Any]) -> Order | None:
        amount = float(position.get("positionAmt", 0) or 0)
        if amount == 0:
            return None
        side = SignalSide.SELL if amount > 0 else SignalSide.BUY
        mark_price = float(position.get("markPrice", 0) or 0)
        return await self.market_order(symbol, side, abs(amount), mark_price)

    async def cancel_all_open_orders(self, symbol: str) -> dict:
        if self.dry_run:
            return {"symbol": symbol, "status": "DRY_RUN"}
        return await self.client.cancel_all_open_orders(symbol)

    def minimum_quantity_for_notional(self, symbol: str, price: float, notional: float) -> float:
        if price <= 0:
            raise ValueError("Price must be positive")
        rules = self._rules.get(symbol, {})
        min_notional = float(rules.get("min_notional", Decimal("0")) or 0)
        target_notional = max(notional, min_notional)
        return self.normalize_quantity(symbol, target_notional / price)

    def normalize_quantity(self, symbol: str, quantity: float) -> float:
        rules = self._rules.get(symbol)
        if not rules:
            return quantity
        step = rules["step_size"]
        quantized = (Decimal(str(quantity)) / step).to_integral_value(rounding=ROUND_DOWN) * step
        if quantized < rules["min_qty"]:
            return 0.0
        return float(quantized)

    def _min_notional(self, symbol: str) -> Decimal:
        return self._rules.get(symbol, {}).get("min_notional", Decimal("0"))

    def _format_decimal(self, value: float) -> str:
        return format(Decimal(str(value)).normalize(), "f")
