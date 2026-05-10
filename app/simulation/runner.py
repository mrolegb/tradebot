from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config.loader import Settings
from app.exchange.factory import build_market_data_client
from app.market.candles import candles_to_frame
from app.simulation.report import write_csv, write_json
from app.strategies import build_strategy
from app.types import SignalSide


@dataclass
class OpenPosition:
    symbol: str
    side: SignalSide
    entry_time: str
    entry_price: float
    raw_entry_price: float
    quantity: float
    stop_loss: float
    take_profit: float
    entry_fee: float


async def run_simulation(settings: Settings) -> dict[str, Any]:
    client = build_market_data_client(settings)
    strategy = build_strategy(settings.strategy.name, settings.strategy.params)

    all_trades: list[dict[str, Any]] = []
    all_signals: list[dict[str, Any]] = []
    equity_curve: list[dict[str, Any]] = []
    balance = settings.trading.quote_balance
    peak_balance = balance
    trading_halted = False

    try:
        for symbol in settings.trading.symbols:
            candles = await client.fetch_klines(symbol, settings.trading.timeframe, settings.simulation.candles_limit)
            frame = candles_to_frame(candles)
            position: OpenPosition | None = None
            cooldown_bars = 0

            warmup = max(30, int(settings.strategy.params.get("slow_period", 0)) + 2)
            for end in range(warmup, len(frame) + 1):
                window = frame.iloc[:end]
                latest = window.iloc[-1]
                price = float(latest["close"])
                high = float(latest["high"])
                low = float(latest["low"])
                current_time = latest["open_time"].isoformat()
                signal = strategy.generate_signal(symbol, window)

                all_signals.append(
                    {
                        "time": current_time,
                        "symbol": symbol,
                        "price": price,
                        "side": signal.side.value,
                        "confidence": signal.confidence,
                        "reason": signal.reason,
                    }
                )

                if trading_halted:
                    signal = signal.__class__(symbol, SignalSide.HOLD, 0.0, "max daily loss reached", price)

                if cooldown_bars > 0:
                    cooldown_bars -= 1
                    if position is None:
                        continue

                if not trading_halted and position is None and signal.side in {SignalSide.BUY, SignalSide.SELL}:
                    position = _open_position(settings, symbol, signal.side, current_time, price, balance)
                    continue

                if position is not None:
                    exit_reason, exit_price = _exit_reason_and_price(position, signal.side, price, high, low)
                    if exit_reason:
                        trade = _close_position(position, current_time, exit_price, exit_reason, settings)
                        balance += trade["net_pnl"]
                        peak_balance = max(peak_balance, balance)
                        trade["balance_after"] = balance
                        all_trades.append(trade)
                        if trade["net_pnl"] < 0:
                            cooldown_bars = _cooldown_bars(settings)
                        if _max_daily_loss_reached(settings, balance):
                            trading_halted = True
                        position = None

                equity = balance + (_unrealized_pnl(position, price) if position else 0.0)
                peak_balance = max(peak_balance, equity)
                equity_curve.append(
                    {
                        "time": current_time,
                        "symbol": symbol,
                        "balance": balance,
                        "equity": equity,
                        "drawdown": equity - peak_balance,
                        "drawdown_percent": _percent(equity - peak_balance, peak_balance),
                    }
                )

            if position is not None:
                latest = frame.iloc[-1]
                trade = _close_position(
                    position,
                    latest["open_time"].isoformat(),
                    float(latest["close"]),
                    "end_of_data",
                    settings,
                )
                balance += trade["net_pnl"]
                peak_balance = max(peak_balance, balance)
                trade["balance_after"] = balance
                all_trades.append(trade)
    finally:
        await client.close()

    summary = _build_summary(settings, all_trades, equity_curve, balance)
    output_dir = Path(settings.simulation.output_dir)
    write_json(output_dir / "summary.json", summary)
    write_csv(output_dir / "trades.csv", all_trades)
    write_csv(output_dir / "signals.csv", all_signals)
    write_csv(output_dir / "equity_curve.csv", equity_curve)
    return summary


