from app.config.loader import RiskConfig
from app.risk.risk_manager import RiskManager
from app.types import PositionRequest, SignalSide


def test_position_size_uses_configured_risk() -> None:
    manager = RiskManager(RiskConfig(max_risk_per_trade_percent=1, max_open_positions=1))

    decision = manager.evaluate(
        PositionRequest(
            symbol="BTCUSDT",
            side=SignalSide.BUY,
            entry_price=100,
            stop_loss_price=99,
            account_equity=1000,
        )
    )

    assert decision.allowed
    assert decision.quantity == 10

