from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.config.loader import CooldownConfig


class CooldownManager:
    def __init__(self, config: CooldownConfig) -> None:
        self.config = config
        self.consecutive_losses = 0
        self.cooldown_until: datetime | None = None

    def is_active(self, now: datetime | None = None) -> bool:
        if not self.config.enabled or self.cooldown_until is None:
            return False
        current = now or datetime.now(timezone.utc)
        return current < self.cooldown_until

    def register_trade_result(self, pnl: float, now: datetime | None = None) -> None:
        current = now or datetime.now(timezone.utc)
        if pnl >= 0:
            self.consecutive_losses = 0
            self.cooldown_until = None
            return

        self.consecutive_losses += 1
        minutes = self.config.after_loss_minutes
        if self.consecutive_losses >= 3:
            minutes = self.config.after_3_losses_minutes
        elif self.consecutive_losses >= 2:
            minutes = self.config.after_2_losses_minutes
        self.cooldown_until = current + timedelta(minutes=minutes)

