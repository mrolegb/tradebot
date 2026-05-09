from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum


class RuntimeStatus(StrEnum):
    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class RuntimeStatusModel:
    status: RuntimeStatus = RuntimeStatus.IDLE
    reason: str | None = None
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def set_status(self, status: RuntimeStatus, reason: str | None = None) -> None:
        self.status = status
        self.reason = reason
        self.updated_at = datetime.now(timezone.utc).isoformat()
