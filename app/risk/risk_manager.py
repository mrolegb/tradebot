from __future__ import annotations

from app.config.loader import RiskConfig
from app.types import PositionRequest, RiskDecision, SignalSide


class RiskManager:
    def __init__(self, config: RiskConfig) -> None:
        self.config = config
        self.open_positions = 0
        self.realized_daily_pnl = 0.0

    def evaluate(self, request: PositionRequest) -> RiskDecision:
        if request.side == SignalSide.HOLD:
            return RiskDecision(False, reason="hold signal")
        if self.open_positions >= self.config.max_open_positions:
            return RiskDecision(False, reason="max open positions reached")

        max_daily_loss = request.account_equity * self.config.max_daily_loss_percent / 100
        if self.realized_daily_pnl <= -max_daily_loss:
            return RiskDecision(False, reason="max daily loss reached")

        risk_per_unit = abs(request.entry_price - request.stop_loss_price)
        if risk_per_unit <= 0:
            return RiskDecision(False, reason="invalid stop loss")

        risk_amount = request.account_equity * self.config.max_risk_per_trade_percent / 100
        quantity = risk_amount / risk_per_unit
        if quantity <= 0:
            return RiskDecision(False, reason="position size is zero")
        return RiskDecision(True, quantity=quantity, reason="risk accepted")

    def register_open_position(self) -> None:
        self.open_positions += 1

    def register_close_position(self, pnl: float) -> None:
        self.open_positions = max(0, self.open_positions - 1)
        self.realized_daily_pnl += pnl