def _open_position(
    settings: Settings,
    symbol: str,
    side: SignalSide,
    entry_time: str,
    raw_entry_price: float,
    balance: float,
) -> OpenPosition:
    entry_price = _execution_price(raw_entry_price, side, is_entry=True, settings=settings)
    stop_multiplier = 1 - settings.simulation.stop_loss_percent / 100
    take_profit_multiplier = 1 + settings.simulation.take_profit_percent / 100
    if side == SignalSide.SELL:
        stop_multiplier = 1 + settings.simulation.stop_loss_percent / 100
        take_profit_multiplier = 1 - settings.simulation.take_profit_percent / 100

    stop_loss = entry_price * stop_multiplier
    take_profit = entry_price * take_profit_multiplier
    risk_amount = balance * settings.risk.max_risk_per_trade_percent / 100
    quantity = risk_amount / abs(entry_price - stop_loss)
    entry_fee = entry_price * quantity * settings.simulation.fee_rate_percent / 100

    return OpenPosition(
        symbol=symbol,
        side=side,
        entry_time=entry_time,
        entry_price=entry_price,
        raw_entry_price=raw_entry_price,
        quantity=quantity,
        stop_loss=stop_loss,
        take_profit=take_profit,
        entry_fee=entry_fee,
    )


def _exit_reason(position: OpenPosition, signal_side: SignalSide, price: float) -> str | None:
    reason, _ = _exit_reason_and_price(position, signal_side, price, price, price)
    return reason


def _exit_reason_and_price(
    position: OpenPosition,
    signal_side: SignalSide,
    price: float,
    high: float,
    low: float,
) -> tuple[str | None, float]:
    if position.side == SignalSide.BUY:
        if low <= position.stop_loss:
            return "stop_loss", position.stop_loss
        if high >= position.take_profit:
            return "take_profit", position.take_profit
        if signal_side == SignalSide.SELL:
            return "reverse_signal", price
    if position.side == SignalSide.SELL:
        if high >= position.stop_loss:
            return "stop_loss", position.stop_loss
        if low <= position.take_profit:
            return "take_profit", position.take_profit
        if signal_side == SignalSide.BUY:
            return "reverse_signal", price
    return None, price


def _unrealized_pnl(position: OpenPosition, mark_price: float) -> float:
    if position.side == SignalSide.BUY:
        return (mark_price - position.entry_price) * position.quantity
    return (position.entry_price - mark_price) * position.quantity


def _close_position(position: OpenPosition, exit_time: str, raw_exit_price: float, exit_reason: str, settings: Settings) -> dict[str, Any]:
    exit_price = _execution_price(raw_exit_price, position.side, is_entry=False, settings=settings)
    if position.side == SignalSide.BUY:
        gross_pnl = (exit_price - position.entry_price) * position.quantity
    else:
        gross_pnl = (position.entry_price - exit_price) * position.quantity

    exit_fee = exit_price * position.quantity * settings.simulation.fee_rate_percent / 100
    funding = _funding_cost(position, exit_time, settings)
    fees = position.entry_fee + exit_fee + funding
    net_pnl = gross_pnl - fees
    return {
        "symbol": position.symbol,
        "side": position.side.value,
        "entry_time": position.entry_time,
        "exit_time": exit_time,
        "raw_entry_price": position.raw_entry_price,
        "raw_exit_price": raw_exit_price,
        "entry_price": position.entry_price,
        "exit_price": exit_price,
        "quantity": position.quantity,
        "stop_loss": position.stop_loss,
        "take_profit": position.take_profit,
        "exit_reason": exit_reason,
        "gross_pnl": gross_pnl,
        "fees": fees,
        "funding": funding,
        "net_pnl": net_pnl,
        "return_percent": _percent(net_pnl, position.entry_price * position.quantity),
        "win": net_pnl > 0,
    }


