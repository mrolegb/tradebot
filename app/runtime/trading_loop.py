from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.config.loader import Settings
from app.exchange.binance_client import BinanceFuturesClient
from app.exchange.order_executor import BinanceOrderExecutor
from app.market.candles import candles_to_frame
from app.risk.risk_manager import RiskManager
from app.runtime.state import RuntimeState
from app.storage.database import Database
from app.strategies import build_strategy
from app.types import PositionRequest, SignalSide
from app.utils.logger import get_logger


@dataclass
class TradingLoopOptions:
    poll_seconds: float = 15.0
    once: bool = False


async def run_binance_trading_loop(settings: Settings, state: RuntimeState, options: TradingLoopOptions | None = None) -> None:
    options = options or TradingLoopOptions()
    log = get_logger(__name__)
    client = BinanceFuturesClient(settings.exchange)
    executor = BinanceOrderExecutor(client, settings.app.mode)
    database = Database(settings.storage.sqlite_path)
    strategy = build_strategy(settings.strategy.name, settings.strategy.params)
    risk_manager = RiskManager(settings.risk)

    try:
        await executor.load_exchange_rules()
        for symbol in settings.trading.symbols:
            await executor.prepare_symbol(symbol, settings.trading.leverage)

        while state.running:
            account = await client.account()
            equity = _account_equity(account, settings.trading.quote_balance)

            for symbol in settings.trading.symbols:
                candles = await client.fetch_klines(symbol, settings.trading.timeframe, limit=settings.simulation.candles_limit)
                frame = candles_to_frame(candles)
                signal = strategy.generate_signal(symbol, frame)
                if signal.side == SignalSide.HOLD or signal.price is None:
                    continue

                positions = await client.position_risk(symbol)
                current_position = _active_position(positions)
                if current_position:
                    current_side = SignalSide.BUY if float(current_position["positionAmt"]) > 0 else SignalSide.SELL
                    if current_side != signal.side:
                        close_order = await executor.close_position(symbol, current_position)
                        if close_order:
                            database.save_order(close_order)
                            database.delete_position(symbol)
                    continue

                stop_loss = signal.price * (0.99 if signal.side == SignalSide.BUY else 1.01)
                decision = risk_manager.evaluate(
                    PositionRequest(
                        symbol=symbol,
                        side=signal.side,
                        entry_price=signal.price,
                        stop_loss_price=stop_loss,
                        account_equity=equity,
                    )
                )
                if not decision.allowed:
                    log.info("risk_rejected", symbol=symbol, reason=decision.reason)
                    continue

                order = await executor.market_order(symbol, signal.side, decision.quantity, signal.price)
                database.save_order(order)
                if order.status in {"FILLED", "DRY_RUN", "NEW"}:
                    database.upsert_position(symbol, signal.side.value, order.quantity, order.price, settings.app.mode)

            state.simulated_open_positions = database.list_positions()
            database.save_runtime_state(state.register_loop_run())
            if options.once:
                break
            await asyncio.sleep(options.poll_seconds)
    finally:
        database.save_runtime_state(state.stop())
        database.close()
        await client.close()


def _account_equity(account: dict, fallback: float) -> float:
    for key in ("totalWalletBalance", "totalMarginBalance", "availableBalance"):
        if key in account:
            try:
                return float(account[key])
            except (TypeError, ValueError):
                pass
    return fallback


def _active_position(positions: list[dict]) -> dict | None:
    for position in positions:
        try:
            if abs(float(position.get("positionAmt", 0))) > 0:
                return position
        except (TypeError, ValueError):
            continue
    return None
