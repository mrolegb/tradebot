from __future__ import annotations

import argparse
import asyncio
import json
import os
from dataclasses import replace
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from app.config.loader import Settings, load_settings
from app.exchange.binance_client import BinanceFuturesClient
from app.exchange.factory import build_market_data_client
from app.exchange.order_executor import BinanceOrderExecutor
from app.exchange.safety import execution_guard_error, live_smoke_enabled
from app.simulation.runner import run_simulation
from app.storage.database import Database
from app.types import SignalSide


DEFAULT_SMOKE_NOTIONAL = 10.0


async def run_local_smoke(config_path: str) -> dict[str, Any]:
    settings = load_settings(config_path)
    output_dir = Path(settings.simulation.output_dir) / "smoke"
    settings = replace(settings, simulation=replace(settings.simulation, output_dir=str(output_dir), candles_limit=min(settings.simulation.candles_limit, 240)))
    summary = await run_simulation(settings)
    required_files = ["summary.json", "trades.csv", "signals.csv", "equity_curve.csv"]
    missing = [name for name in required_files if not (output_dir / name).exists()]
    if missing:
        raise RuntimeError(f"Local smoke did not create expected report files: {', '.join(missing)}")
    return {
        "mode": settings.app.mode,
        "status": "passed",
        "summary": {
            "final_balance": summary["final_balance"],
            "return_percent": summary["return_percent"],
            "total_trades": summary["total_trades"],
            "max_drawdown_percent": summary["max_drawdown_percent"],
        },
        "output_dir": str(output_dir),
    }


async def run_binance_smoke(config_path: str, *, force_live_order: bool = False) -> dict[str, Any]:
    load_dotenv()
    settings = load_settings(config_path)
    if settings.app.mode not in {"testnet", "live"}:
        raise ValueError("Binance smoke requires a testnet or live config")
    if settings.app.mode == "live" and not force_live_order and not live_smoke_enabled():
        raise RuntimeError(
            "Live smoke is blocked. Set BINANCE_LIVE_EXECUTION_ENABLED=true, "
            "BINANCE_LIVE_CONFIRM=I_UNDERSTAND_THIS_CAN_LOSE_MONEY, and "
            "BINANCE_LIVE_SMOKE_CONFIRM=PLACE_LIVE_SMOKE_ORDER."
        )

    symbol = os.getenv("BINANCE_SMOKE_SYMBOL", settings.trading.symbols[0])
    notional = float(os.getenv("BINANCE_SMOKE_NOTIONAL_USDT", str(DEFAULT_SMOKE_NOTIONAL)))
    client = BinanceFuturesClient(settings.exchange)
    executor = BinanceOrderExecutor(client, settings.app.mode)
    database = Database(settings.storage.sqlite_path)
    opened_order = None
    close_order = None

    try:
        guard_error = execution_guard_error(settings.app.mode)
        dry_run = guard_error is not None
        account = await client.account()
        await executor.load_exchange_rules()
        candles = await client.fetch_klines(symbol, settings.trading.timeframe, limit=2)
        if not candles:
            raise RuntimeError(f"No candles returned for {symbol}")
        price = candles[-1].close
        quantity = executor.minimum_quantity_for_notional(symbol, price, notional)
        if quantity <= 0:
            raise RuntimeError(f"Smoke quantity for {symbol} is below exchange limits")

        before_positions = await client.position_risk(symbol)
        before_active = _active_position(before_positions)
        if before_active and not dry_run:
            raise RuntimeError(f"{symbol} already has an active position; close it before smoke testing")

        await executor.prepare_symbol(symbol, settings.trading.leverage)
        await executor.cancel_all_open_orders(symbol)
        opened_order = await executor.market_order(symbol, SignalSide.BUY, quantity, price)
        database.save_order(opened_order)

        after_open_positions = await client.position_risk(symbol)
        after_open_active = _active_position(after_open_positions)
        if not dry_run and not after_open_active:
            raise RuntimeError(f"{symbol} order was sent but no active position was found")

        if after_open_active:
            close_order = await executor.close_position(symbol, after_open_active)
            if close_order:
                database.save_order(close_order)
            await executor.cancel_all_open_orders(symbol)

        after_close_positions = await client.position_risk(symbol)
        after_close_active = _active_position(after_close_positions)
        if not dry_run and after_close_active:
            raise RuntimeError(f"{symbol} position is still active after close attempt")

        result = {
            "mode": settings.app.mode,
            "status": "passed",
            "dry_run": dry_run,
            "symbol": symbol,
            "price": price,
            "quantity": quantity,
            "target_notional": notional,
            "account_checked": bool(account),
            "opened_order_status": opened_order.status if opened_order else None,
            "close_order_status": close_order.status if close_order else None,
            "guard": guard_error,
        }
        database.save_runtime_state({"last_smoke": result})
        return result
    finally:
        database.close()
        await client.close()


async def run_smoke(mode: str, config_path: str) -> dict[str, Any]:
    if mode == "local":
        return await run_local_smoke(config_path)
    if mode in {"testnet", "live"}:
        return await run_binance_smoke(config_path)
    raise ValueError(f"Unsupported smoke mode: {mode}")


def _active_position(positions: list[dict]) -> dict | None:
    for position in positions:
        try:
            if abs(float(position.get("positionAmt", 0))) > 0:
                return position
        except (TypeError, ValueError):
            continue
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["local", "testnet", "live"], required=True)
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    result = asyncio.run(run_smoke(args.mode, args.config))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
