from __future__ import annotations

import os


LIVE_CONFIRMATION = "I_UNDERSTAND_THIS_CAN_LOSE_MONEY"


def testnet_execution_enabled() -> bool:
    return os.getenv("BINANCE_TESTNET_EXECUTION_ENABLED", "").lower() in {"1", "true", "yes"}


def live_execution_enabled() -> bool:
    return (
        os.getenv("BINANCE_LIVE_EXECUTION_ENABLED", "").lower() in {"1", "true", "yes"}
        and os.getenv("BINANCE_LIVE_CONFIRM") == LIVE_CONFIRMATION
    )


def execution_guard_error(mode: str) -> str | None:
    if mode == "testnet" and not testnet_execution_enabled():
        return "Set BINANCE_TESTNET_EXECUTION_ENABLED=true to allow real Binance testnet orders."
    if mode == "live" and not live_execution_enabled():
        return (
            "Live Binance execution is blocked. Set BINANCE_LIVE_EXECUTION_ENABLED=true "
            f"and BINANCE_LIVE_CONFIRM={LIVE_CONFIRMATION}."
        )
    return None
