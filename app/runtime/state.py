from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from app.runtime.status import RuntimeStatus, RuntimeStatusModel
from app.runtime.storage import RuntimeStorage


MAX_CONSECUTIVE_FAILURES = 3
DEFAULT_BACKOFF_MINUTES = 15
STALE_DATA_SECONDS = 120


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


@dataclass
class RuntimeHealth:
    heartbeat_at: str | None = None
    consecutive_failures: int = 0
    last_failure: str | None = None
    last_failure_at: str | None = None
    pause_until: str | None = None
    last_market_data_at: str | None = None
    last_latency_ms: float | None = None

    def heartbeat(self) -> None:
        self.heartbeat_at = _now_iso()

    def record_market_data(self, latency_ms: float | None = None) -> None:
        self.last_market_data_at = _now_iso()
        self.last_latency_ms = latency_ms

    def record_success(self) -> None:
        self.consecutive_failures = 0
        self.last_failure = None
        self.last_failure_at = None

    def record_failure(self, reason: str) -> None:
        self.consecutive_failures += 1
        self.last_failure = reason
        self.last_failure_at = _now_iso()

    def set_backoff(self, minutes: int = DEFAULT_BACKOFF_MINUTES) -> None:
        self.pause_until = (_now() + timedelta(minutes=minutes)).isoformat()

    def clear_backoff(self) -> None:
        self.pause_until = None


@dataclass
class RuntimeState:
    running: bool = False
    selected_profile: str = "simulation"
    selected_strategy: str = "breakout"
    loop_count: int = 0
    last_run_at: str | None = None
    last_action: str = "initialized"
    last_action_at: str = field(default_factory=_now_iso)
    simulated_open_positions: list[dict] = field(default_factory=list)
    runtime_status: RuntimeStatusModel = field(default_factory=RuntimeStatusModel)
    health: RuntimeHealth = field(default_factory=RuntimeHealth)
    storage: RuntimeStorage = field(default_factory=RuntimeStorage, repr=False)

    def __post_init__(self) -> None:
        self._restore_snapshot()
        self._persist("initialized")

    def select_profile(self, profile: str) -> dict:
        self.selected_profile = profile
        self.running = False
        self.runtime_status.set_status(RuntimeStatus.IDLE, f"profile_selected:{profile}")
        return self._record(f"profile_selected:{profile}")

    def select_strategy(self, strategy: str) -> dict:
        self.selected_strategy = strategy
        return self._record(f"strategy_selected:{strategy}")

    def start(self) -> dict:
        self.running = True
        self.health.clear_backoff()
        self.health.heartbeat()
        self.runtime_status.set_status(RuntimeStatus.RUNNING, "runtime_started")
        return self._record("started")

    def stop(self) -> dict:
        self.running = False
        self.runtime_status.set_status(RuntimeStatus.STOPPED, "runtime_stopped")
        return self._record("stopped")

    def pause(self, reason: str, *, minutes: int = DEFAULT_BACKOFF_MINUTES) -> dict:
        self.running = False
        self.health.set_backoff(minutes)
        self.runtime_status.set_status(RuntimeStatus.PAUSED, reason)
        return self._record(f"paused:{reason}")

    def error(self, reason: str) -> dict:
        self.running = False
        self.health.record_failure(reason)
        self.runtime_status.set_status(RuntimeStatus.ERROR, reason)
        return self._record(f"error:{reason}")

    def heartbeat(self) -> dict:
        self.health.heartbeat()
        return self._record("heartbeat")

    def record_market_data(self, *, latency_ms: float | None = None) -> dict:
        self.health.record_market_data(latency_ms)
        return self._record("market_data_received")

    def record_runtime_success(self) -> dict:
        self.health.record_success()
        return self._record("runtime_success")

    def record_runtime_failure(self, reason: str) -> dict:
        self.health.record_failure(reason)
        if self.health.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            return self.pause(reason=f"failsafe:{reason}")
        return self._record(f"runtime_failure:{reason}")

    def stale_market_data(self, *, max_age_seconds: int = STALE_DATA_SECONDS) -> bool:
        if self.health.last_market_data_at is None:
            return True
        last_seen = datetime.fromisoformat(self.health.last_market_data_at)
        return (_now() - last_seen).total_seconds() > max_age_seconds

    def register_loop_run(self) -> dict:
        self.loop_count += 1
        self.last_run_at = _now_iso()
        self.health.heartbeat()
        return self._record("simulation_loop_run")

    def audit_events(self, limit: int = 100) -> list[dict]:
        return self.storage.audit_events(limit=limit)

    def snapshot(self) -> dict:
        return {
            "running": self.running,
            "selected_profile": self.selected_profile,
            "selected_strategy": self.selected_strategy,
            "loop_count": self.loop_count,
            "last_run_at": self.last_run_at,
            "last_action": self.last_action,
            "last_action_at": self.last_action_at,
            "simulated_open_positions": self.simulated_open_positions,
            "runtime_status": {
                "status": self.runtime_status.status,
                "reason": self.runtime_status.reason,
                "updated_at": self.runtime_status.updated_at,
            },
            "health": {
                "heartbeat_at": self.health.heartbeat_at,
                "consecutive_failures": self.health.consecutive_failures,
                "last_failure": self.health.last_failure,
                "last_failure_at": self.health.last_failure_at,
                "pause_until": self.health.pause_until,
                "last_market_data_at": self.health.last_market_data_at,
                "last_latency_ms": self.health.last_latency_ms,
                "stale_market_data": self.stale_market_data(),
            },
        }

    def _record(self, action: str) -> dict:
        self.last_action = action
        self.last_action_at = _now_iso()
        snapshot = self.snapshot()
        self._persist(action)
        return snapshot

    def _persist(self, action: str) -> None:
        self.storage.save_snapshot(self.snapshot(), action=action)

    def _restore_snapshot(self) -> None:
        snapshot = self.storage.load_snapshot()
        if not snapshot:
            return
        self.running = False
        self.selected_profile = snapshot.get("selected_profile", self.selected_profile)
        self.selected_strategy = snapshot.get("selected_strategy", self.selected_strategy)
        self.loop_count = snapshot.get("loop_count", self.loop_count)
        self.last_run_at = snapshot.get("last_run_at", self.last_run_at)
        self.simulated_open_positions = snapshot.get("simulated_open_positions", [])
        self.last_action = "restored"
        self.last_action_at = _now_iso()

        status = snapshot.get("runtime_status", {})
        status_value = status.get("status", RuntimeStatus.IDLE)
        try:
            restored_status = RuntimeStatus(status_value)
        except ValueError:
            restored_status = RuntimeStatus.IDLE
        self.runtime_status.set_status(restored_status, status.get("reason"))

        health = snapshot.get("health", {})
        self.health = RuntimeHealth(
            heartbeat_at=health.get("heartbeat_at"),
            consecutive_failures=health.get("consecutive_failures", 0),
            last_failure=health.get("last_failure"),
            last_failure_at=health.get("last_failure_at"),
            pause_until=health.get("pause_until"),
            last_market_data_at=health.get("last_market_data_at"),
            last_latency_ms=health.get("last_latency_ms"),
        )


runtime_state = RuntimeState()
