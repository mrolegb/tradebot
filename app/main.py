from __future__ import annotations

import argparse
import asyncio

from dotenv import load_dotenv

from app.config.loader import load_settings
from app.exchange.factory import build_market_data_client
from app.exchange.order_executor import OrderExecutor
from app.market.candles import candles_to_frame
from app.risk.cooldown_manager import CooldownManager
from app.risk.risk_manager import RiskManager
from app.storage.database import Database
from app.strategies import build_strategy
from app.types import PositionRequest, SignalSide
from app.utils.logger import configure_logging, get_logger


async def run_once(config_path: str) -> None:
    load_dotenv()
    settings = load_settings(config_path)
    configure_logging(settings.app.log_level)
    log = get_logger(__name__)

    strategy = build_strategy(settings.strategy.name, settings.strategy.params)
    risk_manager = RiskManager(settings.risk)
    cooldown_manager = CooldownManager(settings.cooldown)
    executor = OrderExecutor(mode=settings.app.mode)
    database = Database(settings.storage.sqlite_path)
    client = build_market_data_client(settings)

    try:
        for symbol in settings.trading.symbols:
            if cooldown_manager.is_active():
                log.info("cooldown_active", symbol=symbol)
                continue

            candles = await client.fetch_klines(symbol, settings.trading.timeframe)
            frame = candles_to_frame(candles)
            signal = strategy.generate_signal(symbol, frame)
            log.info("signal", symbol=symbol, side=signal.side.value, reason=signal.reason)

            if signal.side == SignalSide.HOLD or signal.price is None:
                continue

            stop_loss = signal.price * (0.99 if signal.side == SignalSide.BUY else 1.01)
            decision = risk_manager.evaluate(
                PositionRequest(
                    symbol=symbol,
                    side=signal.side,
                    entry_price=signal.price,
                    stop_loss_price=stop_loss,
                    account_equity=settings.trading.quote_balance,
                )
            )
            if not decision.allowed:
                log.info("risk_rejected", symbol=symbol, reason=decision.reason)
                continue

            order = await executor.market_order(symbol, signal.side, decision.quantity, signal.price)
            database.save_order(order)
            risk_manager.register_open_position()
            log.info("order_saved", symbol=symbol, side=order.side.value, quantity=order.quantity, mode=order.mode)
    finally:
        database.close()
        await client.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/global.yaml")
    args = parser.parse_args()
    asyncio.run(run_once(args.config))


if __name__ == "__main__":
    main()
