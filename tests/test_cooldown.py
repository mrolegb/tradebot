from datetime import datetime, timezone

from app.config.loader import CooldownConfig
from app.risk.cooldown_manager import CooldownManager


def test_cooldown_after_loss() -> None:
    manager = CooldownManager(CooldownConfig(after_loss_minutes=10))
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    manager.register_trade_result(-1, now=now)

    assert manager.is_active(now=now)

