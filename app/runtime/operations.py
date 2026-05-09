from __future__ import annotations

import asyncio
import json
import sqlite3
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any

from app.runtime.engine import CandleRuntimeEngine
from app.runtime.state import runtime_state


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


class RuntimeRecordStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SUBMITTED = "submitted"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class SupervisorState(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class RuntimeRecord:
    symbol: str
    action: str
    quantity: float
    reason: str
    status: RuntimeRecordStatus = RuntimeRecordStatus.PENDING
    external_id: str | None = None
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReconciliationRecord:
    symbol: str
    healthy: bool
    missing_on_exchange: list[str]
    unknown_on_exchange: list[str]
    open_order_symbols: list[str]
    created_at: str = field(default_factory=utc_now_iso)
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExposurePolicy:
    allowed_symbols: set[str] = field(default_factory=lambda: {"BTCUSDT", "ETHUSDT"})
    max_open_positions: int = 1
    max_symbol_notional: float = 250.0
    max_total_notional: float = 500.0
    max_leverage: int = 1
    allow_shorts: bool = False
    action_cooldown_seconds: int = 60

    def validate_symbol(self, symbol: str) -> tuple[bool, str]:
        if symbol not in self.allowed_symbols:
            return False, "symbol_not_allowed"
        return True, "accepted"

    def validate_action(self, *, symbol: str, action: str) -> tuple[bool, str]:
        allowed, reason = self.validate_symbol(symbol)
        if not allowed:
            return allowed, reason
        if action == "open_short" and not self.allow_shorts:
            return False, "shorts_disabled"
        if action == "hold":
            return False, "hold_action"
        return True, "accepted"


@dataclass
class WatchdogStatus:
    heartbeat_at: str | None = None
    last_cycle_at: str | None = None
    last_error: str | None = None
    last_error_at: str | None = None
    consecutive_errors: int = 0

    def heartbeat(self) -> None:
        self.heartbeat_at = utc_now_iso()

    def record_cycle(self) -> None:
        self.last_cycle_at = utc_now_iso()
        self.consecutive_errors = 0
        self.last_error = None
        self.last_error_at = None

    def record_error(self, reason: str) -> None:
        self.consecutive_errors += 1
        self.last_error = reason
        self.last_error_at = utc_now_iso()

    def unhealthy(self, *, max_heartbeat_age_seconds: int = 180, max_errors: int = 3) -> bool:
        if self.consecutive_errors >= max_errors:
            return True
        if self.heartbeat_at is None:
            return True
        heartbeat = datetime.fromisoformat(self.heartbeat_at)
        return (utc_now() - heartbeat).total_seconds() > max_heartbeat_age_seconds


class RuntimeStore:
    def __init__(self, sqlite_path: str | Path = "data/tradebot.sqlite3") -> None:
        self.sqlite_path = Path(sqlite_path)
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.sqlite_path)

    def _init_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS runtime_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    action TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    reason TEXT NOT NULL,
                    status TEXT NOT NULL,
                    external_id TEXT,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS runtime_reconciliation_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    healthy INTEGER NOT NULL,
                    missing_on_exchange_json TEXT NOT NULL,
                    unknown_on_exchange_json TEXT NOT NULL,
                    open_order_symbols_json TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def add_record(self, record: RuntimeRecord) -> int:
        payload = json.dumps(_jsonable(record.payload), sort_keys=True)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO runtime_records (
                    symbol, action, quantity, reason, status, external_id,
                    payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.symbol,
                    record.action,
                    record.quantity,
                    record.reason,
                    record.status,
                    record.external_id,
                    payload,
                    record.created_at,
                    record.updated_at,
                ),
            )
            return int(cursor.lastrowid)

    def recent_record(self, *, symbol: str, action: str, within_seconds: int) -> dict[str, Any] | None:
        threshold = (utc_now() - timedelta(seconds=within_seconds)).isoformat()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, symbol, action, quantity, reason, status, created_at, updated_at
                FROM runtime_records
                WHERE symbol = ? AND action = ? AND created_at >= ?
                ORDER BY id DESC LIMIT 1
                """,
                (symbol, action, threshold),
            ).fetchone()
        if row is None:
            return None
        return {
            "id": row[0],
            "symbol": row[1],
            "action": row[2],
            "quantity": row[3],
            "reason": row[4],
            "status": row[5],
            "created_at": row[6],
            "updated_at": row[7],
        }

    def add_reconciliation(self, record: ReconciliationRecord) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO runtime_reconciliation_records (
                    symbol, healthy, missing_on_exchange_json,
                    unknown_on_exchange_json, open_order_symbols_json,
                    payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.symbol,
                    1 if record.healthy else 0,
                    json.dumps(record.missing_on_exchange, sort_keys=True),
                    json.dumps(record.unknown_on_exchange, sort_keys=True),
                    json.dumps(record.open_order_symbols, sort_keys=True),
                    json.dumps(_jsonable(record.payload), sort_keys=True),
                    record.created_at,
                ),
            )
            return int(cursor.lastrowid)

    def pending_records(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, symbol, action, quantity, reason, status, created_at, updated_at
                FROM runtime_records
                WHERE status IN ('pending', 'unknown', 'submitted')
                ORDER BY id DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "id": row[0],
                "symbol": row[1],
                "action": row[2],
                "quantity": row[3],
                "reason": row[4],
                "status": row[5],
                "created_at": row[6],
                "updated_at": row[7],
            }
            for row in rows
        ]


class DuplicateActionGuard:
    def __init__(self, store: RuntimeStore, policy: ExposurePolicy) -> None:
        self.store = store
        self.policy = policy

    def allowed(self, *, symbol: str, action: str) -> tuple[bool, str]:
        recent = self.store.recent_record(
            symbol=symbol,
            action=action,
            within_seconds=self.policy.action_cooldown_seconds,
        )
        if recent is not None:
            return False, "duplicate_action_cooldown"
        return True, "accepted"


class RuntimeSupervisor:
    def __init__(
        self,
        engine: CandleRuntimeEngine,
        *,
        store: RuntimeStore | None = None,
        policy: ExposurePolicy | None = None,
        cycle_interval_seconds: int = 60,
    ) -> None:
        self.engine = engine
        self.store = store or RuntimeStore()
        self.policy = policy or ExposurePolicy()
        self.duplicate_guard = DuplicateActionGuard(self.store, self.policy)
        self.watchdog = WatchdogStatus()
        self.state = SupervisorState.IDLE
        self.cycle_interval_seconds = cycle_interval_seconds
        self.last_cycle: dict[str, Any] | None = None

    async def run_once(self, *, symbol: str, interval: str, lookback: int = 200) -> dict[str, Any]:
        self.state = SupervisorState.RUNNING
        self.watchdog.heartbeat()
        try:
            cycle = await self.engine.runtime_cycle(symbol=symbol, interval=interval, lookback=lookback)
            self.last_cycle = cycle
            self._persist_cycle(cycle)
            self.watchdog.record_cycle()
            return self.snapshot()
        except Exception as exc:
            self.watchdog.record_error(f"{exc.__class__.__name__}: {exc}")
            runtime_state.record_runtime_failure(f"supervisor_cycle_failed:{exc.__class__.__name__}")
            self.state = SupervisorState.ERROR
            raise

    async def run_forever(self, *, symbol: str, interval: str, lookback: int = 200) -> None:
        self.state = SupervisorState.RUNNING
        while self.state is SupervisorState.RUNNING:
            await self.run_once(symbol=symbol, interval=interval, lookback=lookback)
            if self.watchdog.unhealthy():
                self.state = SupervisorState.PAUSED
                runtime_state.pause("supervisor_watchdog_unhealthy")
                break
            await asyncio.sleep(self.cycle_interval_seconds)

    def stop(self) -> None:
        self.state = SupervisorState.STOPPING

    def pending_recovery(self) -> dict[str, Any]:
        return {
            "pending_records": self.store.pending_records(),
            "watchdog": asdict(self.watchdog),
            "state": self.state,
        }

    def snapshot(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "watchdog": asdict(self.watchdog),
            "last_cycle": self.last_cycle,
            "pending_recovery": self.pending_recovery(),
        }

    def _persist_cycle(self, cycle: dict[str, Any]) -> None:
        intent = cycle.get("intent") or {}
        safety = cycle.get("safety") or {}
        operation = cycle.get("execution") or {}
        reconciliation = cycle.get("reconciliation") or {}

        symbol = intent.get("symbol", cycle.get("symbol", "UNKNOWN"))
        action = str(intent.get("intent", "hold"))
        quantity = float(intent.get("quantity", 0) or 0)
        policy_allowed, policy_reason = self.policy.validate_action(symbol=symbol, action=action)
        duplicate_allowed, duplicate_reason = self.duplicate_guard.allowed(symbol=symbol, action=action)

        status = RuntimeRecordStatus.REJECTED
        reason = operation.get("reason") or safety.get("reason") or intent.get("reason", "")
        if operation.get("executed") and policy_allowed and duplicate_allowed:
            status = RuntimeRecordStatus.ACCEPTED
        elif not policy_allowed:
            reason = policy_reason
        elif not duplicate_allowed:
            reason = duplicate_reason

        self.store.add_record(
            RuntimeRecord(
                symbol=symbol,
                action=action,
                quantity=quantity,
                reason=reason,
                status=status,
                payload={"cycle": cycle, "policy_allowed": policy_allowed, "duplicate_allowed": duplicate_allowed},
            )
        )

        self.store.add_reconciliation(
            ReconciliationRecord(
                symbol=cycle.get("symbol", symbol),
                healthy=bool(reconciliation.get("healthy", False)),
                missing_on_exchange=list(reconciliation.get("missing_on_exchange", [])),
                unknown_on_exchange=list(reconciliation.get("unknown_on_exchange", [])),
                open_order_symbols=list(reconciliation.get("open_order_symbols", [])),
                payload=reconciliation,
            )
        )


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, StrEnum):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    return value
