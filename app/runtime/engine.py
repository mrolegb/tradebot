from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from math import floor

import pandas as pd

from app.exchange.binance_client import BinanceFuturesClient
from app.market.indicators import ema
from app.runtime.state import runtime_state
from app.types import Candle


class ExecutionIntentType(StrEnum):
    OPEN_LONG = "open_long"
    OPEN_SHORT = "open_short"
    CLOSE_LONG = "close_long"
    CLOSE_SHORT = "close_short"
    HOLD = "hold"


class ExecutionMode(StrEnum):
    DRY_RUN = "dry_run"
    TESTNET = "testnet"


@dataclass
class ExecutionIntent:
    symbol: str
    intent: ExecutionIntentType
    quantity: float = 0.0
    reason: str = ""
    reduce_only: bool = False
    metadata: dict = field(default_factory=dict)

    @property
    def wants_order(self) -> bool:
        return self.intent is not ExecutionIntentType.HOLD and self.quantity > 0


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

    def validate_quantity(self, quantity: float) -> bool:
        return quantity >= self.min_qty

    def validate_notional(self, *, quantity: float, price: float) -> bool:
        return quantity * price >= self.min_notional


@dataclass
class SafetyDecision:
    allowed: bool
    reason: str
    normalized_quantity: float = 0.0
    metadata: dict = field(default_factory=dict)


@dataclass
class ExecutionResult:
    mode: ExecutionMode
    executed: bool
    reason: str
    order: dict | None = None
    intent: ExecutionIntent | None = None


@dataclass
class ReconciliationSnapshot:
    positions: list[dict]
    open_orders: list[dict]
    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class RuntimeReconciliation:
    def compare(self, *, local_positions: list[dict], exchange_positions: list[dict], open_orders: list[dict] | None = None) -> dict:
        active_exchange_positions = [p for p in exchange_positions if abs(float(p.get("positionAmt", 0) or 0)) > 0]
        local_symbols = {p.get("symbol") for p in local_positions if p.get("symbol")}
        exchange_symbols = {p.get("symbol") for p in active_exchange_positions if p.get("symbol")}
        missing_on_exchange = sorted(local_symbols - exchange_symbols)
        unknown_on_exchange = sorted(exchange_symbols - local_symbols)
        open_order_symbols = sorted({o.get("symbol") for o in (open_orders or []) if o.get("symbol")})
        return {
            "healthy": not missing_on_exchange and not unknown_on_exchange,
            "missing_on_exchange": missing_on_exchange,
            "unknown_on_exchange": unknown_on_exchange,
            "open_order_symbols": open_order_symbols,
            "active_exchange_positions": active_exchange_positions,
        }


class ExecutionSafety:
    def __init__(self, *, max_open_positions: int = 1, allow_shorts: bool = False) -> None:
        self.max_open_positions = max_open_positions
        self.allow_shorts = allow_shorts

    def evaluate(
        self,
        *,
        intent: ExecutionIntent,
        precision: SymbolPrecision,
        last_price: float,
        reconciliation: dict,
        local_positions: list[dict],
    ) -> SafetyDecision:
        if intent.intent is ExecutionIntentType.HOLD:
            return SafetyDecision(False, "hold_intent")
        if intent.intent is ExecutionIntentType.OPEN_SHORT and not self.allow_shorts:
            return SafetyDecision(False, "shorts_disabled")
        if not reconciliation.get("healthy", False):
            return SafetyDecision(False, "reconciliation_unhealthy", metadata=reconciliation)
        if len(local_positions) >= self.max_open_positions and intent.intent in {
            ExecutionIntentType.OPEN_LONG,
            ExecutionIntentType.OPEN_SHORT,
        }:
            return SafetyDecision(False, "max_open_positions_reached")

        normalized_quantity = precision.normalize_quantity(intent.quantity)
        if not precision.validate_quantity(normalized_quantity):
            return SafetyDecision(False, "quantity_below_minimum", normalized_quantity=normalized_quantity)
        if not precision.validate_notional(quantity=normalized_quantity, price=last_price):
            return SafetyDecision(False, "notional_below_minimum", normalized_quantity=normalized_quantity)

        return SafetyDecision(True, "accepted", normalized_quantity=normalized_quantity)


