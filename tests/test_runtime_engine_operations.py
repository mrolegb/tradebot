from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from app.runtime.engine import (
    CandleRuntimeEngine,
    DryRunExecutor,
    ExecutionIntent,
    ExecutionIntentType,
    ExecutionMode,
    ExecutionSafety,
    RuntimeReconciliation,
    SymbolPrecision,
)
from app.runtime.operations import (
    DuplicateActionGuard,
    ExposurePolicy,
    RuntimeRecord,
    RuntimeRecordStatus,
    RuntimeStore,
    RuntimeSupervisor,
    WatchdogStatus,
)
from app.types import Candle


class FakeClient:
    async def fetch_klines(self, symbol: str, interval: str, limit: int = 200):
        return [
            Candle(
                symbol=symbol,
                open_time=datetime.now(timezone.utc),
                open=100 + index,
                high=101 + index,
                low=99 + index,
                close=100 + index,
                volume=10,
            )
            for index in range(limit)
        ]

    async def exchange_info(self, symbol: str | None = None):
        return {
            "symbols": [
                {
                    "symbol": symbol or "BTCUSDT",
                    "filters": [
                        {"filterType": "PRICE_FILTER", "tickSize": "0.10"},
                        {"filterType": "LOT_SIZE", "stepSize": "0.001", "minQty": "0.001"},
                        {"filterType": "MIN_NOTIONAL", "notional": "5"},
                    ],
                }
            ]
        }

    async def positions(self, symbol: str | None = None):
        return []

    async def open_orders(self, symbol: str | None = None):
        return []

    async def place_order(self, **kwargs):
        return {"status": "NEW", **kwargs}


class EmptyDataClient(FakeClient):
    async def fetch_klines(self, symbol: str, interval: str, limit: int = 200):
        return []


def test_symbol_precision_normalizes_and_validates() -> None:
    precision = SymbolPrecision("BTCUSDT", tick_size=0.1, step_size=0.001, min_qty=0.001, min_notional=5)

    assert precision.normalize_price(101.27) == pytest.approx(101.2)
    assert precision.normalize_quantity(0.123456) == pytest.approx(0.123)
    assert precision.validate_quantity(0.001) is True
    assert precision.validate_notional(quantity=0.1, price=100) is True


def test_reconciliation_detects_unknown_exchange_positions() -> None:
    reconciliation = RuntimeReconciliation().compare(
        local_positions=[],
        exchange_positions=[{"symbol": "BTCUSDT", "positionAmt": "0.1"}],
        open_orders=[{"symbol": "BTCUSDT"}],
    )

    assert reconciliation["healthy"] is False
    assert reconciliation["unknown_on_exchange"] == ["BTCUSDT"]
    assert reconciliation["open_order_symbols"] == ["BTCUSDT"]


def test_safety_blocks_shorts_by_default() -> None:
    safety = ExecutionSafety(allow_shorts=False)
    decision = safety.evaluate(
        intent=ExecutionIntent("BTCUSDT", ExecutionIntentType.OPEN_SHORT, quantity=0.01),
        precision=SymbolPrecision("BTCUSDT", tick_size=0.1, step_size=0.001, min_qty=0.001, min_notional=5),
        last_price=1000,
        reconciliation={"healthy": True},
        local_positions=[],
    )

    assert decision.allowed is False
    assert decision.reason == "shorts_disabled"


def test_safety_accepts_normalized_long() -> None:
    safety = ExecutionSafety(allow_shorts=False)
    decision = safety.evaluate(
        intent=ExecutionIntent("BTCUSDT", ExecutionIntentType.OPEN_LONG, quantity=0.01234),
        precision=SymbolPrecision("BTCUSDT", tick_size=0.1, step_size=0.001, min_qty=0.001, min_notional=5),
        last_price=1000,
        reconciliation={"healthy": True},
        local_positions=[],
    )

    assert decision.allowed is True
    assert decision.normalized_quantity == pytest.approx(0.012)


