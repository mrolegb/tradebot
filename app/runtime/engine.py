from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from math import floor

from app.exchange.binance_client import BinanceFuturesClient
from app.market.indicators import atr, ema
from app.runtime.state import runtime_state
from app.types import Candle


class ExecutionIntentType(StrEnum):
    OPEN_LONG = "open_long"
    OPEN_SHORT = "open_short"
    CLOSE_LONG = "close_long"
    CLOSE_SHORT = "close_short"
    HOLD = "hold"


@dataclass
class ExecutionIntent:
    symbol: str
    intent: ExecutionIntentType
    quantity: float = 0.0
    reason: str = ""
    reduce_only: bool = False
    metadata: dict = field(default_factory=dict)


@dataclass
class SymbolPrecision:
    symbol: str
    tick_size: float
    step_size: float
    min_qty: float
    min_notional: float

    def normalize_price(self, value: float) -> float:
        return floor(value / self.tick_size) * self.tick_size

    def normalize_quantity(self, value: float) -> float:
        return floor(value / self.step_size) * self.step_size

    def validate_notional(self, *, quantity: float, price: float) -> bool:
        return quantity * price >= self.min_notional


@dataclass
class ReconciliationSnapshot:
    positions: list[dict]
    open_orders: list[dict]
    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class RuntimeReconciliation:
    def compare(self, *, local_positions: list[dict], exchange_positions: list[dict]) -> dict:
        local_symbols = {p.get("symbol") for p in local_positions}
        exchange_symbols = {p.get("symbol") for p in exchange_positions}
        missing_on_exchange = sorted(local_symbols - exchange_symbols)
        unknown_on_exchange = sorted(exchange_symbols - local_symbols)
        return {
            "healthy": not missing_on_exchange and not unknown_on_exchange,
            "missing_on_exchange": missing_on_exchange,
            "unknown_on_exchange": unknown_on_exchange,
        }


class CandleRuntimeEngine:
    def __init__(self, client: BinanceFuturesClient) -> None:
        self.client = client
        self.reconciliation = RuntimeReconciliation()

    async def exchange_precision(self, symbol: str) -> SymbolPrecision:
        exchange_info = await self.client.exchange_info(symbol)
        symbols = exchange_info.get("symbols", [])
        if not symbols:
            raise RuntimeError(f"Exchange metadata not found for {symbol}")
        metadata = symbols[0]
        filters = {item["filterType"]: item for item in metadata.get("filters", [])}
        lot_size = filters.get("LOT_SIZE", {})
        price_filter = filters.get("PRICE_FILTER", {})
        min_notional = filters.get("MIN_NOTIONAL", {})
        return SymbolPrecision(
            symbol=symbol,
            tick_size=float(price_filter.get("tickSize", 0.1)),
            step_size=float(lot_size.get("stepSize", 0.001)),
            min_qty=float(lot_size.get("minQty", 0.001)),
            min_notional=float(min_notional.get("notional", 5)),
        )

    async def runtime_cycle(self, *, symbol: str, interval: str, lookback: int = 200) -> dict:
        started_at = datetime.now(timezone.utc)
        runtime_state.heartbeat()

        candles = await self.client.fetch_klines(symbol, interval, limit=lookback)
        if not candles:
            runtime_state.record_runtime_failure("empty_market_data")
            return {"status": "no_data"}

        runtime_state.record_market_data()

        signal = self._signal(symbol, candles)
        precision = await self.exchange_precision(symbol)
        reconciliation = await self.reconcile(symbol)

        runtime_state.record_runtime_success()

        return {
            "status": "completed",
            "symbol": symbol,
            "started_at": started_at.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "intent": {
                "symbol": signal.symbol,
                "intent": signal.intent,
                "quantity": signal.quantity,
                "reason": signal.reason,
            },
            "precision": {
                "tick_size": precision.tick_size,
                "step_size": precision.step_size,
                "min_qty": precision.min_qty,
                "min_notional": precision.min_notional,
            },
            "reconciliation": reconciliation,
        }

    async def reconcile(self, symbol: str) -> dict:
        exchange_positions = await self.client.positions(symbol)
        exchange_orders = await self.client.open_orders(symbol)
        snapshot = ReconciliationSnapshot(
            positions=exchange_positions,
            open_orders=exchange_orders,
        )
        return self.reconciliation.compare(
            local_positions=runtime_state.simulated_open_positions,
            exchange_positions=snapshot.positions,
        )

    def _signal(self, symbol: str, candles: list[Candle]) -> ExecutionIntent:
        closes = [c.close for c in candles]
        if len(closes) < 50:
            return ExecutionIntent(
                symbol=symbol,
                intent=ExecutionIntentType.HOLD,
                reason="insufficient_history",
            )

        fast = ema(closes, period=20)
        slow = ema(closes, period=50)
        volatility = atr(candles, period=14)

        latest_fast = fast[-1]
        latest_slow = slow[-1]
        latest_volatility = volatility[-1]
        latest_price = closes[-1]

        if latest_volatility <= 0:
            return ExecutionIntent(
                symbol=symbol,
                intent=ExecutionIntentType.HOLD,
                reason="invalid_volatility",
            )

        quantity = round(max(0.001, 25 / latest_price), 3)

        if latest_fast > latest_slow:
            return ExecutionIntent(
                symbol=symbol,
                intent=ExecutionIntentType.OPEN_LONG,
                quantity=quantity,
                reason="ema_trend_long",
                metadata={
                    "ema_fast": latest_fast,
                    "ema_slow": latest_slow,
                    "atr": latest_volatility,
                },
            )

        if latest_fast < latest_slow:
            return ExecutionIntent(
                symbol=symbol,
                intent=ExecutionIntentType.OPEN_SHORT,
                quantity=quantity,
                reason="ema_trend_short",
                metadata={
                    "ema_fast": latest_fast,
                    "ema_slow": latest_slow,
                    "atr": latest_volatility,
                },
            )

        return ExecutionIntent(
            symbol=symbol,
            intent=ExecutionIntentType.HOLD,
            reason="neutral_market",
        )