class DryRunExecutor:
    async def execute(self, *, intent: ExecutionIntent, safety: SafetyDecision) -> ExecutionResult:
        if not safety.allowed:
            return ExecutionResult(
                mode=ExecutionMode.DRY_RUN,
                executed=False,
                reason=safety.reason,
                intent=intent,
            )
        return ExecutionResult(
            mode=ExecutionMode.DRY_RUN,
            executed=True,
            reason="dry_run_order_accepted",
            intent=intent,
            order={
                "symbol": intent.symbol,
                "intent": intent.intent,
                "quantity": safety.normalized_quantity,
                "reduce_only": intent.reduce_only,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )


class TestnetExecutor:
    def __init__(self, client: BinanceFuturesClient) -> None:
        self.client = client

    async def execute(self, *, intent: ExecutionIntent, safety: SafetyDecision) -> ExecutionResult:
        if not safety.allowed:
            return ExecutionResult(
                mode=ExecutionMode.TESTNET,
                executed=False,
                reason=safety.reason,
                intent=intent,
            )

        if intent.intent is ExecutionIntentType.OPEN_LONG:
            side = "BUY"
            reduce_only = False
        elif intent.intent is ExecutionIntentType.OPEN_SHORT:
            side = "SELL"
            reduce_only = False
        elif intent.intent is ExecutionIntentType.CLOSE_LONG:
            side = "SELL"
            reduce_only = True
        elif intent.intent is ExecutionIntentType.CLOSE_SHORT:
            side = "BUY"
            reduce_only = True
        else:
            return ExecutionResult(mode=ExecutionMode.TESTNET, executed=False, reason="hold_intent", intent=intent)

        order = await self.client.place_order(
            symbol=intent.symbol,
            side=side,
            order_type="MARKET",
            quantity=safety.normalized_quantity,
            reduce_only=reduce_only,
        )
        return ExecutionResult(mode=ExecutionMode.TESTNET, executed=True, reason="testnet_order_submitted", intent=intent, order=order)


class CandleRuntimeEngine:
    def __init__(
        self,
        client: BinanceFuturesClient,
        *,
        mode: ExecutionMode = ExecutionMode.DRY_RUN,
        allow_shorts: bool = False,
        max_open_positions: int = 1,
    ) -> None:
        self.client = client
        self.mode = mode
        self.reconciliation = RuntimeReconciliation()
        self.safety = ExecutionSafety(max_open_positions=max_open_positions, allow_shorts=allow_shorts)
        self.dry_run_executor = DryRunExecutor()
        self.testnet_executor = TestnetExecutor(client)

    async def exchange_precision(self, symbol: str) -> SymbolPrecision:
        exchange_info = await self.client.exchange_info(symbol)
        symbols = exchange_info.get("symbols", [])
        if not symbols:
            raise RuntimeError(f"Exchange metadata not found for {symbol}")
        metadata = symbols[0]
        filters = {item["filterType"]: item for item in metadata.get("filters", [])}
        lot_size = filters.get("LOT_SIZE", {})
        price_filter = filters.get("PRICE_FILTER", {})
        min_notional = filters.get("MIN_NOTIONAL") or filters.get("NOTIONAL", {})
        return SymbolPrecision(
            symbol=symbol,
            tick_size=float(price_filter.get("tickSize", 0.1)),
            step_size=float(lot_size.get("stepSize", 0.001)),
            min_qty=float(lot_size.get("minQty", 0.001)),
            min_notional=float(min_notional.get("notional", min_notional.get("minNotional", 5))),
        )

    async def runtime_cycle(self, *, symbol: str, interval: str, lookback: int = 200) -> dict:
        started_at = datetime.now(timezone.utc)
        runtime_state.heartbeat()

        try:
            candles = await self.client.fetch_klines(symbol, interval, limit=lookback)
            if not candles:
                runtime_state.record_runtime_failure("empty_market_data")
                return {"status": "no_data"}

            runtime_state.record_market_data()
            last_price = candles[-1].close
            intent = self._signal(symbol, candles)
            precision = await self.exchange_precision(symbol)
            reconciliation = await self.reconcile(symbol)
            safety = self.safety.evaluate(
                intent=intent,
                precision=precision,
                last_price=last_price,
                reconciliation=reconciliation,
                local_positions=runtime_state.simulated_open_positions,
            )
            execution = await self._execute(intent=intent, safety=safety)
            runtime_state.record_runtime_success()

            return {
                "status": "completed",
                "symbol": symbol,
                "mode": self.mode,
                "started_at": started_at.isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "intent": _intent_dict(intent),
                "safety": {
                    "allowed": safety.allowed,
                    "reason": safety.reason,
                    "normalized_quantity": safety.normalized_quantity,
                    "metadata": safety.metadata,
                },
                "execution": {
                    "mode": execution.mode,
                    "executed": execution.executed,
                    "reason": execution.reason,
                    "order": execution.order,
                },
                "precision": {
                    "tick_size": precision.tick_size,
                    "step_size": precision.step_size,
                    "min_qty": precision.min_qty,
                    "min_notional": precision.min_notional,
                },
                "reconciliation": reconciliation,
            }
        except Exception as exc:
            runtime_state.record_runtime_failure(f"runtime_cycle_failed:{exc.__class__.__name__}")
            raise

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
            open_orders=snapshot.open_orders,
        )

    async def recover(self, *, symbol: str) -> dict:
        reconciliation = await self.reconcile(symbol)
        if not reconciliation["healthy"]:
            runtime_state.pause("reconciliation_unhealthy")
        return reconciliation

    async def _execute(self, *, intent: ExecutionIntent, safety: SafetyDecision) -> ExecutionResult:
        if self.mode is ExecutionMode.DRY_RUN:
            return await self.dry_run_executor.execute(intent=intent, safety=safety)
        return await self.testnet_executor.execute(intent=intent, safety=safety)

    def _signal(self, symbol: str, candles: list[Candle]) -> ExecutionIntent:
        closes = pd.Series([c.close for c in candles])
        if len(closes) < 50:
            return ExecutionIntent(symbol=symbol, intent=ExecutionIntentType.HOLD, reason="insufficient_history")

        fast = ema(closes, period=20)
        slow = ema(closes, period=50)
        latest_fast = float(fast.iloc[-1])
        latest_slow = float(slow.iloc[-1])
        latest_price = float(closes.iloc[-1])
        recent_range = _average_true_range(candles[-14:])

        if recent_range <= 0:
            return ExecutionIntent(symbol=symbol, intent=ExecutionIntentType.HOLD, reason="invalid_volatility")

        quantity = round(max(0.001, 25 / latest_price), 6)

        if latest_fast > latest_slow:
            return ExecutionIntent(
                symbol=symbol,
                intent=ExecutionIntentType.OPEN_LONG,
                quantity=quantity,
                reason="ema_trend_long",
                metadata={"ema_fast": latest_fast, "ema_slow": latest_slow, "atr": recent_range},
            )

        if latest_fast < latest_slow:
            return ExecutionIntent(
                symbol=symbol,
                intent=ExecutionIntentType.OPEN_SHORT,
                quantity=quantity,
                reason="ema_trend_short",
                metadata={"ema_fast": latest_fast, "ema_slow": latest_slow, "atr": recent_range},
            )

        return ExecutionIntent(symbol=symbol, intent=ExecutionIntentType.HOLD, reason="neutral_market")


def _average_true_range(candles: list[Candle]) -> float:
    if not candles:
        return 0.0
    ranges = [c.high - c.low for c in candles]
    return sum(ranges) / len(ranges)


def _intent_dict(intent: ExecutionIntent) -> dict:
    return {
        "symbol": intent.symbol,
        "intent": intent.intent,
        "quantity": intent.quantity,
        "reason": intent.reason,
        "reduce_only": intent.reduce_only,
        "metadata": intent.metadata,
    }