def test_dry_run_executor_records_safe_result() -> None:
    async def run() -> None:
        safety = ExecutionSafety().evaluate(
            intent=ExecutionIntent("BTCUSDT", ExecutionIntentType.OPEN_LONG, quantity=0.01),
            precision=SymbolPrecision("BTCUSDT", tick_size=0.1, step_size=0.001, min_qty=0.001, min_notional=5),
            last_price=1000,
            reconciliation={"healthy": True},
            local_positions=[],
        )
        result = await DryRunExecutor().execute(
            intent=ExecutionIntent("BTCUSDT", ExecutionIntentType.OPEN_LONG, quantity=0.01),
            safety=safety,
        )
        assert result.mode == ExecutionMode.DRY_RUN
        assert result.executed is True
        assert result.order["symbol"] == "BTCUSDT"

    asyncio.run(run())


def test_runtime_cycle_returns_intent_safety_and_reconciliation() -> None:
    async def run() -> None:
        engine = CandleRuntimeEngine(FakeClient(), mode=ExecutionMode.DRY_RUN, allow_shorts=False)
        result = await engine.runtime_cycle(symbol="BTCUSDT", interval="5m", lookback=80)

        assert result["status"] == "completed"
        assert "intent" in result
        assert "safety" in result
        assert "reconciliation" in result
        assert result["execution"]["mode"] == ExecutionMode.DRY_RUN

    asyncio.run(run())


def test_runtime_cycle_handles_empty_market_data() -> None:
    async def run() -> None:
        engine = CandleRuntimeEngine(EmptyDataClient(), mode=ExecutionMode.DRY_RUN)
        result = await engine.runtime_cycle(symbol="BTCUSDT", interval="5m", lookback=80)

        assert result["status"] == "no_data"

    asyncio.run(run())


def test_runtime_store_persists_records_and_detects_duplicates(tmp_path) -> None:
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    policy = ExposurePolicy(action_cooldown_seconds=120)
    guard = DuplicateActionGuard(store, policy)

    store.add_record(RuntimeRecord(symbol="BTCUSDT", action="open_long", quantity=0.1, reason="test", status=RuntimeRecordStatus.ACCEPTED))

    allowed, reason = guard.allowed(symbol="BTCUSDT", action="open_long")
    pending = store.pending_records()

    assert allowed is False
    assert reason == "duplicate_action_cooldown"
    assert pending == []


def test_exposure_policy_blocks_disallowed_symbols_and_shorts() -> None:
    policy = ExposurePolicy(allowed_symbols={"BTCUSDT"}, allow_shorts=False)

    assert policy.validate_action(symbol="ETHUSDT", action="open_long") == (False, "symbol_not_allowed")
    assert policy.validate_action(symbol="BTCUSDT", action="open_short") == (False, "shorts_disabled")
    assert policy.validate_action(symbol="BTCUSDT", action="open_long") == (True, "accepted")


def test_watchdog_becomes_unhealthy_after_errors() -> None:
    watchdog = WatchdogStatus()
    watchdog.heartbeat()
    watchdog.record_error("one")
    watchdog.record_error("two")
    watchdog.record_error("three")

    assert watchdog.unhealthy() is True


def test_supervisor_persists_cycle_snapshot(tmp_path) -> None:
    async def run() -> None:
        store = RuntimeStore(tmp_path / "runtime.sqlite3")
        supervisor = RuntimeSupervisor(
            CandleRuntimeEngine(FakeClient(), mode=ExecutionMode.DRY_RUN),
            store=store,
            policy=ExposurePolicy(allowed_symbols={"BTCUSDT"}, allow_shorts=False),
        )

        snapshot = await supervisor.run_once(symbol="BTCUSDT", interval="5m", lookback=80)

        assert snapshot["state"] == "running"
        assert snapshot["last_cycle"]["status"] == "completed"
        assert "pending_records" in snapshot["pending_recovery"]

    asyncio.run(run())
