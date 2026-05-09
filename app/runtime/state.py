from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.runtime.status import RuntimeStatus, RuntimeStatusModel


@dataclass
class RuntimeState:
    running: bool = False
    selected_profile: str = "simulation"
    selected_strategy: str = "breakout"
    loop_count: int = 0
    last_run_at: str | None = None
    last_action: str = "initialized"
    last_action_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    simulated_open_positions: list[dict] = field(default_factory=list)
    runtime_status: RuntimeStatusModel = field(default_factory=RuntimeStatusModel)

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
        self.runtime_status.set_status(RuntimeStatus.RUNNING, "runtime_started")
        return self._record("started")

    def stop(self) -> dict:
        self.running = False
        self.runtime_status.set_status(RuntimeStatus.STOPPED, "runtime_stopped")
        return self._record("stopped")

    def pause(self, reason: str) -> dict:
        self.running = False
        self.runtime_status.set_status(RuntimeStatus.PAUSED, reason)
        return self._record(f"paused:{reason}")

    def error(self, reason: str) -> dict:
        self.running = False
        self.runtime_status.set_status(RuntimeStatus.ERROR, reason)
        return self._record(f"error:{reason}")

    def register_loop_run(self) -> dict:
        self.loop_count += 1
        self.last_run_at = datetime.now(timezone.utc).isoformat()
        return self._record("simulation_loop_run")

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
        }

    def _record(self, action: str) -> dict:
        self.last_action = action
        self.last_action_at = datetime.now(timezone.utc).isoformat()
        return self.snapshot()


runtime_state = RuntimeState()