def _build_summary(settings: Settings, trades: list[dict[str, Any]], equity_curve: list[dict[str, Any]], final_balance: float) -> dict[str, Any]:
    wins = [trade for trade in trades if trade["net_pnl"] > 0]
    losses = [trade for trade in trades if trade["net_pnl"] <= 0]
    gross_profit = sum(trade["net_pnl"] for trade in wins)
    gross_loss = abs(sum(trade["net_pnl"] for trade in losses))
    net_pnl = final_balance - settings.trading.quote_balance
    max_drawdown = min((row["drawdown"] for row in equity_curve), default=0.0)
    max_drawdown_percent = min((row["drawdown_percent"] for row in equity_curve), default=0.0)

    return {
        "mode": settings.app.mode,
        "strategy": settings.strategy.name,
        "symbols": settings.trading.symbols,
        "timeframe": settings.trading.timeframe,
        "candles_limit": settings.simulation.candles_limit,
        "seed": settings.simulation.seed,
        "market_regime": settings.simulation.market_regime,
        "costs": {
            "fee_rate_percent": settings.simulation.fee_rate_percent,
            "spread_percent": settings.simulation.spread_percent,
            "slippage_percent": settings.simulation.slippage_percent,
            "funding_rate_percent": settings.simulation.funding_rate_percent,
            "funding_interval_hours": settings.simulation.funding_interval_hours,
        },
        "initial_balance": settings.trading.quote_balance,
        "final_balance": final_balance,
        "net_pnl": net_pnl,
        "return_percent": _percent(net_pnl, settings.trading.quote_balance),
        "total_trades": len(trades),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "win_rate_percent": _percent(len(wins), len(trades)),
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "profit_factor": math.inf if gross_loss == 0 and gross_profit > 0 else (gross_profit / gross_loss if gross_loss else 0),
        "average_trade_pnl": sum((trade["net_pnl"] for trade in trades), 0.0) / len(trades) if trades else 0.0,
        "best_trade_pnl": max((trade["net_pnl"] for trade in trades), default=0.0),
        "worst_trade_pnl": min((trade["net_pnl"] for trade in trades), default=0.0),
        "max_drawdown": max_drawdown,
        "max_drawdown_percent": max_drawdown_percent,
        "max_daily_loss_halt": _max_daily_loss_reached(settings, final_balance),
        "report_files": {
            "summary": f"{settings.simulation.output_dir}/summary.json",
            "trades": f"{settings.simulation.output_dir}/trades.csv",
            "signals": f"{settings.simulation.output_dir}/signals.csv",
            "equity_curve": f"{settings.simulation.output_dir}/equity_curve.csv",
        },
    }


def _percent(value: float, base: float) -> float:
    if base == 0:
        return 0.0
    return value / base * 100


def _execution_price(raw_price: float, side: SignalSide, *, is_entry: bool, settings: Settings) -> float:
    half_spread = settings.simulation.spread_percent / 200
    slippage = settings.simulation.slippage_percent / 100
    adverse_move = half_spread + slippage
    pays_ask = (side == SignalSide.BUY and is_entry) or (side == SignalSide.SELL and not is_entry)
    return raw_price * (1 + adverse_move if pays_ask else 1 - adverse_move)


def _funding_cost(position: OpenPosition, exit_time: str, settings: Settings) -> float:
    from datetime import datetime

    entry = datetime.fromisoformat(position.entry_time)
    exit_ = datetime.fromisoformat(exit_time)
    hours = max(0.0, (exit_ - entry).total_seconds() / 3600)
    intervals = hours / settings.simulation.funding_interval_hours if settings.simulation.funding_interval_hours else 0.0
    notional = position.entry_price * position.quantity
    return notional * settings.simulation.funding_rate_percent / 100 * intervals


def _cooldown_bars(settings: Settings) -> int:
    if not settings.cooldown.enabled:
        return 0
    timeframe_minutes = _timeframe_minutes(settings.trading.timeframe)
    return max(1, math.ceil(settings.cooldown.after_loss_minutes / timeframe_minutes))


def _timeframe_minutes(timeframe: str) -> int:
    unit = timeframe[-1]
    amount = int(timeframe[:-1])
    if unit == "m":
        return amount
    if unit == "h":
        return amount * 60
    if unit == "d":
        return amount * 60 * 24
    raise ValueError(f"Unsupported timeframe: {timeframe}")


def _max_daily_loss_reached(settings: Settings, balance: float) -> bool:
    max_loss = settings.trading.quote_balance * settings.risk.max_daily_loss_percent / 100
    return balance <= settings.trading.quote_balance - max_loss
